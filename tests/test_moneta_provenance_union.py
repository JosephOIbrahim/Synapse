"""The COMPOSITION of moneta_provenance() — all five R64 conditions at once.

R64 specified five conditions and said one function would compose them. The
work was then dispatched as two independent legs which rewrote that function
from the same base in ignorance of each other:

    LEDGER (repair/ledger-moneta-seam @ eb25abe)  available + version + file
                                                  + revision
    H6     (merged to the working line)           available + schema_registered
                                                  + schema_in_use

Neither branch had all five, and the two conflicted textually (R91). The union
was AUTHORED, not merge-resolved.

Each leg already pins its own half — ``tests/test_ledger_moneta_seam.py`` and
``tests/test_moneta_substrate_truth.py``. Those two files passing does NOT
prove the union: each was green on a branch that was missing the other half.
This file pins only what neither leg could see — the composition itself, and
the behaviour the composition made necessary.

Every pin here is written to the R34 standard: it must FAIL against a
deliberately broken implementation, and the mutation it catches is named in its
docstring. The battery is ``harness/verify/mutate_ledger_moneta_seam.py``.

Run: python -m pytest tests/test_moneta_provenance_union.py -v
"""

import os
import sys
import types

import pytest

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.memory import moneta_runtime as mr

FAKE_SHA = "0123456789abcdef0123456789abcdef01234567"
ENCLOSING_SHA = "fedcba9876543210fedcba9876543210fedcba98"

# The five conditions of R64, and the field(s) that carry each. Condition 5
# ("a memory round-trips typed") has no field of its own: it IS 3 AND 4, and
# giving it a field would be a sixth signal standing in for a conjunction —
# the exact defect R64 exists to remove.
LEDGER_HALF = ("available", "version", "file", "revision", "revision_ref",
               "revision_source", "revision_scope", "moneta_src", "root")
H6_HALF = ("available", "schema_registered", "schema_registered_reason",
           "schema_in_use", "schema_in_use_reason")


@pytest.fixture
def clean_caches():
    mr.reset_revision_cache()
    yield
    mr.reset_revision_cache()


def _make_repo(root, sha):
    """A synthetic git repo at *root* whose HEAD resolves to *sha*."""
    git_dir = os.path.join(root, ".git")
    os.makedirs(os.path.join(git_dir, "refs", "heads"), exist_ok=True)
    with open(os.path.join(git_dir, "HEAD"), "w", encoding="utf-8") as fh:
        fh.write("ref: refs/heads/main\n")
    with open(os.path.join(git_dir, "refs", "heads", "main"), "w",
              encoding="utf-8") as fh:
        fh.write(sha + "\n")
    return git_dir


def _fake_moneta_at(monkeypatch, package_file):
    """Make moneta_provenance() believe the loaded copy lives at *package_file*.

    Patches the module object rather than the resolver, so the pin exercises
    the real ``moneta.__file__ -> _resolve_revision`` path that production uses.
    """
    stub = types.ModuleType("moneta")
    stub.__file__ = package_file
    monkeypatch.setitem(sys.modules, "moneta", stub)
    monkeypatch.setattr(mr, "_MONETA_AVAILABLE", True)


# ═════════════════════════════════════════════════════════════════
# The union — one payload, five conditions
# ═════════════════════════════════════════════════════════════════


class TestBothHalvesArePresent:

    def test_one_payload_carries_all_five_conditions(self):
        """The whole point of the leg. Fails if EITHER leg's half is dropped.

        Each half already has a pin in its own leg's file; this is the only
        assertion that fails when the two stop being the same function.
        MUTATIONS CAUGHT: union-drops-the-revision-half,
        union-defaults-probe-schema-off.
        """
        prov = mr.moneta_provenance()
        missing = [f for f in LEDGER_HALF + H6_HALF if f not in prov]
        assert not missing, (
            f"moneta_provenance() is not the union — missing {missing}. "
            "R64 requires all five conditions in ONE payload."
        )

    def test_neither_half_is_seeded_but_never_computed(self):
        """Key-presence is too weak on its own: the payload seeds every field,
        so a probe deleted outright leaves its key behind and a presence-only
        pin passes vacuously (this is mutation M9 from the H6 battery, one
        level up). Both halves must show evidence they RAN.

        MUTATIONS CAUGHT: union-drops-the-revision-half,
        union-defaults-probe-schema-off.
        """
        prov = mr.moneta_provenance()
        # H6 half: a reason string only a probe that executed can produce.
        for field in ("schema_registered", "schema_in_use"):
            reason = prov.get(f"{field}_reason")
            assert isinstance(reason, str) and reason.strip(), (
                f"{field} present but never computed"
            )
            assert mr.NOT_PROBED_REASON not in reason, (
                f"{field} was skipped on a default call — probe_schema must "
                "default to True"
            )
        # LEDGER half: 'unavailable' is the seeded default and means the
        # resolver never ran. Any other value means it did.
        if prov["available"]:
            assert prov["revision_source"] != "unavailable", (
                "the revision resolver never ran on an available Moneta"
            )

    def test_the_two_halves_are_independent_not_gated_on_each_other(self):
        """A schema can be registered with no moneta importable, and prims can
        be authored by a copy this interpreter cannot import. Gating one half
        on the other would re-collapse conditions — the defect R64 removes.

        MUTATION CAUGHT: gate-schema-probes-on-availability.
        """
        prov = mr.moneta_provenance()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(mr, "_MONETA_AVAILABLE", False)
            unavailable = mr.moneta_provenance()
        assert unavailable["available"] is False
        # The schema half must answer identically whether or not the PACKAGE
        # imported — it is a property of the USD runtime, not of sys.path.
        assert unavailable["schema_registered"] == prov["schema_registered"]
        assert unavailable["schema_registered_reason"] == \
            prov["schema_registered_reason"]


# ═════════════════════════════════════════════════════════════════
# probe_schema — declining to look is not the same as looking and failing
# ═════════════════════════════════════════════════════════════════


class TestProbeSchemaOptOut:

    def test_opting_out_reports_unknown_by_request_not_false(self):
        """The composition put an uncached, stage-traversing probe on a caller
        that runs once per ledger record. The opt-out exists for that; it must
        not become a fourth way to say False.

        MUTATION CAUGHT: not-probed-collapsed-to-false.
        """
        prov = mr.moneta_provenance(probe_schema=False)
        assert prov["schema_registered"] is None
        assert prov["schema_in_use"] is None
        for field in ("schema_registered", "schema_in_use"):
            assert prov[f"{field}_reason"] == mr.NOT_PROBED_REASON

    def test_the_not_probed_reason_is_distinguishable_from_could_not_check(self):
        """'I was not asked' and 'I looked and could not tell' are different
        facts. A reader that cannot tell them apart has the same defect as a
        bool that cannot say None.

        MUTATION CAUGHT: not-probed-reuses-could-not-check.
        """
        assert "not probed" in mr.NOT_PROBED_REASON
        assert not mr.NOT_PROBED_REASON.startswith("could not check")
        probed = mr.moneta_provenance()["schema_registered_reason"]
        assert probed != mr.NOT_PROBED_REASON

    def test_opting_out_actually_skips_the_probes(self):
        """The reason the parameter exists. A version that sets the reason
        string and probes anyway is a lie that costs exactly what it claims to
        save — and every other pin in this class would still pass.

        MUTATION CAUGHT: probe-schema-false-still-probes.
        """
        calls = []
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(mr, "_schema_registered_detail",
                       lambda: calls.append("registered") or (None, "x"))
            mp.setattr(mr, "_schema_in_use_detail",
                       lambda u=None: calls.append("in_use") or (None, "x", None))
            mr.moneta_provenance(probe_schema=False)
            assert calls == [], f"probe_schema=False still probed: {calls}"
            # Positive control: the same patched probes ARE called by default,
            # so an empty list above cannot be an artefact of the patch.
            mr.moneta_provenance()
        assert sorted(calls) == ["in_use", "registered"]

    def test_opting_out_still_reports_which_copy_loaded(self):
        """The opt-out is scoped to conditions 3 and 4. Dropping conditions 1
        and 2 with them would make it useless to the caller that needs it.

        Field-presence alone cannot see this: every field is seeded, so an
        early return leaves the whole LEDGER half present and empty. The
        assertion has to be that the two calls AGREE on that half.

        MUTATION CAUGHT: probe-schema-false-drops-the-revision-half.
        """
        opted_out = mr.moneta_provenance(probe_schema=False)
        probed = mr.moneta_provenance()
        for field in LEDGER_HALF:
            assert field in opted_out
            assert opted_out[field] == probed[field], (
                f"probe_schema=False changed {field!r} — the opt-out is "
                "scoped to conditions 3 and 4 only"
            )
        assert opted_out["revision_scope"] == mr.REVISION_SCOPE


# ═════════════════════════════════════════════════════════════════
# The oracle: the walk is bounded, end-to-end through the public function
# ═════════════════════════════════════════════════════════════════


class TestBoundedWalkThroughThePublicFunction:
    """LEDGER pins the bound on ``_resolve_revision``. The oracle asks the
    question of ``moneta_provenance()`` — the function an operator actually
    reads — so it is demonstrated there too, two-sided."""

    def test_provenance_does_not_report_an_enclosing_repos_head(
        self, tmp_path, monkeypatch, clean_caches
    ):
        """A Moneta nested too deep inside another repository must report NO
        revision — never that repository's HEAD. Unbounded, this reported
        ENCLOSING_SHA and the substrate was confidently mis-attributed
        (LEDGER.F2 / R52).

        MUTATIONS CAUGHT: unbounded-upward-walk, widen-the-walk-bound.
        """
        enclosing = tmp_path / "some-other-project"
        enclosing.mkdir()
        _make_repo(str(enclosing), ENCLOSING_SHA)

        deep = enclosing / "vendor" / "moneta-src" / "moneta"
        deep.mkdir(parents=True)
        pkg_file = str(deep / "__init__.py")
        with open(pkg_file, "w", encoding="utf-8") as fh:
            fh.write("# vendored deep\n")

        _fake_moneta_at(monkeypatch, pkg_file)
        prov = mr.moneta_provenance()

        assert prov["revision"] != ENCLOSING_SHA, (
            "moneta_provenance() reported the ENCLOSING repository's HEAD as "
            "Moneta's revision — fabricated provenance, the defect R52 closed"
        )
        assert prov["revision"] is None
        assert prov["revision_source"] == "not-a-git-worktree"
        assert prov["revision_repo"] is None

    def test_the_deployed_layout_still_resolves(
        self, tmp_path, monkeypatch, clean_caches
    ):
        """Positive control for the pin above — without it, a bound of 0 (or a
        resolver that always returns None) passes the negative case trivially
        and the pair proves nothing. $MONETA_SRC=<repo>/src is the deployed
        layout and MUST still resolve, and must name the repo it read.

        MUTATION CAUGHT: revision-always-none.
        """
        repo = tmp_path / "Moneta"
        repo.mkdir()
        _make_repo(str(repo), FAKE_SHA)

        pkg = repo / "src" / "moneta"
        pkg.mkdir(parents=True)
        pkg_file = str(pkg / "__init__.py")
        with open(pkg_file, "w", encoding="utf-8") as fh:
            fh.write("# deployed layout\n")

        _fake_moneta_at(monkeypatch, pkg_file)
        prov = mr.moneta_provenance()

        assert prov["revision"] == FAKE_SHA
        assert prov["revision_source"] == "git-loose-ref"
        assert os.path.abspath(prov["revision_repo"]) == os.path.abspath(str(repo))

    def test_the_two_arms_actually_disagree(self, tmp_path, monkeypatch,
                                            clean_caches):
        """R60 — the reader needs its own control. If the two arms above ever
        returned the same thing, both pins would be green and the bound would
        be measuring nothing. Assert they DISAGREE, in one test, so a resolver
        insensitive to depth cannot pass.

        MUTATIONS CAUGHT: unbounded-upward-walk, revision-always-none.
        """
        results = {}
        for label, rel in (("deep", ("vendor", "moneta-src", "moneta")),
                           ("deployed", ("src", "moneta"))):
            repo = tmp_path / label
            repo.mkdir()
            _make_repo(str(repo), FAKE_SHA)
            pkg = repo.joinpath(*rel)
            pkg.mkdir(parents=True)
            pkg_file = str(pkg / "__init__.py")
            with open(pkg_file, "w", encoding="utf-8") as fh:
                fh.write("# x\n")
            mr.reset_revision_cache()
            with pytest.MonkeyPatch.context() as mp:
                _fake_moneta_at(mp, pkg_file)
                results[label] = mr.moneta_provenance()["revision"]

        assert results["deployed"] == FAKE_SHA
        assert results["deep"] is None
        assert results["deep"] != results["deployed"], (
            "depth makes no difference to the resolver — the bound is not "
            "being measured by these pins"
        )


# ═════════════════════════════════════════════════════════════════
# Never raise — the contract _make_store depends on, across BOTH halves
# ═════════════════════════════════════════════════════════════════


class TestTheUnionNeverRaises:
    """``_make_store`` calls moneta_provenance() from inside its own except
    handler. A raise there escapes _make_store and stops Houdini's panel from
    loading. Each leg fenced its own half; the union has to fence both."""

    def test_it_survives_a_revision_probe_that_explodes(self, clean_caches):
        """LEDGER's half had no fence of its own — it did not need one, because
        _resolve_revision only reads files. Composed with H6's 'this function
        must never raise' contract it needs one, and that is a requirement
        neither leg could see.

        MUTATION CAUGHT: union-revision-fence-removed.
        """
        with pytest.MonkeyPatch.context() as mp:
            def boom(_package_file):
                raise RuntimeError("git metadata is on fire")
            mp.setattr(mr, "_MONETA_AVAILABLE", True)
            mp.setattr(mr, "_resolve_revision", boom)
            prov = mr.moneta_provenance()  # must not raise
        assert "could not check" in prov["revision_source"]
        assert "RuntimeError" in prov["revision_source"]
        # The other half must be unharmed by the failure of this one.
        assert prov["schema_registered_reason"]

    def test_it_survives_both_probes_exploding_at_once(self, clean_caches):
        """Each leg pinned its own probe failing alone. Nothing pinned both,
        which is the state a genuinely broken environment produces."""
        with pytest.MonkeyPatch.context() as mp:
            def boom(*a, **k):
                raise RuntimeError("everything is on fire")
            mp.setattr(mr, "_MONETA_AVAILABLE", True)
            mp.setattr(mr, "_resolve_revision", boom)
            mp.setattr(mr, "_schema_registered_detail", boom)
            mp.setattr(mr, "_schema_in_use_detail", boom)
            prov = mr.moneta_provenance()  # must not raise
        assert prov["schema_registered"] is None
        assert prov["schema_in_use"] is None
        assert "RuntimeError" in prov["schema_registered_reason"]
        assert "RuntimeError" in prov["schema_in_use_reason"]
        assert "RuntimeError" in prov["revision_source"]

    def test_make_store_survives_a_broken_revision_half(self, tmp_path,
                                                        clean_caches):
        """The contract exercised through the REAL caller, with the REAL
        composed body running.

        H6 pins this seam by replacing ``moneta_provenance`` wholesale with a
        function that raises — which proves the handler is fenced but never
        executes the composed body. This pin breaks only the revision half and
        lets the real union run, which is the arm that appeared when LEDGER's
        resolver was folded into H6's never-raise contract.

        MUTATION CAUGHT: union-revision-fence-removed (through the seam that
        made the contract necessary).
        """
        from synapse.memory import moneta_store
        from synapse.memory.store import MemoryStore, SynapseMemory

        def broken_adapter(*_a, **_k):
            raise RuntimeError("adapter drift")

        def broken_revision(_package_file):
            raise RuntimeError("git metadata is on fire")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(moneta_store.MonetaBackedStore, "from_storage_dir",
                       staticmethod(broken_adapter))
            mp.setattr(mr, "_resolve_revision", broken_revision)
            mp.setattr(mr, "_MONETA_AVAILABLE", True)
            mp.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
            try:
                store = SynapseMemory._make_store(None, tmp_path)
            except Exception as exc:  # noqa: BLE001
                pytest.fail(
                    f"_make_store raised on the composed provenance: {exc!r}"
                )
        assert isinstance(store, MemoryStore)
