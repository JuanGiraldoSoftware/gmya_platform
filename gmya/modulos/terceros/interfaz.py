"""Pantalla del modulo Creacion de terceros (v6.20).

Contrato:
  modulo_terceros() -> carga el listado de clientes de HELISA, los contactos
      de Alegra y/o el reporte de Medifony (y opcionalmente el resultado de
      la Consulta de Cedulas), muestra que terceros hay que crear, que
      revisar y que esta distinto, y descarga el Excel (formato "A SUBIR A
      HELISA" de la firma). Toda la logica esta en terceros/logica.py.
Depende de: gmya.comun.cache, gmya.ui.componentes, gmya.ui.visual,
gmya.modulos.terceros.logica, gmya.registro.interfaz
"""

import datetime
from collections import Counter

import streamlit as st

from gmya.comun.cache import _cache_datos
from gmya.ui.componentes import banner_modulo, encabezado_carga, titulo_seccion
from gmya.ui.visual import grafico, html_barras, kpis
from gmya.modulos.terceros.logica import (
    CONFIG_TERCEROS, NOMBRE_CLASE, clave_texto, cruzar, excel_terceros,
    leer_consulta_cedulas, leer_helisa_clientes, leer_origenes,
    nombre_archivo,
)
from gmya.registro.interfaz import reportar_error


@_cache_datos
def _helisa(contenido):
    return leer_helisa_clientes(contenido)


@_cache_datos
def _origenes(archivos):
    return leer_origenes(list(archivos))


@_cache_datos
def _consulta(contenido):
    return leer_consulta_cedulas(contenido)


def _parametros(origenes):
    """Valores fijos del archivo a subir y clase de HELISA por tipo de
    documento (solo los tipos que trae el origen)."""
    import pandas as pd
    config = dict(CONFIG_TERCEROS)
    with st.expander("Parámetros del archivo a subir y clases de documento"):
        c1, c2, c3 = st.columns(3)
        config["cartera"] = c1.text_input("CARTERA", config["cartera"],
                                          key="ter_cartera")
        config["naturaleza"] = c2.text_input(
            "NATURALEZA", config["naturaleza"], key="ter_naturaleza")
        config["regimen"] = c3.text_input("REGIMEN", config["regimen"],
                                          key="ter_regimen")
        c1, c2, c3 = st.columns(3)
        config["responsable"] = c1.text_input(
            "RESPONSABLE", config["responsable"], key="ter_responsable")
        config["tipo_persona"] = c2.text_input(
            "Tipo de persona (si el origen no lo trae)",
            config["tipo_persona"], key="ter_tipo_persona")
        config["resp_tributaria"] = c3.text_input(
            "Responsabilidad tributaria (si el origen no la trae)",
            config["resp_tributaria"], key="ter_resp_trib")
        config["incluir_nit"] = st.toggle(
            "Incluir los NIT en el archivo a subir", value=False,
            key="ter_incluir_nit",
            help="Por defecto no: el listado de HELISA es de clientes y los "
                 "NIT que no están suelen ser proveedores (se listan en «No "
                 "se suben» para confirmarlos).")
        tipos = Counter(r["tipo"] for r in origenes["registros"])
        filas = [{"Tipo en el origen": t, "Registros": n,
                  "Clase HELISA": config["clases"].get(clave_texto(t), "")}
                 for t, n in tipos.most_common()]
        st.caption("Clase de HELISA de cada tipo de documento (C cédula, R "
                   "registro civil, T tarjeta de identidad, P pasaporte, X "
                   "cédula de extranjería, D documento extranjero, O otro, A "
                   "NIT). Las de fábrica salen de los terceros que ya están "
                   "creados en HELISA.")
        editada = st.data_editor(
            pd.DataFrame(filas), hide_index=True, use_container_width=True,
            key="ter_clases", column_config={
                "Tipo en el origen": st.column_config.TextColumn(
                    disabled=True),
                "Registros": st.column_config.NumberColumn(disabled=True),
                "Clase HELISA": st.column_config.SelectboxColumn(
                    options=["", "C", "R", "T", "P", "X", "E", "D", "O",
                             "A"])})
        clases = dict(config["clases"])
        for _, fila in editada.iterrows():
            clases[clave_texto(fila["Tipo en el origen"])] = \
                fila["Clase HELISA"] or ""
        config["clases"] = clases
    return config


def modulo_terceros():
    banner_modulo(
        "Módulo 7 · Terceros", "Creación de terceros",
        "Compara los clientes de Alegra y de Medifony con los terceros de "
        "HELISA y arma el archivo para crear los que faltan, con las "
        "cédulas verificadas.",
        ("Alegra", "Medifony", "Consulta de cédulas"))

    titulo_seccion(
        "Archivos", 1,
        "El <b>listado de clientes de HELISA</b> dice quién ya está creado. "
        "El <b>origen</b> es lo que se quiere crear: los contactos de "
        "<b>Alegra</b> (el .zip tal como se descarga, o sus CSV) y/o el "
        "<b>Reporte Facturación Total de Medifony</b>; se reconocen solos. "
        "El resultado de la <b>Consulta de Cédulas</b> es opcional: con él "
        "las cédulas quedan verificadas con nombres y apellidos oficiales.")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga("HELISA", "Clientes de HELISA",
                         "Obligatorio · .xls tal como se descarga",
                         "Listado de clientes de HELISA (Código, Identidad, "
                         "Clase, Nombre…). Solo se lee.")
        f_helisa = st.file_uploader("Clientes HELISA",
                                    type=["xls", "xlsx", "csv"],
                                    key="ter_helisa",
                                    label_visibility="collapsed")
    with c2:
        encabezado_carga("ORIGEN", "Alegra y/o Medifony",
                         "Obligatorio · .zip, .csv, .xlsx o .xls",
                         "Contactos de Alegra (contacts_….zip o sus partes "
                         "CSV, aunque las partes 2 y 3 no traigan títulos) y "
                         "el reporte de facturación de Medifony.")
        f_origen = st.file_uploader("Origen",
                                    type=["zip", "csv", "xlsx", "xls"],
                                    accept_multiple_files=True,
                                    key="ter_origen",
                                    label_visibility="collapsed")
    encabezado_carga("CC", "Resultado de la Consulta de Cédulas",
                     "Opcional · .xls o .xlsx",
                     "Primero descarga la hoja CEDULAS POR CONSULTAR, pásala "
                     "por la consulta y carga aquí su resultado (Cédula, "
                     "apellidos, nombres, Estado Consulta).")
    f_consulta = st.file_uploader("Consulta de cédulas",
                                  type=["xls", "xlsx", "csv"],
                                  key="ter_consulta",
                                  label_visibility="collapsed")
    if not (f_helisa and f_origen):
        st.info("Carga el listado de clientes de HELISA y al menos un archivo "
                "de Alegra o Medifony.")
        return
    try:
        with st.spinner("Leyendo HELISA y el origen…"):
            helisa = _helisa(f_helisa.getvalue())
            origenes = _origenes(tuple((f.name, f.getvalue())
                                       for f in f_origen))
            consulta = _consulta(f_consulta.getvalue()) if f_consulta \
                else None
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    for a in origenes["avisos"]:
        st.warning(a)
    if not origenes["registros"]:
        st.error("Ningún archivo del origen se reconoció como contactos de "
                 "Alegra o reporte de Medifony.")
        return
    st.caption("Leídos: HELISA " + f"{helisa['n']:,}".replace(",", ".")
               + " clientes · " + " · ".join(
                   f"{s} {n:,} registros".replace(",", ".")
                   for s, n in origenes["sistemas"].items())
               + (f" · consulta de cédulas {len(consulta)}" if consulta
                  else ""))

    titulo_seccion(
        "Parámetros", 2,
        "Valores fijos del archivo a subir (CARTERA CLIENTES, NATURALEZA 0, "
        "REGIMEN y RESPONSABLE 49, como el archivo de la firma) y la clase "
        "de HELISA de cada tipo de documento.")
    config = _parametros(origenes)
    try:
        r = cruzar(helisa, origenes, consulta, config)
    except Exception as error:
        reportar_error("No se pudo hacer el cruce", error)
        return

    titulo_seccion(
        "Resultado", 3,
        "Se compara por documento sin espacios, puntos, guiones, caracteres "
        "invisibles ni ceros a la izquierda (el BUSCARV de Excel no encuentra "
        "esos casos). Un tercero por documento; los repetidos se avisan.")
    res = r["resumen"]
    kpis([
        {"etiqueta": "A crear en HELISA", "valor": str(len(r["crear"])),
         "icono": "usuario", "tono": "magenta",
         "detalle": f"de {res['En el origen (documentos únicos)']:,} "
                    "documentos del origen".replace(",", ".")},
        {"etiqueta": "Ya están en HELISA",
         "valor": f"{res['Ya están en HELISA']:,}".replace(",", "."),
         "icono": "ok", "tono": "verde"},
        {"etiqueta": "Cédulas por consultar",
         "valor": str(len(r["por_consultar"])), "icono": "escudo",
         "tono": "ambar" if r["por_consultar"] else "verde",
         "estado": "alerta" if r["por_consultar"] else "ok",
         "estado_texto": "Pendiente" if r["por_consultar"] else "Listo"},
        {"etiqueta": "Para revisar", "valor": str(len(r["revisar"])),
         "icono": "alerta", "tono": "ambar" if r["revisar"] else "verde"}])
    if r["por_consultar"]:
        st.warning(
            f"**{len(r['por_consultar'])} cédulas sin verificar** (amarillo en "
            "el archivo a subir). Descarga el Excel, pasa la hoja CEDULAS POR "
            "CONSULTAR por la Consulta de Cédulas y carga aquí su resultado: "
            "las cédulas quedan con nombres y apellidos oficiales.")
    por_clase = Counter(c["fila"]["CLASE DE "] for c in r["crear"])
    g1, g2 = st.columns(2)
    with g1:
        grafico("Terceros a crear por tipo de documento", html_barras(
            [(NOMBRE_CLASE.get(k, k), v) for k, v in por_clase.most_common()]),
            icono_nombre="personas")
    with g2:
        otros = [(k, v) for k, v in res.items()
                 if k not in ("En el origen (documentos únicos)",
                              "Ya están en HELISA", "A crear en HELISA")]
        grafico("Qué más dejó el cruce", html_barras(otros),
                icono_nombre="capas")

    pestanas = ["A subir a HELISA", "Para revisar", "Cédulas por consultar",
                "No se suben", "Ya en HELISA con datos distintos"]
    if r["completo"]:
        pestanas.append("En HELISA y no en Alegra")
    tabs = st.tabs(pestanas)
    with tabs[0]:
        st.dataframe([dict(c["fila"], Estado={
            "lista": "Lista", "cc_sin_verificar": "Cédula sin verificar",
            "cc_sin_resultado": "Cédula sin resultado"}[c["estado"]])
            for c in r["crear"]], use_container_width=True, hide_index=True)
    with tabs[1]:
        if r["revisar"]:
            st.dataframe([{"Qué": x["tipo"], "Identificación": x["id"],
                           "Nombre": x["nombre"], "Origen": x["origen"],
                           "Detalle": x["detalle"]} for x in r["revisar"]],
                         use_container_width=True, hide_index=True)
        else:
            st.success("Nada para revisar.")
    with tabs[2]:
        st.dataframe([{"Cédula": c} for c in r["por_consultar"]],
                     use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe([{"Identificación": x["id"], "Tipo": x["tipo"],
                       "Nombre": x["nombre"], "Origen": x["sistema"],
                       "Motivo": x["motivo"]} for x in r["no_se_suben"]],
                     use_container_width=True, hide_index=True)
    with tabs[4]:
        st.caption("Terceros que ya existen en HELISA pero con otra clase de "
                   "documento (p. ej. un niño que ya tiene tarjeta de "
                   "identidad y en HELISA sigue con registro civil) o con "
                   "otro nombre: actualizar en HELISA si corresponde.")
        st.dataframe([{"Identificación": d["id"], "Clase HELISA":
                       d["clase_helisa"], "Nombre HELISA": d["nombre_helisa"],
                       "Origen": d["origen"], "Tipo en origen":
                       d["tipo_origen"], "Nombre en origen":
                       d["nombre_origen"], "Qué cambia": d["que"]}
                      for d in r["datos_distintos"]],
                     use_container_width=True, hide_index=True)
    if r["completo"]:
        with tabs[5]:
            st.caption("Clientes de HELISA que no están en los contactos de "
                       "Alegra (al revés). Incluye los pacientes de Medifony "
                       "y terceros internos: es informativo.")
            st.dataframe([{"Código": h["codigo"], "Identidad": h["id"],
                           "Clase": h["clase"], "Nombre": h["nombre"]}
                          for h in r["helisa_no_en_origen"]],
                         use_container_width=True, hide_index=True)
    elif "Medifony" in r["sistemas"]:
        st.caption("El reporte de Medifony es de las facturas del periodo: no "
                   "se compara al revés (HELISA tiene clientes que no "
                   "facturaron en el periodo).")

    titulo_seccion("Descargar", 4,
                   "Hojas: A SUBIR A HELISA (formato de la firma), CEDULAS "
                   "POR CONSULTAR, REVISAR, NO SE SUBEN, YA EN HELISA DATOS "
                   "DISTINTOS, YA CREADOS (BUSCARV NO LOS VE), REPETIDOS EN "
                   "ORIGEN, DETALLE y RESUMEN.")
    try:
        datos = excel_terceros(r)
    except Exception as error:
        reportar_error("No se pudo armar el Excel", error)
        return
    st.download_button(
        "Descargar terceros a crear en HELISA", datos,
        file_name=nombre_archivo(r, datetime.date.today()),
        mime="application/vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet", type="primary",
        use_container_width=True, key="ter_descargar")
