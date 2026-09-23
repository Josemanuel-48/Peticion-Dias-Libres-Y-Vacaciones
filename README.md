# Peticion De Vacaciones

Dashboard de escritorio (aplicacion web local con Flask) para gestionar peticiones
de vacaciones personales del personal operario. Pensado para que un responsable
registre las peticiones, viendo en un calendario que dias ya estan ocupados por
otros operarios antes de confirmar.

## Que se ha creado

- Entorno virtual de Python (`venv/`) para aislar las dependencias del proyecto.
- `requirements.txt` con las dependencias (Flask).
- `.gitignore` para excluir el entorno virtual, la base de datos y archivos temporales.
- `database.py`: creacion de la base de datos SQLite (`vacaciones.db`) y funciones
  para insertar, consultar, editar, eliminar peticiones y detectar solapamientos.
- `app.py`: servidor Flask con login de responsables, sesiones y la API REST.
- `templates/index.html`: interfaz del dashboard ("Peticion de Vacaciones Personales").
- `static/style.css`: estilos del dashboard (colores, tarjetas, calendario).
- `static/script.js`: logica de front-end (login, calculo de dias, calendario
  mensual, envio, edicion, eliminacion y modal de conflicto).
- `test.py`: pruebas funcionales automatizadas de login, aislamiento y operaciones
  de peticiones.

## Funcionalidad principal

1. El responsable inicia sesion con su matricula y seccion de trabajo.
2. El responsable rellena el nombre del operario, la matricula, la fecha de inicio
  y la fecha de fin. Los dias completos se calculan automaticamente.
3. Al enviar la peticion:
   - Si las fechas no se solapan con otra peticion, se guarda en la base de datos
     y se muestra el mensaje **"Se ha realizado correctamente."**
   - Si las fechas ya estan cogidas por otro operario, el calendario muestra esos
     dias en rojo y aparece un aviso: **"Error: estos dias ya estan cogidos.
     ¿Desea continuar con la peticion?"**. Si el responsable confirma, la peticion
     se guarda igualmente.
4. El calendario mensual (con navegacion de mes anterior/siguiente) pinta en rojo
   todos los dias ya reservados por cualquier operario.
5. Cada responsable solo ve sus propias peticiones. El calendario muestra las fechas
  ocupadas de forma anonima.
6. Las peticiones se pueden editar o eliminar. El borrado requiere confirmacion y
  solo puede realizarlo el responsable que creo la peticion.

## Instalacion y ejecucion

```powershell
cd "Peticion De Vcaciones"
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abrir el navegador en `http://127.0.0.1:5000/`.

La base de datos SQLite (`vacaciones.db`) se crea automaticamente al arrancar
la aplicacion.

Para ejecutar las pruebas:

```powershell
python test.py
```

SQLite esta configurado con WAL, espera de 30 segundos ante bloqueos e indices
para las consultas por responsable y fechas. Esto mejora el uso concurrente de la
aplicacion. Se recomienda realizar copias de seguridad periodicas de `vacaciones.db`.

En un entorno compartido, define una clave de sesion propia antes de arrancar:

```powershell
$env:FLASK_SECRET_KEY = "una-clave-larga-y-segura"
python app.py
```

## Uso en una empresa

Para que varios jefes puedan utilizar la aplicacion, debe instalarse en un
servidor central de la empresa. Los jefes accederan desde sus navegadores y no
necesitaran instalar Python ni copiar la base de datos en sus ordenadores.

La arquitectura recomendada es:

```text
Jefe 1 ─┐
Jefe 2 ─┼── navegador ──> servidor de vacaciones ──> base de datos
Jefe 3 ─┘
```

La direccion podria ser una URL interna como:

```text
https://vacaciones.empresa.local
```

En una primera prueba dentro de la red local tambien se puede utilizar:

```text
http://nombre-del-servidor:5000
```

El departamento de informatica debe encargarse de:

1. Instalar la aplicacion en un servidor encendido y accesible desde la red de
  la empresa.
2. Configurar el firewall para permitir unicamente el acceso necesario.
3. Ejecutar Flask con un servidor de produccion y no con `debug=True`.
4. Configurar HTTPS para proteger las sesiones y los datos.
5. Crear copias de seguridad automaticas de la base de datos.
6. Mantener actualizado Python, Flask y el sistema operativo.

## Acceso a la base de datos

Los jefes no deben abrir ni modificar directamente la base de datos. Solo
utilizan la aplicacion desde el navegador.

El acceso a la base de datos debe quedar limitado a:

- La aplicacion que se ejecuta en el servidor.
- El administrador de sistemas.
- El personal autorizado para mantenimiento y copias de seguridad.

La base de datos no debe colocarse en una carpeta compartida de red. Si se
mantiene SQLite, el archivo `vacaciones.db` debe permanecer en el disco local
del servidor y nunca debe abrirse directamente desde los ordenadores de los
jefes.

## Base de datos para produccion

SQLite es suficiente para una prueba o para pocos accesos simultaneos. Para una
empresa con muchos jefes conectados al mismo tiempo se recomienda PostgreSQL o
SQL Server, porque soportan mejor varios usuarios escribiendo a la vez.

La interfaz y las rutas de la aplicacion pueden mantenerse. Solo se sustituye
la capa de acceso de `database.py` y se configura la conexion al servidor de base
de datos.

## Seguridad del acceso

El login actual usa matricula y seccion y es adecuado para pruebas internas,
pero no es suficiente como autenticacion empresarial: una persona podria
escribir la matricula de otro jefe.

Antes de poner la aplicacion en produccion se recomienda implementar una de
estas opciones:

- Usuario y contrasena almacenados de forma segura.
- Integracion con Active Directory o Microsoft Entra ID.
- Inicio de sesion corporativo mediante SSO.

Cada jefe debe ver unicamente sus propias peticiones. El calendario puede
mostrar las fechas ocupadas de forma anonima. Un administrador autorizado puede
tener una pantalla separada para consultar todas las peticiones.

## Puesta en marcha recomendada

1. Probar la aplicacion en un ordenador de pruebas.
2. Elegir el servidor y decidir entre SQLite, PostgreSQL o SQL Server.
3. Configurar usuarios, permisos, firewall y HTTPS con informatica.
4. Migrar los datos existentes y hacer una copia de seguridad.
5. Publicar la URL interna para los jefes.
6. Ejecutar `python test.py` despues de cada cambio importante.

## Estructura del proyecto

```
Peticion De Vcaciones/
├── app.py
├── database.py
├── requirements.txt
├── test.py
├── .gitignore
├── README.md
├── static/
│   ├── style.css
│   └── script.js
└── templates/
    └── index.html
```
