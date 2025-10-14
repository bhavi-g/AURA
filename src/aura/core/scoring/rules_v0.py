SEVERITY_W = {"LOW": 1, "MEDIUM": 3, "HIGH": 6, "CRITICAL": 10}
CONF_W = {"LOW": 0.6, "MEDIUM": 0.85, "HIGH": 1.0}
CATEGORY_W = {
    "Reentrancy": 1.3,
    "Access Control": 1.2,
    "Arithmetic": 1.1,
    "Gas/DoS": 1.0,
    "Best Practices": 0.6,
    "Unknown": 1.0,
}


def score_finding(f):
    base = SEVERITY_W[f["severity"]] * CONF_W[f["confidence"]] * CATEGORY_W.get(f["category"], 1.0)
    return round(max(0.5, base), 2)


def aggregate_score(findings):
    total = sum(score_finding(f) for f in findings)
    n_crit = sum(1 for f in findings if f["severity"] == "CRITICAL")
    return round(min(100.0, 20 * (1 - (1 / (1 + total / 10))) + 5 * n_crit), 2)
