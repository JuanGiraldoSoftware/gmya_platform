"""Planillas de seguridad social: separa el PDF consolidado en un archivo por
persona y genera los TXT (sin Streamlit).

Contrato:
  procesar_planilla(archivo) -> datos de la planilla por persona.
  generar_resultados(planillas, modalidad, plantillas=None) -> archivos
      para descargar.

Depende de: gmya.comun.texto
"""

import io
import re
import unicodedata
import zipfile
from collections import OrderedDict

import streamlit as st

from gmya.comun.texto import decodificar


# ============================================================
# NORMALIZACION Y LECTURA
# ============================================================
def limpiar_linea(linea):
    return linea.rstrip("\r\n")


def normalizar_nombre(nombre):
    nombre = unicodedata.normalize("NFC", nombre)
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre.strip().upper()


def nombre_seguro(nombre, predeterminado="PLANTILLA"):
    nombre = normalizar_nombre(nombre).rstrip(". ")
    return nombre or predeterminado


def nombre_disponible(nombre, existentes):
    if nombre.casefold() not in existentes:
        return nombre

    base = nombre[:-4] if nombre.upper().endswith(".TXT") else nombre
    contador = 2

    while True:
        candidato = f"{base} ({contador}).TXT"

        if candidato.casefold() not in existentes:
            return candidato

        contador += 1


# ============================================================
# IDENTIFICACION
# ============================================================

def extraer_identificacion(linea):
    """
    Extrae el serial del primer campo de la planilla.

    Formatos admitidos:
        001-CC-123456789
        002-CE-987654321
        003-OTROTIPO-123456789
        001CC123456789

    No depende de siglas especificas como CC o CE.
    """

    contenido = limpiar_linea(linea).strip()

    if not contenido:
        return None

    primer_campo = re.split(r"\s+", contenido, maxsplit=1)[0]
    partes = primer_campo.split("-")

    if len(partes) >= 3:
        serial = partes[-1]

        if serial.isdigit():
            return serial

    coincidencia = re.fullmatch(
        r"\d+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)(\d+)",
        primer_campo,
    )

    if coincidencia:
        return coincidencia.group(2)

    return None


# ============================================================
# NOMBRE DE LA PERSONA
# ============================================================

def extraer_nombre_completo(linea):
    """
    Utiliza las posiciones de nombre del codigo original.
    Deben corresponder a la estructura real del TXT.
    """

    contenido = limpiar_linea(linea)

    campos_nombre = [
        contenido[36:56].strip(),
        contenido[56:86].strip(),
        contenido[86:106].strip(),
        contenido[106:126].strip(),
    ]

    nombre = " ".join(
        campo for campo in campos_nombre if campo
    )

    return normalizar_nombre(nombre)


def crear_nombre_persona(nombre, identificacion):
    nombre = nombre_seguro(
        nombre,
        predeterminado=f"COTIZANTE {identificacion}",
    )

    reservados = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    if nombre in reservados:
        nombre = f"PERSONA {nombre}"

    return f"{nombre}.TXT"


# ============================================================
# PROCESAMIENTO DE PLANILLAS
# ============================================================

def procesar_planilla(archivo):
    texto = decodificar(archivo.getvalue())
    lineas = texto.splitlines(keepends=True)

    if not lineas:
        raise ValueError("La planilla esta vacia.")

    cabecera = lineas[0]
    grupos = OrderedDict()
    nombres = {}
    advertencias = []
    sin_identificar = []

    for numero_linea, linea in enumerate(lineas[1:], start=2):
        if not limpiar_linea(linea).strip():
            continue

        identificacion = extraer_identificacion(linea)

        if not identificacion:
            advertencias.append(
                f"Linea {numero_linea}: no se identifico el documento. "
                "El registro no se asigno a ninguna persona; queda en el "
                "archivo REGISTROS SIN IDENTIFICACION para revisarlo."
            )
            # v6.6: el registro no se pierde: va a un TXT aparte.
            sin_identificar.append(linea)
            continue

        nombre = extraer_nombre_completo(linea)

        if identificacion not in grupos:
            grupos[identificacion] = []
            nombres[identificacion] = nombre

        # Todos los registros de una persona permanecen juntos.
        grupos[identificacion].append(linea)

        if not nombres[identificacion] and nombre:
            nombres[identificacion] = nombre

    return {
        "origen": archivo.name,
        "cabecera": cabecera,
        "grupos": grupos,
        "nombres": nombres,
        "advertencias": advertencias,
        "sin_identificar": sin_identificar,
    }


# ============================================================
# UTILIDADES DE ESTADO
# ============================================================

def invalidar_resultado():
    st.session_state.pop("resultado_gmya", None)


def agregar_plantilla(indice_planilla, clave_seleccion, clave_nombre):
    seleccion = st.session_state.get(clave_seleccion, [])
    nombre = st.session_state.get(clave_nombre, "").strip()

    if not seleccion:
        st.session_state["mensaje_gmya"] = (
            "Selecciona al menos una persona antes de agregar la plantilla."
        )
        return

    plantillas = st.session_state.get("plantillas_gmya", [])

    asignadas = {
        (p["indice_planilla"], identificacion)
        for p in plantillas
        for identificacion in p["identificaciones"]
    }

    duplicadas = [
        identificacion
        for identificacion in seleccion
        if (indice_planilla, identificacion) in asignadas
    ]

    if duplicadas:
        st.session_state["mensaje_gmya"] = (
            "Una o mas personas ya estan asignadas a otra plantilla."
        )
        return

    siguiente_id = st.session_state.get("siguiente_id_plantilla", 1)

    if not nombre:
        nombre = f"PLANTILLA {siguiente_id}"

    plantillas.append({
        "id": siguiente_id,
        "nombre": nombre_seguro(nombre),
        "indice_planilla": indice_planilla,
        "identificaciones": list(seleccion),
    })

    st.session_state["plantillas_gmya"] = plantillas
    st.session_state["siguiente_id_plantilla"] = siguiente_id + 1

    # Limpiar controles antes de redibujar la interfaz.
    st.session_state[clave_seleccion] = []
    st.session_state[clave_nombre] = ""

    st.session_state["mensaje_gmya"] = (
        f"Plantilla agregada: {nombre}. "
        f"Personas seleccionadas: {len(seleccion)}."
    )

    invalidar_resultado()


def eliminar_plantilla(identificador):
    plantillas = st.session_state.get("plantillas_gmya", [])

    st.session_state["plantillas_gmya"] = [
        p for p in plantillas
        if p["id"] != identificador
    ]

    st.session_state["mensaje_gmya"] = "Plantilla eliminada."
    invalidar_resultado()


# ============================================================
# GENERACION DE RESULTADOS
# ============================================================

def codificar_txt(contenido):
    return contenido.encode("latin-1", errors="replace")


def generar_resultados(planillas, modalidad, plantillas=None):
    resultados = OrderedDict()
    informe = []

    total_personas = 0
    total_registros = 0
    total_advertencias = 0

    plantillas = plantillas or []

    # Identificaciones asignadas a plantillas compuestas,
    # separadas por planilla de origen.
    asignadas_por_planilla = {}

    for plantilla in plantillas:
        indice = plantilla["indice_planilla"]

        asignadas_por_planilla.setdefault(indice, set())
        asignadas_por_planilla[indice].update(
            plantilla["identificaciones"]
        )

    # Resumen de las planillas procesadas.
    for planilla in planillas:
        cantidad_personas = len(planilla["grupos"])
        cantidad_registros = sum(
            len(registros)
            for registros in planilla["grupos"].values()
        )

        total_personas += cantidad_personas
        total_registros += cantidad_registros
        total_advertencias += len(planilla["advertencias"])

        informe.extend([
            f"Planilla de origen: {planilla['origen']}",
            f"Personas identificadas: {cantidad_personas}",
            f"Registros identificados: {cantidad_registros}",
            f"Modalidad: {modalidad}",
        ])

        informe.extend(planilla["advertencias"])
        informe.append("-" * 60)

    # --------------------------------------------------------
    # MODALIDAD 1: INDIVIDUALIZAR TODAS LAS PERSONAS
    # --------------------------------------------------------

    if modalidad == "Individualizar":
        for planilla in planillas:
            for identificacion, registros in planilla["grupos"].items():
                nombre = crear_nombre_persona(
                    planilla["nombres"].get(identificacion, ""),
                    identificacion,
                )

                nombre = nombre_disponible(nombre, resultados)

                contenido = planilla["cabecera"] + "".join(registros)
                resultados[nombre] = codificar_txt(contenido)

                informe.append(
                    f"{nombre} | Registros: {len(registros)}"
                )

    # --------------------------------------------------------
    # MODALIDAD 2: PLANTILLAS PERSONALIZADAS + RESTANTES
    # --------------------------------------------------------

    else:
        # Primero generar los TXT compuestos elegidos por el usuario.
        for plantilla in plantillas:
            indice = plantilla["indice_planilla"]
            planilla = planillas[indice]

            partes = [planilla["cabecera"]]
            cantidad_registros = 0

            for identificacion in plantilla["identificaciones"]:
                registros = planilla["grupos"].get(
                    identificacion, []
                )

                partes.extend(registros)
                cantidad_registros += len(registros)

            base = nombre_seguro(
                plantilla["nombre"],
                predeterminado=f"PLANTILLA_{plantilla['id']}",
            )

            nombre = nombre_disponible(
                f"{base}.TXT",
                resultados,
            )

            resultados[nombre] = codificar_txt("".join(partes))

            informe.append(
                f"{nombre} | "
                f"Planilla de origen: {planilla['origen']} | "
                f"Personas: {len(plantilla['identificaciones'])} | "
                f"Registros: {cantidad_registros}"
            )

        # Todas las personas no asignadas se individualizan.
        for indice, planilla in enumerate(planillas):
            asignadas = asignadas_por_planilla.get(indice, set())
            individuales = 0

            for identificacion, registros in planilla["grupos"].items():
                if identificacion in asignadas:
                    continue

                nombre = crear_nombre_persona(
                    planilla["nombres"].get(identificacion, ""),
                    identificacion,
                )

                nombre = nombre_disponible(nombre, resultados)

                contenido = planilla["cabecera"] + "".join(registros)
                resultados[nombre] = codificar_txt(contenido)

                individuales += 1

                informe.append(
                    f"{nombre} | Individual automatico | "
                    f"Registros: {len(registros)}"
                )

            informe.append(
                f"Personas individualizadas automaticamente "
                f"desde {planilla['origen']}: {individuales}"
            )

    # --------------------------------------------------------
    # CREAR ZIP
    # --------------------------------------------------------

    memoria = io.BytesIO()

    with zipfile.ZipFile(
        memoria,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as paquete:
        for nombre, contenido in resultados.items():
            paquete.writestr(nombre, contenido)
        # v6.6: registros sin identificacion, aparte (antes se perdian).
        for planilla in planillas:
            if planilla.get("sin_identificar"):
                base = re.sub(r"\.[^.]+$", "", str(planilla["origen"]))
                paquete.writestr(
                    nombre_seguro(f"REGISTROS SIN IDENTIFICACION - {base}")
                    + ".TXT",
                    codificar_txt(planilla["cabecera"] + "".join(
                        planilla["sin_identificar"])))

        paquete.writestr(
            "INFORME_PROCESAMIENTO.TXT",
            "\n".join(informe).encode("utf-8"),
        )

    return {
        "zip": memoria.getvalue(),
        "nombres": list(resultados.keys()),
        "personas": total_personas,
        "registros": total_registros,
        "cantidad_txt": len(resultados),
        "advertencias": total_advertencias,
        "informe": "\n".join(informe),
        "modalidad": modalidad,
    }
