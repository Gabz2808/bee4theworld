# Continuidad de la sesión — 14 de noviembre de 2026

## Estado

- El issue [#4: experiencia y dirección visual](https://github.com/B-28-Labs/bee4theworld/issues/4) está cerrado. El [brief de experiencia](brief-experiencia.md) recoge el público general, recorrido, estados y dirección natural y científica elegida por Manuel. La paleta exacta, tipografía y logo no están aprobados.
- `apps/web` contiene un prototipo Next.js en español con ECharts y una tabla alternativa. La serie es sintética y está identificada como ficticia; los controles de selección están deshabilitados. No hay conexión real a la API ni análisis estadístico.
- Se ejecutaron el lint completo y la compilación con éxito. Con Playwright y Chrome headless se revisaron escritorio (1440 × 900) y móvil (390 × 844), el ejemplo y la tabla; no se detectaron errores de JavaScript ni desbordamiento horizontal. Se corrigieron una desalineación de navegación y una superposición en móvil. Las capturas y el script de esa comprobación están en `.tools/`, directorio local ignorado por Git; no forman parte del repositorio.
- Playwright y ECharts están registrados en el lockfile. La última instalación informó ocho vulnerabilidades moderadas en el árbol completo; no se ejecutó una auditoría adicional ni se ha determinado su alcance.
- La clave SSH de la cuenta del usuario permitió subir al repositorio. La cuenta `alquimiacria` tiene acceso y se usó para crear los issues; la creación de un GitHub Project de organización falló por falta de permisos. No se guardan credenciales en el repositorio.

## Siguiente trabajo

El [#5: Construir base visual adaptable](https://github.com/B-28-Labs/bee4theworld/issues/5) está cerrado: salto al explorador, foco en el resultado al cargar o recargar y estados más claros. Lint y compilación pasaron; Chrome headless comprobó teclado, tabla y ausencia de desbordamiento en 320, 390, 768 y 1440 px, con revisión visual en móvil y escritorio. La comprobación no sustituye pruebas con dispositivos físicos ni lectores de pantalla.

El [#6: acordar contrato de integración](https://github.com/B-28-Labs/bee4theworld/issues/6) está en curso. Se preparó [una propuesta para revisión conjunta](propuesta-integracion.md) y se encapsuló la fuente del ejemplo ficticio detrás de un puerto interno. No se ha acordado ni implementado el contrato real: la revisión del compañero y una capa cliente validada contra ese acuerdo siguen pendientes. No dar por finalizado el flujo científico: ese trabajo corresponde a los issues posteriores.

El compañero lidera ingesta, análisis y API. El primer caso acordado es precipitación IMERG para Costa Rica, investigada mediante Giovanni. La geometría, versión, período y método deben acordarse y validarse. Una prueba de metadatos OPeNDAP con autenticación funcionó, pero no se ha extraído ni validado una serie real. No compartir ni versionar tokens.

## Para arrancar

Leer `AGENTS.md`, `DEPENDENCIAS.md`, `docs/analisis-y-decisiones.md` y este documento; comprobar estado de Git y el issue vigente. Desde `apps/web`, ejecutar `npm ci` y `npm run dev`. El uso de Playwright puede aprovechar Chrome instalado; no se requiere descargarlo de nuevo para esa configuración. Verificar los requisitos y plazos oficiales vigentes y cualquier plazo específico de la sede.
