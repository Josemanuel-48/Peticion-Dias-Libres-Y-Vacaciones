"""Pruebas funcionales de la aplicacion de vacaciones.

Se ejecuta con:
    python test.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

import database


class PruebasAplicacion(unittest.TestCase):
    """Pruebas de integracion HTTP con una base de datos SQLite temporal."""

    @classmethod
    def setUpClass(cls):
        """Configura una base aislada y carga la aplicacion en modo de prueba."""
        cls.directorio_temporal = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(cls.directorio_temporal.name) / "pruebas.sqlite"

        # La aplicacion inicializa la base de datos al importarse; se vuelve a
        # cargar despues de redirigir DB_PATH para no tocar la base real.
        sys.modules.pop("app", None)
        import app

        cls.app = app.app
        cls.app.config.update(TESTING=True, SECRET_KEY="clave-de-pruebas")

    @classmethod
    def tearDownClass(cls):
        """Elimina el directorio temporal al terminar toda la suite."""
        cls.directorio_temporal.cleanup()

    def setUp(self):
        """Deja las tablas sin peticiones y crea un cliente HTTP nuevo por prueba."""
        database.init_db()
        conexion = database.get_connection()
        try:
            conexion.execute("DELETE FROM peticiones")
            conexion.commit()
        finally:
            conexion.close()
        self.cliente = self.app.test_client()

    def iniciar_sesion(self, matricula="RESP-01", seccion="Produccion"):
        """Autentica el cliente de prueba con los datos de responsable indicados."""
        return self.cliente.post(
            "/api/login",
            json={"matricula": matricula, "seccion": seccion},
        )

    def crear_peticion(self, matricula="OP-01", inicio="2099-01-10", fin="2099-01-12"):
        """Crea una peticion con valores comunes y permite cambiar operario y fechas."""
        return self.cliente.post(
            "/api/peticiones",
            json={
                "nombre_operario": "Operario de prueba",
                "matricula": matricula,
                "fecha_inicio": inicio,
                "fecha_fin": fin,
            },
        )

    def test_api_protegida_sin_login(self):
        """Las rutas privadas rechazan clientes que no tienen una sesion activa."""
        respuesta = self.cliente.get("/api/peticiones")
        self.assertEqual(respuesta.status_code, 401)

    def test_login_sesion_y_pagina_principal(self):
        """La pagina carga antes y despues del login y la API conserva la sesion."""
        pagina_antes = self.cliente.get("/")
        self.assertEqual(pagina_antes.status_code, 200)
        self.assertIn("form-login", pagina_antes.get_data(as_text=True))

        login = self.iniciar_sesion("RESP-01", "Produccion")
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["success"])

        sesion = self.cliente.get("/api/session")
        self.assertEqual(sesion.status_code, 200)
        self.assertEqual(
            sesion.get_json()["responsable"],
            {"matricula": "RESP-01", "seccion": "PRODUCCION"},
        )

        pagina_despues = self.cliente.get("/")
        self.assertEqual(pagina_despues.status_code, 200)
        self.assertIn("panel-aplicacion", pagina_despues.get_data(as_text=True))

    def test_peticion_guarda_responsable(self):
        """Cada nueva peticion queda asociada al responsable que la envio."""
        self.iniciar_sesion("RESP-01", "Produccion")
        respuesta = self.crear_peticion()
        self.assertEqual(respuesta.status_code, 200)

        peticiones = self.cliente.get("/api/peticiones").get_json()
        self.assertEqual(len(peticiones), 1)
        self.assertEqual(peticiones[0]["responsable_matricula"], "RESP-01")
        self.assertEqual(peticiones[0]["responsable_seccion"], "PRODUCCION")

    def test_peticion_guarda_varios_tipos_de_dias(self):
        """La API almacena y confirma correctamente una seleccion de varios tipos."""
        self.iniciar_sesion()
        respuesta = self.cliente.post(
            "/api/peticiones",
            json={
                "nombre_operario": "Operario de prueba",
                "matricula": "OP-01",
                "tipos_peticion": ["Dias libres", "Dias de jornada industrial"],
                "fecha_inicio": "2099-06-10",
                "fecha_fin": "2099-06-12",
            },
        )

        self.assertTrue(respuesta.get_json()["success"])
        peticion = self.cliente.get("/api/peticiones").get_json()[0]
        self.assertEqual(
            peticion["tipo_peticion"],
            "Dias libres, Dias de jornada industrial",
        )
        self.assertIn("Dias libres, Dias de jornada industrial", respuesta.get_json()["message"])

    def test_peticion_aparece_despues_de_salir_y_volver_a_entrar(self):
        """Las peticiones persisten y vuelven a estar visibles tras reautenticarse."""
        self.iniciar_sesion("jefe-01", "Produccion")
        self.crear_peticion("OP-01", "2099-05-10", "2099-05-12")
        self.assertEqual(len(self.cliente.get("/api/peticiones").get_json()), 1)

        self.cliente.post("/api/logout")
        login = self.cliente.post(
            "/api/login",
            json={"matricula": "JEFE-01", "seccion": "PRODUCCION"},
        )
        self.assertTrue(login.get_json()["success"])
        peticiones = self.cliente.get("/api/peticiones").get_json()
        self.assertEqual(len(peticiones), 1)
        self.assertEqual(peticiones[0]["nombre_operario"], "Operario de prueba")

    def test_responsables_solo_ven_sus_peticiones(self):
        """Las consultas y fechas ocupadas estan aisladas por seccion responsable."""
        self.iniciar_sesion("RESP-A", "Produccion")
        self.crear_peticion("OP-A", "2099-02-10", "2099-02-11")

        otro_cliente = self.app.test_client()
        otro_cliente.post(
            "/api/login",
            json={"matricula": "RESP-B", "seccion": "Mantenimiento"},
        )
        otro_cliente.post(
            "/api/peticiones",
            json={
                "nombre_operario": "Operario B",
                "matricula": "OP-B",
                "fecha_inicio": "2099-02-20",
                "fecha_fin": "2099-02-21",
            },
        )

        peticiones_a = self.cliente.get("/api/peticiones").get_json()
        peticiones_b = otro_cliente.get("/api/peticiones").get_json()
        self.assertEqual(len(peticiones_a), 1)
        self.assertEqual(peticiones_a[0]["responsable_matricula"], "RESP-A")
        self.assertEqual(len(peticiones_b), 1)
        self.assertEqual(peticiones_b[0]["responsable_matricula"], "RESP-B")

        fechas = self.cliente.get("/api/fechas-ocupadas").get_json()
        self.assertEqual(set(fechas), {"2099-02-10", "2099-02-11"})
        self.assertTrue(all(isinstance(fecha, str) for fecha in fechas))

        fechas_b = otro_cliente.get("/api/fechas-ocupadas").get_json()
        self.assertEqual(set(fechas_b), {"2099-02-20", "2099-02-21"})

    def test_otra_seccion_no_muestra_ni_bloquea_fechas(self):
        """Una peticion de otra seccion no se muestra ni provoca un conflicto."""
        self.iniciar_sesion("RESP-A", "Produccion")
        self.crear_peticion("OP-A", "2099-07-10", "2099-07-12")

        otra_seccion = self.app.test_client()
        otra_seccion.post(
            "/api/login",
            json={"matricula": "RESP-B", "seccion": "Mantenimiento"},
        )
        self.assertEqual(
            otra_seccion.get("/api/fechas-ocupadas").get_json(),
            [],
        )
        respuesta = otra_seccion.post(
            "/api/peticiones",
            json={
                "nombre_operario": "Operario B",
                "matricula": "OP-B",
                "fecha_inicio": "2099-07-10",
                "fecha_fin": "2099-07-12",
            },
        )
        self.assertTrue(respuesta.get_json()["success"])

    def test_conflicto_no_revela_datos(self):
        """Los solapamientos se notifican sin exponer los datos de otras peticiones."""
        self.iniciar_sesion()
        self.crear_peticion("OP-01", "2099-03-10", "2099-03-12")
        conflicto = self.crear_peticion("OP-02", "2099-03-11", "2099-03-13")
        datos = conflicto.get_json()

        self.assertTrue(datos["conflict"])
        self.assertNotIn("solapamientos", datos)

    def test_editar_y_eliminar_solo_para_su_responsable(self):
        """Permite editar y borrar la propia peticion, pero no la de otro responsable."""
        self.iniciar_sesion("RESP-A", "Produccion")
        creada = self.crear_peticion("OP-A", "2099-04-10", "2099-04-11")
        peticion_id = creada.get_json()["id"]

        otro_cliente = self.app.test_client()
        otro_cliente.post(
            "/api/login",
            json={"matricula": "RESP-B", "seccion": "Mantenimiento"},
        )
        borrado_ajeno = otro_cliente.delete(f"/api/peticiones/{peticion_id}")
        self.assertEqual(borrado_ajeno.status_code, 404)

        editada = self.cliente.put(
            f"/api/peticiones/{peticion_id}",
            json={
                "nombre_operario": "Operario actualizado",
                "matricula": "OP-A",
                "fecha_inicio": "2099-04-12",
                "fecha_fin": "2099-04-14",
            },
        )
        self.assertTrue(editada.get_json()["success"])
        peticiones = self.cliente.get("/api/peticiones").get_json()
        self.assertEqual(peticiones[0]["fecha_inicio"], "2099-04-12")
        self.assertEqual(peticiones[0]["dias_completos"], 3)

        borrada = self.cliente.delete(f"/api/peticiones/{peticion_id}")
        self.assertTrue(borrada.get_json()["success"])
        self.assertEqual(self.cliente.get("/api/peticiones").get_json(), [])


if __name__ == "__main__":
    # Conserva el codigo de salida de la suite para automatizaciones y CI.
    resultado = unittest.main(verbosity=2, exit=False)
    raise SystemExit(0 if resultado.result.wasSuccessful() else 1)
