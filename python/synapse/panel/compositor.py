"""Compositor — maps a layout manifest onto SynapsePanel's existing build calls.

Two halves, one hard boundary:

* ``resolve(manifest)`` — pure data. Validates against the manifests schema,
  folds the manifest's defaults into every region and widget entry, and drops
  what the vocabulary doesn't know — an unknown region or widget id is logged
  and skipped, never a crash (L2: it frays visibly). This module imports no
  Qt, so headless tests and tooling can run resolve anywhere.

* ``compose(panel, root, manifest)`` — the Qt assembly. Calls the SAME
  ``_build_*`` methods the panel has always used, in the manifest's region
  order, then applies each widget spec to the widget that build call created.
  No new widgets, no rewiring — the manifest chooses order, visibility,
  collapse, stretch and prominence over what already exists. Only this half
  ever touches live Qt objects, and it does so by duck-typing (no import).

Honest scope of "ordered widget ids": region order drives the real root-layout
order. Widget order WITHIN a region is preserved through resolve (it is the
spec application order), but a widget's position inside its region's own
layouts still comes from the region's build call — reordering those would mean
rewriting the build methods, which this task deliberately does not do.

Spec application (all best-effort, all logged on failure):
  visible False  -> widget.setVisible(False)
  collapsed True -> widget.setMaximumHeight(0)   (stays wired, holds no space)
  stretch        -> region: root.addWidget(w, stretch); widget: best-effort
                    setStretchFactor on the parent box layout
  prominence     -> Qt dynamic property "prominence" + repolish, for QSS hooks

Density (L5-18) is panel-wide, never per-widget: ``resolve()`` lifts the
optional ``density`` default out of the fold ("standard" when absent) and
``compose()`` stamps it ONCE on the panel root as a Qt dynamic property +
repolish — one property drives the whole panel's rhythm through the QSS
descendant rules keyed on it.
"""

import logging

from synapse.panel.manifests import ManifestError, validate_manifest

logger = logging.getLogger(__name__)

# region id -> the existing SynapsePanel build method (the v5.42.0 calls).
REGION_BUILDERS = {
    "rail": "_build_rail",
    "context_ribbon": "_build_context_ribbon",
    "mode_bar": "_build_mode_bar",
    "faces": "_build_faces",
}

# widget id -> the panel attribute its build call creates. "attr.key" reaches
# into a dict attribute (the mode-bar pills live in _face_pills). The overflow
# "⋯" button is a build-local variable, not on self — it has no id on purpose.
WIDGET_ATTRS = {
    # rail
    "mark": "_mark",
    "wordmark": "_wordmark",
    "header_status": "_header_status",
    "author_token": "_author_lbl",
    "token_meter": "_meter_lbl",
    "palette_hint": "_palette_hint",
    "stop": "_stop_btn",
    "connection_dot": "_foot_dot",
    "connection_label": "_foot_label",
    "connect": "_connect_btn",
    "corpus": "_corpus_btn",
    "activity_meter": "_observe",
    # context_ribbon
    "context_label": "_ctx_label",
    # mode_bar
    "chat_pill": "_face_pills.direct",
    "token_pill": "_face_pills.token",
    # faces
    "faces_stack": "_faces",
}

_SPEC_KEYS = ("visible", "collapsed", "stretch", "prominence")

# Qt's QWIDGETSIZE_MAX — the "no maximum" sentinel a widget carries by default.
# Restoring maxHeight to this (not leaving it pinned at 0) is what makes collapse
# TWO-WAY: a later profile that does not collapse a widget re-expands it on a
# mode switch-back (J4.4). Named so the substring is greppable in _apply_spec.
_QWIDGETSIZE_MAX = (1 << 24) - 1  # 16777215


def known_widget_ids():
    """The compositor's widget vocabulary (a frozen copy)."""
    return frozenset(WIDGET_ATTRS)


def resolve(manifest, known=None):
    """Validate + normalize a manifest into a fully-defaulted layout plan.

    Pure data in, pure data out — no Qt, no panel. Raises ``ManifestError`` on
    a schema violation; unknown region/widget ids skip-log instead (vocabulary
    drift is not a malformed manifest, and it must never crash the panel).
    ``known`` overrides the widget vocabulary (tests)."""
    problems = validate_manifest(manifest)
    if problems:
        profile = manifest.get("profile") if isinstance(manifest, dict) else None
        raise ManifestError(profile, problems)
    profile = manifest["profile"]
    known = frozenset(known) if known is not None else frozenset(WIDGET_ATTRS)
    defaults = dict(manifest["defaults"])
    # L5-18: density is ONE panel-wide rhythm, not a per-widget knob — lift it
    # out of the defaults BEFORE the fold so no region/widget spec carries it.
    density = defaults.pop("density", "standard")
    regions = []
    for region in manifest["regions"]:
        rid = region["id"]
        if rid not in REGION_BUILDERS:
            logger.warning(
                "compositor: unknown region id %r skipped (profile %r)",
                rid, profile,
            )
            continue
        widgets = []
        for entry in region["widgets"]:
            spec = {"id": entry} if isinstance(entry, str) else dict(entry)
            if spec["id"] not in known:
                logger.warning(
                    "compositor: unknown widget id %r skipped "
                    "(region %r, profile %r)", spec["id"], rid, profile,
                )
                continue
            widgets.append({**defaults, **spec})
        merged = {**defaults, **{k: region[k] for k in _SPEC_KEYS if k in region}}
        merged["id"] = rid
        merged["builder"] = REGION_BUILDERS[rid]
        merged["widgets"] = widgets
        regions.append(merged)
    return {
        "profile": profile,
        "system_prompt_overlay": manifest["system_prompt_overlay"],
        "defaults": defaults,
        "density": density,
        "regions": regions,
    }


def _panel_widget(panel, widget_id):
    """The live widget behind an id, or None (graceful-degradation builds may
    not have created it)."""
    attr, _, key = WIDGET_ATTRS[widget_id].partition(".")
    obj = getattr(panel, attr, None)
    if key and isinstance(obj, dict):
        obj = obj.get(key)
    return obj


def _apply_spec(widget, spec, what):
    """Best-effort application of one resolved spec to one live widget.

    Every knob is applied TWO-WAY so a later profile that does not set it
    restores the widget on a mode switch-back: visible toggles both ways, and
    collapse toggles maxHeight between 0 and ``_QWIDGETSIZE_MAX`` (Qt's "no
    maximum"). The prior one-way collapse only ever set maxHeight to 0 and had
    no restore branch, so a folded readout stayed pinned collapsed through the
    next switch — the friction J4.4 measured (density switch-back never
    re-expanded folded readouts)."""
    try:
        widget.setVisible(bool(spec["visible"]))
        widget.setMaximumHeight(0 if spec["collapsed"] else _QWIDGETSIZE_MAX)
        widget.setProperty("prominence", spec["prominence"])
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
    except Exception:
        logger.warning("compositor: could not apply spec to %s", what,
                       exc_info=True)


def _apply_widget_stretch(widget, stretch, what):
    """Per-widget stretch, best-effort: it lands only when the widget sits
    directly in a box layout (setStretchFactor returns False otherwise)."""
    try:
        parent = widget.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is None or not layout.setStretchFactor(widget, stretch):
            logger.debug("compositor: stretch %d not applicable to %s",
                         stretch, what)
    except Exception:
        logger.warning("compositor: stretch failed for %s", what,
                       exc_info=True)


def _repolish_tree(widget):
    """Unpolish/polish a widget AND every descendant widget.

    A Qt dynamic property set on a parent does not restyle its children, so
    descendant QSS selectors keyed on that property go unapplied. Anything
    driving a panel-wide property (density) must repolish the whole tree.

    Walks the live object tree by duck-typing ``QObject.children()`` — no Qt
    import at all, honouring this module's stated no-Qt contract. The prior
    version imported ``qtpy``, which is not installed in the Houdini seat, so
    the ``except: return`` fired and the function was a silent no-op: density
    never reached a single child and all three profiles rendered identically
    (J4.3 Defect A). A ``break`` right after the ``findChildren`` extend
    compounded it by repolishing only the root (Defect B). This version has
    neither. Returns the number of widgets repolished (0 == nothing reachable),
    so a caller/probe can measure that density actually propagated.
    """
    repolished = 0
    stack = [widget]
    while stack:
        w = stack.pop()
        try:
            st = w.style()
            st.unpolish(w)
            st.polish(w)
            w.update()
            repolished += 1
        except Exception:
            # not a stylable widget (a layout, a timer, ...) — skip it but keep
            # walking; its own children may still be stylable widgets.
            pass
        try:
            stack.extend(w.children())
        except Exception:
            pass
    return repolished


def compose(panel, root, manifest):
    """Assemble the panel's root layout from a manifest (the Qt half).

    Each region's EXISTING build method runs once, its widget goes into
    ``root`` with the region's stretch, and every widget spec is applied to
    the attribute that build call created (missing attribute -> logged and
    skipped). Also stamps ``panel._system_prompt_overlay`` for
    ``_build_system_prompt`` and the resolved density on the panel root (one
    Qt dynamic property — the QSS descendant rules key on it). Returns the
    resolved plan."""
    resolved = resolve(manifest)
    panel._system_prompt_overlay = resolved["system_prompt_overlay"]
    # L5-18: one property on the panel root drives the whole panel's rhythm
    # (the _apply_spec prominence idiom, applied once). Set BEFORE the region
    # builds so widgets created below polish against the right density.
    try:
        panel.setProperty("density", resolved["density"])
        # Qt does NOT cascade a dynamic-property change to children: the
        # descendant rules (#DsRoot[density=...] QPushButton#DsButton) match
        # on paper and never repaint unless every child is repolished too.
        # That bug made all three profiles render identically. Repolish the
        # whole subtree, root first.
        _repolish_tree(panel)
    except Exception:
        logger.warning("compositor: could not apply density %r to the panel "
                       "root", resolved["density"], exc_info=True)
    for region in resolved["regions"]:
        widget = getattr(panel, region["builder"])()
        root.addWidget(widget, region["stretch"])
        _apply_spec(widget, region, "region %r" % region["id"])
        for spec in region["widgets"]:
            target = _panel_widget(panel, spec["id"])
            if target is None:
                logger.warning(
                    "compositor: widget %r missing on the panel — skipped "
                    "(region %r)", spec["id"], region["id"],
                )
                continue
            what = "widget %r" % spec["id"]
            _apply_spec(target, spec, what)
            if spec["stretch"]:
                _apply_widget_stretch(target, spec["stretch"], what)
    return resolved
