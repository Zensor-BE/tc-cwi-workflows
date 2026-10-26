"""Tests for Airbus workflow helpers and synthetic signal CWI stretching."""

from pathlib import Path

import numpy as np
import pytest
from airbus_workflow import (
    _build_plateau_indices,
    _get_peak_window_sizes,
    _moving_rms,
    _resolve_airbus_paths,
    _zscore,
)
from tc_cwi import tc_cwi


class TestZscore:
    """Unit tests for the _zscore normalization helper."""

    def test_zscore_standard_array(self):
        rng = np.random.default_rng(42)
        x = rng.normal(loc=10.0, scale=3.0, size=500)
        z = _zscore(x)

        assert z.shape == x.shape
        assert np.isclose(np.mean(z), 0.0, atol=1e-12)
        assert np.isclose(np.std(z), 1.0, atol=1e-12)

    def test_zscore_deterministic_values(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        z = _zscore(x)
        expected = (x - 3.0) / np.sqrt(2.0)
        np.testing.assert_allclose(z, expected, atol=1e-12)

    def test_zscore_constant_array(self):
        x = np.full(100, 42.0)
        z = _zscore(x)
        assert z.shape == x.shape
        np.testing.assert_allclose(z, np.zeros_like(x))

    def test_zscore_zero_variance_zeros(self):
        x = np.zeros(50)
        z = _zscore(x)
        assert z.shape == x.shape
        np.testing.assert_allclose(z, np.zeros_like(x))

    def test_zscore_empty_array(self):
        x = np.array([])
        z = _zscore(x)
        assert z.shape == (0,)
        assert isinstance(z, np.ndarray)


class TestAirbusWorkflowHelpers:
    """Unit tests for internal Airbus workflow helpers."""

    def test_build_plateau_indices(self):
        idx_full = _build_plateau_indices(150)
        assert idx_full == [0, 10, 22, 34, 46, 58, 70, 82, 94, 106, 118, 130]

        idx_short = _build_plateau_indices(25)
        assert idx_short == [0, 10, 22]

        idx_empty = _build_plateau_indices(0)
        assert idx_empty == []

    def test_get_peak_window_sizes(self):
        assert _get_peak_window_sizes(1) == (8, 2)
        assert _get_peak_window_sizes(2) == (8, 13)

        with pytest.raises(ValueError, match="Invalid peaks: 3"):
            _get_peak_window_sizes(3)

    def test_moving_rms(self):
        x = np.array([0.0, 0.0, 2.0, 2.0, 0.0, 0.0])
        rms = _moving_rms(x, window_size=3)
        assert rms.shape == x.shape
        assert np.all(rms >= 0.0)

    def test_resolve_airbus_paths(self):
        ondulys, excel = _resolve_airbus_paths()
        assert isinstance(ondulys, Path)
        assert isinstance(excel, Path)
        assert "ONDULYS" in str(ondulys)
        assert "USER-2024-06-26.xlsx" in str(excel)


class TestSyntheticSignalCWI:
    """Integration tests verifying tc_cwi baseline correlation and signal stretching."""

    def test_baseline_correlation_with_synthetic_signals(self):
        t = np.linspace(0.0, 1.0, 500)
        y0 = np.sin(2 * np.pi * 10 * t) + 0.5 * np.cos(2 * np.pi * 25 * t)

        # Build signals: identical, scaled, and orthogonal/shifted
        y_identical = y0.copy()
        y_scaled = y0 * 3.5
        y_shifted = np.sin(2 * np.pi * 10 * t + np.pi / 2)

        signals = np.column_stack((y_identical, y_scaled, y_shifted))
        out = tc_cwi("getccns", y0, signals)

        assert hasattr(out, "CC")
        assert hasattr(out, "DC")
        # Identical and scaled signals should have correlation 1.0
        assert out.CC[0] == pytest.approx(1.0, abs=1e-10)
        assert out.CC[1] == pytest.approx(1.0, abs=1e-10)
        # Shifted signal has distinct decorrelation
        assert out.CC[2] < 0.99
        np.testing.assert_allclose(out.DC, 1.0 - out.CC, atol=1e-12)

    def test_synthetic_signal_stretching_compensation(self):
        t = np.linspace(0.0, 1.0, 500)
        # Broadband synthetic signal
        y0 = np.sin(2 * np.pi * 15 * t) * np.exp(-((t - 0.5) ** 2) / 0.05)

        eps_applied = 0.008
        y_stretched = tc_cwi("stretch", y0, t, eps_applied)

        # Baseline correlation before stretch compensation should be degraded
        baseline = tc_cwi("getccns", y0, y_stretched)
        assert baseline.CC[0] < 0.99

        # Time stretching optimization should recover -eps
        twin_ind = np.arange(50, 450)
        recovered = tc_cwi("findeps", y0, y_stretched, t, 0.0, 2, twin_ind)

        assert recovered.eps == pytest.approx(-eps_applied, abs=1e-3)
        assert recovered.DC == pytest.approx(0.0, abs=1e-3)
