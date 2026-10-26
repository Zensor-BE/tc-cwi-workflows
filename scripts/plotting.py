from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PLOTS_DIR = Path("figures")
plt.rcParams.update(
    {
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "figure.figsize": (11, 7.2),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "legend.fontsize": 10,
        "lines.linewidth": 1.8,
    }
)


def _output_path(out_path: str) -> Path:
    out = Path(out_path)
    if out.is_absolute() or out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    return PLOTS_DIR / out


def _normalize_for_plot(x: np.ndarray) -> np.ndarray:
    m = np.max(np.abs(x))
    return x / m if m > 0 else x


def plot_ulb_results(
    sig_idx: np.ndarray,
    temperature: np.ndarray,
    epsf: np.ndarray,
    cc_no_stretch: np.ndarray,
    cc_stretched: np.ndarray,
    out_path: str = "ulb_results.png",
) -> None:
    fig, axes = plt.subplots(3, 1, sharex=True)

    axes[0].plot(sig_idx, temperature, color="darkorange", lw=2, label="Temperature")
    axes[0].set_ylabel("Temperature (°C)")
    axes[0].set_title("Time stretching on Dataset 1 (no obstacle)")
    axes[0].legend(loc="right")

    axes[1].plot(
        sig_idx,
        -epsf * 100,
        color="steelblue",
        lw=2,
        label="Optimal stretch factor (ε)",
    )
    axes[1].set_ylabel("Rel. velocity change (%)")
    axes[1].legend(loc="upper right")

    axes[2].plot(sig_idx, cc_no_stretch, color="k", lw=2, label="Without stretching")
    axes[2].plot(
        sig_idx, cc_stretched, color="seagreen", lw=2, label="After time stretching"
    )
    axes[2].set_ylim([0, 1.005])
    axes[2].set_ylabel("Correlation coeff. CC")
    axes[2].legend(loc="right")

    fig.tight_layout()
    fig.savefig(_output_path(out_path))
    plt.close(fig)


def plot_ulb_dc_sensitivity(
    sig_idx: np.ndarray,
    dc_fixed: np.ndarray,
    dc_ma: np.ndarray,
    ma_window: int,
    obs_idx_fixed: int,
    obs_idx_ma: int,
    sensitivity_fixed: float,
    sensitivity_ma: float,
    out_path: str = "ulb_dataset2_dc_sensitivity.png",
) -> None:
    """Plot DC evolution and obstacle detection sensitivity.

    Top: DC values over signal index for fixed and MA methods.
    Bottom: Sensitivity ratio = DCobs / max(DCw/o obs)
    """
    fig, axes = plt.subplots(2, 1, figsize=(11, 8))
    methods = ["Time streching", f"Time streching + MA ref\n(n={ma_window})"]

    # Top: DC evolution
    ax = axes[0]
    ax.plot(sig_idx, dc_fixed * 100, color="steelblue", lw=2, label=methods[0])
    ax.plot(sig_idx, dc_ma * 100, color="tomato", lw=2, label=methods[1])
    ax.axvline(
        obs_idx_fixed, color="steelblue", linestyle=":", alpha=0.6, linewidth=1.5
    )
    ax.axvline(obs_idx_ma, color="tomato", linestyle=":", alpha=0.6, linewidth=1.5)
    ax.set_ylabel("DC (%)", fontsize=12)
    ax.set_title(
        "Dataset 2 — DC evolution: Fixed vs Moving-Average Reference", fontsize=13
    )
    ax.legend(loc="best", framealpha=0.9, fontsize=11)
    ax.grid(True, alpha=0.3)

    # Bottom: Obstacle detection sensitivity
    ax = axes[1]
    sensitivities = [sensitivity_fixed, sensitivity_ma]
    colors = ["steelblue", "tomato"]
    bars = ax.bar(
        methods,
        sensitivities,
        color=colors,
        alpha=0.7,
        edgecolor="black",
        linewidth=1.5,
    )
    ax.set_ylabel("Sensitivity ratio", fontsize=12)
    ax.set_ylim([0, max(sensitivities) * 1.2])
    ax.axhline(1.0, color="k", linestyle="--", linewidth=1, label="Detection threshold")
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, alpha=0.3, axis="y")

    # Add value labels on bars
    for bar, sens in zip(bars, sensitivities, strict=True):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 0.05,
            f"{sens:.2f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    fig.tight_layout(pad=1.0)
    fig.savefig(_output_path(out_path))
    plt.close(fig)


def plot_airbus_mean_cc(
    tempinterval: np.ndarray,
    mean_cc_full_nonstretched: np.ndarray,
    mean_cc_full_stretched: np.ndarray,
    mean_cc_windowed_stretched: np.ndarray,
    out_path: str = "airbus_mean_cc_vs_temperature.png",
) -> None:
    fig, ax = plt.subplots()
    ax.plot(tempinterval, mean_cc_full_nonstretched, "-o", linewidth=1.5)
    ax.plot(tempinterval, mean_cc_full_stretched, "-s", linewidth=1.5)
    ax.plot(tempinterval, mean_cc_windowed_stretched, "-^", linewidth=1.5)
    ax.set_xlabel("Temperature (°C)")
    ax.set_xticks(np.arange(20, 71, 5))
    ax.set_ylabel("CC")
    ax.legend(
        [
            "CC on full signal without time stretching",
            "CC on full signal with time stretching",
            "CC on ToF region with time stretching",
        ],
        loc="lower left",
    )
    ax.set_title("Mean CC trends for different signal configurations")
    fig.savefig(_output_path(out_path))
    plt.close(fig)


def plot_airbus_compensated_signal(
    t: np.ndarray,
    i0: int,
    i1: int,
    signal_t1: np.ndarray,
    signal_t2: np.ndarray,
    compensated_signal_t2: np.ndarray,
    T1: float,
    T2: float,
    sensor: int,
) -> None:
    fig, ax = plt.subplots()
    ax.plot(t, _normalize_for_plot(signal_t1), "b", linewidth=1.5)
    ax.plot(t, _normalize_for_plot(signal_t2), "r", linewidth=1.5)
    ax.plot(
        t,
        _normalize_for_plot(compensated_signal_t2),
        color=(0.9290, 0.6940, 0.1250),
        linewidth=1,
        ls="--",
    )
    ax.fill_between(t[i0:i1], -1, 1, color="b", alpha=0.2)
    ax.legend(
        [
            f"Signal at {T1:.0f} ºC",
            f"Signal at {T2:.0f} ºC",
            "Compensated signal",
            "CC calculation range",
        ]
    )
    ax.set_title(f"Sensor {sensor}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(1e-4, 4e-4)
    ax.ticklabel_format(axis="x", style="sci", scilimits=(-4, -4), useMathText=True)
    fig.savefig(_output_path(f"airbus_sensor_{sensor}.png"))
    plt.close(fig)
