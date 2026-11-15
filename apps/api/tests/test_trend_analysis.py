import unittest

import numpy as np
import pandas as pd
from app.models.exploration import AnnualPrecipitation
from app.services.trend_analysis import (
    analyze_annual_trend,
    calculate_climatology_and_anomalies,
    calculate_ols_trend,
    calculate_theil_sen_slope,
    mann_kendall_test,
)
try:
    from scipy.stats import kendalltau, norm, theilslopes
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class TrendAnalysisServiceTests(unittest.TestCase):
    @unittest.skipUnless(HAS_SCIPY, "scipy no está disponible en este entorno")
    def test_unadjusted_trend_against_scipy_on_known_series(self) -> None:
        # Datos sintéticos; el contraste no valida la corrección por autocorrelación.
        cases = (
            [1, 2, 4, 5, 5, 8, 9, 9, 12, 14, 14, 16],
            [18, 16, 17, 14, 13, 13, 11, 8, 7, 6, 4, 3],
            [4, 9, 3, 7, 10, 2, 8, 5, 6, 1, 8, 4],
        )
        for values in cases:
            with self.subTest(values=values):
                y = np.asarray(values, dtype=float)
                x = np.arange(len(y), dtype=float)
                self.assertAlmostEqual(calculate_theil_sen_slope(x, y), theilslopes(y, x).slope)
                _, variance, p_value, _ = mann_kendall_test(y, apply_autocorrelation_correction=False)
                # SciPy usa la aproximación asintótica sin corrección de continuidad;
                # se añade la corrección de una unidad de S para hacerla comparable.
                scipy_p = kendalltau(x, y, method="asymptotic").pvalue
                z = norm.isf(scipy_p / 2)
                expected_p = 2 * norm.sf(max(0.0, z - 1 / np.sqrt(variance)))
                self.assertAlmostEqual(p_value, expected_p, places=12)

    def test_calculate_climatology_and_anomalies(self) -> None:
        # Crear 2 años de datos sintéticos mensuales (2021-2022)
        dates = pd.date_range("2021-01-01", periods=24, freq="MS")
        # Año 1: enero 100, febrero 200...
        # Año 2: enero 120, febrero 180...
        # Para 2021: [100, 200, 100, 200...]
        # Para 2022: [120, 180, 120, 180...]
        values = [100.0, 200.0] * 6 + [120.0, 180.0] * 6
        frame = pd.DataFrame(
            {
                "precipitation_mm": values,
                "coverage_fraction": 1.0,
                "quality_flag": "ok",
            },
            index=dates,
        )

        result = calculate_climatology_and_anomalies(frame)

        # La media de enero debe ser (100 + 120)/2 = 110.0
        self.assertAlmostEqual(result.loc["2021-01-01", "climatology_mean_mm"], 110.0)
        # Anomalía 2021-01: 100 - 110 = -10.0
        self.assertAlmostEqual(result.loc["2021-01-01", "anomaly_mm"], -10.0)
        # Anomalía 2022-01: 120 - 110 = +10.0
        self.assertAlmostEqual(result.loc["2022-01-01", "anomaly_mm"], 10.0)

    def test_climatology_preserves_nan_for_missing_months(self) -> None:
        dates = pd.date_range("2021-01-01", periods=12, freq="MS")
        values = [100.0] * 11 + [np.nan]
        frame = pd.DataFrame(
            {
                "precipitation_mm": values,
                "coverage_fraction": 1.0,
                "quality_flag": "ok",
            },
            index=dates,
        )

        result = calculate_climatology_and_anomalies(frame)
        self.assertTrue(np.isnan(result.loc["2021-12-01", "anomaly_mm"]))

    def test_theil_sen_slope_with_linear_data(self) -> None:
        x = np.array([2000, 2001, 2002, 2003, 2004, 2005], dtype=float)
        # y = 5*x + 10
        y = 5.0 * x + 10.0
        slope = calculate_theil_sen_slope(x, y)
        self.assertAlmostEqual(slope, 5.0)

    def test_theil_sen_slope_robust_to_single_outlier(self) -> None:
        x = np.array([1, 2, 3, 4, 5, 6, 7], dtype=float)
        y = np.array([10, 20, 30, 40, 50, 60, 70], dtype=float)  # pendiente pura = 10
        # Añadir un outlier extremo en el centro
        y_outlier = y.copy()
        y_outlier[3] = 999.0  # outlier severo
        slope = calculate_theil_sen_slope(x, y_outlier)
        # La pendiente de Sen debe seguir siendo 10.0 por ser la mediana
        self.assertAlmostEqual(slope, 10.0)

    def test_ols_trend(self) -> None:
        x = np.array([1, 2, 3, 4, 5], dtype=float)
        y = np.array([2, 4, 6, 8, 10], dtype=float)
        slope, intercept, r2 = calculate_ols_trend(x, y)
        self.assertAlmostEqual(slope, 2.0)
        self.assertAlmostEqual(intercept, 0.0)
        self.assertAlmostEqual(r2, 1.0)

    def test_mann_kendall_test_significant_increasing(self) -> None:
        # Serie creciente estricta
        y = np.array([10, 15, 20, 25, 30, 35, 40, 45, 50, 55], dtype=float)
        s, _var_s, p_val, is_sig = mann_kendall_test(y, alpha=0.05)
        self.assertGreater(s, 0)
        self.assertLess(p_val, 0.05)
        self.assertTrue(is_sig)

    def test_mann_kendall_test_non_significant_flat(self) -> None:
        # Serie oscilante sin tendencia
        y = np.array([100, 105, 98, 102, 99, 101, 100, 97, 103, 100], dtype=float)
        _, _, p_val, is_sig = mann_kendall_test(y, alpha=0.05)
        self.assertGreaterEqual(p_val, 0.05)
        self.assertFalse(is_sig)

    def test_analyze_annual_trend_inconclusive_when_insufficient_years(self) -> None:
        # Solo 3 años (< min_years=5)
        annual_data = [
            AnnualPrecipitation(year=2021, annual_precipitation_mm=2500.0, months_reported=12),
            AnnualPrecipitation(year=2022, annual_precipitation_mm=2600.0, months_reported=12),
            AnnualPrecipitation(year=2023, annual_precipitation_mm=2700.0, months_reported=12),
        ]
        result = analyze_annual_trend(annual_data, min_years=5)

        self.assertEqual(result.status, "inconclusive")
        self.assertIsNone(result.slope)
        self.assertIsNone(result.p_value)
        self.assertIsNotNone(result.methodological_note)
        self.assertIn("al menos 5 años", result.methodological_note)

    def test_analyze_annual_trend_conclusive_significant(self) -> None:
        # 10 años con incremento sostenido
        annual_data = [
            AnnualPrecipitation(
                year=2010 + i,
                annual_precipitation_mm=2000.0 + i * 50.0,
                months_reported=12,
            )
            for i in range(10)
        ]
        result = analyze_annual_trend(annual_data, min_years=5, confidence_level=0.95)

        self.assertEqual(result.status, "conclusive")
        self.assertAlmostEqual(result.slope, 50.0)
        self.assertEqual(result.slope_unit, "mm/year")
        self.assertLess(result.p_value, 0.05)
        self.assertTrue(result.is_significant)
        self.assertIsNone(result.methodological_note)
        self.assertIn("Se detecta una tendencia positiva", result.summary)

    def test_analyze_annual_trend_conclusive_non_significant(self) -> None:
        # 8 años oscilantes alrededor de 2500 mm
        annual_data = [
            AnnualPrecipitation(year=2015, annual_precipitation_mm=2510.0, months_reported=12),
            AnnualPrecipitation(year=2016, annual_precipitation_mm=2490.0, months_reported=12),
            AnnualPrecipitation(year=2017, annual_precipitation_mm=2520.0, months_reported=12),
            AnnualPrecipitation(year=2018, annual_precipitation_mm=2480.0, months_reported=12),
            AnnualPrecipitation(year=2019, annual_precipitation_mm=2505.0, months_reported=12),
            AnnualPrecipitation(year=2020, annual_precipitation_mm=2495.0, months_reported=12),
            AnnualPrecipitation(year=2021, annual_precipitation_mm=2515.0, months_reported=12),
            AnnualPrecipitation(year=2022, annual_precipitation_mm=2490.0, months_reported=12),
        ]
        result = analyze_annual_trend(annual_data, min_years=5, confidence_level=0.95)

        self.assertEqual(result.status, "conclusive")
        self.assertFalse(result.is_significant)
        self.assertGreaterEqual(result.p_value, 0.05)
        self.assertIsNone(result.methodological_note)
        self.assertIn("No se detecta una tendencia estadísticamente significativa", result.summary)


if __name__ == "__main__":
    unittest.main()
