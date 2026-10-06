import json

from jev_pii.generate import generate_records, generate_tables
from jev_pii.taxonomy import LABELS, NONE_LABEL


def test_spans_match_text_exactly():
    for r in generate_records(300, seed=7):
        for s in r.spans:
            assert r.text[s["start"] : s["end"]] == s["value"], (r.id, s)
            assert s["label"] in LABELS


def test_mix_of_formats_and_negatives():
    recs = generate_records(400, seed=3)
    formats = {r.format for r in recs}
    assert formats == {"ticket", "log", "json"}
    frac_no_pii = sum(1 for r in recs if not r.spans) / len(recs)
    assert 0.2 < frac_no_pii < 0.4
    assert {s["label"] for r in recs for s in r.spans} == set(LABELS)


def test_json_records_are_valid_json():
    for r in generate_records(200, seed=11):
        if r.format == "json":
            obj = json.loads(r.text)
            assert isinstance(obj, dict) and obj


def test_deterministic():
    a = [r.text for r in generate_records(50, seed=5)]
    b = [r.text for r in generate_records(50, seed=5)]
    assert a == b


def test_tables():
    tables = generate_tables(20, seed=2)
    assert any(t.obfuscated for t in tables) and any(not t.obfuscated for t in tables)
    for t in tables:
        assert len(t.rows) == 25
        assert all(len(row) == len(t.columns) for row in t.rows)
        for c in t.columns:
            assert c["label"] in LABELS or c["label"] == NONE_LABEL
    labels = {c["label"] for t in tables for c in t.columns}
    assert NONE_LABEL in labels and len(labels) >= 6
