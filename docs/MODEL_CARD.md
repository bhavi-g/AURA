
# AURA Model Card

**Version:** 1.0.0  
**Date:** TBD  
**Owner:** AURA Team (Bhavish Goyal)

## Intended Use
Risk scoring for smart contracts pre-deployment and in CI.

## Data
- Sources: curated incidents, SmartBugs, internal labels
- Splits: family-based (no leakage)

## Metrics
- F1_macro, AUROC
- ECE, Brier, NLL
- PoC success rate for High/Critical

## Limitations
- Chain coverage limited to EVM in v1
- Economic models depend on data freshness

## Safety
- Human-in-the-loop for R>=0.5 or CRITICAL findings
- Reproducibility: dataset & model hashes recorded
