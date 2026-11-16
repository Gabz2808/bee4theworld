"use client";

import { useState } from "react";
import {
  WORLD_CONTINENT_PATHS,
  GLOBAL_OBSERVATION_SITES,
  type GlobalSite,
} from "./map-geometry";
import { useI18n } from "../i18n/provider";

interface WorldMapProps {
  selectedRegionId?: string;
  onSelectRegion?: (regionId: string, regionName: string) => void;
}

export function WorldMap({
  selectedRegionId = "costa-rica-snit-continental-v1",
  onSelectRegion,
}: WorldMapProps) {
  const { t } = useI18n();
  const siteText = (site: GlobalSite) => t.sites[site.id] ?? site;
  const [viewMode, setViewMode] = useState<"globe" | "flat">("globe");
  const [hoveredSite, setHoveredSite] = useState<GlobalSite | null>(null);
  const [activeSite, setActiveSite] = useState<GlobalSite | null>(() => {
    return GLOBAL_OBSERVATION_SITES.find((s) => s.regionId === selectedRegionId) || GLOBAL_OBSERVATION_SITES[0];
  });
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  const handleSelectSite = (site: GlobalSite) => {
    setActiveSite(site);
    if (site.regionId && onSelectRegion) {
      onSelectRegion(site.regionId, siteText(site).name);
    }
  };

  const currentDisplaySite = hoveredSite || activeSite || GLOBAL_OBSERVATION_SITES[0];

  return (
    <div className="world-map-wrapper" role="region" aria-label={t.world.aria}>
      {/* Barra superior de estado del mapa planetario */}
      <div className="world-map-topbar">
        <div className="world-map-title-block">
          <div className="world-map-kicker">
            <span className="live-dot" /> {t.world.kicker}
          </div>
          <h4 className="world-map-heading">
            {viewMode === "globe" ? t.world.globeTitle : t.world.flatTitle}
          </h4>
          <p className="world-map-caption">
            {t.world.caption}
          </p>
        </div>

        {/* Selector de modo estilo AirIndx: [ 3D GLOBE ] [ MAPA PLANO ] */}
        <div className="world-mode-toggle" role="group" aria-label={t.world.modeGroup}>
          <button
            type="button"
            className={`world-mode-btn ${viewMode === "globe" ? "active" : ""}`}
            onClick={() => setViewMode("globe")}
            aria-pressed={viewMode === "globe"}
          >
            <span aria-hidden="true">🌐 </span>{t.world.globe}
          </button>
          <button
            type="button"
            className={`world-mode-btn ${viewMode === "flat" ? "active" : ""}`}
            onClick={() => setViewMode("flat")}
            aria-pressed={viewMode === "flat"}
          >
            <span aria-hidden="true">🗺️ </span>{t.world.flat}
          </button>
        </div>
      </div>

      {/* Tarjeta flotante de telemetría y sitio activo (inspirada en AirIndx) */}
      <div className="telemetry-overlay">
        <div className="telemetry-card">
          <div className="telemetry-header">
            <span className="telemetry-badge">
              {currentDisplaySite.status === "verified"
                ? t.world.verified
                : currentDisplaySite.status === "on_demand"
                ? t.world.onDemand
                : t.world.research}
            </span>
            <span className="telemetry-coords">
              {currentDisplaySite.lat >= 0 ? `${currentDisplaySite.lat}°N` : `${Math.abs(currentDisplaySite.lat)}°S`} ·{" "}
              {currentDisplaySite.lon >= 0 ? `${currentDisplaySite.lon}°E` : `${Math.abs(currentDisplaySite.lon)}°W`}
            </span>
          </div>
          <strong className="telemetry-site-name">{siteText(currentDisplaySite).name}</strong>
          <span className="telemetry-country">{siteText(currentDisplaySite).country}</span>
          <p className="telemetry-desc">{siteText(currentDisplaySite).description}</p>
          {currentDisplaySite.regionId ? (
            <div className="telemetry-action">
              {activeSite?.id === currentDisplaySite.id ? (
                <span className="telemetry-selected-tag">✓ {t.world.active}</span>
              ) : (
                <button
                  type="button"
                  className="telemetry-select-btn"
                  onClick={() => handleSelectSite(currentDisplaySite)}
                >
                  {t.world.select} →
                </button>
              )}
            </div>
          ) : (
            <span className="telemetry-note">{t.world.calibration}</span>
          )}
        </div>
      </div>

      {/* Contenedor SVG Visual */}
      <div className="world-canvas-container">
        {viewMode === "globe" ? (
          /* ==============================================================
             VISTA 1: GLOBO 3D ORBITAL
             ============================================================== */
          <svg
            viewBox="0 0 500 500"
            className="globe-svg"
            style={{ transform: `scale(${zoomLevel})` }}
            aria-label={t.world.globeAria}
          >
            <defs>
              {/* Resplandor atmosférico exterior */}
              <radialGradient id="globe-atmosphere" cx="50%" cy="50%" r="50%">
                <stop offset="70%" stopColor="#111318" stopOpacity="0" />
                <stop offset="90%" stopColor="#526A86" stopOpacity="0.25" />
                <stop offset="98%" stopColor="#F5B82E" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#111318" stopOpacity="0" />
              </radialGradient>

              {/* Shading esférico 3D del océano */}
              <radialGradient id="globe-shading" cx="38%" cy="32%" r="65%">
                <stop offset="0%" stopColor="#223042" />
                <stop offset="45%" stopColor="#16202c" />
                <stop offset="80%" stopColor="#0d131a" />
                <stop offset="100%" stopColor="#080b0f" />
              </radialGradient>

              {/* Sombra de limbo (efecto de profundidad) */}
              <radialGradient id="globe-limb" cx="50%" cy="50%" r="50%">
                <stop offset="85%" stopColor="#000000" stopOpacity="0" />
                <stop offset="100%" stopColor="#000000" stopOpacity="0.75" />
              </radialGradient>

              {/* Clip circular de la esfera */}
              <clipPath id="globe-clip">
                <circle cx="250" cy="250" r="190" />
              </clipPath>

              {/* Patrón de líneas orbitales */}
              <pattern id="globe-grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#526A86" strokeWidth="0.3" opacity="0.25" />
              </pattern>
            </defs>

            {/* Aura exterior de la atmósfera */}
            <circle cx="250" cy="250" r="215" fill="url(#globe-atmosphere)" />

            {/* Borde exterior orbital */}
            <circle cx="250" cy="250" r="191" fill="none" stroke="#526A86" strokeWidth="1.2" opacity="0.6" />

            {/* Esfera base con sombra 3D */}
            <circle cx="250" cy="250" r="190" fill="url(#globe-shading)" />

            {/* Elementos internos recortados a la esfera */}
            <g clipPath="url(#globe-clip)">
              {/* Grilla orbital interna */}
              <rect x="60" y="60" width="380" height="380" fill="url(#globe-grid)" />

              {/* Paralelos esféricos (elipses) */}
              <ellipse cx="250" cy="170" rx="170" ry="24" fill="none" stroke="#526A86" strokeWidth="0.6" strokeDasharray="3,3" opacity="0.4" />
              <ellipse cx="250" cy="250" rx="190" ry="28" fill="none" stroke="#F5B82E" strokeWidth="0.8" strokeDasharray="4,4" opacity="0.5" />
              <ellipse cx="250" cy="330" rx="170" ry="24" fill="none" stroke="#526A86" strokeWidth="0.6" strokeDasharray="3,3" opacity="0.4" />

              {/* Meridianos esféricos */}
              <ellipse cx="250" cy="250" rx="45" ry="190" fill="none" stroke="#526A86" strokeWidth="0.5" opacity="0.3" />
              <ellipse cx="250" cy="250" rx="110" ry="190" fill="none" stroke="#526A86" strokeWidth="0.5" opacity="0.3" />

              {/* Silueta de las Américas y continentes centrados en el globo */}
              <g transform="translate(65, 80) scale(0.68)" opacity="0.85">
                <path
                  d={WORLD_CONTINENT_PATHS.north_america}
                  fill="#1E2734"
                  stroke="#526A86"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                />
                <path
                  d={WORLD_CONTINENT_PATHS.south_america}
                  fill="#1E2734"
                  stroke="#526A86"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                />
              </g>

              {/* Sombra de limbo sobre los continentes para curvatura realista */}
              <circle cx="250" cy="250" r="190" fill="url(#globe-limb)" />
            </g>

            {/* Marcadores sobre el Globo */}
            {/* 1. Costa Rica (Centro orbital) */}
            <g
              className="globe-marker primary-marker"
              transform="translate(198, 222)"
              onClick={() => handleSelectSite(GLOBAL_OBSERVATION_SITES[0])}
              onMouseEnter={() => setHoveredSite(GLOBAL_OBSERVATION_SITES[0])}
              onMouseLeave={() => setHoveredSite(null)}
              tabIndex={0}
              role="button"
              aria-label={siteText(GLOBAL_OBSERVATION_SITES[0]).name}
            >
              {/* Pulso animado */}
              <circle cx="0" cy="0" r="14" fill="none" stroke="#F5B82E" strokeWidth="1.5" className="pin-pulse" />
              <circle cx="0" cy="0" r="6" fill="#F5B82E" stroke="#111318" strokeWidth="2" />
              <circle cx="0" cy="0" r="2" fill="#E9EDF2" />
              {/* Etiqueta badge de alta visibilidad */}
              <g transform="translate(10, -12)">
                <rect x="0" y="0" width="86" height="24" rx="4" fill="#171B22" stroke="#F5B82E" strokeWidth="1" />
                <text x="8" y="15" fill="#E9EDF2" fontSize="10" fontWeight="bold">
                  🇨🇷 Costa Rica
                </text>
              </g>
            </g>

            {/* 2. Canal de Panamá */}
            <g
              className="globe-marker"
              transform="translate(225, 234)"
              onClick={() => handleSelectSite(GLOBAL_OBSERVATION_SITES[1])}
              onMouseEnter={() => setHoveredSite(GLOBAL_OBSERVATION_SITES[1])}
              onMouseLeave={() => setHoveredSite(null)}
              tabIndex={0}
              role="button"
              aria-label={t.globeLabels.panamaAria}
            >
              <circle cx="0" cy="0" r="4.5" fill="#526A86" stroke="#E9EDF2" strokeWidth="1.5" />
              <text x="7" y="3" fill="#8E9FAE" fontSize="9">
                {t.globeLabels.panama}
              </text>
            </g>

            {/* 3. Cuenca del Amazonas */}
            <g
              className="globe-marker"
              transform="translate(265, 280)"
              onClick={() => handleSelectSite(GLOBAL_OBSERVATION_SITES[3])}
              onMouseEnter={() => setHoveredSite(GLOBAL_OBSERVATION_SITES[3])}
              onMouseLeave={() => setHoveredSite(null)}
              tabIndex={0}
              role="button"
              aria-label={t.globeLabels.amazonAria}
            >
              <circle cx="0" cy="0" r="4" fill="#526A86" stroke="#111318" strokeWidth="1" />
              <text x="7" y="3" fill="#8E9FAE" fontSize="8.5">
                {t.globeLabels.amazon}
              </text>
            </g>

            {/* 4. Corredor Seco */}
            <g
              className="globe-marker"
              transform="translate(178, 204)"
              onClick={() => handleSelectSite(GLOBAL_OBSERVATION_SITES[2])}
              onMouseEnter={() => setHoveredSite(GLOBAL_OBSERVATION_SITES[2])}
              onMouseLeave={() => setHoveredSite(null)}
              tabIndex={0}
              role="button"
              aria-label={t.globeLabels.chiquimulaAria}
            >
              <circle cx="0" cy="0" r="4" fill="#526A86" stroke="#111318" strokeWidth="1" />
              <text x="-48" y="-6" fill="#8E9FAE" fontSize="8.5">
                Chiquimula
              </text>
            </g>
          </svg>
        ) : (
          /* ==============================================================
             VISTA 2: MAPAMUNDI PLANO (PROYECCIÓN EQUIRECTANGULAR 720x360)
             ============================================================== */
          <svg
            viewBox="0 0 720 360"
            className="flat-map-svg"
            style={{ transform: `scale(${zoomLevel})` }}
            aria-label={t.world.flatAria}
          >
            <defs>
              <linearGradient id="ocean-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#141820" />
                <stop offset="100%" stopColor="#0f1217" />
              </linearGradient>
              <pattern id="lat-grid" width="60" height="30" patternUnits="userSpaceOnUse">
                <path d="M 60 0 L 0 0 0 30" fill="none" stroke="#526A86" strokeWidth="0.3" opacity="0.2" />
              </pattern>
            </defs>

            {/* Océano plano */}
            <rect width="720" height="360" fill="url(#ocean-gradient)" rx="6" />
            <rect width="720" height="360" fill="url(#lat-grid)" rx="6" />

            {/* Franja de cobertura orbital NASA GPM Core (65°S a 65°N) */}
            <rect
              x="0"
              y="50"
              width="720"
              height="260"
              fill="rgba(82, 106, 134, 0.08)"
              stroke="#526A86"
              strokeWidth="0.75"
              strokeDasharray="4,4"
            />
            <text x="10" y="44" fill="#8E9FAE" fontSize="8" fontFamily="monospace">
              {t.world.orbitN}
            </text>
            <text x="10" y="324" fill="#8E9FAE" fontSize="8" fontFamily="monospace">
              {t.world.orbitS}
            </text>

            {/* Ecuador 0° */}
            <line x1="0" y1="180" x2="720" y2="180" stroke="#F5B82E" strokeWidth="0.75" strokeDasharray="4,4" opacity="0.4" />
            <text x="650" y="176" fill="#F5B82E" fontSize="8" fontFamily="monospace" opacity="0.7">
              {t.world.equator}
            </text>

            {/* Continentes */}
            {Object.entries(WORLD_CONTINENT_PATHS).map(([key, d]) => (
              <path
                key={key}
                d={d}
                fill="#1A202C"
                stroke="#526A86"
                strokeWidth="0.9"
                strokeLinejoin="round"
                className="continent-shape"
              />
            ))}

            {/* Puntos y sitios globales */}
            {GLOBAL_OBSERVATION_SITES.map((site) => {
              const isSelected = activeSite?.id === site.id;
              return (
                <g
                  key={site.id}
                  className={`site-pin ${isSelected ? "selected" : ""}`}
                  onClick={() => handleSelectSite(site)}
                  onMouseEnter={() => setHoveredSite(site)}
                  onMouseLeave={() => setHoveredSite(null)}
                  tabIndex={0}
                  role="button"
                  aria-label={`${siteText(site).name} (${siteText(site).country})`}
                >
                  {site.isPrimary && (
                    <circle cx={site.x} cy={site.y} r="10" fill="none" stroke="#F5B82E" strokeWidth="1.2" className="pin-pulse" />
                  )}
                  <circle
                    cx={site.x}
                    cy={site.y}
                    r={isSelected ? 5.5 : site.isPrimary ? 4.5 : 3.5}
                    fill={site.isPrimary ? "#F5B82E" : "#526A86"}
                    stroke="#111318"
                    strokeWidth="1.6"
                  />
                  <text
                    x={site.x + 8}
                    y={site.y + 3}
                    fontSize="9"
                    fontWeight={site.isPrimary ? "bold" : "normal"}
                    fill={site.isPrimary ? "#F5B82E" : "#E9EDF2"}
                  >
                    {siteText(site).name}
                  </text>
                </g>
              );
            })}
          </svg>
        )}

        {/* Controles de Zoom en la esquina inferior derecha (estilo AirIndx) */}
        <div className="map-zoom-controls">
          <span className="zoom-label">{t.world.zoom}</span>
          <button
            type="button"
            className="zoom-btn"
            onClick={() => setZoomLevel((z) => Math.min(1.8, +(z + 0.2).toFixed(1)))}
            aria-label={t.world.zoomIn}
          >
            +
          </button>
          <button
            type="button"
            className="zoom-btn"
            onClick={() => setZoomLevel((z) => Math.max(0.8, +(z - 0.2).toFixed(1)))}
            aria-label={t.world.zoomOut}
          >
            −
          </button>
          {zoomLevel !== 1 && (
            <button
              type="button"
              className="zoom-reset-btn"
              onClick={() => setZoomLevel(1)}
              aria-label={t.world.zoomReset}
            >
              1:1
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
