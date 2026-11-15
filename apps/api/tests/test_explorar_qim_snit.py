"""Codex (Manuel): comprobaciones sintéticas del resumen exploratorio QIm."""
import numpy as np
import pytest

from scripts.explorar_qim_snit import summarize


def test_weighted_quantiles_classes_and_distinct_masks():
    result = summarize([1, 3, 10, np.nan], [0, 2, 3, 4], [1, 2, 1, 2], 6)
    assert result["coverage_precip"] == 1
    assert result["coverage_qim"] == 4 / 6
    assert result["coverage_joint"] == 4 / 6
    assert (result["q10"], result["q50"], result["q90"]) == (1, 3, 10)
    assert result["area_classes"] == [0.25, 0.5, 0.25]


def test_absence_is_not_zero():
    result = summarize([1, 2], [np.nan, np.nan], [1, 1], 2)
    assert result["coverage_joint"] == 0
    assert result["q50"] is None and result["area_classes"] is None


def test_rejects_overlapping_grid_weights():
    with pytest.raises(ValueError, match="excede"):
        summarize([1, 2], [1, 2], [1, 1], 1)
