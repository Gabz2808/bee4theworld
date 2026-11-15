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

Estado del 14 de noviembre de 2026: `apps/web` contiene un prototipo Next.js con TypeScript y Tailwind y un `package-lock.json`. En `apps/web`, ejecutar `npm ci` para reinstalar, `npm run dev` para desarrollo y `npm run lint` para revisión. La instalación inicial informó 7 vulnerabilidades moderadas en el árbol completo; una comprobación anterior de `npm audit --omit=dev` no informó vulnerabilidades de producción. Revisar las dependencias de desarrollo y la advertencia de soporte de ESLint antes de su uso continuado.

Playwright está instalado como dependencia de desarrollo para comprobaciones en navegador. En este equipo se utilizó Chrome ya instalado en modo headless; la última instalación informó 8 vulnerabilidades moderadas en el árbol completo. No se ha realizado una auditoría adicional ni se han clasificado aquí.

Inicializar Next.js con TypeScript y Tailwind mediante el generador oficial; fijar versiones y guardar `package-lock.json`. Añadir cuando el código las requiera: `maplibre-gl`, `echarts`, `@tanstack/react-query`; seguir documentación oficial para shadcn/ui, que añade componentes al código y no es solo una dependencia. Para instalaciones reproducibles posteriores usar `npm ci` en `apps/web` cuando exista el lockfile.

## Backend (`apps/api`)

Actualizado al 15 de noviembre de 2026 (Issue #21):
- `apps/api/requirements.txt`: Manifiesto de ejecución en producción con rangos compatibles (`fastapi`, `uvicorn`, `pandas`, `pydantic`, `supabase`, `harmony-py`, `netCDF4`, `numpy`, `pyproj`, `shapely`, `xarray`, `python-dotenv`, `httpx`).
- `apps/api/requirements-dev.txt`: Dependencias de desarrollo, pruebas y verificación estadística (`pytest`, `scipy`).
- `apps/api/requirements-lock.txt`: Registro reproducible de versiones exactas fijadas, verificado libre de conflictos con `pip check`.

### Instalación limpia y verificación:

En Linux / macOS:
```bash
python3 -m venv apps/api/.venv
source apps/api/.venv/bin/activate
pip install --upgrade pip
pip install -r apps/api/requirements.txt
pip install -r apps/api/requirements-dev.txt
python -m pip check
```

En Windows:
```powershell
py -3.12 -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install --upgrade pip
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements.txt
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-dev.txt
apps/api/.venv/Scripts/python.exe -m pip check
```

Para verificar suite completa de pruebas:
```bash
PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -v
```

## Impeccable y herramientas reutilizables

La copia local `.codex/skills/impeccable/` no se versiona; cada integrante puede usar el skill disponible en su entorno. Para tareas UI, leer su `SKILL.md`. Sus herramientas pueden descargar componentes: verificar procedencia, checksum, red y permisos antes de ejecutar. No es dependencia de producción.

Del proyecto de videos son útiles **como herramientas opcionales** `scripts/gemini_analyze.py` (inspección de referencias multimedia mediante Vertex) y Scribe vía fal (transcripción); no se copian porque dependen de credenciales, paquetes, configuración y scripts del proyecto anterior. Solo integrarlos si el equipo realmente necesita esa función y revisa costos, privacidad y licencias. No copiar `.env`, credenciales, hooks, permisos de Claude, proyectos cloud ni configuración de producción.

## Datos y servicios opcionales

- El acceso a Supabase mediante MCP respondió a una consulta de prueba; la conexión directa local no está configurada. El diagnóstico directo opcional dispone de un entorno aislado con Psycopg; consulta [acceso a Supabase](docs/supabase-acceso-local.md). La elección de dependencias de la API corresponde al compañero.
- Crear una cuenta Earthdata Login solo si el producto elegido lo requiere; verificar su acceso antes de comprometer la demo. No incluir tokens en repositorio.
- PostgreSQL/PostGIS y Docker Compose son opcionales hasta que haya una necesidad real de consultas espaciales; archivos estáticos versionados pueden bastar para una sola región.
- Hosting, cuentas, dominios y servicios de pago no están configurados. No provisionarlos ni desplegar automáticamente.
- Al implementar: registrar versiones de producto y dependencias, agregar `.env.example` sin secretos, `.gitignore`, instrucciones de arranque y pruebas, y comprobar una instalación limpia.
