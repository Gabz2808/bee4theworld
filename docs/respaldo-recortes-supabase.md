# Respaldo privado de recortes IMERG

El 15 de noviembre de 2026 se respaldaron los recortes NASA CMR/Harmony utilizados para la geometría continental SNIT. El bucket `iyok-imerg-backups` es privado, con RLS habilitado en `storage.objects` y sin políticas de acceso para `anon` ni `authenticated` en el momento de la comprobación. Por tanto, el procedimiento usa exclusivamente `SUPABASE_SECRET_KEY` en el servidor; esta clave tiene privilegios amplios y nunca debe llegar al navegador ni a Git. Para operación de equipo a largo plazo conviene evaluar credenciales de alcance más limitado.

El bucket limita el tamaño por objeto a 2 MiB y acepta `application/x-tar` y `application/json`. Contiene 24 archivos TAR, uno por año, y un manifiesto: 25 objetos, 22.342.396 bytes. El manifiesto se subió al final y registra cada archivo mensual, fechas, tamaños, huellas SHA-256, fuente, versión de producto, trabajo Harmony y huella de geometría. Son recortes espaciales, no gránulos globales completos; para una región fuera del rectángulo conservado se necesitaría otra extracción. El respaldo guarda los recortes y el manifiesto; la geometría está en `datos/fuentes/` y debe conservarse y versionarse por separado.

## Uso desde `apps/api`

Las variables `SUPABASE_URL` y `SUPABASE_SECRET_KEY` se leen desde el entorno o `.env` local. El script comprueba el host del proyecto configurado y se niega a usar otro destino. Ninguna clave se incluye en los archivos de respaldo.

```powershell
# Comprobar el respaldo remoto completo sin modificarlo.
.\.venv\Scripts\python.exe scripts/backup_recortes_supabase.py verify

# Restaurar a una carpeta nueva ignorada por Git; nunca sobrescribe una restauración existente.
.\.venv\Scripts\python.exe scripts/backup_recortes_supabase.py restore

# Reprocesar la restauración en una salida nueva; requiere también la geometría local
# y acceso a CMR para comprobar los identificadores de los gránulos.
.\.venv\Scripts\python.exe scripts/procesar_cache_snit.py --cache data/cache/restaurado-imerg-snit-v1 --output data/cache/serie-restaurada.json
```

Para crear otra copia de esta misma versión, `prepare` genera los TAR deterministas desde los archivos locales y `upload` los sube con `upsert=false`. Si un objeto ya existe, solo se acepta si sus bytes coinciden. Cada objeto subido se descarga y compara con su huella; el manifiesto se guarda al final. Una versión nueva de datos requiere un prefijo y manifiesto nuevos: no modificar la huella fijada para hacer pasar otra versión como la original. Una interrupción puede dejar archivos anuales sin manifiesto; `upload` permite reanudar con el mismo contenido. No elimina ni sobrescribe objetos.

## Verificación realizada

- La consulta de metadatos de Storage devolvió `public=false`, 25 objetos, RLS activo y cero políticas sobre `storage.objects`. El intento de asumir el rol `anon` mediante MCP fue rechazado por permisos; no se completó una prueba autenticada con la clave publicable. Una solicitud HTTP sin credenciales a la URL pública recibió HTTP 400, lo cual por sí solo no demuestra el resultado con una clave publicable.
- `verify` descargó los 24 TAR y comprobó las huellas de cada archivo y de los 288 recortes. `restore` recuperó los 288 archivos en otra carpeta local y comprobó sus huellas sin necesitar la caché original.
- Se reprocesó la restauración: los 288 puntos, identificadores y huella de geometría coincidieron exactamente con la serie local SNIT. Esto comprueba recuperación y reproducibilidad de este procesamiento, no valida la ciencia o la frontera.

Referencias: [bucket privado de Supabase](https://supabase.com/docs/guides/storage/buckets/fundamentals), [control de acceso de Storage](https://supabase.com/docs/guides/storage/security/access-control) y [documentación de claves](https://supabase.com/docs/guides/api/api-keys).
