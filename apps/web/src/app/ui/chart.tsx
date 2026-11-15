"use client";
import { useEffect, useRef } from "react";
import { init } from "echarts";
import type { Observation } from "../lib/exploration";
export function Chart({ points }: { points: Observation[] }) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const chart = init(element.current);
    chart.setOption({ grid:{top:24,left:44,right:18,bottom:35}, tooltip:{trigger:"axis"}, xAxis:{type:"category",data:points.map(p=>p.date),axisTick:{show:false},axisLabel:{color:"#53665e"}}, yAxis:{type:"value",axisLabel:{color:"#53665e"},splitLine:{lineStyle:{color:"#e3eae3"}}}, series:[{type:"line",data:points.map(p=>p.value),connectNulls:false,showAllSymbol:true,symbolSize:8,lineStyle:{color:"#276a50",width:3},itemStyle:{color:"#276a50"}}] });
    const observer = new ResizeObserver(() => chart.resize()); observer.observe(element.current);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [points]);
  return <div ref={element} className="chart" aria-hidden="true" />;
}
