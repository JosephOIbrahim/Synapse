"""Hour3 design M5 (2026-10-06): radius literals that already equal a token
name the token. Zero-pixel by construction: ``{t.RADIUS_LG}`` is 12 and
``{t.RADIUS_SM}`` is 4, so the generated sheet is byte-identical.

Landed sites: #DsAuthor (bc-wave ruled block), the SWEEP_A gate_body rule,
and the editorial-tail #DsStop. NOT landed, because an existing pin holds
their literal text (probe log: hour3 design_proof/m5_pin_probe.log):
the first #DsStop rule and #DsChip padding (test_panel_sweep_a.py
test_qss_is_append_only_..., amendment text at :416/:430/:450 and :260-262),
and the context_action / dot-label paddings (test_pnl_l2_..., PNL tuple
:385-390).

Two pins here:
- golden sha256 of qss.stylesheet(s) at six scales, taken on b4a5fe3a before
  the edit, so any byte drift reddens;
- a census ratchet on raw ``border-*radius: <int>px`` literals in qss.py, so a
  new raw literal reddens (lower it when a pinned site is later freed).
"""
import hashlib
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_QSS = os.path.join(_ROOT, "python", "synapse", "panel", "designsystem", "qss.py")

# Produced by design_proof.py on b4a5fe3a (log: design_proof/base_a.log).
GOLDEN = {
    1.0: "db6564a64232ba86f4ed2b63953dfdc81d90ce1ccbd04357d42cd07a71ba6d3b",
    1.15: "9b293ba872a7a0767b21a3a9fd33a52e897c6c1db03e5d8316336963a6323c75",
    1.25: "5fd2ccca8e8a8ca6a6af9a4c9ce6a406934dfc09745ceed942397d21e4ce1d7e",
    1.4: "29f82763390ae7cdd685f2b8ac9ff6f8fc89ba28ec14e592a99896b94b9383ef",
    1.6: "98cc871515c9e3a9dcc856ea997ced5984cd81c54a5873358ff6585472c3bf5d",
    2.25: "dc014c5cb813a8e06790a94a86edef90d1c427851ed02d2ed773dafe8b275dae",
}
RAW_RADIUS_LITERALS_MAX = 30  # 33 on b4a5fe3a; M5 named three


@pytest.mark.parametrize("scale", sorted(GOLDEN))
def test_composed_sheet_is_byte_identical_to_the_pre_m5_golden(scale):
    from synapse.panel.designsystem import qss
    got = hashlib.sha256(qss.stylesheet(scale).encode("utf-8")).hexdigest()
    assert got == GOLDEN[scale]


def test_raw_radius_literal_census_only_ratchets_down():
    src = open(_QSS, encoding="utf-8").read()
    raw = re.findall(r"border-(?:[a-z]+-)*radius: \d+px", src)
    assert len(raw) <= RAW_RADIUS_LITERALS_MAX, len(raw)


def test_the_three_landed_sites_name_their_tokens():
    src = open(_QSS, encoding="utf-8").read()
    named = "border-radius: {t.RADIUS_LG}px; border-bottom-right-radius: {t.RADIUS_SM}px;"
    author = src[src.index("QPushButton#DsAuthor {{"):]
    assert author[:author.index("}}")].count(named) == 1
    tail_stop = src[src.rindex("QPushButton#DsStop {{"):]
    assert tail_stop[:tail_stop.index("}}")].count(named) == 1
    assert ("border: 1px solid {t.GRAPHITE}; border-radius: {t.RADIUS_SM}px;"
            in src[src.index('"gate_body"'):src.index('"gate_integrity"')])


def test_the_tokens_still_carry_the_values_the_sheet_relied_on():
    from synapse.panel.designsystem import tokens as t
    assert (t.RADIUS_LG, t.RADIUS_SM) == (12, 4)
