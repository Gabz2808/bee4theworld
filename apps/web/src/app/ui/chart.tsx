"use client";
import { useEffect, useRef } from "react";
import { init } from "echarts";
import type { Observation } from "../lib/exploration";

export function Chart({ points, selectedDate }: { points: Observation[]; selectedDate?: string }) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const chart = init(element.current);
    chart.setOption({
      backgroundColor: "transparent",
      grid: { top: 24, left: 48, right: 18, bottom: 35 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#171B22",
        borderColor: "#526A86",
        borderWidth: 1,
        textStyle: { color: "#E9EDF2" },
      },
      xAxis: {
        type: "category",
        data: points.map((p) => p.date),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(82, 106, 134, 0.3)" } },
        axisLabel: { color: "#8E9FAE", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#8E9FAE", fontSize: 11 },
        splitLine: { lineStyle: { color: "rgba(82, 106, 134, 0.2)" } },
      },
      series: [
        {
          type: "line",
          markLine: selectedDate
            ? {
                silent: true,
                symbol: "none",
                label: { show: false },
                lineStyle: { color: "#F5B82E", type: "dashed", width: 1.5 },
                data: [{ xAxis: selectedDate }],
              }
            : undefined,
          data: points.map((p) => p.value),
          connectNulls: false,
          showAllSymbol: true,
          symbolSize: 6,
          lineStyle: { color: "#F5B82E", width: 2.5 },
          itemStyle: { color: "#F5B82E" },
        },
      ],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [points, selectedDate]);
  return <div ref={element} className="chart" aria-hidden="true" />;
}

