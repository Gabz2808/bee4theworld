"""Prueba local de conexión de solo lectura; no modifica el proyecto remoto."""
import os
import sys

import psycopg


def user_setting(name: str) -> str:
    value = os.environ.get(name, "")
    if value or sys.platform != "win32":
        return value
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value if isinstance(value, str) else ""
    except FileNotFoundError:
        return ""


connection_string = user_setting("IYOK_SUPABASE_DB_URL")
certificate = user_setting("IYOK_SUPABASE_CA_CERT")
if not connection_string or not certificate:
    print("Falta configurar IYOK_SUPABASE_DB_URL o IYOK_SUPABASE_CA_CERT.")
    sys.exit(2)

try:
    with psycopg.connect(
        connection_string,
        sslmode="verify-full",
        sslrootcert=certificate,
        connect_timeout=10,
    ) as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user, current_setting('transaction_read_only')")
            role, readonly = cursor.fetchone()
            if readonly != "on":
                raise RuntimeError("No se pudo establecer la transacción de solo lectura.")
            print(f"Conexión verificada con TLS y transacción de solo lectura. Rol: {role}")
except (psycopg.Error, OSError, ValueError, RuntimeError) as error:
    # Los mensajes del controlador pueden contener datos de conexión.
    print(f"No se pudo verificar la conexión ({type(error).__name__}).")
    sys.exit(1)
