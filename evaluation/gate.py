import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--f1", type=float, default=0.75)
    ap.add_argument("--ece", type=float, default=0.05)
    args = ap.parse_args()

    data = json.load(open(args.results))
    m = data["metrics"]
    passes = (m["f1_macro"] >= args.f1) and (m["ece"] <= args.ece)
    print(
        {
            "f1_macro": m["f1_macro"],
            "auroc": m["auroc"],
            "ece": m["ece"],
            "brier": m["brier"],
            "passes_acceptance": passes,
        }
    )
    if not passes:
        sys.exit(1)


if __name__ == "__main__":
    main()
