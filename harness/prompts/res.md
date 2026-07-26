Read harness/AGENT_CONSTITUTION.md first - it binds you. Then read harness/notes/CTO_RULINGS_01.md rulings R41, R42 and R43. You are ORCHESTRATOR for the fake-hou residency leg. This leg is the release condition for H2 - H2 cannot start until it lands.

THE DEFECT, verified 2026-07-26 (R41):
python/synapse/mcp/tool_impls/solaris/component_builder.py:315 raises
  AttributeError: 'Parm' object has no attribute 'set'
under hython3.13 against REAL Houdini. Same at scene_template.py:218.

POSITIVE CONTROL, already established - do not re-derive:
  hython3.13 -c "import hou; print(hou.Parm.set)"  ->  exists, 22.0.368,
  module .../houdini/python3.13libs/hou.py
hou.Parm.set EXISTS. Therefore a STUB Parm is shadowing the real class. This is Q1's defect class - fake-hou residency - surviving in a different module. tests/solaris/test_live_wiring.py believes it drives live Houdini and does not.

PRIOR RUN, 2026-07-26 09:15-11:47: an earlier dispatch of this leg received a TRUNCATED brief - the prompt was passed as a CLI argument and split at an embedded double quote, so that agent got everything up to "POSITIVE CONTROL ... hython3.13 -c" and nothing after. It never received the WORK steps, the oracle, or the instruction to write a receipt. It nonetheless located the root cause and reported "Mile 1 of ~6 - root cause located". Its transcript is at ~/.claude/projects/C--Users-User-SYNAPSE--claude-worktrees-fake-hou-residency/. Read it FIRST - do not re-derive what it already established. Then complete the leg.

WORK:
1. Find what installs the stub hou/Parm and when. Import-time sys.modules planting is the prime suspect (Q1's mechanism), but PROVE it rather than assuming - Q1's real diagnosis was restore-by-object vs restore-by-reimport, which looks identical and is not.
2. Eliminate the residency on the Solaris test path. Q1's pattern in tests/test_hda_panel.py:160-204 is the reference: capture the ORIGINAL module OBJECTS, restore those exact objects. Restore-by-reimport is NOT equivalent.
3. Then the ~17 tests in Q2 bucket 2 (R43) - same mechanism, same fix.
4. Every regression pin must FAIL against a deliberately broken implementation (R34 mutation standard). A pin that survives its own mutation is a decoration - report it, do not quietly fix it.

ORACLE: the AttributeError disappears under hython3.13; tests/solaris/test_live_wiring.py drives real hou; gate suite holds at 4881+ with 0 failed; Commandment 7 - count strictly increases or holds.

Write harness/notes/receipts/RES.json (receipt/v1, model + settings_profile per R25). Never push, never merge, never tag.
