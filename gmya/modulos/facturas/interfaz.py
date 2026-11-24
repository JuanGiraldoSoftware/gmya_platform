"""Pantalla del modulo Renombrar facturas (v6.22).

Contrato:
  modulo_facturas() -> dos formas de cargar: una carpeta del equipo (ruta) o
      subir los archivos. Muestra la tabla de revision (proveedor y numero
      editables) y entrega: copiar a una carpeta destino, renombrar en la
      misma carpeta (nunca dentro de 001. EMPRESAS ACTIVAS USO DIARIO) o
      descargar un ZIP. Toda la logica esta en facturas/logica.py.
Depende de: gmya.comun.config_equipo, gmya.ui.componentes, gmya.ui.visual,
gmya.modulos.facturas.logica, gmya.registro.interfaz
"""

import datetime
from pathlib import Path

import streamlit as st

from gmya.comun.config_equipo import guardar_config, leer_config
from gmya.ui.componentes import banner_modulo, encabezado_carga, titulo_seccion
from gmya.ui.visual import kpis
import gmya.modulos.facturas.logica as L
from gmya.registro.interfaz import reportar_error

ESTADOS = ("Listo", "Incompleto", "No es factura")


def _leer(archivos):
    """archivos: [(nombre, bytes, ruta o None)] -> filas de revision."""
    docs = [(n, c, r, L.leer_documento(n, c)) for n, c, r in archivos]
    propio = L.nit_propio_probable([d for *_, d in docs])
    return docs, propio


def _filas(docs, propio, guardados, conservar):
    filas = []
    for nombre, contenido, ruta, d in docs:
        r = L.resolver(d, propio, guardados)
        filas.append({
            "Usar": r["estado"] == "Listo", "Archivo original": nombre,
            "Proveedor": r["proveedor"], "Número": r["numero"],
            "Tipo": r["tipo_doc"], "NIT": r["nit"], "Estado": r["estado"],
            "Nota": r["nota"],
            "_extra": L.anotacion_original(nombre) if conservar else "",
            "_contenido": contenido, "_ruta": ruta,
            "_proveedor_doc": r["proveedor"]})
    return filas


def modulo_facturas():
    banner_modulo(
        "Módulo 8 · Archivos", "Renombrar facturas",
        "Lee cada factura (PDF, XML de la DIAN o ZIP) y la nombra «PROVEEDOR "
        "NÚMERO»: el proveedor es el tercero (el emisor en las compras; el "
        "cliente si la factura es de la propia empresa).",
        ("PDF · XML · ZIP", "Carpeta o archivos subidos",
         "Copia, renombra o ZIP"))

    titulo_seccion(
        "Archivos", 1,
        "Con una <b>carpeta del equipo</b> la plataforma lee la ruta (p. ej. "
        "la carpeta de facturas de un mes) y puede copiar las facturas "
        "renombradas a otra carpeta o renombrarlas ahí mismo. Si prefieres, "
        "<b>sube los archivos</b> y descárgalos renombrados en un ZIP. La "
        "carpeta «001. EMPRESAS ACTIVAS USO DIARIO» es solo lectura: de ahí "
        "se lee, pero no se renombra ni se escribe nada.")
    forma = st.radio("¿De dónde salen las facturas?",
                     ["Carpeta del equipo", "Subir archivos"],
                     horizontal=True, key="fac_ren_forma")
    archivos, origen = [], ""
    if forma == "Carpeta del equipo":
        c1, c2 = st.columns([4, 1])
        origen = c1.text_input(
            "Ruta de la carpeta",
            value=leer_config().get("facturas_ultima_ruta", ""),
            key="fac_ren_ruta",
            placeholder=r"G:\Mi unidad\…\FACTURAS NOVIEMBRE")
        recursivo = c2.toggle("Incluir subcarpetas", key="fac_ren_rec")
        if not origen:
            st.info("Escribe la ruta de la carpeta con las facturas.")
            return
        try:
            leidos = L.archivos_de_carpeta(origen, recursivo)
        except Exception as error:
            st.error(str(error))
            return
        guardar_config(facturas_ultima_ruta=origen)
        archivos = [(p.name, c, p) for p, c in leidos]
    else:
        encabezado_carga("PDF", "Facturas", "PDF, XML o ZIP · varias",
                         "Facturas electrónicas en PDF, sus XML de la DIAN o "
                         "los ZIP que llegan por correo.")
        subidos = st.file_uploader("Facturas", type=["pdf", "xml", "zip"],
                                   accept_multiple_files=True,
                                   key="fac_ren_subidos",
                                   label_visibility="collapsed") or []
        archivos = [(f.name, f.getvalue(), None) for f in subidos]
    if not archivos:
        st.info("No hay facturas (PDF, XML o ZIP) para revisar.")
        return
    try:
        with st.spinner(f"Leyendo {len(archivos)} archivos…"):
            docs, propio = _leer(archivos)
    except Exception as error:
        reportar_error("No se pudieron leer las facturas", error)
        return

    titulo_seccion(
        "Revisión", 2,
        "Proveedor y número salen de cada documento (el número se valida "
        "con el rango de la resolución cuando viene; el NIT con su dígito de "
        "verificación). Puedes corregirlos en la tabla; si cambias el nombre "
        "de un proveedor se puede recordar para las próximas veces (por "
        "NIT).")
    c1, c2, c3 = st.columns(3)
    propio = c1.text_input(
        "NIT de la empresa (no es el proveedor)", value=propio,
        key="fac_ren_nit", help="Se detecta solo: el NIT que aparece en la "
        "mayoría de las facturas. En las facturas que emitió la propia "
        "empresa, el nombre es el del cliente.")
    conservar = c2.toggle(
        "Conservar «codigo …» del nombre original", value=True,
        key="fac_ren_cod",
        help="Lo que la persona escribió desde «codigo» (p. ej. «codigo 100 "
             "200.000-300 400.000») se agrega al final del nombre nuevo.")
    recordar = c3.toggle("Recordar los nombres que cambie", value=True,
                         key="fac_ren_recordar")
    guardados = L.nombres_guardados()
    filas = _filas(docs, propio, guardados, conservar)
    import pandas as pd
    tabla = pd.DataFrame([{k: v for k, v in f.items()
                           if not k.startswith("_")} for f in filas])
    editada = st.data_editor(
        tabla, hide_index=True, use_container_width=True,
        key=f"fac_ren_tabla_{propio}_{conservar}",
        column_config={
            "Usar": st.column_config.CheckboxColumn(width="small"),
            "Archivo original": st.column_config.TextColumn(disabled=True),
            "Proveedor": st.column_config.TextColumn(width="large"),
            "Número": st.column_config.TextColumn(),
            "Tipo": st.column_config.TextColumn(disabled=True),
            "NIT": st.column_config.TextColumn(disabled=True),
            "Estado": st.column_config.TextColumn(disabled=True),
            "Nota": st.column_config.TextColumn(disabled=True,
                                                width="large")})
    plan = []
    for f, (_, e) in zip(filas, editada.iterrows()):
        usar = bool(e["Usar"]) and e["Proveedor"] and e["Número"]
        nuevo = L.nombre_nuevo(e["Proveedor"], e["Número"],
                               Path(f["Archivo original"]).suffix,
                               f["_extra"]) if usar else ""
        plan.append({"original": f["Archivo original"], "nuevo": nuevo,
                     "ruta": f["_ruta"], "contenido": f["_contenido"],
                     "proveedor": e["Proveedor"], "numero": e["Número"],
                     "nit": f["NIT"], "tipo_doc": f["Tipo"],
                     "estado": f["Estado"], "nota": f["Nota"],
                     "_cambio": f["NIT"] and e["Proveedor"] and
                     e["Proveedor"] != f["_proveedor_doc"]})
    finales = L.unicos([p["nuevo"] for p in plan])
    for p, n in zip(plan, finales):
        p["nuevo"] = n
    listos = sum(1 for p in plan if p["nuevo"])
    kpis([
        {"etiqueta": "Archivos", "valor": str(len(plan)), "icono": "archivo",
         "tono": "indigo"},
        {"etiqueta": "Se renombran", "valor": str(listos), "icono": "ok",
         "tono": "verde"},
        {"etiqueta": "Sin identificar", "valor": str(len(plan) - listos),
         "icono": "alerta", "tono": "ambar" if len(plan) > listos else
         "verde", "detalle": "Quedan con su nombre"}])
    st.dataframe([{"Archivo original": p["original"],
                   "Nombre nuevo": p["nuevo"] or "(se deja igual)"}
                  for p in plan], use_container_width=True, hide_index=True)

    titulo_seccion(
        "Aplicar", 3,
        "Copiar a otra carpeta no toca los originales. Renombrar en la misma "
        "carpeta solo se permite fuera de «001. EMPRESAS ACTIVAS USO "
        "DIARIO». En todos los casos queda un REGISTRO con el nombre "
        "original y el nuevo de cada archivo.")
    cambios = {p["nit"]: p["proveedor"] for p in plan if p["_cambio"]}

    def _recordar():
        if recordar and cambios:
            donde = L.guardar_nombres(cambios)
            st.caption(f"Nombres de proveedor recordados en {donde}.")

    fecha = datetime.date.today().strftime("%d-%m-%Y")
    st.download_button(
        "Descargar renombradas en ZIP", L.zip_renombrados(plan),
        file_name=f"FACTURAS RENOMBRADAS {fecha}.zip",
        mime="application/zip", use_container_width=True,
        key="fac_ren_zip",
        on_click=(lambda: L.guardar_nombres(cambios)) if recordar and cambios
        else None)
    if forma == "Carpeta del equipo":
        es_protegida = L.protegida(origen)
        opciones = ["Copiar renombradas a otra carpeta"] + (
            [] if es_protegida else ["Renombrar en la misma carpeta"])
        accion = st.radio("En la carpeta", opciones, horizontal=True,
                          key="fac_ren_accion")
        if es_protegida:
            st.caption("La carpeta está dentro de «001. EMPRESAS ACTIVAS USO "
                       "DIARIO» (solo lectura): solo se puede copiar a otra "
                       "carpeta o descargar el ZIP.")
        destino = ""
        if accion.startswith("Copiar"):
            sugerido = "" if es_protegida else str(Path(origen) /
                                                  "RENOMBRADAS")
            destino = st.text_input("Carpeta destino", value=sugerido,
                                    key="fac_ren_destino")
        confirmar = accion.startswith("Copiar") or st.checkbox(
            f"Confirmo renombrar {listos} archivos en la carpeta original",
            key="fac_ren_confirmo")
        if st.button(accion, type="primary", use_container_width=True,
                     disabled=not (listos and confirmar),
                     key="fac_ren_aplicar"):
            try:
                registro = L.aplicar(
                    plan, "renombrar" if accion.startswith("Renombrar")
                    else "copiar", destino)
                _recordar()
                renombrados = sum(1 for r in registro
                                  if r["accion"] != "sin cambio"
                                  and r["nuevo"] != r["original"])
                if accion.startswith("Renombrar"):
                    st.success(f"Listo: {renombrados} archivos renombrados. "
                               "El registro quedó en la misma carpeta.")
                else:
                    st.success(f"Listo: {len(registro)} archivos copiados a "
                               f"la carpeta destino ({renombrados} con el "
                               "nombre nuevo; los demás con su nombre). El "
                               "registro quedó en la carpeta destino.")
            except PermissionError as error:
                st.error(str(error))
            except Exception as error:
                reportar_error("No se pudieron aplicar los nombres", error)
