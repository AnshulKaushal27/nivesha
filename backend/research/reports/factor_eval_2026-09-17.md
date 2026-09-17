# Buy Rank factor evaluation — 2026-09-17

Sample: 2025-07-23 → 2026-08-19, 269 days, horizon 21 trading days.

## Verdict

**PASS** — mean IC 0.0634 (t = 9.09, hit rate 71%), net decile spread 0.95% per period (11.4% annualised).

Pass criteria: mean IC ≥ 0.03, t ≥ 2, net top-minus-bottom spread > 0.

## Composite score

| metric | value |
| --- | --- |
| mean daily IC | 0.0634 |
| IC std | 0.1143 |
| t-stat | 9.09 |
| IC > 0 share of days | 70.6% |
| rolling 12m mean IC (latest) | 0.0679 |

## Per-factor IC (marginal usefulness)

| factor | mean IC | t-stat | hit rate |
| --- | --- | --- | --- |
| mom_12_1 | 0.0646 | 10.64 | 73% |
| mom_6_1 | 0.0233 | 3.30 | 59% |
| trend | 0.0263 | 3.86 | 57% |
| low_vol | 0.0077 | 0.82 | 59% |
| liquidity | 0.0369 | 6.03 | 65% |
| vol_conf | -0.0128 | -3.04 | 43% |
| overheat | -0.0063 | -1.23 | 53% |

A factor with negative mean IC and |t| > 2 should have its weight set to zero in config.

## Decile portfolios (equal-weight, rebalanced every horizon)

| decile | mean period return | annualised |
| --- | --- | --- |
| 1 | -1.03% | -12.3% |
| 2 | -0.89% | -10.7% |
| 3 | -0.12% | -1.4% |
| 4 | 0.30% | 3.6% |
| 5 | -0.24% | -2.9% |
| 6 | 0.34% | 4.1% |
| 7 | -0.50% | -6.0% |
| 8 | 0.44% | 5.3% |
| 9 | 0.28% | 3.4% |
| 10 | 0.53% | 6.3% |

Top − bottom, gross: 1.55% per period; net of 0.3% round-trip: 0.95%. Rebalances: 13.