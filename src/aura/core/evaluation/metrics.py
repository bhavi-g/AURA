from dataclasses import dataclass

Key = tuple[str, int, str]  # (file, line, rule_id)


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    fn: int


def confusion(pred: set[Key], gold: set[Key]) -> Confusion:
    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)
    return Confusion(tp, fp, fn)


def precision(tp: int, fp: int) -> float:
    return tp / (tp + fp) if (tp + fp) else 0.0


def recall(tp: int, fn: int) -> float:
    return tp / (tp + fn) if (tp + fn) else 0.0


def f1(p: float, r: float) -> float:
    return (2 * p * r) / (p + r) if (p + r) else 0.0
