# AURA Report (Week 3)

- Generated: 2025-11-03T20:33:16
- Findings: **9**
- Score: **13.01**

## Severity Breakdown
| Severity | Count |
|---|---|
| `LOW` | 6 |
| `HIGH` | 2 |
| `MEDIUM` | 1 |

## Category Breakdown
| Category | Count |
|---|---|
| `solc-version` | 3 |
| `arbitrary-send-eth` | 1 |
| `tx-origin` | 1 |
| `missing-zero-check` | 1 |
| `immutable-states` | 1 |
| `reentrancy-eth` | 1 |
| `low-level-calls` | 1 |

## Top Rules
| Rule ID | Hits |
|---|---|
| `solc-version` | 3 |
| `arbitrary-send-eth` | 1 |
| `tx-origin` | 1 |
| `missing-zero-check` | 1 |
| `immutable-states` | 1 |
| `reentrancy-eth` | 1 |
| `low-level-calls` | 1 |

## Sample Findings (first 10)
| Rule | Severity | File:Line | Title |
|---|---|---|---|
| `solc-version` | LOW | samples/contracts/UncheckedMath.sol:2 | solc-version |
| `arbitrary-send-eth` | HIGH | samples/contracts/TxOriginAuth.sol:6 | arbitrary-send-eth |
| `tx-origin` | MEDIUM | samples/contracts/TxOriginAuth.sol:6 | tx-origin |
| `missing-zero-check` | LOW | samples/contracts/TxOriginAuth.sol:6 | missing-zero-check |
| `solc-version` | LOW | samples/contracts/TxOriginAuth.sol:2 | solc-version |
| `immutable-states` | LOW | samples/contracts/TxOriginAuth.sol:4 | immutable-states |
| `reentrancy-eth` | HIGH | samples/contracts/Reentrancy.sol:6 | reentrancy-eth |
| `solc-version` | LOW | samples/contracts/Reentrancy.sol:2 | solc-version |
| `low-level-calls` | LOW | samples/contracts/Reentrancy.sol:6 | low-level-calls |