"""Capa de acceso a datos: creación de la base de datos SQLite y operaciones CRUD
sobre la tabla de peticiones de vacaciones."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "vacaciones.db"
SQLITE_TIMEOUT_SECONDS = 30


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db():
    """Crea la tabla 'peticiones' si no existe."""
    conn = get_connection()
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS peticiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_operario TEXT NOT NULL,
            matricula TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            dias_completos INTEGER NOT NULL,
            tipo_peticion TEXT NOT NULL DEFAULT 'Dias de vacaciones',
            responsable_matricula TEXT,
            responsable_seccion TEXT,
            creado_en TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    columnas = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(peticiones)")
    }
    if "responsable_matricula" not in columnas:
        conn.execute("ALTER TABLE peticiones ADD COLUMN responsable_matricula TEXT")
    if "responsable_seccion" not in columnas:
        conn.execute("ALTER TABLE peticiones ADD COLUMN responsable_seccion TEXT")
    if "tipo_peticion" not in columnas:
        conn.execute(
            "ALTER TABLE peticiones ADD COLUMN tipo_peticion TEXT "
            "NOT NULL DEFAULT 'Dias de vacaciones'"
        )
    conn.execute(
        "UPDATE peticiones SET responsable_matricula = UPPER(responsable_matricula), "
        "responsable_seccion = UPPER(responsable_seccion) "
        "WHERE responsable_matricula IS NOT NULL OR responsable_seccion IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_peticiones_responsable "
        "ON peticiones (responsable_matricula, responsable_seccion)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_peticiones_fechas "
        "ON peticiones (fecha_inicio, fecha_fin)"
    )
    conn.commit()
    conn.close()


def obtener_peticiones(responsable_matricula=None, responsable_seccion=None):
    conn = get_connection()
    query = "SELECT * FROM peticiones"
    params = []
    if responsable_matricula is not None and responsable_seccion is not None:
        query += " WHERE responsable_matricula = ? AND responsable_seccion = ?"
        params.extend([responsable_matricula, responsable_seccion])
    query += " ORDER BY fecha_inicio ASC"
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(fila) for fila in filas]


def obtener_fechas_ocupadas(responsable_seccion):
    conn = get_connection()
    filas = conn.execute(
        "SELECT fecha_inicio, fecha_fin FROM peticiones "
        "WHERE responsable_seccion = ?",
        (responsable_seccion,),
    ).fetchall()
    conn.close()

    fechas = set()
    for fila in filas:
        inicio = datetime.strptime(fila["fecha_inicio"], "%Y-%m-%d").date()
        fin = datetime.strptime(fila["fecha_fin"], "%Y-%m-%d").date()
        while inicio <= fin:
            fechas.add(inicio.isoformat())
            inicio += timedelta(days=1)
    return sorted(fechas)


def obtener_solapamientos(
    fecha_inicio, fecha_fin, responsable_seccion, matricula=None, excluir_id=None
):
    """Devuelve las peticiones existentes cuyo rango de fechas se solapa
    con el rango indicado. Si se pasa matricula, excluye esa matricula
    (para permitir editar/ampliar la propia petición)."""
    conn = get_connection()
    query = (
        "SELECT * FROM peticiones WHERE fecha_inicio <= ? AND fecha_fin >= ? "
        "AND responsable_seccion = ?"
    )
    params = [fecha_fin, fecha_inicio, responsable_seccion]
    if matricula:
        query += " AND matricula != ?"
        params.append(matricula)
    if excluir_id is not None:
        query += " AND id != ?"
        params.append(excluir_id)
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(fila) for fila in filas]


def actualizar_peticion(
    peticion_id,
    nombre_operario,
    matricula,
    fecha_inicio,
    fecha_fin,
    dias_completos,
    tipo_peticion,
    responsable_matricula,
    responsable_seccion,
):
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE peticiones
        SET nombre_operario = ?, matricula = ?, fecha_inicio = ?, fecha_fin = ?,
            dias_completos = ?, tipo_peticion = ?, responsable_matricula = ?,
            responsable_seccion = ?
        WHERE id = ? AND responsable_matricula = ? AND responsable_seccion = ?
        """,
        (
            nombre_operario,
            matricula,
            fecha_inicio,
            fecha_fin,
            dias_completos,
            tipo_peticion,
            responsable_matricula,
            responsable_seccion,
            peticion_id,
            responsable_matricula,
            responsable_seccion,
        ),
    )
    conn.commit()
    actualizado = cursor.rowcount > 0
    conn.close()
    return actualizado


def eliminar_peticion(peticion_id, responsable_matricula, responsable_seccion):
    conn = get_connection()
    cursor = conn.execute(
        """
        DELETE FROM peticiones
        WHERE id = ? AND responsable_matricula = ? AND responsable_seccion = ?
        """,
        (peticion_id, responsable_matricula, responsable_seccion),
    )
    conn.commit()
    eliminado = cursor.rowcount > 0
    conn.close()
    return eliminado


def insertar_peticion(
    nombre_operario,
    matricula,
    fecha_inicio,
    fecha_fin,
    dias_completos,
    tipo_peticion,
    responsable_matricula,
    responsable_seccion,
):
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO peticiones (
            nombre_operario, matricula, fecha_inicio, fecha_fin, dias_completos,
            tipo_peticion, responsable_matricula, responsable_seccion
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            nombre_operario,
            matricula,
            fecha_inicio,
            fecha_fin,
            dias_completos,
            tipo_peticion,
            responsable_matricula,
            responsable_seccion,
        ),
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return nuevo_id
