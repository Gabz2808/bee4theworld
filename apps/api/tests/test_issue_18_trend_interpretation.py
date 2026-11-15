"""Pruebas para Issue #18: Backend 4/7 - Validar tendencia, cobertura e interpretación científica.

Verifica:
1. Longitud mínima de serie: 10 años para veredicto concluyente en clima; series menores retornan 'inconclusive'.
2. Tratamiento de autocorrelación serial (dependencia temporal):
   - Estimación sobre residuos sin tendencia (detrended residuals según Yue & Wang / USGS).
   - Aplicación de corrección de varianza (Modified Mann-Kendall) ante autocorrelación positiva.
   - Declaración de 'inconclusive' ante autocorrelación severa (r1 >= 0.60).
3. Cobertura espacial mínima: Exclusión de años del acumulado anual si algún mes presenta cobertura < 70%.
4. Rigor en la narrativa e interpretación científica:
   - Jamás atribuir p >= 0.05 a "causas naturales" ni afirmar ausencia de cambio.
   - Pautas de prudencia que documentan la transición instrumental de sensores (TRMM a GPM en 2014).
5. Compatibilidad total con el contrato v1 del cliente (api-v1.ts).
"""
from __future__ import annotations

import unittest
from datetime import date

import numpy as np
import pandas as pd
from app.models.exploration import (
    AnnualPrecipitation,
    DateRange,
    EffectiveSelection,
    ExplorationMetadata,
    TrendAnalysis,
)
from app.services.interpretation_service import generate_interpretation
from app.services.precipitation_processing import (
    QUALITY_OK,
    QUALITY_PARTIAL_COVERAGE,
    aggregate_annual_precipitation,
)
from app.services.trend_analysis import (
    DEFAULT_MIN_YEARS_FOR_TREND,
    analyze_annual_trend,
    calculate_lag1_autocorrelation,
    mann_kendall_test,
)


class Issue18TrendInterpretationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = ExplorationMetadata(
            variable_name="Precipitación mensual estimada",
            source="NASA GES DISC / Giovanni",
            dataset="GPM_3IMERGM.07",
            unit="mm/month",
            spatial_resolution="0.1° (~10 km); promedio ponderado espacial",
            selection=EffectiveSelection(
                region_id="costa-rica-continental",
                region_name="Costa Rica Continental",
                boundary_source="Instituto Geográfico Nacional (IGN) Costa Rica / WDC Cartography",
                boundary_version="2024",
                requested_period=DateRange(start=date(2010, 1, 1), end=date(2023, 12, 31)),
                effective_period=DateRange(start=date(2010, 1, 1), end=date(2023, 12, 31)),
            ),
        )

    # -------------------------------------------------------------------------
    # Criterio 1: Longitud de Serie y Representatividad Climática
    # -------------------------------------------------------------------------
    def test_default_min_years_is_ten(self) -> None:
        """El umbral predeterminado de representatividad climática es de al menos 10 años."""
        self.assertEqual(DEFAULT_MIN_YEARS_FOR_TREND, 10)

    def test_insufficient_years_returns_inconclusive(self) -> None:
        """Una serie con menos de 10 años (ej. 5 o 6 años) retorna status 'inconclusive'."""
        annual_data = [
            AnnualPrecipitation(year=2019 + i, annual_precipitation_mm=2500.0 + i * 20.0, months_reported=12)
            for i in range(5)
        ]
        result = analyze_annual_trend(annual_data)
        self.assertEqual(result.status, "inconclusive")
        self.assertIsNone(result.slope)
        self.assertIsNone(result.p_value)
        self.assertIsNotNone(result.methodological_note)
        self.assertIn("al menos 10 años", result.methodological_note)

    def test_ten_complete_years_evaluates_conclusive_trend(self) -> None:
        """Una serie con 10 años completos sin autocorrelación anómala evalúa tendencia 'conclusive'."""
        annual_data = [
            AnnualPrecipitation(year=2010 + i, annual_precipitation_mm=2000.0 + i * 40.0, months_reported=12)
            for i in range(10)
        ]
        result = analyze_annual_trend(annual_data)
        self.assertEqual(result.status, "conclusive")
        self.assertIsNotNone(result.slope)
        self.assertIsNotNone(result.p_value)
        self.assertTrue(result.is_significant)
        self.assertEqual(result.slope_unit, "mm/year")

    # -------------------------------------------------------------------------
    # Criterio 2: Autocorrelación Serial y Dependencia Temporal (USGS)
    # -------------------------------------------------------------------------
    def test_detrended_autocorrelation_isolates_residuals(self) -> None:
        """La autocorrelación lag-1 sobre una serie con tendencia pura es cero al evaluar residuos."""
        x = np.arange(10, dtype=float)
        y = 100.0 + 15.0 * x  # Tendencia lineal pura
        r1_residual = calculate_lag1_autocorrelation(y, x=x, slope=15.0)
        self.assertAlmostEqual(r1_residual, 0.0, places=5)

    def test_severe_autocorrelation_returns_inconclusive(self) -> None:
        """Una serie multianual con fuerte dependencia temporal residual (r1 >= 0.60) se declara 'inconclusive'."""
        # Serie con oscilación cíclica suave (14 años) donde el residuo tiene fuerte persistencia (r1 >= 0.60)
        years = np.arange(2010, 2024, dtype=float)
        t = np.arange(len(years))
        y = 2000.0 + 200.0 * np.sin(np.pi * t / (len(t) - 1))
        annual_data = [
            AnnualPrecipitation(year=int(yr), annual_precipitation_mm=round(float(val), 2), months_reported=12)
            for yr, val in zip(years, y)
        ]
        result = analyze_annual_trend(annual_data)
        # Debe marcarse como inconcluso debido a la fuerte dependencia temporal residual que invalida el supuesto de independencia
        self.assertEqual(result.status, "inconclusive")
        self.assertIn("dependencia temporal serial", result.summary)
        self.assertIn("USGS", result.methodological_note)

    def test_modified_mann_kendall_adjusts_variance_for_positive_autocorrelation(self) -> None:
        """Cuando se detecta autocorrelación positiva estadísticamente significativa, la varianza de Mann-Kendall es ajustada hacia arriba."""
        y = np.array([10.0, 12.0, 11.0, 14.0, 13.0, 16.0, 15.0, 18.0, 17.0, 20.0], dtype=float)
        s, var_unadj, _p_unadj, _ = mann_kendall_test(y, apply_autocorrelation_correction=False)
        s_adj, var_adj, _p_adj, _ = mann_kendall_test(y, apply_autocorrelation_correction=True, r1=0.55)
        self.assertEqual(s, s_adj)
        # La varianza ajustada debe ser mayor que la no ajustada
        self.assertGreater(var_adj, var_unadj)

    # -------------------------------------------------------------------------
    # Criterio 3: Cobertura Espacial Mínima Mensual para Totales Anuales
    # -------------------------------------------------------------------------
    def test_annual_accumulation_omits_year_when_month_has_low_spatial_coverage(self) -> None:
        """Si un mes de un año calendario tiene cobertura espacial < 70%, el año es excluido del acumulado anual."""
        dates = pd.date_range("2023-01-01", periods=12, freq="MS")
        # Mes 5 (mayo) tiene solo 40% de cobertura espacial
        coverages = [1.0] * 12
        coverages[4] = 0.40
        flags = [QUALITY_OK] * 12
        flags[4] = QUALITY_PARTIAL_COVERAGE

        frame = pd.DataFrame(
            {
                "precipitation_mm": [100.0] * 12,
                "coverage_fraction": coverages,
                "quality_flag": flags,
            },
            index=dates,
        )
        annual = aggregate_annual_precipitation(frame, min_monthly_coverage=0.70)
        # El año 2023 no debe incluirse porque mayo no cumple el umbral mínimo
        self.assertTrue(annual.empty, "El año con un mes de cobertura < 70% debe ser excluido")

    def test_annual_accumulation_accepts_year_when_all_months_meet_coverage_threshold(self) -> None:
        """Si todos los meses tienen cobertura >= 70%, el año se acumula correctamente."""
        dates = pd.date_range("2023-01-01", periods=12, freq="MS")
        coverages = [1.0] * 12
        coverages[6] = 0.75  # 75% >= 70%

        frame = pd.DataFrame(
            {
                "precipitation_mm": [100.0] * 12,
                "coverage_fraction": coverages,
                "quality_flag": [QUALITY_OK] * 12,
            },
            index=dates,
        )
        annual = aggregate_annual_precipitation(frame, min_monthly_coverage=0.70)
        self.assertEqual(len(annual), 1)
        self.assertEqual(annual.loc[2023, "annual_precipitation_mm"], 1200.0)

    # -------------------------------------------------------------------------
    # Criterio 4: Narrativa, Incertidumbre e Interpretación Científica Prudente
    # -------------------------------------------------------------------------
    def test_non_significant_trend_never_claims_natural_causes(self) -> None:
        """Cuando p >= 0.05, el sistema NUNCA afirma que la variación se deba a 'causas naturales' ni prueba ausencia."""
        annual_data = [
            AnnualPrecipitation(year=2010 + i, annual_precipitation_mm=2500.0 + (i % 3) * 10.0, months_reported=12)
            for i in range(10)
        ]
        trend = analyze_annual_trend(annual_data)
        self.assertEqual(trend.status, "conclusive")
        self.assertFalse(trend.is_significant)
        self.assertGreaterEqual(trend.p_value, 0.05)

        # Verificación en summary del TrendAnalysis
        self.assertNotIn("causa natural", trend.summary.lower())
        self.assertNotIn("causas naturales", trend.summary.lower())
        self.assertNotIn("variabilidad natural", trend.summary.lower())
        self.assertIn("no se rechaza la hipótesis nula", trend.summary.lower())

        # Verificación en la interpretación en lenguaje natural
        dates = pd.date_range("2010-01-01", periods=120, freq="MS")
        frame = pd.DataFrame(
            {
                "precipitation_mm": [200.0] * 120,
                "coverage_fraction": [1.0] * 120,
                "quality_flag": [QUALITY_OK] * 120,
                "anomaly_mm": [0.0] * 120,
            },
            index=dates,
        )
        interp = generate_interpretation(self.metadata, trend, frame, annual_data)
        verdict = interp.trend_verdict_plain_language.lower()
        self.assertNotIn("fluctuación natural", verdict)
        self.assertNotIn("causas naturales", verdict)
        self.assertIn("no debe interpretarse como prueba de que no haya cambio", verdict)

    def test_prudence_guidelines_documents_sensor_transition_in_2014(self) -> None:
        """Las pautas de prudencia documentan explícitamente la transición de sensores de TRMM a GPM en 2014."""
        trend = TrendAnalysis(
            status="inconclusive",
            method="Sen's slope estimator & Mann-Kendall test",
            summary="Serie insuficiente.",
            methodological_note="Se requieren al menos 10 años.",
        )
        dates = pd.date_range("2023-01-01", periods=12, freq="MS")
        frame = pd.DataFrame(
            {
                "precipitation_mm": [100.0] * 12,
                "coverage_fraction": [1.0] * 12,
                "quality_flag": [QUALITY_OK] * 12,
                "anomaly_mm": [0.0] * 12,
            },
            index=dates,
        )
        annual = [AnnualPrecipitation(year=2023, annual_precipitation_mm=1200.0, months_reported=12)]
        interp = generate_interpretation(self.metadata, trend, frame, annual)

        sensor_warning = next((g for g in interp.prudence_guidelines if "TRMM" in g and "2014" in g), None)
        self.assertIsNotNone(sensor_warning, "Debe existir una advertencia explícita sobre la transición instrumental de 2014")
        self.assertIn("GPM Core Observatory", sensor_warning)


if __name__ == "__main__":
    unittest.main()
