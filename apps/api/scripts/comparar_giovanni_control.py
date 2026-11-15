"""Compara exportaciones Giovanni de control con la respuesta Harmony guardada."""
from __future__ import annotations

import calendar
import csv
import json
from pathlib import Path

EVIDENCIA = Path(__file__).resolve().parents[3] / "docs" / "evidencia"
REGION = "-85.5,9,-85.3,9.2"


def main() -> None:
    harmony = json.loads((EVIDENCIA / "harmony-control-2024.json").read_text(encoding="utf-8"))
    expected = {point["date"][:7]: point["value"] for point in harmony["timeseries"]}
    if len(expected) != 12 or set(expected) != {f"2024-{month:02}" for month in range(1, 13)}:
        raise ValueError("Harmony no contiene exactamente los 12 meses esperados")
    observed: dict[str, float] = {}
    for path in sorted(EVIDENCIA.glob("giovanni-control-2024-*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
        metadata = {row[0].strip(): row[1].strip() for row in rows if len(row) >= 2}
        if metadata.get("User Bounding Box:") != REGION:
            raise ValueError(f"Geometría inesperada en {path.name}")
        header = next((i for i, row in enumerate(rows) if row and row[0].strip() == "time"), None)
        if header is None or "GPM_3IMERGM_07_precipitation" not in rows[header][1]:
            raise ValueError(f"Variable desconocida en {path.name}")
        for row in rows[header + 1:]:
            if len(row) < 2:
                continue
            month = row[0][:7]
            if month not in expected or month in observed:
                raise ValueError(f"Mes inesperado o duplicado: {month}")
            rate = float(row[1])
            if rate < 0:
                raise ValueError(f"Valor negativo o faltante: {month}")
            year, number = map(int, month.split("-"))
            observed[month] = rate * 24 * calendar.monthrange(year, number)[1]
    if set(observed) != set(expected):
        raise ValueError(f"Faltan meses de Giovanni: {sorted(set(expected) - set(observed))}")
    differences = {month: observed[month] - expected[month] for month in expected}
    for month, difference in differences.items():
        print(f"{month}: Giovanni {observed[month]:.6f}, Harmony {expected[month]:.2f}, diferencia {difference:+.6f} mm")
    maximum = max(abs(value) for value in differences.values())
    print(f"Diferencia absoluta máxima: {maximum:.6f} mm; Harmony reporta dos decimales")
    if maximum > 0.00501:
        raise ValueError("Hay diferencias superiores al redondeo esperado; investigar métodos y datos")


if __name__ == "__main__":
    main()
