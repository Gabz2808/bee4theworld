"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";
import type { Exploration } from "../lib/api-v1";
import { useI18n } from "../i18n/provider";

type Cell = [number, number, number, number, number | null];
type Manifest = { dataset: string; geometry_sha256: string; months: { month: string; file: string }[] };
type LayerState = "loading" | "ready" | "error";

const geometryHash = "ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb";
const dataset = "GPM_3IMERGM.07";
const empty = { type: "FeatureCollection" as const, features: [] };
// Cortes de color en mm/mes; la leyenda usa las mismas posiciones relativas.
const stops: [number, string][] = [[0, "#e8eac2"], [100, "#a8d8ad"], [300, "#45a4a2"], [600, "#246995"], [1000, "#273878"]];
const legendGradient = `linear-gradient(90deg, ${stops.map(([v, c]) => `${c} ${v / 10}%`).join(", ")})`;

async function loadManifest(signal: AbortSignal): Promise<Manifest> {
  const response = await fetch("/map-data/manifest.json", { signal });
  if (!response.ok) throw new Error("manifest");
  const data = await response.json() as Manifest;
  if (data.dataset !== dataset || data.geometry_sha256 !== geometryHash || !Array.isArray(data.months)) throw new Error("manifest");
  return data;
}

export default function PrecipitationMap({ result, index, setIndex }: { result: Exploration; index: number; setIndex: (index: number) => void }) {
  // El componente se vuelve a montar al cambiar de idioma (key en el explorador), así que t es estable aquí.
  const { t } = useI18n();
  const number = new Intl.NumberFormat(t.numberLocale, { maximumFractionDigits: 1 });
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [mapProblem, setMapProblem] = useState("");
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [manifestProblem, setManifestProblem] = useState(false);
  const [layer, setLayer] = useState<{ month: string; state: LayerState } | null>(null);
  const [basemapProblem, setBasemapProblem] = useState(false);
  const [playing, setPlaying] = useState(false);
  const point = result.points[index];
  const month = point?.date.slice(0, 7);
  const last = result.points.length - 1;
  const selection = result.metadata.selection as Record<string, unknown>;
  const compatible = selection.geometry_sha256 === geometryHash && result.metadata.dataset === dataset;
  const layerState: LayerState = manifestProblem ? "error" : layer?.month === month ? layer.state : "loading";

  useEffect(() => {
    const controller = new AbortController();
    loadManifest(controller.signal).then(setManifest).catch((error: Error) => { if (error.name !== "AbortError") setManifestProblem(true); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!container.current) return;
    let instance: MapLibreMap;
    try {
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
      instance = new maplibregl.Map({
        container: container.current,
        bounds: [[-86.1, 8.0], [-82.5, 11.25]],
        fitBoundsOptions: { padding: { top: 16, right: 16, left: 16, bottom: 48 } },
        minZoom: 4,
        maxZoom: 11,
        attributionControl: false,
        cooperativeGestures: true,
        locale: t.map.controls,
        style: {
          version: 8,
          sources: {
            basemap: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              maxzoom: 19,
              attribution: `© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">${t.map.osm}</a>`,
            },
          },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#111318" } },
            { id: "basemap", type: "raster", source: "basemap", paint: { "raster-saturation": -0.85, "raster-brightness-max": 0.45, "raster-opacity": 0.65 } },
          ],
        },
      });
    } catch { queueMicrotask(() => setMapProblem(t.map.webgl)); return; }
    map.current = instance;
    instance.on("error", (event) => { if ("sourceId" in event && event.sourceId === "basemap") setBasemapProblem(true); });
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    instance.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-right");
    instance.on("load", () => {
      instance.addSource("cells", { type: "geojson", data: empty, attribution: "IMERG: NASA GES DISC" });
      instance.addLayer({ id: "cells", type: "fill", source: "cells", paint: { "fill-color": ["interpolate", ["linear"], ["get", "value"], ...stops.flat()], "fill-opacity": 0.75, "fill-outline-color": "rgba(233,237,242,0.3)" } });
      instance.addSource("boundary", { type: "geojson", data: "/map-data/boundary.json", attribution: t.map.boundaryAttribution });
      instance.addLayer({ id: "boundary", type: "line", source: "boundary", paint: { "line-color": "#F5B82E", "line-width": 2 } });
      const popup = new maplibregl.Popup({ closeButton: true, maxWidth: "240px" });
      instance.on("click", "cells", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;
        const text = document.createElement("p");
        text.className = "map-popup";
        text.textContent = t.map.popup(number.format(Number(feature.properties.value)));
        popup.setLngLat(event.lngLat).setDOMContent(text).addTo(instance);
      });
      instance.on("mouseenter", "cells", () => { instance.getCanvas().style.cursor = "pointer"; });
      instance.on("mouseleave", "cells", () => { instance.getCanvas().style.cursor = ""; });
      setLoaded(true);
    });
    return () => { instance.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- se monta una sola vez por idioma
  }, []);

  useEffect(() => {
    if (!loaded || !map.current) return;
    const source = map.current.getSource("cells") as GeoJSONSource;
    // Retira la capa anterior antes de pedir otra para no mostrar un mes desfasado.
    source.setData(empty);
    if (!month || !compatible || !manifest) return;
    const entry = manifest.months.find((item) => item.month === month);
    const controller = new AbortController();
    const fail = () => { if (!controller.signal.aborted) setLayer({ month, state: "error" }); };
    if (!entry) { queueMicrotask(fail); return () => controller.abort(); }
    fetch(`/map-data/${entry.file}`, { signal: controller.signal }).then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then((data: { month: string; cells: Cell[] }) => {
      if (data.month !== month || !Array.isArray(data.cells)) throw new Error();
      source.setData({ type: "FeatureCollection", features: data.cells.filter((c) => c[4] !== null).map(([west, south, east, north, value]) => ({ type: "Feature", properties: { value }, geometry: { type: "Polygon", coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] } })) });
      setLayer({ month, state: "ready" });
    }).catch(fail);
    return () => controller.abort();
  }, [loaded, month, compatible, manifest]);

  useEffect(() => {
    if (!playing) return;
    if (layerState === "error") { queueMicrotask(() => setPlaying(false)); return; }
    // Avanza cuando la capa actual ya se mostró, para no saltar meses sin dibujar.
    if (layerState !== "ready") return;
    const timer = window.setTimeout(() => setIndex(index >= last ? 0 : index + 1), 900);
    return () => window.clearTimeout(timer);
  }, [playing, layerState, index, last, setIndex]);

  const regional = point?.value === null || point?.value === undefined ? t.map.noData : `${number.format(point.value)} ${result.metadata.unit === "mm/month" ? t.map.unit : String(result.metadata.unit)}`;
  const status = !compatible ? t.map.incompatible : manifestProblem ? t.map.manifest : layerState === "error" ? t.map.layerError(month ?? "") : layerState === "loading" ? t.map.layerLoading(month ?? "") : "";

  return <section className="map-view" aria-label={t.map.aria}>
    <div className="map-topline"><div><strong>{t.map.title}</strong><p>IMERG Final V07 · {month} · {t.map.unit}</p><p className="map-note">{t.map.note}</p></div><span>{t.map.badge}</span></div>
    <div className="map-canvas" ref={container} role="region" aria-label={t.map.canvas(month ?? "")} />
    {mapProblem && <p className="map-error" role="alert">{mapProblem}</p>}
    <p className={!compatible || manifestProblem || layerState === "error" ? "map-error" : "map-loading"} role="status">{mapProblem ? "" : status}</p>
    {basemapProblem && <p className="map-error">{t.map.basemap}</p>}
    <div className="map-legend"><span>{t.map.unit}</span><div className="map-legend-scale"><div style={{ background: legendGradient }} aria-hidden="true" /><span style={{ left: "0%" }}>0</span><span style={{ left: "30%" }}>300</span><span style={{ left: "60%" }}>600</span><span style={{ left: "100%" }}>{t.map.legendMax}</span></div></div>
    <div className="map-timeline">
      <button type="button" onClick={() => { if (!playing && index >= last) setIndex(0); setPlaying(!playing); }} disabled={last < 1 || !compatible || manifestProblem}>{playing ? t.map.pause : t.map.play}</button>
      <label htmlFor="map-month">{t.map.month} <strong>{month}</strong></label>
      <input id="map-month" type="range" min="0" max={Math.max(0, last)} value={index} aria-valuetext={month} onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value)); }} />
      <span aria-hidden="true">{result.points.at(-1)?.date.slice(0, 7)}</span>
    </div>
    <p className="map-description">{t.map.regionalLead(month ?? "")} <strong>{regional}</strong>. {t.map.description}</p>
  </section>;
}
