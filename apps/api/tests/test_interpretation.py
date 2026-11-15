import unittest
from datetime import date

import pandas as pd
from app.models.exploration import (
    AnnualPrecipitation,
    DateRange,
    EffectiveSelection,
    ExplorationMetadata,
    TrendAnalysis,
)
from app.services.interpretation_service import (
    format_month_label,
    generate_interpretation,
)


class InterpretationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = ExplorationMetadata(
            variable_name="Precipitación mensual estimada",
            source="NASA GES DISC / Giovanni",
            dataset="GPM_3IMERGM.07",
            unit="mm/month",
            spatial_resolution="0.1° (~10 km)",
            selection=EffectiveSelection(
                region_id="costa-rica-continental",
                region_name="Costa Rica Continental",
                boundary_source="IGN",
                boundary_version="2024",
                requested_period=DateRange(start=date(2023, 1, 1), end=date(2023, 12, 31)),
                effective_period=DateRange(start=date(2023, 1, 1), end=date(2023, 12, 31)),
            ),
        )

    def test_format_month_label(self) -> None:
        self.assertEqual(format_month_label(1, 2023), "enero de 2023")
        self.assertEqual(format_month_label(12), "diciembre")

    def test_interpretation_inconclusive_few_years(self) -> None:
        # 1 año (2023)
        dates = pd.date_range("2023-01-01", periods=12, freq="MS")
        frame = pd.DataFrame(
            {
                "precipitation_mm": [50.0, 40.0, 30.0, 80.0, 200.0, 250.0, 220.0, 210.0, 260.0, 270.0, 180.0, 70.0],
                "coverage_fraction": [1.0] * 12,
                "quality_flag": ["ok"] * 12,
                "anomaly_mm": [0.0] * 12,
            },
            index=dates,
        )
        annual = [AnnualPrecipitation(year=2023, annual_precipitation_mm=1860.0, months_reported=12)]
        trend = TrendAnalysis(
            status="inconclusive",
            method="Sen's slope estimator & Mann-Kendall test",
            summary="Serie de tiempo insuficiente.",
            methodological_note="Se requieren al menos 5 años.",
        )

        interp = generate_interpretation(self.metadata, trend, frame, annual)

        self.assertIn("inconclusa", interp.headline.lower())
        self.assertIn("1860.0 mm/año", interp.narrative)
        self.assertIn("Costa Rica Continental", interp.narrative)
        self.assertIn("octubre de 2023", interp.narrative)  # Mes más lluvioso (270 mm)
        self.assertIn("marzo de 2023", interp.narrative)    # Mes más seco (30 mm)
        self.assertIn("El Niño", interp.trend_verdict_plain_language)
        self.assertIn("menos de 5 años", interp.trend_verdict_plain_language)
        self.assertGreaterEqual(len(interp.prudence_guidelines), 3)

    def test_interpretation_conclusive_significant(self) -> None:
        dates = pd.date_range("2015-01-01", periods=60, freq="MS")
        frame = pd.DataFrame(
            {
                "precipitation_mm": [100.0 + i * 2 for i in range(60)],
                "coverage_fraction": [1.0] * 60,
                "quality_flag": ["ok"] * 60,
                "anomaly_mm": [i * 2.0 - 60.0 for i in range(60)],
            },
            index=dates,
        )
        annual = [
            AnnualPrecipitation(year=y, annual_precipitation_mm=1200.0 + y * 10, months_reported=12)
            for y in range(2015, 2020)
        ]
        trend = TrendAnalysis(
            status="conclusive",
            method="Sen's slope estimator & Mann-Kendall test",
            slope=15.4,
            slope_unit="mm/year",
            p_value=0.012,
            is_significant=True,
            confidence_level=0.95,
            summary="Tendencia positiva significativa.",
        )

        interp = generate_interpretation(self.metadata, trend, frame, annual)

        self.assertIn("significativa", interp.headline.lower())
        self.assertIn("Mann-Kendall", interp.trend_verdict_plain_language)
        self.assertIn("15.40 mm/year", interp.trend_verdict_plain_language)
        self.assertIn("0.0120", interp.trend_verdict_plain_language)

    def test_interpretation_not_computed(self) -> None:
        # Solo 3 meses (año incompleto)
        dates = pd.date_range("2024-01-01", periods=3, freq="MS")
        frame = pd.DataFrame(
            {
                "precipitation_mm": [50.0, 40.0, 30.0],
                "coverage_fraction": [1.0, 1.0, 1.0],
                "quality_flag": ["ok", "ok", "ok"],
                "anomaly_mm": [10.0, 0.0, -10.0],
            },
            index=dates,
        )
        annual = []
        trend = TrendAnalysis(
            status="not_computed",
            method="Sen's slope estimator & Mann-Kendall test",
            summary="No calculado.",
            methodological_note="Sin años completos.",
        )

        interp = generate_interpretation(self.metadata, trend, frame, annual)

        self.assertIn("sin evaluación de tendencia anual", interp.headline.lower())
        self.assertIn("no contiene años calendario cerrados", interp.trend_verdict_plain_language)


if __name__ == "__main__":
    unittest.main()
