import unittest
from datetime import date

import numpy as np
from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation
from app.services.precipitation_processing import (
    QUALITY_MISSING_MONTH,
    QUALITY_MISSING_VALUE,
    QUALITY_OK,
    QUALITY_PARTIAL_COVERAGE,
    PrecipitationProcessingError,
    aggregate_annual_precipitation,
    prepare_monthly_precipitation,
)


def _result(
    observations: tuple[MonthlyPrecipitation, ...],
    source_units: str = "mm",
) -> GPMIMERGResult:
    region = GeoJSONPolygon(
        type="Polygon",
        coordinates=[[
            (-85.1, 9.9),
            (-84.9, 9.9),
            (-84.9, 10.1),
            (-85.1, 10.1),
            (-85.1, 9.9),
        ]],
    )
    return GPMIMERGResult(
        dataset="GPM_3IMERGM.07",
        version="07",
        region=region,
        source_units=source_units,
        output_units="mm/month",
        unit_conversion=(
            "La conversión a mm/month se aplica en Pandas usando la duración "
            "real de cada mes."
        ),
        spatial_resolution_degrees=0.1,
        granule_ids=("granule-1",),
        weighting_method="area",
        monthly_values=observations,
    )


class MonthlyPrecipitationProcessingTests(unittest.TestCase):
    def test_orders_months_and_preserves_gaps_and_partial_coverage(self) -> None:
        data = _result(
            (
                MonthlyPrecipitation(date(2024, 3, 1), 8.0, 0.75),
                MonthlyPrecipitation(date(2024, 1, 1), 5.0, 1.0),
            )
        )

        frame = prepare_monthly_precipitation(
            data,
            date(2024, 1, 1),
            date(2024, 3, 31),
        )

        self.assertEqual(frame.index.strftime("%Y-%m").tolist(), ["2024-01", "2024-02", "2024-03"])
        self.assertEqual(frame.loc["2024-01-01", "quality_flag"], QUALITY_OK)
        self.assertEqual(frame.loc["2024-02-01", "quality_flag"], QUALITY_MISSING_MONTH)
        self.assertTrue(np.isnan(frame.loc["2024-02-01", "precipitation_mm"]))
        self.assertEqual(frame.loc["2024-02-01", "coverage_fraction"], 0)
        self.assertEqual(frame.loc["2024-03-01", "quality_flag"], QUALITY_PARTIAL_COVERAGE)
        self.assertEqual(frame.attrs["granule_ids"], ["granule-1"])

    def test_rate_conversion_uses_actual_month_length_in_pandas(self) -> None:
        frame = prepare_monthly_precipitation(
            _result(
                (MonthlyPrecipitation(date(2024, 2, 1), 1.0, 1.0),),
                source_units="mm/hr",
            ),
            date(2024, 2, 1),
            date(2024, 2, 29),
        )

        self.assertEqual(frame.iloc[0]["precipitation_mm"], 696)
        self.assertEqual(
            frame.attrs["conversion_factors_by_month"]["2024-02"],
            696,
        )

    def test_unknown_source_units_are_rejected(self) -> None:
        with self.assertRaises(PrecipitationProcessingError):
            prepare_monthly_precipitation(
                _result(
                    (MonthlyPrecipitation(date(2024, 2, 1), 1.0, 1.0),),
                    source_units="bananas",
                ),
                date(2024, 2, 1),
                date(2024, 2, 29),
            )

    def test_preserves_extreme_rainfall_values(self) -> None:
        frame = prepare_monthly_precipitation(
            _result((MonthlyPrecipitation(date(2024, 1, 1), 1000.0, 1.0),)),
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        self.assertEqual(frame.iloc[0]["precipitation_mm"], 1000.0)

    def test_preserves_null_monthly_values_as_missing(self) -> None:
        frame = prepare_monthly_precipitation(
            _result((MonthlyPrecipitation(date(2024, 1, 1), None, 0.0),)),
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        self.assertTrue(np.isnan(frame.iloc[0]["precipitation_mm"]))
        self.assertEqual(frame.iloc[0]["quality_flag"], QUALITY_MISSING_VALUE)

    def test_rejects_negative_precipitation(self) -> None:
        with self.assertRaises(PrecipitationProcessingError):
            prepare_monthly_precipitation(
                _result((MonthlyPrecipitation(date(2024, 1, 1), -0.1, 1.0),)),
                date(2024, 1, 1),
                date(2024, 1, 31),
            )

    def test_rejects_duplicate_months(self) -> None:
        observations = (
            MonthlyPrecipitation(date(2024, 1, 1), 1.0, 1.0),
            MonthlyPrecipitation(date(2024, 1, 1), 2.0, 1.0),
        )
        with self.assertRaises(PrecipitationProcessingError):
            prepare_monthly_precipitation(
                _result(observations),
                date(2024, 1, 1),
                date(2024, 1, 31),
            )

    def test_annual_sum_requires_all_twelve_reported_months(self) -> None:
        observations = tuple(
            MonthlyPrecipitation(
                date(2024, month, 1),
                float(month),
                0.75 if month == 7 else 1.0,
            )
            for month in range(1, 13)
        )
        monthly = prepare_monthly_precipitation(
            _result(observations),
            date(2024, 1, 1),
            date(2024, 12, 31),
        )

        annual = aggregate_annual_precipitation(monthly)

        self.assertEqual(annual.loc[2024, "annual_precipitation_mm"], 78.0)
        self.assertEqual(annual.loc[2024, "months_reported"], 12)
        self.assertIn("cobertura espacial parcial", annual.attrs["annual_aggregation_rule"])

    def test_annual_sum_omits_years_with_a_missing_month(self) -> None:
        observations = tuple(
            MonthlyPrecipitation(date(2024, month, 1), float(month), 1.0)
            for month in range(1, 13)
            if month != 2
        )
        monthly = prepare_monthly_precipitation(
            _result(observations),
            date(2024, 1, 1),
            date(2024, 12, 31),
        )

        annual = aggregate_annual_precipitation(monthly)

        self.assertTrue(annual.empty)

    def test_annual_sum_omits_partial_calendar_years(self) -> None:
        monthly = prepare_monthly_precipitation(
            _result(
                tuple(
                    MonthlyPrecipitation(
                        date(2024, month, 1),
                        float(month),
                        1.0,
                    )
                    for month in range(2, 13)
                )
            ),
            date(2024, 2, 1),
            date(2024, 12, 31),
        )

        annual = aggregate_annual_precipitation(monthly)

        self.assertTrue(annual.empty)


if __name__ == "__main__":
    unittest.main()
