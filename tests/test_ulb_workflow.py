"""Tests for ULB workflow obstacle sensitivity metric and tc-cwi external package integration."""

from types import SimpleNamespace

import numpy as np
import pytest
import tc_cwi
from tc_cwi import Struct, stretch
from tc_cwi import tc_cwi as run_tc_cwi
from ulb_workflow import obstacle_sensitivity


class TestObstacleSensitivity:
    """Unit tests for the obstacle_sensitivity function in ulb_workflow."""

    def test_sensitivity_computation(self):
        ref_dc = [0.1, 0.2]
        obs_dc = [0.1, 0.15, 0.8, 0.85]
        result = obstacle_sensitivity(ref_dc, obs_dc)

        assert isinstance(result, (Struct, SimpleNamespace))
        assert result.insertion_index == 2
        assert result.sensitivity_ratio == pytest.approx(4.0)
        assert result.dc_at_insertion == pytest.approx(0.8)
        assert result.max_reference_dc == pytest.approx(0.2)

        # Verify alias fields
        assert result.obs_idx == 2
        assert result.sensitivity == pytest.approx(4.0)
        assert result.dc_obs == pytest.approx(0.8)
        assert result.dc_max_ref == pytest.approx(0.2)

        # Enforce attribute access over subscription
        with pytest.raises(TypeError):
            _ = result["insertion_index"]

    def test_sensitivity_with_multidimensional_numpy_inputs(self):
        ref_dc = np.array([[0.05, 0.1], [0.15, 0.2]])
        obs_dc = np.array([[0.1, 0.12], [0.9, 0.92]])
        result = obstacle_sensitivity(ref_dc, obs_dc)

        assert result.insertion_index == 2
        assert result.sensitivity_ratio == pytest.approx(0.9 / 0.2)
        assert result.dc_at_insertion == pytest.approx(0.9)
        assert result.max_reference_dc == pytest.approx(0.2)

    @pytest.mark.parametrize(
        ("ref_dc", "obs_dc"),
        [
            ([], [0.1, 0.2]),
            ([0.1], []),
            ([0.1], [0.2]),
            ([0.0], [0.1, 0.2]),
            ([-0.5], [0.1, 0.2]),
            ([-0.1, -0.2], [0.1, 0.2]),
            ([np.nan], [0.1, 0.2]),
            ([0.1], [0.2, np.inf]),
            ([np.inf], [0.1, 0.2]),
            ([0.1], [0.2, np.nan]),
        ],
    )
    def test_sensitivity_invalid_inputs(self, ref_dc, obs_dc):
        with pytest.raises(ValueError):
            obstacle_sensitivity(ref_dc, obs_dc)


class TestTcCwiPackageIntegration:
    """Integration tests verifying external tc-cwi package dispatch and behavior."""

    def test_tc_cwi_is_imported_from_site_packages(self):
        assert "site-packages" in tc_cwi.__file__
        assert not tc_cwi.__file__.startswith("src/")

    def test_tc_cwi_getccns_dispatch(self):
        y0 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        signals = np.column_stack((y0, y0 * 2))

        baseline = run_tc_cwi("getccns", y0, signals)
        assert isinstance(baseline, SimpleNamespace)
        np.testing.assert_allclose(baseline.CC, [1.0, 1.0])
        np.testing.assert_allclose(baseline.DC, [0.0, 0.0], atol=1e-12)

        # With sub-indices
        twin_ind = np.array([1, 2, 3])
        baseline_sub = run_tc_cwi("getccns", y0, signals, twin_ind)
        np.testing.assert_allclose(baseline_sub.CC, [1.0, 1.0])
        np.testing.assert_allclose(baseline_sub.DC, [0.0, 0.0], atol=1e-12)

    def test_tc_cwi_findeps_dispatch(self):
        t = np.linspace(0.0, 1.0, 100)
        y = np.sin(2 * np.pi * t)
        signals = np.column_stack((y, y))

        # Multi-signal findeps
        result_multi = run_tc_cwi("findeps", y, signals, t, 0.0, 2)
        assert isinstance(result_multi, SimpleNamespace)
        assert hasattr(result_multi, "EPSf")
        assert hasattr(result_multi, "DCsf")
        np.testing.assert_allclose(result_multi.DCsf, [0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(result_multi.EPSf, [0.0, 0.0], atol=1e-6)

        # Single-signal findeps
        single_out = run_tc_cwi("findeps", y, y, t, 0.0, 2)
        assert isinstance(single_out, SimpleNamespace)
        assert hasattr(single_out, "eps")
        assert hasattr(single_out, "DC")
        assert single_out.eps == pytest.approx(0.0, abs=1e-6)
        assert single_out.DC == pytest.approx(0.0, abs=1e-6)

    def test_tc_cwi_findeps_moving_average_dispatch(self):
        t = np.linspace(0.0, 1.0, 100)
        y = np.sin(2 * np.pi * t)
        signals = np.column_stack((y, y, y))
        twin_ind = np.arange(20, 80)

        result_ma = run_tc_cwi("findeps -ma", y, signals, t, 0.0, 2, twin_ind, 2)
        assert isinstance(result_ma, SimpleNamespace)
        assert hasattr(result_ma, "EPSma")
        assert hasattr(result_ma, "DCma")
        np.testing.assert_allclose(result_ma.DCma, [0.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(result_ma.EPSma, [0.0, 0.0, 0.0], atol=1e-6)

    def test_tc_cwi_stretch_and_recovery(self):
        t = np.linspace(0.0, 1.0, 200)
        y = np.sin(2 * np.pi * 5 * t)

        eps_applied = 0.01
        stretched = stretch(y, t, eps_applied)
        assert isinstance(stretched, np.ndarray)
        assert stretched.shape == y.shape

        # Time-stretching compensation returns -eps
        recovered = run_tc_cwi("findeps", y, stretched, t, 0.0, 2)
        assert recovered.eps == pytest.approx(-eps_applied, abs=1e-3)
        assert recovered.DC == pytest.approx(0.0, abs=1e-3)

    def test_tc_cwi_invalid_command_raises_error(self):
        with pytest.raises(ValueError, match="Unknown command"):
            run_tc_cwi("unsupported_command", np.array([1, 2]))
