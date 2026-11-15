"""Diagnóstico reproducible de falsos positivos; no valida el clima ni una frontera.

Ejecutar desde apps/api: .venv/Scripts/python.exe scripts/evaluar_tendencia_simulada.py
"""
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.trend_analysis import calculate_lag1_autocorrelation, calculate_theil_sen_slope, mann_kendall_test


def main():
    rng = np.random.default_rng(20261115)
    repetitions = 3000
    print("Series AR(1) sin tendencia; 3000 simulaciones, semilla 20261115; alfa=0.05")
    print("años, rho real, rechazos sin ajuste, rechazos con ajuste, rechazos vía API, casos r1>=0.60")
    for n in (10, 24):
        for rho in (0.0, 0.3, 0.6):
            counts = np.zeros(4, dtype=int)
            for _ in range(repetitions):
                noise = rng.normal(size=n)
                y = np.empty(n)
                y[0] = noise[0] / np.sqrt(1 - rho * rho)
                for i in range(1, n):
                    y[i] = rho * y[i - 1] + noise[i]
                slope = calculate_theil_sen_slope(np.arange(n), y)
                r1 = calculate_lag1_autocorrelation(y, x=np.arange(n), slope=slope)
                counts[0] += mann_kendall_test(y, apply_autocorrelation_correction=False)[3]
                adjusted = mann_kendall_test(y, r1=r1, apply_autocorrelation_correction=True)[3]
                counts[1] += adjusted
                counts[2] += adjusted and r1 < 0.60
                counts[3] += r1 >= 0.60
            print(f"{n}, {rho:.1f}, {counts[0]/repetitions:.3f}, {counts[1]/repetitions:.3f}, {counts[2]/repetitions:.3f}, {counts[3]/repetitions:.3f}")
    print("Vía API representa la regla histórica r1<0.60, antes de la protección introducida en esta revisión.")
    print("Son escenarios ideales, no una estimación de la tasa de error de la serie de Costa Rica.")


if __name__ == "__main__":
    main()
