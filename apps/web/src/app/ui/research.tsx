export function Research() {
  return <section id="investigacion" className="research" aria-labelledby="research-heading">
    <div className="wrap research-layout">
      <div className="research-intro">
        <h2 id="research-heading">La investigación, abierta a revisión.</h2>
        <p>Este MVP comparte lo que sabemos, cómo lo calculamos y lo que aún no podemos concluir. Los resultados se actualizan cuando hay evidencia nueva.</p>
      </div>
      <div className="research-body">
        <article><h3>Método y procedencia</h3><p>La serie convierte la tasa media mensual IMERG en acumulado mensual y calcula un promedio ponderado por el área de cada celda dentro del componente terrestre principal de IGN/SNIT. Los componentes separados se excluyen. La geometría y el procesamiento siguen bajo revisión científica.</p><a href="https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation">Consultar documentación IMERG de NASA <span aria-hidden="true">↗</span></a></article>
        <article><h3>Datos disponibles</h3><p>El producto de origen es IMERG Final mensual V07, para 2001–2024. NASA ofrece acceso a los datos originales; la serie procesada y la geometría de Iyök aún no están publicadas aquí. Antes de distribuir derivados revisaremos las condiciones de uso de sus fuentes.</p><a href="https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07">Consultar el producto original de NASA <span aria-hidden="true">↗</span></a></article>
        <article><h3>Pruebas y resultados inconclusos</h3><p>Se contrastó el cálculo de 288 meses y se verificó la integridad de la geometría. En un ensayo separado, el índice mensual de NASA se resumió sobre las celdas de cada mes usando pesos por área; la cobertura conjunta calculada fue aproximadamente 99,9998 %. Son comprobaciones técnicas: no validan las observaciones ni la significancia de una tendencia.</p><p>Usamos provisionalmente los intervalos del ATBD de NASA por celda: menos de 3, de 3 a menos de 10 y 10 o más. Otra guía de NASA propone límites distintos. La relación entre el índice y el error local sigue sin validar; no filtramos la precipitación con esos intervalos. El código y los resultados derivados aún están pendientes de publicación pública.</p><a href="https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_V07_ATBD_final_230712.pdf">Consultar el método de NASA <span aria-hidden="true">↗</span></a></article>
      </div>
    </div>
  </section>;
}
