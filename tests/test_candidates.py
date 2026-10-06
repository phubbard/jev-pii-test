from collections import Counter

from jev_pii.candidates import find_candidates, luhn_ok
from jev_pii.generate import generate_records
from jev_pii.metrics import Span
from jev_pii.taxonomy import LABELS


def test_recall_ceiling_per_label():
    """Every finder must over-find: nearly all gold spans must be covered by a same-kind candidate."""
    hit, total = Counter(), Counter()
    for r in generate_records(400, seed=21):
        cands = [Span(c.start, c.end, c.kind) for c in find_candidates(r.text)]
        for s in r.spans:
            g = Span(s["start"], s["end"], s["label"])
            total[g.label] += 1
            if any(c.label == g.label and c.overlap(g) >= 0.5 for c in cands):
                hit[g.label] += 1
    ceilings = {l: hit[l] / total[l] for l in LABELS}
    print(ceilings)
    for l, v in ceilings.items():
        assert v >= 0.9, (l, v)


def test_simple_finds():
    text = "Call (415) 555-0134 or email jane.doe@gmail.com; SSN 123-45-6789; ip 203.0.113.9; DOB 03/04/1987; card 4532 0151 1283 0366; 742 Evergreen Terrace, Springfield, IL 62704; Maria Gonzalez"
    kinds = {c.kind for c in find_candidates(text)}
    assert kinds == set(LABELS)


def test_luhn():
    assert luhn_ok("4532015112830366")
    assert not luhn_ok("4532015112830367")
