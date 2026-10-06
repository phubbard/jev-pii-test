from jev_pii.metrics import Counts, Span, calibration, match_spans, sweep


def test_prf():
    c = Counts(tp=8, fp=2, fn=2)
    d = c.prf()
    assert d["precision"] == 0.8 and d["recall"] == 0.8 and d["f1"] == 0.8


def test_span_matching_label_aware_and_overlap():
    gold = [Span(0, 10, "EMAIL"), Span(20, 30, "PHONE")]
    pred = [Span(0, 10, "EMAIL"), Span(20, 30, "SSN"), Span(50, 60, "PHONE"), Span(22, 30, "PHONE")]
    m = match_spans(pred, gold)
    assert m["EMAIL"].tp == 1
    assert m["SSN"].fp == 1
    assert m["PHONE"].tp == 1 and m["PHONE"].fp == 1 and m["PHONE"].fn == 0


def test_sweep_and_calibration():
    scored = [(0.9, True), (0.8, True), (0.3, False), (0.1, False), (0.6, False)]
    best = sweep(scored)["best"]
    assert best["f1"] == 1.0 and best["threshold"] > 0.6
    cal = calibration(scored, bins=5)
    assert 0 <= cal["ece"] <= 1
