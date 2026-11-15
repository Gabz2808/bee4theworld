const steps = [
  { label: "Origen", title: "IMERG Final mensual V07", detail: "Serie temporal 2001–2024 (NASA).", icon: "origin" },
  { label: "Recorte espacial", title: "Componente terrestre IGN/SNIT", detail: "Solo territorio continental principal (componentes separados excluidos).", icon: "area" },
  { label: "Cálculo", title: "Acumulado ponderado", detail: "Conversión de tasa media mensual a acumulado + promedio ponderado por área de celda.", icon: "calculation" },
  { label: "Estado", title: "Revisión científica", detail: "Geometría y procesamiento bajo validación antes de liberar derivados.", icon: "review" },
];

function StepIcon({ type }: { type: string }) {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {type === "origin" && <><circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.5 2.2 3.5 5 3.5 8s-1 5.8-3.5 8c-2.5-2.2-3.5-5-3.5-8S9.5 6.2 12 4Z"/></>}
    {type === "area" && <><path d="m4 7 5-3 6 3 5-3v13l-5 3-6-3-5 3V7ZM9 4v13M15 7v13"/></>}
    {type === "calculation" && <><path d="M4 19h16M6 16v-4M12 16V5M18 16V9"/><circle cx="6" cy="10" r="1"/><circle cx="12" cy="3" r="1"/><circle cx="18" cy="7" r="1"/></>}
    {type === "review" && <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 4 4M8 10.5l1.7 1.7 3.3-3.4"/></>}
  </svg>;
}

export function Research() {
  return <section id="investigacion" className="research" aria-labelledby="research-heading">
    <div className="wrap">
      <header className="research-intro">
        <span className="research-badge"><span aria-hidden="true" />MVP • Abierto a revisión científica</span>
        <h2 id="research-heading">La investigación, abierta a revisión.</h2>
        <p>Este MVP comparte lo que sabemos, cómo lo calculamos y lo que aún no podemos concluir. Los resultados se actualizan cuando hay evidencia nueva.</p>
      </header>

      <div className="method-flow" aria-label="Flujo metodológico">
        <ol>{steps.map((step, index) => <li key={step.label}>
          <div className="method-step-top"><span className="method-icon"><StepIcon type={step.icon} /></span><span className="method-number">0{index + 1}</span></div>
          <span className="method-label">{step.label}</span><h3>{step.title}</h3><p>{step.detail}</p>
        </li>)}</ol>
      </div>

      <div className="research-grid">
        <section className="research-panel technical-panel" aria-labelledby="technical-heading">
          <h3 id="technical-heading">Pruebas y alcance técnico</h3>
          <div className="research-metrics">
            <div><strong>288 <small>meses</small></strong><p>Cálculo contrastado e integridad geométrica verificada.</p></div>
            <div><strong>≈ 99,9998 <small>%</small></strong><p>Cobertura conjunta calculada mediante pesos por área, en un ensayo separado del índice mensual por celda.</p></div>
          </div>
          <p className="research-warning"><strong>Alcance limitado:</strong> Estas son comprobaciones técnicas; no validan las observaciones ni la significancia de una tendencia.</p>
        </section>
        <section className="research-panel publication-panel" aria-labelledby="publication-heading">
          <h3 id="publication-heading">Estado de publicación de datos</h3>
          <ul className="publication-list">
            <li><span className="publication-status available">Disponible</span><p>Producto original NASA IMERG Final V07 (2001–2024).</p></li>
            <li><span className="publication-status review">En revisión</span><p>Condiciones de uso y licenciamiento de fuentes.</p></li>
            <li><span className="publication-status pending">Pendiente</span><p>Serie procesada, geometría de Iyök y código fuente.</p></li>
          </ul>
        </section>
      </div>

      <section className="interval-panel" aria-labelledby="interval-heading">
        <div><h3 id="interval-heading">Intervalos de evaluación por celda</h3><p>Intervalos provisionales ATBD de NASA (por celda)</p></div>
        <div className="interval-content"><div className="interval-bar" aria-label="Intervalos: menor que 3; de 3 a menos de 10; 10 o más"><span>&lt; 3</span><span>3 a &lt; 10</span><span>≥ 10</span></div>
          <p><strong>Nota metodológica:</strong> Otra guía de NASA propone límites distintos. La relación entre el índice y el error local sigue sin validar, por lo que <strong>NO filtramos la precipitación</strong> con estos intervalos.</p></div>
      </section>

      <nav className="research-links" aria-label="Referencias oficiales de NASA">
        <a href="https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation">Consultar documentación IMERG de NASA <span aria-hidden="true">↗</span></a>
        <a href="https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07">Consultar el producto original de NASA <span aria-hidden="true">↗</span></a>
        <a href="https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_V07_ATBD_final_230712.pdf">Consultar el método de NASA <span aria-hidden="true">↗</span></a>
      </nav>
    </div>
  </section>;
}
