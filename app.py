"""API Flask para gestionar peticiones de dias libres y vacaciones.

Las rutas sirven la pagina principal y exponen operaciones JSON para la sesion
del responsable, la consulta de disponibilidad y el mantenimiento de peticiones.
"""

from datetime import datetime
import os
from functools import wraps

from flask import Flask, jsonify, render_template, request, session

import database

app = Flask(__name__)
# Flask firma la cookie de sesion con esta clave; en despliegues debe configurarse
# mediante una variable de entorno y no utilizarse el valor local de respaldo.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "clave-local-vacaciones")
# Garantiza que el esquema de almacenamiento este preparado antes de atender rutas.
database.init_db()

# Valores admitidos por la API para evitar guardar categorias arbitrarias.
TIPOS_PETICION = {
    "Dias libres",
    "Dias de vacaciones",
    "Dias de jornada industrial",
}


def obtener_tipo_peticion(datos):
    """Valida las categorias recibidas y devuelve su representacion almacenada.

    Se conserva el tipo de vacaciones predeterminado para clientes antiguos que
    no envian ``tipos_peticion``.
    """
    tipos = datos.get("tipos_peticion")
    if tipos is None:
        return "Dias de vacaciones"
    if not isinstance(tipos, list):
        return None
    tipos_validos = [tipo for tipo in tipos if tipo in TIPOS_PETICION]
    if not tipos_validos or len(tipos_validos) != len(set(tipos)):
        return None
    return ", ".join(tipos_validos)


def responsable_requerido(funcion):
    """Impide acceder a rutas protegidas si no hay responsable en la sesion."""
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "responsable" not in session:
            return jsonify({"success": False, "message": "Debe iniciar sesion."}), 401
        return funcion(*args, **kwargs)

    return envoltura


def calcular_dias_completos(fecha_inicio: str, fecha_fin: str) -> int:
    """Cuenta ambos extremos del intervalo, por lo que un mismo dia cuenta como uno."""
    inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
    fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    return (fin - inicio).days + 1


@app.route("/")
def index():
    """Entrega la interfaz web principal."""
    return render_template("index.html")


@app.route("/api/login", methods=["POST"])
def iniciar_sesion():
    """Inicia una sesion de responsable usando matricula y seccion."""
    datos = request.get_json(force=True) or {}
    matricula = (datos.get("matricula") or "").strip().upper()
    seccion = (datos.get("seccion") or "").strip().upper()

    if not matricula or not seccion:
        return jsonify({
            "success": False,
            "message": "La matricula y la seccion son obligatorias.",
        }), 400

    session["responsable"] = {"matricula": matricula, "seccion": seccion}
    return jsonify({"success": True, "responsable": session["responsable"]})


@app.route("/api/session", methods=["GET"])
def consultar_sesion():
    """Devuelve los datos del responsable autenticado, o ``null`` si no existe."""
    return jsonify({"responsable": session.get("responsable")})


@app.route("/api/logout", methods=["POST"])
def cerrar_sesion():
    """Elimina todos los datos de la sesion actual."""
    session.clear()
    return jsonify({"success": True})


@app.route("/api/peticiones", methods=["GET"])
@responsable_requerido
def listar_peticiones():
    """Lista las peticiones creadas por el responsable de la sesion."""
    responsable = session["responsable"]
    return jsonify(database.obtener_peticiones(
        responsable["matricula"], responsable["seccion"]
    ))


@app.route("/api/fechas-ocupadas", methods=["GET"])
@responsable_requerido
def listar_fechas_ocupadas():
    """Consulta las fechas ocupadas en la seccion del responsable."""
    seccion = session["responsable"]["seccion"]
    return jsonify(database.obtener_fechas_ocupadas(seccion))


@app.route("/api/peticiones", methods=["POST"])
@responsable_requerido
def crear_peticion():
    """Valida y registra una peticion nueva.

    Si ya hay peticiones que coinciden en fechas, solicita confirmacion salvo que
    el cliente reintente enviando ``forzar`` como verdadero.
    """
    datos = request.get_json(force=True) or {}

    nombre_operario = (datos.get("nombre_operario") or "").strip()
    matricula = (datos.get("matricula") or "").strip()
    fecha_inicio = (datos.get("fecha_inicio") or "").strip()
    fecha_fin = (datos.get("fecha_fin") or "").strip()
    tipo_peticion = obtener_tipo_peticion(datos)
    forzar = bool(datos.get("forzar", False))

    if (not nombre_operario or not matricula or not fecha_inicio or not fecha_fin
            or tipo_peticion is None):
        return jsonify({"success": False, "message": "Todos los campos son obligatorios."}), 400

    try:
        dias_completos = calcular_dias_completos(fecha_inicio, fecha_fin)
    except ValueError:
        return jsonify({"success": False, "message": "Formato de fecha invalido."}), 400

    if dias_completos <= 0:
        return jsonify({
            "success": False,
            "message": "La fecha de fin debe ser igual o posterior a la fecha de inicio."
        }), 400

    # La disponibilidad se comprueba por seccion, no solo por operario.
    solapamientos = database.obtener_solapamientos(
        fecha_inicio,
        fecha_fin,
        session["responsable"]["seccion"],
    )

    if solapamientos and not forzar:
        return jsonify({
            "success": False,
            "conflict": True,
            "message": "Error: estos dias ya estan cogidos. ¿Desea continuar con la peticion?",
        }), 200

    nuevo_id = database.insertar_peticion(
        nombre_operario,
        matricula,
        fecha_inicio,
        fecha_fin,
        dias_completos,
        tipo_peticion,
        session["responsable"]["matricula"],
        session["responsable"]["seccion"],
    )

    return jsonify({
        "success": True,
        "id": nuevo_id,
        "dias_completos": dias_completos,
        "message": f"Se ha realizado correctamente: {tipo_peticion}.",
    })


@app.route("/api/peticiones/<int:peticion_id>", methods=["PUT"])
@responsable_requerido
def editar_peticion(peticion_id):
    """Actualiza una peticion existente tras validar fechas y posibles conflictos."""
    datos = request.get_json(force=True) or {}
    nombre_operario = (datos.get("nombre_operario") or "").strip()
    matricula = (datos.get("matricula") or "").strip()
    fecha_inicio = (datos.get("fecha_inicio") or "").strip()
    fecha_fin = (datos.get("fecha_fin") or "").strip()
    tipo_peticion = obtener_tipo_peticion(datos)
    forzar = bool(datos.get("forzar", False))

    if (not nombre_operario or not matricula or not fecha_inicio or not fecha_fin
            or tipo_peticion is None):
        return jsonify({"success": False, "message": "Todos los campos son obligatorios."}), 400

    try:
        dias_completos = calcular_dias_completos(fecha_inicio, fecha_fin)
    except ValueError:
        return jsonify({"success": False, "message": "Formato de fecha invalido."}), 400

    if dias_completos <= 0:
        return jsonify({
            "success": False,
            "message": "La fecha de fin debe ser igual o posterior a la fecha de inicio.",
        }), 400

    # No considerar la propia peticion como conflicto al revisar el nuevo intervalo.
    solapamientos = database.obtener_solapamientos(
        fecha_inicio,
        fecha_fin,
        session["responsable"]["seccion"],
        excluir_id=peticion_id,
    )
    if solapamientos and not forzar:
        return jsonify({
            "success": False,
            "conflict": True,
            "message": "Error: estos dias ya estan cogidos. ¿Desea continuar con la peticion?",
        }), 200

    responsable = session["responsable"]
    actualizado = database.actualizar_peticion(
        peticion_id,
        nombre_operario,
        matricula,
        fecha_inicio,
        fecha_fin,
        dias_completos,
        tipo_peticion,
        responsable["matricula"],
        responsable["seccion"],
    )
    if not actualizado:
        return jsonify({"success": False, "message": "La peticion no existe."}), 404

    return jsonify({
        "success": True,
        "dias_completos": dias_completos,
        "message": f"La peticion se ha actualizado correctamente: {tipo_peticion}.",
    })


@app.route("/api/peticiones/<int:peticion_id>", methods=["DELETE"])
@responsable_requerido
def borrar_peticion(peticion_id):
    """Elimina una peticion solo si pertenece al responsable y a su seccion."""
    responsable = session["responsable"]
    eliminado = database.eliminar_peticion(
        peticion_id, responsable["matricula"], responsable["seccion"]
    )
    if not eliminado:
        return jsonify({"success": False, "message": "La peticion no existe."}), 404
    return jsonify({"success": True, "message": "La peticion se ha eliminado correctamente."})


if __name__ == "__main__":
    # Permite iniciar el servidor de desarrollo ejecutando directamente este archivo.
    app.run(debug=True)
