// Logica del dashboard: formulario, calculo de dias, calendario y deteccion de solapamientos.

const form = document.getElementById("form-vacaciones");
const formLogin = document.getElementById("form-login");
const panelLogin = document.getElementById("panel-login");
const panelAplicacion = document.getElementById("panel-aplicacion");
const mensajeLogin = document.getElementById("mensaje-login");
const responsableActivo = document.getElementById("responsable-activo");
const datosResponsable = document.getElementById("datos-responsable");
const cerrarSesion = document.getElementById("cerrar-sesion");
const inputInicio = document.getElementById("fecha_inicio");
const inputFin = document.getElementById("fecha_fin");
const inputDias = document.getElementById("dias_completos");
const tiposPeticion = Array.from(document.querySelectorAll("input[name='tipos_peticion']"));
const mensajeDiv = document.getElementById("mensaje");
const tablaBody = document.querySelector("#tabla-peticiones tbody");
const tituloFormulario = document.getElementById("titulo-formulario");
const botonFormulario = document.getElementById("boton-formulario");
const cancelarEdicion = document.getElementById("cancelar-edicion");

const modal = document.getElementById("modal-conflicto");
const modalMensaje = document.getElementById("modal-mensaje");
const modalCancelar = document.getElementById("modal-cancelar");
const modalContinuar = document.getElementById("modal-continuar");
const modalEliminacion = document.getElementById("modal-eliminacion");
const eliminarCancelar = document.getElementById("eliminar-cancelar");
const eliminarConfirmar = document.getElementById("eliminar-confirmar");

const calendarioDiv = document.getElementById("calendario");
const tituloMes = document.getElementById("titulo-mes");
const btnMesAnterior = document.getElementById("mes-anterior");
const btnMesSiguiente = document.getElementById("mes-siguiente");

const NOMBRES_MES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];
const DIAS_SEMANA = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"];

let fechaCalendario = new Date();
let diasOcupados = new Set();
let peticionPendiente = null;
let peticionEnEdicion = null;
let peticionPendienteEliminar = null;

function mostrarAplicacion(responsable) {
  panelLogin.classList.add("oculto");
  panelAplicacion.classList.remove("oculto");
  responsableActivo.classList.remove("oculto");
  datosResponsable.textContent = `Responsable: ${responsable.matricula} | Seccion: ${responsable.seccion}`;
  cargarPeticiones();
}

function mostrarLogin() {
  panelLogin.classList.remove("oculto");
  panelAplicacion.classList.add("oculto");
  responsableActivo.classList.add("oculto");
}

formLogin.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const respuesta = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      matricula: document.getElementById("login-matricula").value.trim(),
      seccion: document.getElementById("login-seccion").value.trim(),
    }),
  });
  const resultado = await respuesta.json();
  if (resultado.success) {
    mostrarAplicacion(resultado.responsable);
  } else {
    mensajeLogin.textContent = resultado.message;
    mensajeLogin.className = "mensaje error";
  }
});

cerrarSesion.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  mostrarLogin();
});

function calcularDias() {
  if (!inputInicio.value || !inputFin.value) {
    inputDias.value = "";
    return;
  }
  const inicio = new Date(inputInicio.value);
  const fin = new Date(inputFin.value);
  const diferencia = Math.round((fin - inicio) / (1000 * 60 * 60 * 24)) + 1;
  inputDias.value = diferencia > 0 ? diferencia : "";
}

inputInicio.addEventListener("change", calcularDias);
inputFin.addEventListener("change", calcularDias);

function mostrarMensaje(texto, tipo) {
  mensajeDiv.textContent = texto;
  mensajeDiv.className = `mensaje ${tipo}`;
  mensajeDiv.classList.remove("oculto");
}

function formatoFecha(dateObj) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  const d = String(dateObj.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

async function cargarPeticiones() {
  const [respuestaPeticiones, respuestaFechas] = await Promise.all([
    fetch("/api/peticiones"),
    fetch("/api/fechas-ocupadas"),
  ]);
  const datos = await respuestaPeticiones.json();
  const fechasOcupadas = await respuestaFechas.json();
  window.peticionesActuales = datos;

  tablaBody.innerHTML = "";
  diasOcupados = new Set(fechasOcupadas);

  datos.forEach((p) => {
    const fila = document.createElement("tr");
    fila.innerHTML = `
      <td>${p.nombre_operario}</td>
      <td>${p.matricula}</td>
      <td class="tipo-dias">${(p.tipo_peticion || "Dias de vacaciones").replace(", ", ",<br>")}</td>
      <td class="fecha-peticion">${p.fecha_inicio}</td>
      <td class="fecha-peticion">${p.fecha_fin}</td>
      <td>${p.dias_completos}</td>
      <td>${p.responsable_matricula || "-"}</td>
      <td>${p.responsable_seccion || "-"}</td>
      <td class="acciones">
        <button class="boton-editar" data-accion="editar" data-id="${p.id}">Editar</button>
        <button class="boton-eliminar" data-accion="eliminar" data-id="${p.id}">Borrar</button>
      </td>
    `;
    tablaBody.appendChild(fila);

  });

  dibujarCalendario();
}

function prepararEdicion(peticion) {
  peticionEnEdicion = peticion;
  document.getElementById("nombre_operario").value = peticion.nombre_operario;
  document.getElementById("matricula").value = peticion.matricula;
  tiposPeticion.forEach((tipo) => {
    tipo.checked = (peticion.tipo_peticion || "Dias de vacaciones")
      .split(", ").includes(tipo.value);
  });
  inputInicio.value = peticion.fecha_inicio;
  inputFin.value = peticion.fecha_fin;
  calcularDias();
  tituloFormulario.textContent = "Editar peticion";
  botonFormulario.textContent = "Guardar cambios";
  cancelarEdicion.classList.remove("oculto");
  document.querySelector(".formulario").scrollIntoView({ behavior: "smooth" });
}

function cancelarModoEdicion() {
  peticionEnEdicion = null;
  form.reset();
  inputDias.value = "";
  tituloFormulario.textContent = "Nueva peticion";
  botonFormulario.textContent = "Solicitar vacaciones";
  cancelarEdicion.classList.add("oculto");
}

tablaBody.addEventListener("click", (evento) => {
  const boton = evento.target.closest("button[data-accion]");
  if (!boton) return;
  const peticiones = Array.from(tablaBody.querySelectorAll("tr"));
  const fila = boton.closest("tr");
  const indice = peticiones.indexOf(fila);
  const peticion = window.peticionesActuales[indice];
  if (!peticion) return;
  if (boton.dataset.accion === "editar") prepararEdicion(peticion);
  if (boton.dataset.accion === "eliminar") {
    peticionPendienteEliminar = peticion;
    modalEliminacion.classList.remove("oculto");
  }
});

function dibujarCalendario() {
  calendarioDiv.innerHTML = "";

  DIAS_SEMANA.forEach((dia) => {
    const celda = document.createElement("div");
    celda.className = "dia-semana";
    celda.textContent = dia;
    calendarioDiv.appendChild(celda);
  });

  const anio = fechaCalendario.getFullYear();
  const mes = fechaCalendario.getMonth();
  tituloMes.textContent = `${NOMBRES_MES[mes]} ${anio}`;

  const primerDiaSemana = new Date(anio, mes, 1).getDay();
  const desplazamiento = (primerDiaSemana + 6) % 7; // lunes = 0
  const diasEnMes = new Date(anio, mes + 1, 0).getDate();

  for (let i = 0; i < desplazamiento; i++) {
    const vacio = document.createElement("div");
    vacio.className = "dia-celda vacio";
    calendarioDiv.appendChild(vacio);
  }

  for (let dia = 1; dia <= diasEnMes; dia++) {
    const celda = document.createElement("div");
    const fechaStr = formatoFecha(new Date(anio, mes, dia));
    celda.className = "dia-celda" + (diasOcupados.has(fechaStr) ? " ocupado" : "");
    celda.textContent = dia;
    calendarioDiv.appendChild(celda);
  }
}

btnMesAnterior.addEventListener("click", () => {
  fechaCalendario.setMonth(fechaCalendario.getMonth() - 1);
  dibujarCalendario();
});

btnMesSiguiente.addEventListener("click", () => {
  fechaCalendario.setMonth(fechaCalendario.getMonth() + 1);
  dibujarCalendario();
});

async function enviarPeticion(datos, forzar = false) {
  const url = peticionEnEdicion
    ? `/api/peticiones/${peticionEnEdicion.id}`
    : "/api/peticiones";
  const respuesta = await fetch(url, {
    method: peticionEnEdicion ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...datos, forzar }),
  });
  return respuesta.json();
}

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mensajeDiv.classList.add("oculto");

  const datos = {
    nombre_operario: document.getElementById("nombre_operario").value.trim(),
    matricula: document.getElementById("matricula").value.trim(),
    fecha_inicio: inputInicio.value,
    fecha_fin: inputFin.value,
    tipos_peticion: tiposPeticion.filter((tipo) => tipo.checked).map((tipo) => tipo.value),
  };

  const resultado = await enviarPeticion(datos, false);

  if (resultado.conflict) {
    peticionPendiente = datos;
    modalMensaje.textContent = resultado.message;
    modal.classList.remove("oculto");
    return;
  }

  if (resultado.success) {
    mostrarMensaje(resultado.message, "exito");
    cancelarModoEdicion();
    cargarPeticiones();
  } else {
    mostrarMensaje(resultado.message || "Ha ocurrido un error.", "error");
  }
});

modalCancelar.addEventListener("click", () => {
  modal.classList.add("oculto");
  peticionPendiente = null;
});

modalContinuar.addEventListener("click", async () => {
  if (!peticionPendiente) return;
  const resultado = await enviarPeticion(peticionPendiente, true);
  modal.classList.add("oculto");

  if (resultado.success) {
    mostrarMensaje(resultado.message, "exito");
    cancelarModoEdicion();
    cargarPeticiones();
  } else {
    mostrarMensaje(resultado.message || "Ha ocurrido un error.", "error");
  }
  peticionPendiente = null;
});

cancelarEdicion.addEventListener("click", cancelarModoEdicion);

eliminarCancelar.addEventListener("click", () => {
  modalEliminacion.classList.add("oculto");
  peticionPendienteEliminar = null;
});

eliminarConfirmar.addEventListener("click", async () => {
  if (!peticionPendienteEliminar) return;
  const respuesta = await fetch(
    `/api/peticiones/${peticionPendienteEliminar.id}`,
    { method: "DELETE" },
  );
  const resultado = await respuesta.json();
  modalEliminacion.classList.add("oculto");
  peticionPendienteEliminar = null;
  if (resultado.success) {
    mostrarMensaje(resultado.message, "exito");
    if (peticionEnEdicion) cancelarModoEdicion();
    cargarPeticiones();
  } else {
    mostrarMensaje(resultado.message || "Ha ocurrido un error.", "error");
  }
});

fetch("/api/session")
  .then((respuesta) => respuesta.json())
  .then((resultado) => {
    if (resultado.responsable) {
      mostrarAplicacion(resultado.responsable);
    } else {
      mostrarLogin();
    }
  });
