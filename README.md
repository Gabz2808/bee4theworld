# Iyök

**Exploración de tendencias del sistema terrestre con evidencia verificable.**

Iyök es un proyecto en desarrollo de **Bee4TheWorld** para el reto [Be An Earth System Trend Detective!](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/) del NASA Space Apps Challenge 2026. Su propósito es ayudar a las personas a comprender qué cambia, dónde, cuánto y con qué grado de evidencia científica, mediante datos satelitales, visualizaciones interactivas y explicaciones rigurosas y comprensibles.

El ámbito inicial de estudio es **Costa Rica** y la primera variable seleccionada es la precipitación satelital calibrada **IMERG Final Run** (NASA GES DISC). La arquitectura modular en monorepo está diseñada para facilitar una futura expansión geográfica y temática sujeta a la disponibilidad, calidad y calibración local de cada producto.

---

## Estado del Proyecto

El repositorio está estructurado como un **monorepo unificado** compuesto por el frontend web y la API analítica backend:

* **Backend (`apps/api`):** Implementado y operativo bajo la API v1 acordada:
  * Catálogo unificado (`GET /api/v1/catalog`) con geometrías territoriales en PostGIS, metadatos y rangos de cobertura real.
  * Motor analítico de exploración (`POST /api/v1/explorations`) con **doble modalidad de ingesta**:
    * **Base de datos Supabase (PostgreSQL + PostGIS):** Serie histórica de 24 años (2001-2024) de Costa Rica precargada.
    * **Extracción satelital en vivo con NASA Earthdata / Harmony:** Recorte espacial y descarga on-demand de gránulos NetCDF-4 de NASA GPM IMERG V07 para **cualquier polígono de América Latina** mediante token de Earthdata.
  * **Sistema de Caché de Alto Rendimiento:** Almacenamiento local determinista en disco que reduce tiempos de respuesta subsecuentes de minutos a **< 50 milisegundos (aceleración > 2,000x)**.
  * **Interpretación Científica Comprensible y Prudente (`ScientificInterpretation`):** Generación automática de narrativa en prosa accesible para ciudadanos y tomadores de decisiones, traduciendo picos estacionales, anomalías en mm y veredictos de Mann-Kendall / Theil-Sen con estrictas directrices de prudencia científica (sin atribuciones causales infundadas).
  * CORS habilitado para comunicación directa y sin fricciones con `apps/web`.
  * Suite de pruebas automatizadas con **58 tests unitarios y de integración pasando al 100% en < 0.5 s**.
* **Frontend (`apps/web`):** Prototipo accesible desarrollado con **Next.js 15, TypeScript y Tailwind CSS**, con gráficos interactivos y tabla de observaciones, navegable por teclado y adaptable a escritorio y móvil. En proceso de conexión con los contratos v1 del backend.

---

## Estructura del Repositorio

```text
bee4theworld/
├── apps/
│   ├── api/                     # Backend FastAPI, servicios satelitales y estadísticas
│   │   ├── app/                 # Código de la API (rutas v1, esquemas y lógica científica)
│   │   │   ├── init.sql         # Esquema de base de datos PostGIS en Supabase
│   │   │   └── main.py          # Aplicación principal FastAPI
│   │   ├── tests/               # Suite de 50 pruebas automatizadas
│   │   ├── requirements.txt     # Manifiesto de dependencias Python
│   │   └── requirements-lock.txt# Lockfile versionado
│   └── web/                     # Frontend Next.js, TypeScript y Tailwind CSS
│       ├── src/                 # Componentes, vistas e interfaces de usuario
│       ├── package.json         # Dependencias Node
│       └── package-lock.json    # Lockfile de dependencias npm
├── docs/                        # Documentación técnica, metodológica y de diseño
│   ├── assets/                  # Logotipos, capturas de pantalla y diagramas
│   ├── manual_usuario_tecnico.md# Manual técnico completo de la API v1
│   ├── backend_tasks_iy_k_project.md # Tablero de control de tareas técnicas
│   └── brief-experiencia.md     # Lineamientos de experiencia de usuario y visuales
├── referencias/                 # Contratos API oficiales v1, presentaciones y contexto
│   └── iyok_api_contracts_mock.json # Especificación de contratos JSON v1
├── .env.example                 # Plantilla de variables de entorno
├── .gitignore                   # Reglas de exclusión unificadas (Python y Node)
├── AGENTS.md                    # Centro de contexto y directrices del equipo
├── DEPENDENCIAS.md              # Requisitos y configuración de entornos
└── README.md                    # Descripción general del proyecto
```

---

## Ejecución del Proyecto

### 1. Backend (`apps/api`)

Requiere Python 3.10 o superior (recomendado Python 3.12/3.14).

```bash
# 1. Acceder al directorio del backend
cd apps/api

# 2. Configurar entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate       # En Windows: .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env            # Añadir SUPABASE_URL y SUPABASE_SECRET_KEY

# 4. Iniciar el servidor de desarrollo
uvicorn app.main:app --reload --env-file .env
```
* **API Health Check:** `http://localhost:8000/ping`
* **Documentación interactiva Swagger UI:** `http://localhost:8000/docs`
* **Ejecutar pruebas unitarias e integración (58 tests):**
  ```bash
  python -m unittest discover -s tests -v
  ```
* **Diagnóstico NASA Earthdata / Harmony:**
  ```bash
  python scripts/verificar_earthdata.py --descargar-prueba
  ```
* **Prueba integral de endpoint y caché con datos en vivo:**
  ```bash
  python scripts/probar_exploracion_en_vivo.py --periodo 12meses
  ```

---

### 2. Frontend (`apps/web`)

Requiere Node.js 18+ y npm.

```bash
# 1. Acceder al directorio del frontend
cd apps/web

# 2. Instalar dependencias exactas
npm ci

# 3. Iniciar el servidor de desarrollo
npm run dev
```
* Aplicación disponible en: `http://localhost:3000`
* Para revisar calidad y construcción del frontend:
  ```bash
  npm run lint
  npm run build
  ```

---

## Datos y Rigor Científico

El proyecto sigue estándares científicos estrictos para evitar sesgos o interpretaciones erróneas:
* **Fuente Satelital Oficial:** NASA GPM IMERG Final Run mensual (`GPM_3IMERGM.07`, calibrado con pluviómetros a nivel global).
* **Conversión de Unidades:** La tasa media nativa ($\text{mm/hr}$) se convierte a acumulación mensual ($\text{mm/mes}$) multiplicando por el número exacto de horas de cada mes natural ($24.0 \times \text{días}$), computando con precisión años bisiestos.
* **Ponderación Espacial en Área Equivalente:** La agregación sobre polígonos territoriales se computa en la proyección cilíndrica de igual área **EPSG:6933**, integrando el área en $m^2$ de la intersección exacta de cada celda de cuadrícula ($0.1^\circ$) con la frontera territorial.
* **Política de Ausencia de Datos Faltantes:** Si un mes no cuenta con observaciones, su valor se mantiene estrictamente como `null` con bandera `missing_month` o `missing_value`. **Nunca se imputa con cero**. Los acumulados anuales exigen los 12 meses observados para no distorsionar las series temporales.
* **Separación de Veredictos:** Los análisis se clasifican formalmente en `conclusive`, `inconclusive`, `not_computed` o `failed`. Un valor $p \ge 0.05$ indica que no se rechaza la hipótesis nula bajo el método y umbral elegidos, sin atribuir causalidad ni asumir ausencia absoluta de cambio.
