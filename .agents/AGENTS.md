# Agent Instructions for `tc-cwi-workflows`

This guide outlines architecture, coding conventions, workflows, and tool usage for AI agents working in this repository.

---

## Project Overview

This repository provides reproducible research workflows for Environmental and Operational Condition (EoC) compensation in ultrasonic Structural Health Monitoring (SHM) using Coda Wave Interferometry (CWI) and the Time-Stretching method.

Key components:
- **Upstream Algorithm Package:** Core time-stretching optimization and MATLAB-compatible dispatch are consumed from the external PyPI package [`tc-cwi>=0.1`](https://pypi.org/project/tc-cwi/).
- **Research Workflows (`scripts/`):** Reproducible analysis pipelines for ULB (`ulb_workflow.py`) and Airbus (`airbus_workflow.py`) campaigns with self-contained data loaders.
- **Visualization (`scripts/plotting.py`):** Standardized publication figure generation routines outputting to `figures/`.
- **Curated Documentation Figures (`docs/figures/`):** Permanent curated figures replicating published results in EWSHM 2026.
- **Verification Tests (`tests/`):** Fast, synthetic unit tests in `tests/test_ulb_workflow.py` and `tests/test_airbus_workflow.py`.

---

## Environment & Development Commands

This project uses [`uv`](https://github.com/astral-sh/uv) for environment management and dependency resolution.

### Common Commands

```bash
# Sync environment (installs script dependencies and upstream tc-cwi>=0.1 from PyPI)
uv sync

# Run test suite
uv run pytest

# Lint gate (rule set configured in pyproject.toml [tool.ruff.lint])
uv run ruff check .

# Syntax validation across all scripts
uv run python -m py_compile scripts/*.py

# Quick workflow smoke tests
uv run python scripts/ulb_workflow.py --dataset both --subsample 100
uv run python scripts/airbus_workflow.py --peaks 1 --temp1 20.0 --temp2 25.0 --sensor 1
```

---

## High-Level Architecture

### Data Flow (ULB Workflow)
1. **Load:** `load_ulb_dataset(data_dir, dataset)` → `(t, y, T)` where `y` is an array of shape `(samples, acquisitions)`.
2. **Compute Reference DC:** `tc_cwi("getccns", ...)` on Dataset 1 (no obstacle baseline).
3. **Optimize Stretch:** `tc_cwi("findeps", ...)` calculates optimal strain factor `eps` per signal.
4. **Moving-Average Comparison (Dataset 2):** `tc_cwi("findeps -ma", ...)` uses a moving-average reference frame.
5. **Sensitivity Metric:** `obstacle_sensitivity(dc_ref, dc_obs)` calculates $\text{Sensitivity} = \frac{\text{DC}_{\text{obs}}}{\max(\text{DC}_{\text{ref}})}$.
6. **Plot:** Generates comparison plots (temperature, stretch factor, CC, sensitivity) saved to `figures/`.

### Data Flow (Airbus Workflow)
1. **Load:** `load_airbus_sg2_dataset(ondulys_dir, excel_path)` → `(S, y_all, t)` where `S` is sensor metadata and `y_all` is list of signals per sensor.
2. **Normalize:** `_zscore(x)` normalizes each waveform to zero mean and unit variance.
3. **Environmental Correlation:** Matches SEG-2 acquisition timestamps with temperature and humidity logs from `USER-2024-06-26.xlsx`.
4. **Correlation Analysis:** Evaluates `tc_cwi("getccns", ...)` and `tc_cwi("findeps", ...)` across temperature bounds.
5. **Plot:** Generates mean CC vs temperature and per-sensor waveform plots saved to `figures/`.

### `tc_cwi` Command Dispatch API (Upstream PyPI Package)

The upstream package provides a command-dispatch string pattern:

| Command | Input Arguments | Output Attributes | Description |
| :--- | :--- | :--- | :--- |
| `'getccns'` | `y0, y` `[, ind]` | `CC`, `DC` | Baseline cross-correlation without stretching |
| `'stretch'` | `y, t, eps` | *numpy array* | Stretches signal(s) via 1D linear interpolation |
| `'getccs'` | `y0, y, t, eps` `[, ind]` | `CC`, `DC` | Cross-correlation after applying stretch `eps` |
| `'findeps'` | `y0, y, t, e0, method, ind` | `EPSf`, `DCsf` (multi) or `eps`, `DC` (single) | Optimizes `eps` (`method=1`: bounded, `method=2`: Nelder-Mead) |
| `'findeps -ma'`| `y0, y, t, e0, method, ind, n_ma` | `EPSma`, `DCma` | Time-stretching with moving-average reference |

> **API Convention:** Outputs are wrapped in a `Struct` container (`types.SimpleNamespace`) supporting attribute access (`out.CC`, `out.eps`), mirroring MATLAB struct behavior. Multi-signal results use the `f` suffix (`EPSf`, `DCsf`), while moving-average results use the `ma` suffix (`EPSma`, `DCma`).

---

## Key Conventions & Domain Logic

### 1. Correlation (`CC`) vs Decorrelation (`DC`)
- `CC` is the correlation coefficient ($0 \le \text{CC} \le 1$, higher is better).
- `DC = 1 - CC` is the decorrelation coefficient ($0 \le \text{DC} \le 1$, lower is better).
- The EWSHM 2026 paper uses **DC** for damage/obstacle detection; always compute decorrelation as `1 - CC`.

### 2. Obstacle Sensitivity Metric
$$\text{Sensitivity} = \frac{\text{DC}_{\text{obs}}}{\max(\text{DC}_{\text{ref}})}$$
- $\text{DC}_{\text{obs}}$: Decorrelation value at the obstacle insertion point (identified by the maximum absolute gradient in the DC sequence).
- $\max(\text{DC}_{\text{ref}})$: Maximum decorrelation observed across the reference dataset (Dataset 1, without obstacle).
- A value $> 1.0$ indicates the obstacle is detectable above temperature-induced noise.
- Implemented in `scripts/ulb_workflow.py` via `obstacle_sensitivity(dc_reference, dc_with_obstacle)`.

### 3. Time Window Selection
- Time windows are specified in seconds: `twin = [start_s, end_s]` (e.g., `[290e-6, 330.1e-6]`).
- Convert to indices once per dataset:
  ```python
  i_start = int(np.searchsorted(t, twin[0]))
  i_end = int(np.searchsorted(t, twin[1]))
  twin_ind = np.arange(i_start, i_end)
  if twin_ind.size == 0:
      raise ValueError("Time window contains no samples.")
  ```

### 4. Plotting Standards
- Resolution & Size: `(11, 7.2)` inches, DPI 160.
- Color palette: `steelblue` (Dataset 1 / fixed reference), `tomato` (Dataset 2 / moving-average reference).
- Format: PNG only, saved in `figures/` (created dynamically via `_output_path(out_path)`).
- Terminal logs: Use structured key-value formatting with colon alignment.

### 5. Data Subsampling
- Subsampling factor default is `10` (every 10th acquisition).
- Slice uniformly across acquisitions:
  ```python
  y_use = y[:, ::subsample]
  T_use = T[::subsample] if T.shape[0] > 1 else T
  ```

---

## Common Modification Patterns

### Adding a Workflow Parameter
1. Add an argument to `argparse.ArgumentParser` in `main()` with a sensible default.
2. Thread the parameter into `run_workflow()`.
3. Apply it in computation (e.g., window range, subsample, optimization method).
4. Update the help text string.

### Adding a Test
1. Put ULB workflow tests in `tests/test_ulb_workflow.py` and Airbus workflow tests in `tests/test_airbus_workflow.py`.
2. Build synthetic signals in the test module (`t = np.arange(0.0, 10.0, 0.01)`) — the unit tests must not depend on external datasets in `data/`.
3. Gate changes with `uv run pytest` and `uv run ruff check .`.

### Adding a New Plot Function
1. Define the function in `scripts/plotting.py` accepting `..., out_path="name.png"`.
2. Wrap path handling with `_output_path(out_path)`.
3. Save with `fig.savefig(_output_path(out_path), dpi=160)` and close via `plt.close(fig)`.
4. Call it from the corresponding workflow script.

---

## Known Assumptions & Edge Cases

- **Decoupled Datasets:** Datasets are hosted on Zenodo (ULB record 19139843, Airbus record 19209079) and gitignored in `data/`.
- **Obstacle Detection:** Detected via the maximum gradient of `DC`. Assumes a single, abrupt insertion step. Gradual or multiple insertions require alternative thresholding.
- **Moving-Average Window:** Fixed to `MA_WINDOW = 3` in workflow scripts.
- **ObsPy SEG-2 Warning:** ObsPy emits benign warnings for normalized `DELAY=0` SEG-2 files. These are suppressed in `scripts/airbus_workflow.py` using `warnings.catch_warnings()`.

---

## Engineering Philosophy (Lazy Minimalism)

- Keep functions focused and avoid premature abstractions or factory classes.
- Prefer explicit data flow over hidden state.
- Parameterize shared logic rather than duplicating pipelines.
