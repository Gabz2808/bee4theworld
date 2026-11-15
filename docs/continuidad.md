# Continuidad del proyecto

## Estado vigente — 15 de noviembre de 2026

- `main` está en `94fd272`, compartido con `origin/main` al iniciar esta actualización. Las notas de esta actualización aún pueden estar sin comitear; comprobar `git status` antes de continuar. Los servidores locales de Iyök se detuvieron por solicitud de Manuel.
- El frontend usa las rutas v1 del backend, restringe fechas al intervalo declarado y muestra carga, error y faltantes; etiqueta la serie como no validada y oculta la interpretación estadística. El cliente aceptó una respuesta real guardada de 288 meses y el navegador mostró las 288 filas; no fue una consulta completa en vivo por el proxy.
- Se procesaron 288 meses reales de 2001–2024 con CMR/Harmony para la geometría provisional, con fechas consecutivas e identificadores coincidentes con CMR. La primera consulta tardó varios minutos y supera los 90 segundos del proxy. El frontend advierte `BACKEND_TIMEOUT`; la gestión de trabajos largos y deduplicación sigue en [#20](https://github.com/B-28-Labs/bee4theworld/issues/20).
- La ingesta histórica de Supabase también tiene 288 meses, pero sus identificadores no coinciden con CMR y sus 288 valores difieren de la extracción directa. La causa no está establecida. No usarla como validación ni migrarla a la caché compatible sin aclarar procedencia y procesamiento.
- Se obtuvieron CSV de Giovanni para 2024 en un rectángulo de control; los 12 meses coinciden con Harmony al redondeo. Ese rectángulo no representa Costa Rica ni valida el polígono provisional. La geometría definitiva, la serie histórica y el método estadístico aún requieren revisión conjunta. Ver [evidencia y límites](verificacion-datos-2026-11-15.md).
- Verificación más reciente: 105 pruebas de API y tres subpruebas, siete pruebas del cliente, Ruff, ESLint y compilación pasaron. Se comprobó el mensaje de tiempo agotado en escritorio y móvil con un servicio de prueba lento. El contraste no equivale a validación científica.
- El issue [#6](https://github.com/B-28-Labs/bee4theworld/issues/6) está cerrado en GitHub; [#7–#12](https://github.com/B-28-Labs/bee4theworld/issues?q=is%3Aissue%20is%3Aopen%20label%3AFrontend) y [#15–#21](https://github.com/B-28-Labs/bee4theworld/issues?q=is%3Aissue%20is%3Aopen%20label%3ABackend) siguen abiertos. El traspaso para backend está al comienzo de [coordinación](../apps/api/COORDINACION_FRONTEND_BACKEND.md).

## Notas históricas — 14 de noviembre de 2026

Las notas siguientes documentan observaciones de esa fecha y no sustituyen el estado vigente anterior.

## Estado

- El issue [#4: experiencia y dirección visual](https://github.com/B-28-Labs/bee4theworld/issues/4) está cerrado. El [brief de experiencia](brief-experiencia.md) recoge el público general, recorrido, estados y dirección natural y científica elegida por Manuel. La paleta exacta, tipografía y logo no están aprobados.
- `apps/web` contiene un prototipo Next.js en español con ECharts y una tabla alternativa. El frontend consulta catálogo y exploración de FastAPI mediante rutas de Next.js; presenta cualquier serie devuelta como no validada y no muestra conclusiones estadísticas. Una consulta NASA de enero de 2024 pasó por el cliente y la API. Se comprobó la caché Supabase con ese mes: guardado y recuperación con valores coincidentes. La geometría y la metodología siguen pendientes de validación; ver [frontend](frontend.md), [caché](cache-supabase.md) y [coordinación](../apps/api/COORDINACION_FRONTEND_BACKEND.md).
- Se ejecutaron el lint completo y la compilación con éxito. Con Playwright y Chrome headless se revisaron escritorio (1440 × 900) y móvil (390 × 844), el ejemplo y la tabla; no se detectaron errores de JavaScript ni desbordamiento horizontal. Se corrigieron una desalineación de navegación y una superposición en móvil. Las capturas y el script de esa comprobación están en `.tools/`, directorio local ignorado por Git; no forman parte del repositorio.
- Playwright y ECharts están registrados en el lockfile. La última instalación informó ocho vulnerabilidades moderadas en el árbol completo; no se ejecutó una auditoría adicional ni se ha determinado su alcance.
- La clave SSH de la cuenta del usuario permitió subir al repositorio. La cuenta `alquimiacria` tiene acceso y se usó para crear los issues; la creación de un GitHub Project de organización falló por falta de permisos. No se guardan credenciales en el repositorio.

## Siguiente trabajo

El [#5: Construir base visual adaptable](https://github.com/B-28-Labs/bee4theworld/issues/5) está cerrado: salto al explorador, foco en el resultado al cargar o recargar y estados más claros. Lint y compilación pasaron; Chrome headless comprobó teclado, tabla y ausencia de desbordamiento en 320, 390, 768 y 1440 px, con revisión visual en móvil y escritorio. La comprobación no sustituye pruebas con dispositivos físicos ni lectores de pantalla.

El [#6: contrato de integración](https://github.com/B-28-Labs/bee4theworld/issues/6) cuenta con una respuesta del agente de backend, un [contrato operativo v1](contrato-api-v1.md) y un cliente desacoplado probado con casos sintéticos y una consulta NASA real de un mes. La aceptación del contrato de integración no valida la geometría, la procedencia de Giovanni ni la interpretación científica; esos trabajos continúan en los issues posteriores.

Se recibió un PDF con una propuesta de precipitación del compañero; la [revisión](revision-json-precipitacion.md) identifica campos reutilizables y cuestiones de procedencia, unidades, geometría y análisis. Hay un adaptador provisional que conserva la serie como no verificada; no está conectado al frontend ni acredita datos reales.

El equipo envió una respuesta posterior: consultar la [revisión de backend](revision-respuesta-backend.md). En ese momento se habían comprobado metadatos CMR y una ingesta de 288 meses en Supabase, sin validar independientemente el procesamiento o los datos. El estado posterior del contrato y las discrepancias encontradas se indican arriba.

El compañero lidera ingesta, análisis y API. El primer caso acordado es precipitación IMERG para Costa Rica, investigada mediante Giovanni. La geometría, versión, período y método deben acordarse y validarse. Las extracciones realizadas posteriormente y sus límites se indican arriba. No compartir ni versionar tokens.

## Para arrancar

Leer `AGENTS.md`, `DEPENDENCIAS.md`, `docs/analisis-y-decisiones.md` y este documento; comprobar estado de Git y el issue vigente. Desde `apps/web`, ejecutar `npm ci` y `npm run dev`. El uso de Playwright puede aprovechar Chrome instalado; no se requiere descargarlo de nuevo para esa configuración. Verificar los requisitos y plazos oficiales vigentes y cualquier plazo específico de la sede.
