import argparse
import time as _time
from pathlib import Path

import h5py
import numpy as np
from plotting import plot_ulb_dc_sensitivity, plot_ulb_results
from tc_cwi import Struct, tc_cwi

DATA_DIR = Path("data/ULB")
DEFAULT_TWIN_START_S = 290e-6
DEFAULT_TWIN_END_S = 330.1e-6
DEFAULT_SUBSAMPLE = 10
MA_WINDOW = 3


def load_ulb_dataset(data_dir: Path | str, dataset: int):
    """Load ULB dataset (1 or 2)."""
    if dataset not in (1, 2):
        raise ValueError("dataset must be 1 or 2")
    data_dir_path = Path(data_dir)
    mat_file = data_dir_path / f"data0{dataset}.mat"
    temp_file = data_dir_path / f"Temperature_data0{dataset}.mat"
    if not mat_file.exists() or not temp_file.exists():
        raise FileNotFoundError(
            f"Missing ULB dataset {dataset} files in {data_dir_path}. "
            "Please download data01.mat, data02.mat, Temperature_data01.mat, "
            "and Temperature_data02.mat from Zenodo (record 19139843)."
        )
    with h5py.File(mat_file, "r") as f:
        t = np.squeeze(f["t"][:])
        y = f["y"][:].T

    with h5py.File(temp_file, "r") as f:
        key_t = next(k for k in f.keys() if k != "#refs#")
        T = np.squeeze(f[key_t][:])
    return t, y, T


def obstacle_sensitivity(
    dc_reference: np.ndarray, dc_with_obstacle: np.ndarray
) -> Struct:
    """Estimate obstacle sensitivity from the largest adjacent DC change."""
    dc_reference = np.asarray(dc_reference, dtype=float).ravel()
    dc_with_obstacle = np.asarray(dc_with_obstacle, dtype=float).ravel()
    if dc_reference.size == 0 or dc_with_obstacle.size < 2:
        raise ValueError(
            "Sensitivity requires reference DC and at least two obstacle DC values."
        )
    if not np.all(np.isfinite(dc_reference)) or not np.all(
        np.isfinite(dc_with_obstacle)
    ):
        raise ValueError("Sensitivity requires finite DC values.")

    max_reference_dc = float(np.max(dc_reference))
    if max_reference_dc <= 0:
        raise ValueError("Sensitivity requires a positive maximum reference DC.")

    # ponytail: largest DC jump assumes one clear obstacle insertion.
    insertion_index = int(np.argmax(np.abs(np.diff(dc_with_obstacle)))) + 1
    dc_at_insertion = float(dc_with_obstacle[insertion_index])
    ratio = dc_at_insertion / max_reference_dc
    return Struct(
        sensitivity=ratio,
        obs_idx=insertion_index,
        dc_obs=dc_at_insertion,
        dc_max_ref=max_reference_dc,
    )


def run_workflow(
    t,
    y,
    T,
    twin,
    subsample: int,
    out_path: str,
    dc_ref=None,
    title: str = "Dataset 1 (no obstacle)",
):
    """Run time-stretching workflow with optional MA comparison.

    Args:
        dc_ref: If provided, compute MA comparison and obstacle sensitivity.
    Returns:
        DC values for use as reference.
    """
    y_use = y[:, ::subsample]
    T_use = T[::subsample] if T.shape[0] > 1 else T
    n_sig = y_use.shape[1]

    i_start = int(np.searchsorted(t, twin[0]))
    i_end = int(np.searchsorted(t, twin[1]))
    twin_ind = np.arange(i_start, i_end)

    if twin_ind.size == 0:
        raise ValueError(
            "Selected time window is empty. Adjust --twin-start/--twin-end."
        )

    print(f"  Data shape        : {y.shape[0]} samples × {y.shape[1]} acquisitions")
    print(f"  Time window       : {twin[0] * 1e6:.1f} - {twin[1] * 1e6:.1f} µs")
    print(
        f"  Sample indices    : {twin_ind[0]} - {twin_ind[-1]} ({len(twin_ind)} samples)"
    )
    print(f"  Signals processed : {n_sig} (subsample={subsample})")

    y0_ref = y_use[:, 0]
    out_no_comp = tc_cwi("getccns", y0_ref, y_use, twin_ind)

    print("=" * 60)
    print("  Running Time-Stretching optimisation …")
    t0 = _time.time()
    out = tc_cwi("findeps", y0_ref, y_use, t, 0.0, 2, twin_ind)
    elapsed = _time.time() - t0
    print(f"  Done in {elapsed:.1f} s")

    sig_idx = np.arange(n_sig)
    cc = 1 - out.DCsf

    plot_ulb_results(
        sig_idx=sig_idx,
        temperature=T_use,
        epsf=out.EPSf,
        cc_no_stretch=out_no_comp.CC,
        cc_stretched=cc,
        title=title,
        out_path=out_path,
    )
    print(f"  Saved plot        : {out_path}")

    # MA comparison if reference provided
    if dc_ref is not None:
        print("=" * 60)
        print(f"  Computing moving-average reference (window={MA_WINDOW}) …")
        t0 = _time.time()
        out_ma = tc_cwi("findeps -ma", y0_ref, y_use, t, 0.0, 2, twin_ind, MA_WINDOW)
        elapsed = _time.time() - t0
        print(f"  Done in {elapsed:.1f} s")

        dc_fixed = out.DCsf
        dc_ma = out_ma.DCma

        sens_fixed = obstacle_sensitivity(dc_ref, dc_fixed)
        sens_ma = obstacle_sensitivity(dc_ref, dc_ma)

        plot_ulb_dc_sensitivity(
            sig_idx=sig_idx,
            dc_fixed=dc_fixed,
            dc_ma=dc_ma,
            ma_window=MA_WINDOW,
            obs_idx_fixed=sens_fixed.obs_idx,
            obs_idx_ma=sens_ma.obs_idx,
            sensitivity_fixed=sens_fixed.sensitivity,
            sensitivity_ma=sens_ma.sensitivity,
            out_path=out_path.replace(".png", "_dc_sensitivity.png"),
        )
        print(
            f"  Saved plot        : {out_path.replace('.png', '_dc_sensitivity.png')}"
        )

    return out.DCsf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ULB temperature-compensation workflow (Dataset 1 and 2)."
    )
    parser.add_argument(
        "--twin-start",
        type=float,
        default=DEFAULT_TWIN_START_S,
        help="Time-window start in seconds.",
    )
    parser.add_argument(
        "--twin-end",
        type=float,
        default=DEFAULT_TWIN_END_S,
        help="Time-window end in seconds.",
    )
    parser.add_argument(
        "--subsample",
        type=int,
        default=DEFAULT_SUBSAMPLE,
        help="Subsampling factor over acquisitions (1 = use all).",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["1", "2", "both"],
        default="both",
        help="Which dataset to process: '1', '2', or 'both' (default: 'both').",
    )
    args = parser.parse_args()

    if args.subsample < 1:
        raise ValueError("--subsample must be >= 1")
    if args.twin_start >= args.twin_end:
        raise ValueError("--twin-start must be < --twin-end")

    twin = [args.twin_start, args.twin_end]

    if args.dataset in ("1", "both"):
        print("\nDataset 1 (no obstacle)")
        t, y, T = load_ulb_dataset(DATA_DIR, 1)
        dc_ref = run_workflow(
            t,
            y,
            T,
            twin,
            args.subsample,
            "ulb_results_dataset1.png",
            title="Dataset 1 (no obstacle)",
        )
    else:
        dc_ref = None

    if args.dataset in ("2", "both"):
        print("\nDataset 2 (with obstacle)")
        t, y, T = load_ulb_dataset(DATA_DIR, 2)
        if dc_ref is None:
            # Load dataset 1 as reference when only dataset 2 is requested
            t_ref, y_ref, T_ref = load_ulb_dataset(DATA_DIR, 1)
            dc_ref = run_workflow(
                t_ref,
                y_ref,
                T_ref,
                twin,
                args.subsample,
                "ulb_results_dataset1.png",
                title="Dataset 1 (no obstacle)",
            )
        run_workflow(
            t,
            y,
            T,
            twin,
            args.subsample,
            "ulb_results_dataset2.png",
            dc_ref=dc_ref,
            title="Dataset 2 (with obstacle)",
        )


if __name__ == "__main__":
    main()
