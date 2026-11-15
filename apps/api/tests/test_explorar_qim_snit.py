"""Codex (Manuel): comprobaciones sintéticas del resumen exploratorio QIm."""
import unittest
import numpy as np

from scripts.explorar_qim_snit import summarize


class TestExplorarQImSnit(unittest.TestCase):
    def test_weighted_quantiles_classes_and_distinct_masks(self):
        result = summarize([1, 3, 10, np.nan], [0, 2, 3, 4], [1, 2, 1, 2], 6)
        self.assertEqual(result["coverage_precip"], 1)
        self.assertEqual(result["coverage_qim"], 4 / 6)
        self.assertEqual(result["coverage_joint"], 4 / 6)
        self.assertEqual((result["q10"], result["q50"], result["q90"]), (1, 3, 10))
        self.assertEqual(result["area_classes"], [0.25, 0.5, 0.25])

    def test_absence_is_not_zero(self):
        result = summarize([1, 2], [np.nan, np.nan], [1, 1], 2)
        self.assertEqual(result["coverage_joint"], 0)
        self.assertIsNone(result["q50"])
        self.assertIsNone(result["area_classes"])



def test_rejects_overlapping_grid_weights():
    with pytest.raises(ValueError, match="excede"):
        summarize([1, 2], [1, 2], [1, 1], 1)
