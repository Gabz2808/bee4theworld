"use client";
import Link from "next/link";
import { useI18n } from "../i18n/provider";
import { DataSources, LandingVideo, PLAY_VIDEO_EVENT } from "./landing-sections";

// Landing: presentación del proyecto. Investigación en /investigacion; datos y gráficos en /explorar.
export function Landing() {
  const { t } = useI18n();
  return <main id="inicio">
    <section className="intro wrap">
      <div className="intro-copy">
        <div className="location"><span className="location-dot" /> {t.intro.location}</div>
        <h1>{t.intro.title1}<br /><em>{t.intro.title2}</em></h1>
        <p>{t.intro.body}</p>
        <div className="intro-actions">
          <Link className="primary-link" href="/explorar">{t.intro.cta} <span aria-hidden="true">↗</span></Link>
          <Link className="secondary-link" href="/investigacion">{t.intro.researchCta} <span aria-hidden="true">→</span></Link>
          <a className="video-link" href="#video" onClick={(event) => {
            // Centra el video completo en la ventana (no solo el inicio de la sección) y lo reproduce.
            const frame = document.querySelector(".video-frame");
            if (frame) { event.preventDefault(); frame.scrollIntoView({ behavior: "smooth", block: "center" }); history.replaceState(null, "", "#video"); }
            window.dispatchEvent(new Event(PLAY_VIDEO_EVENT));
          }}><span className="video-link-icon" aria-hidden="true">▶</span>{t.intro.videoCta} <span aria-hidden="true">↓</span></a>
        </div>
      </div>
      <div className="intro-side"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="earth"><span>CR</span></div><div className="intro-caption"><span>{t.intro.captionKicker}</span><strong>{t.intro.caption1}<br />{t.intro.caption2}</strong></div></div>
    </section>
    <LandingVideo />
    <DataSources />
  </main>;
}
