# Acceso provisional directo a NASA

El backend puede consultar IMERG V07 directamente mediante el catálogo CMR y el servicio NASA Harmony. Este flujo **no es una extracción de Giovanni**; los resultados no deben atribuirse a Giovanni. `IYOK_DATA_SOURCE=nasa` fuerza la consulta directa sin caché. La opción predeterminada `auto` intenta primero usar [la caché Supabase](cache-supabase.md) y, si no encuentra una entrada compatible, consulta NASA.

## Configuración local

1. Iniciar sesión en [NASA Earthdata Login](https://urs.earthdata.nasa.gov/) y obtener un token de usuario siguiendo las [instrucciones oficiales](https://urs.earthdata.nasa.gov/documentation/for_users/user_token). Aceptar las autorizaciones de las aplicaciones y condiciones de datos que NASA requiera para la cuenta.
2. En el equipo, copiar `apps/api/.env.example` a `apps/api/.env` si todavía no existe. Añadir el token en la línea `EARTHDATA_TOKEN=` y usar `IYOK_DATA_SOURCE=nasa` si se desea evitar la caché. No enviar el token al chat, guardarlo en Git ni ponerlo en variables públicas del navegador. El archivo `.env` está ignorado por Git.
3. Reiniciar la API desde `apps/api`, de forma que lea el archivo:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env
   ```

4. Con el frontend ejecutándose, recargar la página y probar primero un período de un mes. Las solicitudes pueden tardar: Harmony debe recuperar y procesar los gránulos. El proxy del frontend tiene un límite de espera de 90 segundos; un período largo puede excederlo y el trabajo remoto podría continuar aun cuando el navegador deje de esperar.

Se verificó una consulta real de enero de 2024: CMR encontró un gránulo, Harmony devolvió un NetCDF y el flujo mediante Next.js y FastAPI respondió HTTP 200 con una observación, unidad original `mm/hr` y unidad de salida `mm/month`. El lector accede al grupo `Grid` y acepta el calendario CF Julian observado en el archivo. Sin token, el servicio responde `NASA_AUTH_REQUIRED`; credenciales rechazadas o errores de NASA se muestran como fallo de servicio sin revelar detalles internos. Esta comprobación de un mes no valida períodos más largos ni la metodología científica.

## Alcance y límites

La geometría predeterminada del repositorio es **aproximada y no validada como frontera oficial de Costa Rica**. La disponibilidad mostrada por el catálogo es declarativa y no garantiza que la descarga funcione. El backend devuelve la unidad original, la conversión, el método espacial, identificadores de gránulos y el instante de acceso para consultas directas; se debe revisar su validez y compararla con Giovanni y con el equipo de backend. El frontend identifica la serie como no validada y no presenta las conclusiones estadísticas. No utilizarla como evidencia científica de la demo hasta validar geometría, producto, procesamiento y método.
