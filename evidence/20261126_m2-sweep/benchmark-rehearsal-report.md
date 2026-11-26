# Benchmark report — SmolVLA synthetic rehearsal held-out action error

> Result: **inconclusive** — suite declares no thresholds; the result is informational.
> Suite: `m2-rehearsal-action-error-v1` at level L1, data source `synthetic`.
> Operator: JerichoCheng · Host: jerichocheng-Lenovo-Legion-R9000P2021H · Generated: 2026-11-26T07:22:11Z.
> Dataset: `evidence/20261126_m2-sweep/seed0-samples.jsonl` — 10 samples, 0 trials, sha256 `8cb245b9b36a86e3bd254a70a00d449078c2ec425af5d4c36869763977e247d7`.
> Suite spec: `docs/m2/suites/m2-rehearsal-action-error-v1.yaml`, sha256 `e8d80f7c2a2c5e5c036232cf5d8f201b182792eacd7eb59eb6066964e8dd9172`.

## Metrics

| Metric | Aggregate | Value | Unit |
|---|---|---:|---|
| `action_mae_rad` | count | 10 | rad |
| `action_mae_rad` | mean | 0.484107 | rad |
| `action_mae_rad` | p50 | 0.474862 | rad |
| `action_mae_rad` | p95 | 0.561807 | rad |
| `action_mae_rad` | max | 0.561807 | rad |
| `action_mae_rad` | min | 0.402681 | rad |
| `action_rmse_rad` | count | 10 | rad |
| `action_rmse_rad` | mean | 0.637867 | rad |
| `action_rmse_rad` | p50 | 0.628344 | rad |
| `action_rmse_rad` | p95 | 0.736465 | rad |
| `action_rmse_rad` | max | 0.736465 | rad |
| `action_rmse_rad` | min | 0.513356 | rad |

## Thresholds

| Metric | Aggregate | Rule | Actual | Result |
|---|---|---|---:|---|
| — | — | — | — | — |

## Limitations

- Synthetic data and 20 training steps; not a useful policy.
- Teacher-forced offline action error; no closed-loop success rate.
- No threshold is registered; the result must be inconclusive.
- Data source is synthetic; this result is not a hardware or recorded-data result and must not be reported as one.
- A benchmark threshold is a project gate, not a safety certification.

## Notes

- M2.0 synthetic rehearsal; empty thresholds; not a policy-quality result

---

This is a benchmark report, not an acceptance report. It does not replace the source repository's `ACCEPTANCE.md`.
