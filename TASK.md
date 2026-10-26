## Scope: `tc-cwi-workflows`

Lightweight, publishable research workflow repository for Environmental and Operational Condition (EoC) compensation in ultrasonic Structural Health Monitoring (SHM) using Coda Wave Interferometry (CWI) and the Time-Stretching method.

Consumes upstream PyPI package `tc-cwi>=0.1` and reproduces published results from ULB and Airbus EWSHM 2026 campaigns. Datasets are decoupled and hosted on Zenodo (records 19139843 and 19209079).

---

## Phase 1 & 2: Initial Delivery & Core Packaging (Complete)

- [X] Convert notebook workflow into reproducible Python scripts.
- [X] Implement Airbus `.sg2` ingestion + time-stretching + results workflow.
- [X] Implement ULB workflows for temperature compensation (Dataset 1 & 2).
- [X] Implement moving-average reference path (`findeps -ma`) and obstacle sensitivity metric.
- [X] Validate experimental figures matching EWSHM 2026 papers.

---

## Phase 3: Transition to Standalone Workflow Repository (tc-cwi-workflows v0.2.0)

### 1. Packaging & Dependency Migration (R1)
- [X] Create and switch to release branch `release/use-pypi-tc-cwi`.
- [X] Update `pyproject.toml`: set package name `tc-cwi-workflows`, version `0.2.0`, license `MIT`, `[tool.uv] package = false`, dependency on upstream `tc-cwi>=0.1` and script dependencies.
- [X] Delete vendored algorithm package `src/tc_cwi/` and legacy unit tests.
- [X] Delete educational notebook `TimeStretching.ipynb`.
- [X] Create `tests/test_ulb_workflow.py` testing obstacle sensitivity and `tc_cwi` package dispatch.

### 2. Data Decoupling & Script Reorganization (R2)
- [X] Add `data/` to `.gitignore`.
- [X] Untrack `data/` from git index (`git rm -r --cached data/`) while retaining local files on disk.
- [X] Delete legacy scripts: `scripts/prepare_data.py` and `scripts/load_data.py`.
- [X] Inline `load_ulb_dataset` into `scripts/ulb_workflow.py` with `--dataset` CLI option.
- [X] Inline `load_airbus_sg2_dataset` and `_zscore` into `scripts/airbus_workflow.py` supporting Zenodo directory layouts.
- [X] Reorganize local Airbus files to match Zenodo archive layout (`seg2_data_june2024/ONDULYS`, `temp_and_humidity_data_june2024/USER-2024-06-26.xlsx`).
- [X] Create `tests/test_airbus_workflow.py` testing `_zscore` normalization and synthetic signal correlation.

### 3. Documentation, Licensing, Figures, and Cleanup (R3)
- [X] Delete 5 copyrighted/binary PDF files in `docs/`.
- [X] Delete legacy `matlab/` directory (3 files).
- [X] Add MIT `LICENSE` file (`Copyright (c) 2026 aderaema`).
- [X] Create `docs/figures/` with curated publication figures (`ulb_results_dataset1.png`, `airbus_sensor_5.png`).
- [X] Rewrite `README.md` with complete workflow overview, installation (`uv sync` / `pip install .`), Zenodo download guides, embedded results figures, and 4 BibTeX citations.
- [X] Update `.agents/AGENTS.md` and `TASK.md` for `tc-cwi-workflows`.

### 4. Remote & History Preparation (R4)
- [ ] Commit all changes to `release/use-pypi-tc-cwi` and push to `origin`.
- [ ] Create clean orphan branch `tc-cwi-workflows-main` with single initial commit (no large file git history).
- [ ] Push clean orphan branch to `Zensor-BE/tc-cwi-workflows`.
- [ ] Switch back to `release/use-pypi-tc-cwi`.
