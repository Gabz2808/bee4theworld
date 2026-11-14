# Iyök: experiencia de exploración

Estado: guía completada para el issue #4. La dirección natural y científica fue elegida por Manuel; el prototipo se revisó con Chrome headless en escritorio y móvil, y el lint completo y la compilación pasaron. Los detalles visuales aún no son una identidad gráfica aprobada. Fecha: 14 de noviembre de 2026.

## Propósito y público

Iyök es un proyecto en desarrollo de Bee4TheWorld para ayudar al público general a explorar cambios del sistema terrestre con evidencia verificable. El primer caso acordado es precipitación IMERG en Costa Rica; la geometría, versión, período y metodología siguen pendientes de validación con el compañero. El nombre Iyök está designado, pero no se debe atribuir significado, origen ni pronunciación no comprobados.

Una persona debe poder responder: qué se observó, dónde y cuándo; cómo se representa; qué indica el análisis y con qué límites; y de dónde provienen los datos. Una gráfica o un valor p no demuestran causalidad ni importancia práctica. Si no se cumplen los requisitos estadísticos o faltan datos, el resultado debe expresarse como inconcluso.

## Recorrido y jerarquía

1. **Llegar y comprender:** presentar el propósito, el alcance disponible y la posibilidad de explorar sin prometer datos que aún no existen.
2. **Delimitar:** seleccionar entre territorios, variables y períodos ofrecidos por la cobertura real. Explicar unidades y disponibilidad antes de iniciar; no ofrecer geometrías arbitrarias si el backend no las soporta.
3. **Observar:** mostrar una serie temporal con fechas, unidades, valores ausentes y tabla accesible. La selección y los datos deben pertenecer al mismo análisis.
4. **Interpretar:** explicar dirección y magnitud solo cuando el backend provea un cálculo válido; incluir incertidumbre, método, supuestos y estado inconcluso cuando corresponda.
5. **Comprobar:** permitir consultar proveedor, producto y versión, enlace o DOI, acceso, agregación, calidad, cobertura y limitaciones. Aclarar si una capa de mapa difiere de los datos analizados.

## Estados y contenido

| Estado | Comportamiento y mensaje esperado |
| --- | --- |
| Preparación | Explicar qué falta, mantener deshabilitadas las opciones no disponibles y evitar aparentar conexión real. |
| Ejemplo ficticio | Identificar el ejemplo cerca del control y de cada visualización; no incluirlo como resultado científico de la demostración. |
| Carga | Indicar que la solicitud está en curso; evitar cambios silenciosos o envíos repetidos. |
| Sin cobertura o datos insuficientes | Explicar el motivo disponible y orientar al usuario a seleccionar opciones compatibles; no mostrar ceros en lugar de ausencias. |
| Error | Explicar qué no pudo completarse y ofrecer reintento sin exponer información interna. |
| Resultado real | Identificar región, variable, período, unidad y procedencia; acompañar la gráfica con una tabla y las limitaciones pertinentes. |
| Resultado inconcluso | Mantener la serie si es válida y explicar por qué no se puede emitir una conclusión sobre tendencia. |

## Dirección visual elegida

La dirección elegida es **natural y científica**: tonos tierra y vegetación, con una interfaz clara de investigación. La interfaz de exploración es una herramienta de trabajo: debe favorecer el reconocimiento de controles, la lectura y la confianza. El prototipo utiliza fondos claros, verdes naturales y titulares con serif para vincular territorio y observación. Los verdes oscuros se reservan para texto y acciones; los fondos suaves agrupan el trabajo; los avisos explican su significado en texto, no solo mediante color. La paleta exacta, los tipos y el logo no están aprobados y deben poder ajustarse sin alterar el contenido o los datos.

El prototipo usa `#1b3028` sobre `#f7f8f2` para texto principal y `#53665e` sobre ese fondo para texto secundario. Como orientación, estas parejas alcanzan aproximadamente 13,11:1 y 5,73:1 respectivamente; `#668a69` sobre el mismo fondo alcanza aproximadamente 3,64:1 y se limita a texto grande, no a cuerpo pequeño. Verificar cada combinación real antes de usarla y no basarse solo en estos ejemplos.

## Accesibilidad y adaptación

- Usar HTML semántico, etiquetas explícitas, orden lógico y foco visible; todas las acciones deben funcionar con teclado.
- Ofrecer tabla para las series, con unidad, fechas y faltantes; no depender de color, hover o una imagen para comunicar resultados.
- Mantener texto legible, contraste adecuado, áreas táctiles cómodas y estados comprensibles en escritorio y móvil. Respetar movimiento reducido.
- Escribir en español claro; preparar los textos para futuras traducciones sin anunciar idiomas que no estén implementados.

## Límites y pendientes

El contrato de API, el producto y su cobertura exacta, la geometría, el análisis estadístico y las capas de mapa requieren acuerdo y verificación con el compañero. El mapa y el control temporal se incorporan después de completar el flujo con una serie real compatible. No se implementan predicciones ni alertas. La revisión realizada cubrió el prototipo y su ejemplo ficticio en Chrome headless; el flujo con datos reales debe comprobarse cuando exista.
