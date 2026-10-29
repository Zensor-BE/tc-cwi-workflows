import argparse
import time as _time
import warnings
from pathlib import Path

import numpy as np
import obspy
import pandas as pd
from plotting import plot_airbus_compensated_signal, plot_airbus_mean_cc
from tc_cwi import tc_cwi


def _resolve_airbus_paths() -> tuple[Path, Path]:
    """Resolve paths to Airbus dataset under data/Airbus/ or data/."""
    candidates = [Path("data/Airbus"), Path("data")]
    for base in candidates:
        ondulys = base / "seg2_data_june2024" / "ONDULYS"
        excel = base / "temp_and_humidity_data_june2024" / "USER-2024-06-26.xlsx"
        if ondulys.is_dir() and excel.is_file():
            return ondulys, excel
    # Default fallback for clear error reporting
    return (
        Path("data/Airbus/seg2_data_june2024/ONDULYS"),
        Path("data/Airbus/temp_and_humidity_data_june2024/USER-2024-06-26.xlsx"),
    )


def _zscore(x: np.ndarray) -> np.ndarray:
    """Standardize array to zero mean and unit variance."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.zeros_like(x)
    x = x - np.mean(x)
    s = np.std(x)
    return x / s if s > 0 else np.zeros_like(x)


def load_airbus_sg2_dataset(
    ondulys_dir: Path | str,
    excel_path: Path | str,
    n_sensors: int = 44,
    drop_first_samples: int = 99,
):
    """Load and preprocess Airbus SEG2 ultrasonic records and climate data."""
    ondulys_dir_path = Path(ondulys_dir)
    excel_path_file = Path(excel_path)
    if not ondulys_dir_path.exists():
        raise FileNotFoundError(
            f"No .sg2 directory found at {ondulys_dir_path}. "
            "Please download Dataset_CompositeTest_June2024.zip from Zenodo "
            "(record 19209079) and extract into data/Airbus/ or data/."
        )
    sg2_files = sorted(ondulys_dir_path.glob("*.sg2"))
    if not sg2_files:
        raise FileNotFoundError(
            f"No .sg2 files found in {ondulys_dir_path}. "
            "Please download Dataset_CompositeTest_June2024.zip from Zenodo "
            "(record 19209079) and extract into data/Airbus/ or data/."
        )
    if not excel_path_file.exists():
        raise FileNotFoundError(
            f"Missing climate chamber file {excel_path_file}. "
            "Please download Dataset_CompositeTest_June2024.zip from Zenodo "
            "(record 19209079) and extract into data/Airbus/ or data/."
        )

    rows = pd.read_excel(excel_path_file).to_dict("records")
    # ponytail: k=10, k+=5 means match rows [10, 15, 20, 25, ...];
    # compute direct indices instead of looping arithmetic
    row_indices = (np.arange(len(sg2_files)) * 5 + 10).tolist()

    S, y_all = [], []
    # ponytail: only use the slice we need, not the full range
    t = np.linspace(drop_first_samples * 1e-3 / 2000, 1e-3, 2000 - drop_first_samples)

    for i, sg2 in enumerate(sg2_files):
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*Many companies use custom defined SEG2 header variables.*",
                    category=UserWarning,
                )
                stream = obspy.read(str(sg2), format="SEG2")
        except Exception as e:
            print(f"Error reading {sg2.name}: {e}")
            continue

        data = np.array([tr.data for tr in stream], dtype=float).T
        if data.shape[0] <= drop_first_samples:
            continue

        entry = {"FILENAME": sg2.name, "data": data}
        if i < len(row_indices) and row_indices[i] < len(rows):
            entry["TEMPERATURE"] = rows[row_indices[i]].get("TEMP_MEAS", np.nan)
            entry["HUMIDITY"] = rows[row_indices[i]].get("RH_MEAS", np.nan)
            entry["TIME"] = rows[row_indices[i]].get("Date_Time", None)
        else:
            entry["TEMPERATURE"] = np.nan
            entry["HUMIDITY"] = np.nan
            entry["TIME"] = None

        data_norm = np.column_stack(
            [
                _zscore(data[drop_first_samples:, j])
                for j in range(min(n_sensors, data.shape[1]))
            ]
        )
        S.append(entry)
        y_all.append(data_norm)

    return S, y_all, t


def _moving_rms(x: np.ndarray, window_size: int) -> np.ndarray:
    kernel = np.ones(window_size, dtype=float) / window_size
    return np.sqrt(np.convolve(x**2, kernel, mode="same"))


def _build_plateau_indices(n_records: int) -> list[int]:
    # ponytail: pre-computed from loop pattern (first 10, then +12 each)
    idx = [0, 10, 22, 34, 46, 58, 70, 82, 94, 106, 118, 130]
    return [i for i in idx if i < n_records]


def _get_peak_window_sizes(peaks: int) -> tuple[int, int]:
    sizes = {1: (8, 2), 2: (8, 13)}
    if peaks not in sizes:
        raise ValueError(f"Invalid peaks: {peaks}")
    return sizes[peaks]


def _extract_plateau_signals(S: list[dict], y_all: list[np.ndarray]):
    ind = _build_plateau_indices(len(S))
    if not ind:
        raise ValueError("No valid plateau indices found.")

    tempinterval = np.asarray(
        [S[min(i + 3, len(S) - 1)]["TEMPERATURE"] for i in ind], dtype=float
    )
    y_all_extracted = [np.delete(y_all[i], [2, 3, 40, 41], axis=1) for i in ind]
    n_temp = len(y_all_extracted)
    n_sensor = y_all_extracted[0].shape[1]
    ys = [
        np.column_stack([y_all_extracted[i2][:, i1] for i2 in range(n_temp)])
        for i1 in range(n_sensor)
    ]
    return tempinterval, ys, n_temp, n_sensor


def _compute_full_cc(ys: list[np.ndarray], t: np.ndarray, n_temp: int):
    n_sensor = len(ys)
    CCfns = np.asarray([tc_cwi("getccns", y[:, 0], y).CC for y in ys])
    CCfs = np.zeros((n_sensor, n_temp))
    for i1, y in enumerate(ys):
        y0 = y[:, 0]
        e0 = 0.0
        for i2 in range(n_temp):
            out = tc_cwi("findeps", y0, y[:, i2], t, e0, 2)
            CCfs[i1, i2] = 1 - out.DC
            e0 = out.eps
    return CCfns, CCfs


def _compute_windowed_cc(
    ys: list[np.ndarray],
    t: np.ndarray,
    n_temp: int,
    samples1: int,
    samples2: int,
):
    n_sensor = len(ys)
    locs = np.zeros(n_sensor, dtype=int)
    win_inds = []
    for i1, y in enumerate(ys):
        y0 = y[:, 0]
        rms_energy = _moving_rms(y0, 20)
        noise_std = np.std(y0[: round(len(y0) * 0.3)])
        threshold = 3 * noise_std
        above = np.where(rms_energy > threshold)[0]
        idx_start = int(above[0]) if above.size else 0
        locs[i1] = idx_start
        i0 = max(0, idx_start - samples1)
        i1w = min(len(y0) - 1, idx_start + samples2)
        indw = np.arange(i0, i1w + 1)
        win_inds.append(indw)

    epsws = np.zeros((n_sensor, n_temp))
    CCws = np.zeros((n_sensor, n_temp))
    for i1, y in enumerate(ys):
        y0 = y[:, 0]
        e0 = 0.0
        for i2 in range(n_temp):
            out = tc_cwi("findeps", y0, y[:, i2], t, e0, 2, win_inds[i1])
            epsws[i1, i2] = out.eps
            CCws[i1, i2] = 1 - out.DC
            e0 = out.eps
    return epsws, CCws, locs


def _pick_temperature_indices(
    tempinterval: np.ndarray, T1: float, T2: float, tolerance: float = 0.5
) -> tuple[int, int]:
    idx1 = np.where(np.abs(tempinterval - T1) < tolerance)[0]
    idx2 = np.where(np.abs(tempinterval - T2) < tolerance)[0]
    if idx1.size == 0 or idx2.size == 0:
        raise ValueError("Could not match one or both temperatures.")
    return int(idx1[0]), int(idx2[0])


def main(peaks: int, t1: float, t2: float, sensor: int):
    print("\nAirbus SG2 Workflow")
    print(
        f"  Configuration     : peaks={peaks}, temp_range=[{t1}, {t2}]°C, sensor={sensor}"
    )

    try:
        samples1, samples2 = _get_peak_window_sizes(peaks)
    except ValueError as e:
        print(f"  Error: {e}")
        return

    ondulys_dir, excel_path = _resolve_airbus_paths()
    try:
        S, y_all, t = load_airbus_sg2_dataset(ondulys_dir, excel_path)
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"  Error: {e}")
        return

    # Known-bad Zenodo records; match by FILENAME, not position, so the drop survives a re-sorted or extended dataset
    bad = {
        "1_0_290_LUT_20240619_composite_monitor_02.sg2",
        "1_0_447_LUT_20240619_composite_monitor_02.sg2",
    }
    keep = [i for i, s in enumerate(S) if s["FILENAME"] not in bad]
    S = [S[i] for i in keep]
    y_all = [y_all[i] for i in keep]

    try:
        tempinterval, ys, n_temp, n_sensor = _extract_plateau_signals(S, y_all)
    except ValueError as e:
        print(f"  Error: {e}")
        return

    print(
        f"  Data shape        : {ys[0].shape[0]} samples × {n_temp} records × {n_sensor} sensors"
    )
    print(
        f"  Temperature range : {np.min(tempinterval):.1f} - {np.max(tempinterval):.1f} °C"
    )

    sensor_idx = sensor - 1
    if not (0 <= sensor_idx < n_sensor):
        print(f"  Error: Invalid sensor index. Valid range: 1-{n_sensor}")
        return

    print("  Running CC calculations (full + windowed) …")
    t0 = _time.time()
    CCfns, CCfs = _compute_full_cc(ys, t, n_temp)
    epsws, CCws, locs = _compute_windowed_cc(ys, t, n_temp, samples1, samples2)
    elapsed = _time.time() - t0
    print(f"  Done in {elapsed:.1f} s")

    try:
        idx1, idx2 = _pick_temperature_indices(tempinterval, t1, t2)
    except ValueError as e:
        print(f"  Error: {e}")
        return

    print(f"  Stretching sensor {sensor} …")
    y_sensor_stretched = np.column_stack(
        [
            tc_cwi("stretch", ys[sensor_idx][:, i2], t, epsws[sensor_idx, i2])
            for i2 in range(n_temp)
        ]
    )

    meanCC_full_nonstretched = np.mean(CCfns, axis=0)
    meanCC_full_stretched = np.mean(CCfs, axis=0)
    meanCC_windowed_stretched = np.mean(CCws, axis=0)

    plot_airbus_mean_cc(
        tempinterval=tempinterval,
        mean_cc_full_nonstretched=meanCC_full_nonstretched,
        mean_cc_full_stretched=meanCC_full_stretched,
        mean_cc_windowed_stretched=meanCC_windowed_stretched,
        out_path="airbus_mean_cc_vs_temperature.png",
    )
    print("  Saved plot        : airbus_mean_cc_vs_temperature.png")

    i0 = max(0, locs[sensor_idx] - samples1)
    i1w = min(len(t) - 1, locs[sensor_idx] + samples2)

    plot_airbus_compensated_signal(
        t=t,
        i0=i0,
        i1=i1w,
        signal_t1=ys[sensor_idx][:, idx1],
        signal_t2=ys[sensor_idx][:, idx2],
        compensated_signal_t2=y_sensor_stretched[:, idx2],
        T1=t1,
        T2=t2,
        sensor=sensor,
    )
    print(f"  Saved plot        : airbus_compensated_signal_s{sensor}.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Airbus SG2 temperature-compensation workflow."
    )
    parser.add_argument(
        "--peaks", type=int, default=1, help="1 or 2 peaks for CC calculation"
    )
    parser.add_argument("--temp1", type=float, default=20.0, help="First temperature")
    parser.add_argument("--temp2", type=float, default=60.0, help="Second temperature")
    parser.add_argument("--sensor", type=int, default=5, help="Sensor number (1-based)")
    parser.add_argument(
        "--smoke", action="store_true", help="Run in smoke-test mode (limited data)"
    )
    args = parser.parse_args()

    main(peaks=args.peaks, t1=args.temp1, t2=args.temp2, sensor=args.sensor)
