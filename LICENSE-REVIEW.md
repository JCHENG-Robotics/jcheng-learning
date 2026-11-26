# License review — jcheng-learning

> Status: **pending** as of 2026-11-26.
> No `LICENSE` file exists. This repository follows the organization rule that
> no license is added before the review is signed off
> (`.github/docs/license-review.md`).

## 1. Current facts

| Item | Fact |
|---|---|
| `LICENSE` file | none |
| Code in v0.1.0 | documentation, tests and a shell gate; no runtime code |
| Runtime dependencies | none in v0.1.0 |
| Test dependencies | `pytest` (MIT), `PyYAML` (MIT) — CI only |
| Datasets | outside the repository; each carries its own license |
| Model artifacts | outside the repository (`/opt/jcheng/models/`); each carries its own license and provenance |
| Vendor code or weights | none copied |

## 2. Decision recorded on 2026-11-26

The repository is created **without** a `LICENSE` file until the ecosystem
review closes. Adding MIT now would pre-empt the organization decision and
would suggest the eventual license covers datasets and model artifacts, which
it will not.

The review must decide before the ecosystem reaches v1.0:

1. The copyright holder and year for new repositories.
2. Whether MIT is the intended license for capability repositories.
3. How dataset and model-artifact licenses are recorded and surfaced.
4. Whether a `THIRD_PARTY_NOTICES.md` is required once training dependencies
   (for example PyTorch or ROS packages) enter the repository.

## 3. Third-party inventory (to verify at M2/M3)

| Dependency | Use | Known/probable license | Risk |
|---|---|---|---|
| Python standard library | code | PSF | Low |
| pytest | tests only | MIT | Low |
| PyYAML | manifest parsing | MIT | Low |
| ROS 2 Humble | M3 runtime | Apache-2.0 | Low; keep notices |
| Training framework (TBD) | M2 offline | TBD | Decide before adoption |
| Datasets | M1/M2 | per dataset | Must be recorded per dataset |
| Model weights | M2/M3 | per artifact | Must not enter git |

## 4. Open questions

- [ ] Confirm the copyright holder and year.
- [ ] Confirm MIT for this capability repository.
- [ ] Define the per-dataset and per-model license record.
- [ ] Decide the notice requirement for the training stack.
- [ ] Record the ecosystem-wide decision in `.github/docs/license-review.md`.

## 5. Related

- [`.github/docs/license-review.md`](https://github.com/JCHENG-Robotics/.github/blob/main/docs/license-review.md)
- [Acceptance report](ACCEPTANCE.md)
- [README](README.md)
