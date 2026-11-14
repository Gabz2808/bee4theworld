# Iyök — proyecto independiente

Punto de partida de Bee4TheWorld para el NASA Space Apps Challenge 2026. Empieza por [AGENTS.md](AGENTS.md), [DEPENDENCIAS.md](DEPENDENCIAS.md) y [análisis y decisiones](docs/analisis-y-decisiones.md). Los documentos originales y el contrato de ejemplo se conservan en `referencias/`.

Iyök es el nombre elegido para el producto. El ámbito inicial es Costa Rica, con posible expansión posterior a Latinoamérica. Nuestro trabajo comprende frontend e integración; el compañero desarrolla la API y el análisis. Los datos del mock son ficticios y no son resultados científicos.

`apps/web` contiene una interfaz inicial de exploración con datos de demostración ficticios; no es una aplicación científica terminada. `apps/api` prepara un entorno local para integrar el trabajo del compañero; aún no contiene una API. El contrato y el producto científico siguen pendientes de acuerdo y validación.

Consulta [continuidad](docs/continuidad.md) para retomar el trabajo, [DEPENDENCIAS.md](DEPENDENCIAS.md) para preparar el entorno, [frontend](docs/frontend.md) para el estado y la integración y [el análisis](docs/analisis-y-decisiones.md) para decisiones, riesgos y fuentes.

Para iniciar la interfaz, ejecuta `npm ci` y después `npm run dev` dentro de `apps/web`. La serie de la interfaz es un ejemplo ficticio; Giovanni se ha identificado como fuente para investigar datos reales, que aún deben seleccionarse y validarse con el compañero.
