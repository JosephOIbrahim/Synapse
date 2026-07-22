"""Self-tests for the Solaris hardening harness (seam-hunter + runner + skill).

The harness gates other work; these pin its own invariants so it cannot rot
silently. Pure Python -- reads the harness files, imports the runner. No hou.
"""

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_AGENT = _REPO / ".claude" / "agents" / "seam-hunter.md"
_SKILL = _REPO / ".claude" / "skills" / "solaris-harden" / "SKILL.md"
_RUNNER = _REPO / "scripts" / "run_live_probes.py"


def _frontmatter(md_text):
    parts = md_text.split("---")
    assert len(parts) >= 3, "no YAML frontmatter delimited by ---"
    fm = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


class TestSeamHunterAgent:
    def test_agent_file_exists(self):
        assert _AGENT.exists()

    def test_frontmatter_is_well_formed(self):
        fm = _frontmatter(_AGENT.read_text(encoding="utf-8"))
        assert fm.get("name") == "seam-hunter"
        assert fm.get("description")
        assert fm.get("tools")

    def test_description_has_no_yaml_colon_trap(self):
        # An unquoted description value containing ": " silently unregisters the
        # agent (the registry YAML trap). Must be absent unless the value is quoted.
        fm_line = next(l for l in _AGENT.read_text(encoding="utf-8").splitlines()
                       if l.startswith("description:"))
        value = fm_line[len("description:"):].strip()
        assert not (": " in value and not value[:1] in "\"'"), (
            "description value contains ': ' unquoted -- YAML trap, agent will "
            "silently fail to register")

    def test_agent_is_read_only(self):
        # The seam-gate FINDS, never fixes -- it must not carry Edit/Write.
        fm = _frontmatter(_AGENT.read_text(encoding="utf-8"))
        tools = {t.strip() for t in fm["tools"].split(",")}
        assert "Edit" not in tools and "Write" not in tools, (
            "seam-hunter must be read-only; the author cannot fix its own gate")

    def test_playbook_encodes_the_hard_won_attacks(self):
        # The institutional memory: the attacks that each caught a real bug.
        text = _AGENT.read_text(encoding="utf-8").lower()
        for attack in ("rebuild", "second network", "round-trip", "depth", "arity"):
            assert attack in text, f"playbook missing the '{attack}' attack"


class TestSolarisHardenSkill:
    def test_skill_exists(self):
        assert _SKILL.exists()

    def test_skill_enforces_the_load_bearing_rules(self):
        text = _SKILL.read_text(encoding="utf-8").lower()
        # The seam-gate is un-skippable; land is human; entry gate refuses on stale.
        assert "never skip" in text or "un-skippable" in text
        assert "human" in text and "land" in text
        assert "stale" in text
        assert "seam-hunter" in text          # coordinates the agent
        assert "run_live_probes" in text      # coordinates the runner


class TestProbeRunnerCompanionDetection:
    def _runner(self):
        spec = importlib.util.spec_from_file_location("_rlp", _RUNNER)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_rlp"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_composed_probes_need_no_companion(self, tmp_path):
        rlp = self._runner()
        p = tmp_path / "probe_loop_composed.py"
        p.write_text("print('PASS')", encoding="utf-8")
        assert rlp._has_negative_control(p) is True

    def test_inline_marker_counts_as_negative_control(self, tmp_path):
        rlp = self._runner()
        p = tmp_path / "probe_thing.py"
        p.write_text("# the cross-network collision is REFUSED here\n", encoding="utf-8")
        assert rlp._has_negative_control(p) is True   # 'refus' marker, case-insensitive

    def test_prefix_companion_file_counts(self, tmp_path):
        rlp = self._runner()
        (tmp_path / "probe_b1_render_tier_ordering.py").write_text("x=1", encoding="utf-8")
        (tmp_path / "probe_b1_fix_is_real.py").write_text("x=1", encoding="utf-8")
        assert rlp._has_negative_control(
            tmp_path / "probe_b1_render_tier_ordering.py") is True

    def test_bare_probe_has_no_negative_control(self, tmp_path):
        rlp = self._runner()
        p = tmp_path / "probe_bare.py"
        p.write_text("print('PASS: it works')", encoding="utf-8")
        assert rlp._has_negative_control(p) is False
