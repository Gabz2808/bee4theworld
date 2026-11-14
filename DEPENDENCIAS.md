# Dependencias y primera instalación

Este directorio está evolucionando desde un punto de partida documental. Consulta el estado real de `apps/web` y `apps/api` antes de instalar; prepara solo lo necesario, con versiones compatibles y lockfiles registrados. No ejecutes comandos de instalación de forma oculta. Si faltan permisos o acceso de red, informa el bloqueo y sigue con lo posible.

## Herramientas base

| Herramienta | Uso | Comprobación |
| --- | --- | --- |
| Git | Versionado | `git --version` |
| Node.js LTS y npm | Frontend Next.js | `node --version`, `npm --version` |
| Python 3.12 y pip/venv | API y ciencia | `python --version`, `python -m pip --version` (Windows: `py -3.12`) |
| Docker Desktop con Compose | Opcional, si se usa PostGIS o contenedores | `docker --version`, `docker compose version` |

Instala herramientas de sistema desde sus sitios oficiales si faltan, respetando permisos del entorno. El material propone Next.js 15 y Python 3.12; verificar compatibilidad y seguridad actuales al crear el proyecto. No asumir que `python` apunta a 3.12.

## Frontend, al crear `apps/web`

Estado del 14 de noviembre de 2026: el generador oficial creó `apps/web` con Next.js, TypeScript y Tailwind y generó `package-lock.json`. En `apps/web`, ejecutar `npm ci` para reinstalar, `npm run dev` para desarrollo y `npm run lint` para revisión. La plantilla todavía no es la interfaz de Iyök. La instalación informó 7 vulnerabilidades moderadas en el árbol completo; `npm audit --omit=dev` no informó vulnerabilidades de producción. Revisar las dependencias de desarrollo y la advertencia de soporte de ESLint antes de su uso continuado.

Inicializar Next.js con TypeScript y Tailwind mediante el generador oficial; fijar versiones y guardar `package-lock.json`. Añadir cuando el código las requiera: `maplibre-gl`, `echarts`, `@tanstack/react-query`; seguir documentación oficial para shadcn/ui, que añade componentes al código y no es solo una dependencia. Para instalaciones reproducibles posteriores usar `npm ci` en `apps/web` cuando exista el lockfile.

## Backend, al crear `apps/api`

Estado del 14 de noviembre de 2026: se creó `apps/api/.venv` con Python 3.12.14 del entorno local y se instalaron las dependencias base. `apps/api/requirements-lock.txt` registra las versiones resueltas en Windows; el compañero debe revisarlas y acordar su mantenimiento y compatibilidad con otras plataformas. El entorno virtual no se versiona y depende del Python con el que fue creado.

Para recrearlo con Python 3.12 disponible en Windows:

```powershell
py -3.12 -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-lock.txt
apps/api/.venv/Scripts/python.exe -m pip check
```

No se ha implementado API ni acordado contrato. La selección de bibliotecas de análisis adicionales corresponde al método y formatos que acuerde el equipo.

Crear un entorno virtual (`python -m venv .venv`; en Windows `py -3.12 -m venv .venv`) e instalar mediante un manifiesto y lockfile fijados por el equipo. Base esperada: `fastapi`, `pydantic`, `uvicorn`, `numpy`, `pandas`, `scipy`; para pruebas `pytest`. Evaluar `statsmodels` y `pymannkendall` si el método seleccionado los necesita. Incorporar `xarray`, `rasterio` y motor NetCDF/HDF apropiado solo para el formato real. Evitar instalar librerías geoespaciales pesadas si la demo usa series preprocesadas.

Una vez creados y revisados los archivos de dependencias, instalar conforme a ellos, por ejemplo `python -m pip install -r requirements.txt` desde `apps/api`. No existe tal archivo todavía. Fijar versiones después de comprobar compatibilidad, licencia y vulnerabilidades; no inventar versiones verificadas.

## Impeccable y herramientas reutilizables

La copia local `.codex/skills/impeccable/` no se versiona; cada integrante puede usar el skill disponible en su entorno. Para tareas UI, leer su `SKILL.md`. Sus herramientas pueden descargar componentes: verificar procedencia, checksum, red y permisos antes de ejecutar. No es dependencia de producción.

Del proyecto de videos son útiles **como herramientas opcionales** `scripts/gemini_analyze.py` (inspección de referencias multimedia mediante Vertex) y Scribe vía fal (transcripción); no se copian porque dependen de credenciales, paquetes, configuración y scripts del proyecto anterior. Solo integrarlos si el equipo realmente necesita esa función y revisa costos, privacidad y licencias. No copiar `.env`, credenciales, hooks, permisos de Claude, proyectos cloud ni configuración de producción.

## Datos y servicios opcionales

- Crear una cuenta Earthdata Login solo si el producto elegido lo requiere; verificar su acceso antes de comprometer la demo. No incluir tokens en repositorio.
- PostgreSQL/PostGIS y Docker Compose son opcionales hasta que haya una necesidad real de consultas espaciales; archivos estáticos versionados pueden bastar para una sola región.
- Hosting, cuentas, dominios y servicios de pago no están configurados. No provisionarlos ni desplegar automáticamente.
- Al implementar: registrar versiones de producto y dependencias, agregar `.env.example` sin secretos, `.gitignore`, instrucciones de arranque y pruebas, y comprobar una instalación limpia.
