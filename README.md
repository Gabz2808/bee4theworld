# Iyök

**Exploración de tendencias del sistema terrestre con evidencia verificable.**

Iyök es un proyecto en desarrollo de **Bee4TheWorld** para el reto [Be An Earth System Trend Detective!](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/) del NASA Space Apps Challenge 2026. Busca ayudar a las personas a comprender qué cambia, dónde, cuánto y con qué grado de evidencia, mediante datos, visualizaciones y explicaciones accesibles.

El punto de partida es **Costa Rica** y la primera variable seleccionada para investigar es la precipitación **IMERG**. La arquitectura debe permitir una futura expansión a Latinoamérica, sujeta a la disponibilidad, calidad y contexto de cada región.

## Estado del proyecto

Iyök se encuentra en etapa de prototipo. La interfaz permite explorar una gráfica y una tabla de ejemplo, navegar con teclado y visualizar el diseño en escritorio y móvil. Los valores son **ficticios** y están identificados como demostración; no representan mediciones ni conclusiones científicas.

- Los selectores de territorio, variable y período permanecerán deshabilitados hasta conocer la cobertura real.
- Todavía no hay conexión a una API, serie IMERG validada ni cálculo estadístico integrado.
- El primer producto, su versión, geometría, período y método de análisis requieren validación conjunta.
- La [propuesta de integración](docs/propuesta-integracion.md) es un borrador para revisión; sus rutas y esquemas no son un contrato aprobado.

## Iniciar el frontend

Se necesitan Node.js y npm compatibles con el proyecto. Desde la raíz del repositorio:

```powershell
cd apps/web
npm ci
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000) y selecciona **«Ver ejemplo de interfaz»**. La tabla del ejemplo incluye un valor ausente para mostrar cómo se representa. Para detener el servidor, pulsa `Ctrl + C` en la terminal.

Para comprobar la calidad del código y la compilación, desde `apps/web`:

```powershell
npm run lint
npm run build
```

## Backend e integración

El equipo trabaja en paralelo: el frontend y la integración se desarrollan en `apps/web`; el compañero lidera la ingesta, el análisis y la API. `apps/api` contiene las dependencias fijadas para preparar un entorno local, pero **aún no implementa una API**. El acuerdo sobre el contrato y el caso científico precede a la conexión de ambas partes.

Para preparar el entorno en Windows con Python 3.12 disponible, desde la raíz del repositorio:

```powershell
py -3.12 -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-lock.txt
apps/api/.venv/Scripts/python.exe -m pip check
```

Consulta [DEPENDENCIAS.md](DEPENDENCIAS.md) para más detalles y limitaciones del entorno. No incluyas credenciales ni tokens en el repositorio o en código que se ejecute en el navegador.

## Datos y rigor científico

El equipo investiga la disponibilidad de precipitación IMERG mediante [NASA Giovanni](https://giovanni.gsfc.nasa.gov/giovanni/). Antes de presentar resultados reales, debe documentar el producto y su versión, la geometría, el período, las unidades, la cobertura, la calidad, la agregación, los datos faltantes, el método y sus limitaciones.

Una tendencia estadística no demuestra por sí sola causalidad ni importancia práctica. Si la información es insuficiente o no se cumplen los supuestos del análisis, el resultado deberá indicarse como **inconcluso**. La serie ficticia del prototipo no se utilizará como evidencia científica.

## Estructura del repositorio

| Ubicación | Contenido |
| --- | --- |
| [`apps/web/`](apps/web/) | Prototipo frontend con Next.js, TypeScript y ECharts. |
| [`apps/api/`](apps/api/) | Dependencias para preparar el entorno local del backend; API pendiente. |
| [`docs/`](docs/) | Experiencia, decisiones, integración y continuidad del proyecto. |
| [`referencias/`](referencias/) | Material de contexto y ejemplos; no son especificaciones aprobadas. |

## Documentación y seguimiento

- [Experiencia y dirección visual](docs/brief-experiencia.md): público, recorrido, estados y criterios de diseño.
- [Propuesta de integración](docs/propuesta-integracion.md): borrador para acordar datos, contratos y responsabilidades.
- [Análisis y decisiones](docs/analisis-y-decisiones.md): prioridades, fuentes y cuestiones abiertas.
- [Estado del frontend](docs/frontend.md) y [continuidad](docs/continuidad.md): implementación, límites y próximos pasos.
- [Issues de frontend](docs/issues-frontend.md): desglose de trabajo y enlaces de seguimiento.
- [Guía del proyecto](AGENTS.md) y [dependencias](DEPENDENCIAS.md): contexto de colaboración y preparación del entorno.
