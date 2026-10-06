"""Precision/recall/F1, threshold sweeps, calibration and span matching."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def add(self, pred: bool, gold: bool) -> None:
        if pred and gold:
            self.tp += 1
        elif pred and not gold:
            self.fp += 1
        elif not pred and gold:
            self.fn += 1
        else:
            self.tn += 1

    def prf(self) -> dict[str, float | int]:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "support": self.tp + self.fn,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
        }


def sweep(scored: list[tuple[float, bool]], steps: int = 20) -> dict:
    """Evaluate thresholds 0..1 and return the best-F1 threshold plus the curve."""
    curve = []
    best = None
    for i in range(steps + 1):
        t = i / steps
        c = Counts()
        for s, g in scored:
            c.add(s >= t, g)
        row = {"threshold": round(t, 3), **c.prf()}
        curve.append(row)
        if best is None or row["f1"] > best["f1"]:
            best = row
    return {"best": best, "curve": curve}


def calibration(scored: list[tuple[float, bool]], bins: int = 10) -> dict:
    """Reliability bins and expected calibration error for binary judgments."""
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for s, g in scored:
        idx = min(int(s * bins), bins - 1)
        buckets[idx].append((s, g))
    rows = []
    ece = 0.0
    n = len(scored) or 1
    for i, b in enumerate(buckets):
        if not b:
            continue
        mean_p = sum(s for s, _ in b) / len(b)
        frac = sum(1 for _, g in b if g) / len(b)
        ece += abs(mean_p - frac) * len(b) / n
        rows.append(
            {
                "bin": f"{i / bins:.1f}-{(i + 1) / bins:.1f}",
                "n": len(b),
                "mean_prob": round(mean_p, 3),
                "frac_positive": round(frac, 3),
            }
        )
    return {"ece": round(ece, 4), "bins": rows}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str

    def overlap(self, other: "Span") -> float:
        inter = max(0, min(self.end, other.end) - max(self.start, other.start))
        union = max(self.end, other.end) - min(self.start, other.start)
        return inter / union if union else 0.0


def match_spans(pred: list[Span], gold: list[Span], min_overlap: float = 0.5) -> dict[str, Counts]:
    """Greedy label-aware matching; a prediction counts if it overlaps a same-label gold span."""
    per_label: dict[str, Counts] = {}
    used: set[int] = set()
    for p in sorted(pred, key=lambda s: (s.start, s.end)):
        c = per_label.setdefault(p.label, Counts())
        hit = None
        best = min_overlap
        for i, g in enumerate(gold):
            if i in used or g.label != p.label:
                continue
            o = p.overlap(g)
            if o >= best:
                best, hit = o, i
        if hit is None:
            c.fp += 1
        else:
            used.add(hit)
            c.tp += 1
    for i, g in enumerate(gold):
        if i not in used:
            per_label.setdefault(g.label, Counts()).fn += 1
    return per_label


def merge_counts(parts: list[dict[str, Counts]]) -> dict[str, Counts]:
    out: dict[str, Counts] = {}
    for part in parts:
        for label, c in part.items():
            o = out.setdefault(label, Counts())
            o.tp += c.tp
            o.fp += c.fp
            o.fn += c.fn
            o.tn += c.tn
    return out


def micro(counts: dict[str, Counts]) -> dict:
    total = Counts()
    for c in counts.values():
        total.tp += c.tp
        total.fp += c.fp
        total.fn += c.fn
        total.tn += c.tn
    return total.prf()
