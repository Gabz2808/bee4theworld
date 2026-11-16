"use client";
import { useEffect, useRef } from "react";
import Image from "next/image";
import { useI18n } from "../i18n/provider";
import type { Locale } from "../i18n/dictionaries";

// Video de 30 s por idioma (archivos en public/video/, por ejemplo "/video/iyok-recorrido-en.mp4").
// Portada: un .jpg con el mismo nombre junto al video (iyok-nasa-en.mp4 → iyok-nasa-en.jpg).
// Si el idioma activo no tiene video (null) se muestra un marcador honesto de "video en producción".
export const LANDING_VIDEO_SRC: Record<Locale, string | null> = {
  en: "/video/iyok-nasa-en.mp4",
  es: "/video/iyok-nasa-es.mp4",
};
export const PLAY_VIDEO_EVENT = "iyok-play-video";

export function LandingVideo() {
  const { t, locale } = useI18n();
  const src = LANDING_VIDEO_SRC[locale];
  const video = useRef<HTMLVideoElement>(null);
  const section = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = video.current;
    const target = section.current;
    if (!element || !target) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Se reproduce (en silencio, como exigen los navegadores) al llegar a la sección y se pausa al salir.
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !reducedMotion) element.play().catch(() => {});
      else if (!entry.isIntersecting) element.pause();
    }, { threshold: 0.5 });
    observer.observe(target);
    // El botón de la portada es un gesto de la persona: permite reproducir con sonido.
    const playFromButton = () => { element.muted = false; element.play().catch(() => { element.muted = true; element.play().catch(() => {}); }); };
    window.addEventListener(PLAY_VIDEO_EVENT, playFromButton);
    return () => { observer.disconnect(); window.removeEventListener(PLAY_VIDEO_EVENT, playFromButton); };
    // Al cambiar de idioma se monta el otro video; el observador se vuelve a crear y lo reproduce si la sección está a la vista.
  }, [src]);

  return <section id="video" ref={section} className="landing-video" aria-labelledby="video-heading">
    <div className="wrap">
      <div className="landing-section-heading">
        <p className="section-label">{t.video.kicker}</p>
        <h2 id="video-heading">{t.video.title}</h2>
        <p>{t.video.body}</p>
      </div>
      <div className="video-frame">
        {src
          ? <video key={src} ref={video} src={src} poster={src.replace(/\.mp4$/, ".jpg")} lang={locale} aria-label={t.video.aria} muted playsInline controls preload="metadata" />
          : <div className="video-placeholder" role="note">
              <span className="video-play" aria-hidden="true"><svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor"><path d="M8 5.5v13l11-6.5-11-6.5Z" /></svg></span>
              <strong>{t.video.placeholderTitle}</strong>
              <p>{t.video.placeholder}</p>
              <span className="video-duration">0:30</span>
            </div>}
      </div>
    </div>
  </section>;
}

export function DataSources() {
  const { t } = useI18n();
  const s = t.sources;
  return <section className="data-sources" aria-labelledby="sources-heading">
    <div className="wrap">
      <div className="landing-section-heading">
        <p className="section-label">{s.kicker}</p>
        <h2 id="sources-heading">{s.title}</h2>
        <p>{s.body}</p>
      </div>
      <ul className="source-grid">
        {s.items.map((item) => <li key={item.id} className="source-card">
          <figure>
            <div className="source-shot"><Image src={`/fuentes/${item.id}.jpg`} alt={item.name} width={1280} height={800} sizes="(max-width: 900px) 100vw, 33vw" /></div>
            <figcaption>{s.captured}</figcaption>
          </figure>
          <h3>{item.name}</h3>
          <p>{item.detail}</p>
          <a href={item.url} target="_blank" rel="noopener noreferrer">{s.visit} <span aria-hidden="true">↗</span><span className="sr-only"> {s.newTab}</span></a>
        </li>)}
      </ul>
      <p className="sources-note">{s.note}</p>
    </div>
  </section>;
}
