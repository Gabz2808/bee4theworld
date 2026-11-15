# Acceso a Supabase y diagnóstico local

## Acceso mediante MCP

El 14 de noviembre de 2026 se verificó el acceso mediante la herramienta MCP de Supabase: una consulta `SELECT 1` respondió correctamente y se consultaron metadatos de las tablas públicas. El usuario confirmó que esta es la base que usará Iyök y que los datos proceden de Giovanni. La base contiene una ingesta etiquetada como precipitación IMERG para Costa Rica continental, con 288 registros mensuales de 2001 a 2024. No se ha validado independientemente la procedencia, calidad o procesamiento de los datos.

Para consultas mediante este MCP ya conectado no se necesitan las variables, el certificado ni Psycopg descritos abajo. El acceso MCP tampoco demuestra que la aplicación o una conexión PostgreSQL desde el equipo estén configuradas. No se comprobó que las credenciales del MCP tengan permisos exclusivos de lectura: limitar las consultas a lectura y evitar cambios sin autorización.

## Diagnóstico directo opcional desde el equipo

Para el diagnóstico local se instaló `psycopg[binary]==3.3.9` en `.tools/supabase-venv`, separado de las dependencias de la API. No define la arquitectura del backend ni implica que se haya conectado un proyecto. Para recrearlo, desde la raíz, con Python 3.12 disponible:

```powershell
py -3.12 -m venv .tools/supabase-venv
.tools/supabase-venv/Scripts/python.exe -m pip install 'psycopg[binary]==3.3.9'
.tools/supabase-venv/Scripts/python.exe -m pip check
```

Para ejecutar el script de diagnóstico directo de este repositorio hacen falta una cadena de conexión para un **rol de solo lectura**, el certificado CA de ese proyecto y permisos sobre las tablas que se deseen revisar. El 14 de noviembre el script informó que faltaba configurar `IYOK_SUPABASE_DB_URL` o `IYOK_SUPABASE_CA_CERT`; no se comprobó la conexión directa. El propietario o equipo de backend debe proporcionar el acceso por un canal seguro; no guardar contraseñas, claves o cadenas de conexión en el repositorio. Un proyecto nuevo no contiene automáticamente los datos de otro proyecto de Supabase.

El script `scripts/comprobar_supabase.py` lee `IYOK_SUPABASE_DB_URL` y `IYOK_SUPABASE_CA_CERT` del proceso; en Windows, si faltan, también consulta las variables de usuario. Usa `sslmode=verify-full` con el certificado indicado, establece una transacción de solo lectura y ejecuta una consulta de diagnóstico. La transacción de solo lectura no sustituye a un rol con permisos limitados. No imprime la cadena de conexión ni los mensajes internos del controlador.

```powershell
.tools/supabase-venv/Scripts/python.exe scripts/comprobar_supabase.py
```

La URL y el modo de conexión se obtienen desde **Connect** en el panel del proyecto. La conexión directa puede requerir IPv6; Supabase ofrece el pooler de sesión como alternativa para redes IPv4. El certificado CA se descarga desde la configuración de la base de datos. Para la conexión de frontend prevista por Iyök, el contrato con la API del compañero sigue pendiente; no exponer credenciales de base de datos, claves secretas ni `service_role` al navegador. Fuentes: [conexión a PostgreSQL](https://supabase.com/docs/guides/database/connecting-to-postgres) y [claves de API](https://supabase.com/docs/guides/getting-started/api-keys).
