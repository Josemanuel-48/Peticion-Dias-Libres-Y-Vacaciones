"""Aplicacion Flask: Dashboard de Peticion de Vacaciones Personales."""
from datetime import datetime
import os
from functools import wraps

from flask import Flask, jsonify, render_template, request, session

import database

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "clave-local-vacaciones")
database.init_db()

TIPOS_PETICION = {
    "Dias libres",
    "Dias de vacaciones",
    "Dias de jornada industrial",
}


def obtener_tipo_peticion(datos):
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
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "responsable" not in session:
            return jsonify({"success": False, "message": "Debe iniciar sesion."}), 401
        return funcion(*args, **kwargs)

    return envoltura


def calcular_dias_completos(fecha_inicio: str, fecha_fin: str) -> int:
    inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
    fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    return (fin - inicio).days + 1


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/login", methods=["POST"])
def iniciar_sesion():
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
    return jsonify({"responsable": session.get("responsable")})


@app.route("/api/logout", methods=["POST"])
def cerrar_sesion():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/peticiones", methods=["GET"])
@responsable_requerido
def listar_peticiones():
    responsable = session["responsable"]
    return jsonify(database.obtener_peticiones(
        responsable["matricula"], responsable["seccion"]
    ))


@app.route("/api/fechas-ocupadas", methods=["GET"])
@responsable_requerido
def listar_fechas_ocupadas():
    return jsonify(database.obtener_fechas_ocupadas())


@app.route("/api/peticiones", methods=["POST"])
@responsable_requerido
def crear_peticion():
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

    solapamientos = database.obtener_solapamientos(fecha_inicio, fecha_fin)

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

    solapamientos = database.obtener_solapamientos(
        fecha_inicio, fecha_fin, excluir_id=peticion_id
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
    responsable = session["responsable"]
    eliminado = database.eliminar_peticion(
        peticion_id, responsable["matricula"], responsable["seccion"]
    )
    if not eliminado:
        return jsonify({"success": False, "message": "La peticion no existe."}), 404
    return jsonify({"success": True, "message": "La peticion se ha eliminado correctamente."})


if __name__ == "__main__":
    app.run(debug=True)
