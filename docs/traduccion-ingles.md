# Traducción al inglés (issue #25)

## Enfoque

- Diccionarios tipados en `apps/web/src/app/i18n/dictionaries.ts`. El español es la fuente de redacción y define el tipo; TypeScript impide que falte una clave en inglés.
- `I18nProvider` (React context + `useSyncExternalStore`) guarda la preferencia en `localStorage` (`iyok-locale`) con respaldo en memoria y actualiza `<html lang>` y el título. El inglés es el idioma principal: el servidor lo genera y es el predeterminado; el español se activa con el interruptor del header y se recuerda.
- Sin dependencias ni rutas nuevas (`next-intl` o `/en` se pueden reconsiderar si se necesita SEO por idioma).

## Criterio: transcreación, no traducción literal

Cada cadena se redacta en inglés según su intención y su público (divulgación científica), no su sintaxis. Ejemplos:

| Español | Inglés | Por qué |
|---|---|---|
| Entender la Tierra empieza por mirar. | Understanding Earth starts with a closer look. | "starts by looking" suena incompleto en inglés. |
| Bajo demanda | On request | "On demand" sugiere streaming; aquí la serie se pide al servicio. |
| Ámbito / territorio activo | Study area / active study area | Término habitual en ciencias de la Tierra. |
| Componentes separados excluidos | Detached areas excluded (e.g. islands) | "Separate components" es opaco para el lector. |
| Consultar serie | Get the series | Verbo de acción natural en botones. |
| Sin validar | Not validated | Se conserva el alcance exacto. |

## Glosario fijo

precipitación → precipitation · celda → grid cell · frontera → boundary · serie → (time) series · cobertura → coverage · gránulo → granule · procedencia → provenance · en revisión → under review · inconcluso → inconclusive · pendiente (de la tendencia) → slope · intervalo de confianza → confidence interval · mm/mes → mm/month.

## Reglas

- Las advertencias científicas (MVP, sin validar, inconcluso, sin causalidad, sin intervalo revisado) mantienen exactamente el mismo alcance: el inglés no las suaviza ni las refuerza.
- Nombres propios e institucionales (IGN, SNIT, Registro Nacional, NASA GES DISC, GPM_3IMERGM.07) no se traducen. «Iyök» no se traduce ni se explica.
- Números con `Intl.NumberFormat` según el idioma (`es-CR` / `en-US`).

## Limitaciones conocidas

- Los textos que envía la API (limitaciones, advertencias y nota de análisis) llegan en español; en modo inglés se marcan con `lang="es"` y un aviso. Traducirlos requiere acordarlo con backend.
- Los campos `<input type="month">` muestran el formato del idioma del navegador, no el del sitio.
- El mapa MapLibre se vuelve a montar al cambiar de idioma para aplicar sus controles traducidos.
- Las cadenas en inglés requieren revisión humana del equipo antes de presentarlas.
