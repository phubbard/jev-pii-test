"""Recall-tuned regex candidate finders.

Jev cannot generate text, so span detection works by over-finding candidates in code and
asking Jev to judge each one. Every finder here is deliberately permissive; precision is
Jev's job. The same finders, taken at face value, are the regex-only baseline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jev_pii.taxonomy import LABELS


@dataclass(frozen=True)
class Candidate:
    start: int
    end: int
    text: str
    kind: str  # one of taxonomy.LABELS


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Phone: 10+ digits with common separators, optional +1 / 1- prefix and parentheses.
_PHONE = re.compile(r"(?<![\w.])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)|(?<![\d-])\d{9}(?![\d-])")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)")  # 12 covers Maestro
_IP = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_DATE = re.compile(
    rf"(?<!\d)(?:\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}}|(?:{_MONTHS})\.? \d{{1,2}},? \d{{4}})(?!\d)"
)
_STREET_SUFFIX = (
    "Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Terrace|"
    "Place|Pl|Circle|Cir|Parkway|Pkwy|Highway|Hwy|Trail|Trl|Square|Sq|Loop|Run|Pass|Pike|"
    "Alley|Crossing|Extension|Ext|Fork|Harbor|Hollow|Isle|Junction|Landing|Meadow|Mews|"
    "Mission|Motorway|Mount|Neck|Orchard|Overpass|Park|Path|Plaza|Point|Port|Ramp|Ranch|"
    "Ridge|River|Row|Shoal|Shore|Spring|Springs|Station|Stravenue|Stream|Summit|Throughway|"
    "Tunnel|Turnpike|Underpass|Union|Valley|Via|Village|Ville|Vista|Walk|Wall|Ways|Well|Wells"
)
# Two alternatives: (a) number + capitalised words + optional unit + ", City, ST 12345" tail,
# which covers any street name; (b) number + words + a known street suffix, for addresses
# written without city/state. Both over-find on purpose.
_UNIT = r"(?:(?:Apt\.?|Suite|Ste\.?|Unit|#) ?\w+)"
_ADDRESS = re.compile(
    rf"\b\d{{1,6}} (?:[A-Z][A-Za-z'.-]* ?){{1,5}}(?:{_UNIT} ?)?"
    rf", ?[A-Z][A-Za-z'. ]+?, ?[A-Z]{{2}} \d{{5}}(?:-\d{{4}})?"
    rf"|\b\d{{1,6}} (?:[A-Z][A-Za-z'.-]+ ){{1,4}}(?:{_STREET_SUFFIX})s?\b\.?(?: {_UNIT})?"
)
# Names: 2-3 consecutive capitalised tokens, optional title. Over-finds company/place names.
_NAME = re.compile(
    r"\b(?:(?:Mr|Mrs|Ms|Dr|Prof|Mx)\.? )?[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?"
    r"(?: (?:[A-Z]\.|[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)){1,2}\b"
)

_FINDERS: dict[str, re.Pattern[str]] = {
    "EMAIL": _EMAIL,
    "PHONE": _PHONE,
    "SSN": _SSN,
    "CREDIT_CARD": _CARD,
    "IP_ADDRESS": _IP,
    "DATE_OF_BIRTH": _DATE,
    "STREET_ADDRESS": _ADDRESS,
    "PERSON_NAME": _NAME,
}
assert set(_FINDERS) == set(LABELS), "every taxonomy label needs a finder"


def find_candidates(text: str, kinds: tuple[str, ...] = LABELS) -> list[Candidate]:
    """All candidate spans in document order. Overlaps across kinds are kept on purpose:
    the same digits may be a phone, an SSN-shaped id or part of a card number."""
    out: list[Candidate] = []
    for kind in kinds:
        for m in _FINDERS[kind].finditer(text):
            s, e = m.start(), m.end()
            span = text[s:e].strip()
            if not span:
                continue
            # trim trailing punctuation that the permissive patterns may swallow
            while span and span[-1] in ".,;:" and e > s:
                e -= 1
                span = text[s:e]
            out.append(Candidate(s, e, span, kind))
    # dedupe exact (start,end,kind)
    seen: set[tuple[int, int, str]] = set()
    uniq = []
    for c in out:
        key = (c.start, c.end, c.kind)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    uniq.sort(key=lambda c: (c.start, c.end, c.kind))
    return uniq


def luhn_ok(digits: str) -> bool:
    ds = [int(ch) for ch in digits if ch.isdigit()]
    if len(ds) < 12:
        return False
    total = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
