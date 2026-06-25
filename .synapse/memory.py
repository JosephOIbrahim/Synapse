#!/usr/bin/env python3
"""
SYNAPSE harness long-running memory — the cross-session bridge, behind one interface.
(Architecture from ANVIL; on-thesis for SYNAPSE, which already remembers in USD.)

The long-running problem: each session starts cold; carry state across the gap
losslessly. The backend is swappable behind a small interface:

  * FlatFileMemory  — feature_list.json + progress.md. Zero dependencies. The default;
    runs out of the box.
  * UsdMemory       — a USD cognitive-twin stage. Features are prims with a `state`
    VariantSet (failing/wip/passing/regressed/blocked); provenance in customData;
    verified truth is the strong root layer and each session writes a weaker sublayer
    composed over it (LIVRPS) — so a bad session is a dropped sublayer (revert_session),
    a lossless cognitive revert, not a file diff. This is the SYNAPSE thesis applied to
    harness memory; the same twin can be read by your other tools.

Both are HARNESS-AUTHORITATIVE: only `evaluate()` (which runs the verify commands)
changes whether a feature is passing. The worker never writes the checklist — it
cannot mark its own work done. (CRUCIBLE Commandment 7, structural.)

IP NOTE: UsdMemory uses ONLY vanilla USD APIs (prims, VariantSets, customData,
sublayers). It contains none of the substrate's proprietary internals. Keep this
backend out of any public tag regardless.
"""
import json
import os
import subprocess

STATES = ["failing", "wip", "passing", "regressed", "blocked"]


def _run(verify):
    """Run a feature's verify command; True iff it exits 0. No verify -> not auto-passable."""
    if not verify:
        return None
    return subprocess.run(verify, shell=True, cwd=os.getcwd(),
                          capture_output=True, text=True).returncode == 0


# ----------------------------------------------------------------------------- flat
class FlatFileMemory:
    def __init__(self, task_dir, contract):
        self.dir = task_dir
        self.contract = contract
        self.feat_file = os.path.join(task_dir, "feature_list.json")
        self.prog_file = os.path.join(task_dir, "progress.md")

    def ensure(self):
        os.makedirs(self.dir, exist_ok=True)
        if not os.path.exists(self.feat_file):
            feats = self.contract.get("features") or [
                {"description": d, "verify": None, "passing": False}
                for d in (self.contract.get("done_when") or [self.contract.get("goal", "task complete")])
            ]
            for f in feats:
                f.setdefault("passing", False)
                f.setdefault("verify", None)
            self._save({"goal": self.contract.get("goal", ""), "features": feats})
        if not os.path.exists(self.prog_file):
            with open(self.prog_file, "w", encoding="utf-8") as fh:
                fh.write(f"# Progress - {self.contract.get('id','')}\n\n_Goal: "
                         f"{self.contract.get('goal','')}_\n\n(no sessions yet)\n")

    def _load(self):
        return json.load(open(self.feat_file, encoding="utf-8"))

    def _save(self, data):
        with open(self.feat_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def evaluate(self):
        data = self._load()
        npass = 0
        for f in data["features"]:
            r = _run(f.get("verify"))
            if r is True:
                f["passing"] = True
            elif r is False:
                if f.get("passing"):       # was true, now fails -> regression
                    f["regressed"] = True
                f["passing"] = False
            npass += 1 if f.get("passing") else 0
        self._save(data)
        return npass, len(data["features"])

    def next_failing(self):
        for f in self._load()["features"]:
            if not f.get("passing"):
                return f.get("description")
        return None

    def note_session(self, n, summary, meta):
        with open(self.prog_file, "a", encoding="utf-8") as fh:
            fh.write(f"\n## session {n} ({meta.get('ts','')})\n"
                     f"- features: {meta.get('npass')}/{meta.get('ntotal')}  "
                     f"cost: ${meta.get('cost_usd',0):.2f}  turns: {meta.get('turns','?')}\n"
                     f"- {summary.strip()[:500]}\n")

    def orientation(self):
        data = self._load()
        lines = [f"feature checklist ({self.feat_file}):"]
        for f in data["features"]:
            lines.append(f"  [{'x' if f.get('passing') else ' '}] {f.get('description','')}")
        if os.path.exists(self.prog_file):
            tail = open(self.prog_file, encoding="utf-8").read().strip().splitlines()[-12:]
            lines += ["", f"recent progress ({self.prog_file}):"] + ["  " + t for t in tail]
        return "\n".join(lines)

    def owns_extra(self):
        # the worker may append its own prose log; it may NOT touch the checklist
        return [os.path.relpath(self.prog_file, os.getcwd()).replace("\\", "/")]


# ----------------------------------------------------------------------------- usd
class UsdMemory:
    """USD cognitive-twin backend. Lazy-imports pxr so the dependency is optional."""

    def __init__(self, task_dir, contract):
        from pxr import Usd, Sdf  # noqa: F401  (raises ImportError if usd-core absent)
        self._Usd = Usd
        self._Sdf = Sdf
        self.dir = task_dir
        self.contract = contract
        self.stage_path = os.path.join(task_dir, "cognitive_twin.usda")
        self.sessions_dir = os.path.join(task_dir, "sessions")

    def _open(self):
        return self._Usd.Stage.Open(self.stage_path)

    def _feature_prims(self, stage):
        feats = stage.GetPrimAtPath("/Task/Features")
        return list(feats.GetChildren()) if feats else []

    def _state(self, prim):
        return prim.GetVariantSets().GetVariantSet("state").GetVariantSelection()

    def _set_state(self, prim, value):
        prim.GetVariantSets().GetVariantSet("state").SetVariantSelection(value)

    def ensure(self):
        os.makedirs(self.sessions_dir, exist_ok=True)
        if os.path.exists(self.stage_path):
            return
        Usd = self._Usd
        stage = Usd.Stage.CreateNew(self.stage_path)
        task = stage.DefinePrim("/Task")
        task.SetCustomDataByKey("id", self.contract.get("id", ""))
        task.SetCustomDataByKey("goal", self.contract.get("goal", ""))
        stage.DefinePrim("/Task/Features")
        stage.DefinePrim("/Task/Sessions")
        feats = self.contract.get("features") or [
            {"description": d, "verify": None} for d in
            (self.contract.get("done_when") or [self.contract.get("goal", "task complete")])
        ]
        for i, f in enumerate(feats):
            p = stage.DefinePrim(f"/Task/Features/F{i}")
            vset = p.GetVariantSets().AddVariantSet("state")
            for s in STATES:
                vset.AddVariant(s)
            vset.SetVariantSelection("failing")           # all start failing
            p.SetCustomDataByKey("description", f.get("description", ""))
            p.SetCustomDataByKey("verify", f.get("verify") or "")
        stage.GetRootLayer().Save()

    def evaluate(self):
        stage = self._open()
        npass = 0
        for p in self._feature_prims(stage):
            verify = p.GetCustomDataByKey("verify")
            r = _run(verify)
            cur = self._state(p)
            if r is True:
                self._set_state(p, "passing")
            elif r is False:
                self._set_state(p, "regressed" if cur == "passing" else "failing")
            if self._state(p) == "passing":
                npass += 1
        stage.GetRootLayer().Save()
        return npass, len(self._feature_prims(stage))

    def next_failing(self):
        stage = self._open()
        for p in self._feature_prims(stage):
            if self._state(p) != "passing":
                return p.GetCustomDataByKey("description")
        return None

    def note_session(self, n, summary, meta):
        """Author this session's account into its OWN weaker sublayer, composed over the
        authoritative root. Dropping this sublayer later = lossless revert."""
        Usd = self._Usd
        rel = f"sessions/session_{n}.usda"
        sub_path = os.path.join(self.dir, rel)
        sub_stage = Usd.Stage.CreateNew(sub_path) if not os.path.exists(sub_path) else Usd.Stage.Open(sub_path)
        sp = sub_stage.DefinePrim(f"/Task/Sessions/Session_{n}")
        sp.SetCustomDataByKey("summary", (summary or "").strip()[:800])
        sp.SetCustomDataByKey("cost_usd", float(meta.get("cost_usd", 0.0)))
        sp.SetCustomDataByKey("turns", int(meta.get("turns", 0) or 0))
        sp.SetCustomDataByKey("features", f"{meta.get('npass')}/{meta.get('ntotal')}")
        sp.SetCustomDataByKey("ts", meta.get("ts", ""))
        sub_stage.GetRootLayer().Save()
        stage = self._open()
        root = stage.GetRootLayer()
        if rel not in root.subLayerPaths:
            root.subLayerPaths.append(rel)               # weaker than root: root wins on truth
            root.Save()

    def revert_session(self, n):
        """Lossless cognitive revert: drop a session's sublayer; truth is untouched."""
        stage = self._open()
        root = stage.GetRootLayer()
        rel = f"sessions/session_{n}.usda"
        if rel in root.subLayerPaths:
            root.subLayerPaths.remove(rel)
            root.Save()

    def orientation(self):
        stage = self._open()
        lines = ["cognitive twin (USD) — feature states:"]
        for p in self._feature_prims(stage):
            st = self._state(p)
            desc = p.GetCustomDataByKey("description")
            blk = p.GetCustomDataByKey("blocker")
            lines.append(f"  [{st:9}] {desc}" + (f"  (blocked: {blk})" if blk else ""))
        sessions = stage.GetPrimAtPath("/Task/Sessions")
        kids = sorted(sessions.GetChildren(), key=lambda x: x.GetName()) if sessions else []
        if kids:
            last = kids[-1]
            lines += ["", f"last session ({last.GetName()}): "
                      f"{last.GetCustomDataByKey('summary') or ''}"]
        return "\n".join(lines)

    def owns_extra(self):
        return []


# ----------------------------------------------------------------------------- factory
def get_memory(backend, task_dir, contract):
    if backend == "usd":
        try:
            return UsdMemory(task_dir, contract)
        except ImportError:
            print("SYNAPSE harness: usd-core not installed; falling back to flat-file memory "
                  "(pip install usd-core to use the cognitive-twin backend).")
    return FlatFileMemory(task_dir, contract)
