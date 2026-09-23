"""Standard IR / classification metrics used by the evaluation harness."""

from __future__ import annotations

import math
from collections import Counter
from typing import Hashable, Iterable, Mapping, Sequence


def precision_at_k(retrieved: Sequence[Hashable], relevant: set[Hashable], k: int) -> float:
    if k <= 0:
        return 0.0
    top = list(retrieved)[:k]
    if not top:
        return 0.0
    hits = sum(1 for item in top if item in relevant)
    return hits / len(top)


def recall_at_k(retrieved: Sequence[Hashable], relevant: set[Hashable], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(list(retrieved)[:k])
    return len(top & relevant) / len(relevant)


def mrr(retrieved: Sequence[Hashable], relevant: set[Hashable]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved: Sequence[Hashable],
    graded: Mapping[Hashable, int],
    k: int,
) -> float:
    """nDCG@k with exponential gain 2^g - 1 (TREC convention)."""
    if k <= 0:
        return 0.0
    gains = [max(int(graded.get(item, 0)), 0) for item in list(retrieved)[:k]]
    dcg = sum((2**gain - 1) / math.log2(idx + 2) for idx, gain in enumerate(gains))
    ideal = sorted((max(int(g), 0) for g in graded.values()), reverse=True)[:k]
    idcg = sum((2**gain - 1) / math.log2(idx + 2) for idx, gain in enumerate(ideal))
    if idcg <= 0:
        return 0.0
    return dcg / idcg


def mean(values: Iterable[float]) -> float:
    seq = list(values)
    if not seq:
        return 0.0
    return sum(seq) / len(seq)


def stdev(values: Iterable[float]) -> float:
    seq = list(values)
    if len(seq) < 2:
        return 0.0
    avg = mean(seq)
    variance = sum((x - avg) ** 2 for x in seq) / (len(seq) - 1)
    return math.sqrt(variance)


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def set_prf(
    predicted: set[str],
    gold: set[str],
) -> dict[str, float]:
    if not predicted and not gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(predicted & gold)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(gold) if gold else 0.0
    return {"precision": precision, "recall": recall, "f1": f1(precision, recall)}


def spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation; ties get average ranks."""
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0

    def _ranks(values: Sequence[float]) -> list[float]:
        indexed = sorted(enumerate(values), key=lambda pair: pair[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = _ranks(xs)
    ry = _ranks(ys)
    n = len(rx)
    mean_x = mean(rx)
    mean_y = mean(ry)
    num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    den_x = math.sqrt(sum((rx[i] - mean_x) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ry[i] - mean_y) ** 2 for i in range(n)))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def confusion(
    pairs: Sequence[tuple[str, str]],
) -> dict[str, object]:
    """Return a label-wise P/R/F1 table plus accuracy from (gold, pred) pairs."""
    labels = sorted({gold for gold, _ in pairs} | {pred for _, pred in pairs})
    matrix: dict[tuple[str, str], int] = Counter(pairs)
    per_label: dict[str, dict[str, float]] = {}
    correct = 0
    for label in labels:
        tp = matrix.get((label, label), 0)
        fp = sum(matrix.get((g, label), 0) for g in labels if g != label)
        fn = sum(matrix.get((label, p), 0) for p in labels if p != label)
        correct += tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_label[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1(precision, recall),
            "support": float(tp + fn),
        }
    accuracy = correct / len(pairs) if pairs else 0.0
    macro = mean(row["f1"] for row in per_label.values()) if per_label else 0.0
    return {
        "labels": labels,
        "per_label": per_label,
        "accuracy": accuracy,
        "macro_f1": macro,
        "n": len(pairs),
    }


def paired_wilcoxon_p(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Two-sided Wilcoxon signed-rank p-value, or None if scipy is missing."""
    if len(a) != len(b) or len(a) < 6:
        return None
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        return None
    try:
        result = wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    except ValueError:
        return None
    return float(result.pvalue)
