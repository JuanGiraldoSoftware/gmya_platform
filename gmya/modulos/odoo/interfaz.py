"""Pantalla "Automatizaciones Odoo" (Streamlit). Contrato: modulo_odoo().

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.cache, gmya.ui.componentes, gmya.modulos.odoo.logica, gmya.registro.interfaz
"""

import json
import re
from collections import OrderedDict, defaultdict

import streamlit as st

from gmya.comun.texto import _solo_digitos
from gmya.comun.numeros import formato_cop
from gmya.comun.cache import _cache, _huella
from gmya.ui.componentes import (
    banner_modulo, encabezado_carga, _glosario_pp, titulo_seccion,
)
from gmya.modulos.odoo.logica import (
    coberturas_odoo, EMPRESAS_ODOO, es_afiliado_sura, generar_excel_odoo_sura,
    guardar_coberturas_odoo, leer_factura_sura, leer_relacion_sura,
    lineas_odoo_sura, maestro_empresa_odoo, nombre_archivo_odoo_sura,
    partidas_sura, periodo_por_defecto_sura, PRODUCTOS_SURA,
    resumen_lineas_sura, texto_periodo_sura, validar_sura,
)
from gmya.registro.interfaz import reportar_error


# ============================================================
# INTERFAZ: AUTOMATIZACIONES ODOO
# ============================================================
GLOSARIO_ODOO = [
    ("% empresa", "Parte de la prima que asume la empresa (gasto 5105 54 / "
                  "7305 54). El resto se registra como <b>descuento al "
                  "empleado</b> en la cuenta 136595, con el empleado como "
                  "tercero. Afiliados: 100 %. Beneficiarios: 50 %, salvo "
                  "las excepciones."),
    ("Cuenta 5 / 7", "Columna «Cuenta» de la relación de cuentas y centros "
                     "de costo: <b>5</b> → 5105 54 (gasto administrativo), "
                     "<b>7</b> → 7305 54 (costo). Termina en <b>01</b> para "
                     "salud colectivo y <b>02</b> para vida de grupo."),
    ("Centro de costo", "Va a la <b>distribución analítica</b> de Odoo en 3 "
                        "dígitos (0227 → {\"227\": 100.0}). Los "
                        "beneficiarios usan el de su afiliado."),
    ("Ajuste", "Diferencia entre la factura y la suma de la relación "
               "(aproximación de SURA): débito 53959501 si la factura es "
               "mayor, crédito 429581 si es menor; analítica 004."),
]


@_cache
def _leer_documentos_sura(factura_bytes, relacion_bytes):
    """Lee los dos PDF; si se cargaron al reves, los intercambia."""
    try:
        factura = leer_factura_sura(factura_bytes)
        relacion = leer_relacion_sura(relacion_bytes)
        return factura, relacion, False
    except ValueError:
        factura = leer_factura_sura(relacion_bytes)
        relacion = leer_relacion_sura(factura_bytes)
        return factura, relacion, True


def _opciones_cc_odoo(clave):
    vistos = OrderedDict()
    for _, _, cc, nombre_cc, _ in EMPRESAS_ODOO[clave]["maestro"]:
        vistos.setdefault(str(cc).strip(), f"{cc} · {nombre_cc}")
    return vistos


def _tabla_revision_odoo(partidas, clave):
    import pandas as pd
    nombres_cc = _opciones_cc_odoo(clave)
    filas = []
    for p in partidas:
        filas.append({
            "Asegurado (ID · nombre)": _id_nombre(p["id_texto"],
                                                  p["nombre"]),
            "Parentesco": p["parentesco"],
            "Afiliado (ID · nombre)": _id_nombre(p["afiliado_id"],
                                                 p["afiliado_nombre"]),
            "Prima": p["prima"], "% empresa": p["pct_empresa"],
            "Cuenta 5 / 7": str(p["cuenta_5_7"] or ""),
            "Centro de costo": nombres_cc.get(p["cc"], p["cc"] or ""),
            "Origen": ("Relación de cuentas" if p["en_maestro"]
                       else "⚠ No está en la relación"),
            "Motivo": p["motivo"],
        })
    return pd.DataFrame(filas)


def _aplicar_revision_odoo(partidas, tabla, clave):
    inverso = {v: k for k, v in _opciones_cc_odoo(clave).items()}
    for p, (_, fila) in zip(partidas, tabla.iterrows()):
        try:
            pct = float(fila["% empresa"])
        except (TypeError, ValueError):
            pct = p["pct_empresa"]
        p["pct_empresa"] = max(0.0, min(100.0, pct))
        cuenta = str(fila["Cuenta 5 / 7"] or "").strip()
        p["cuenta_5_7"] = int(cuenta) if cuenta in ("5", "7") else None
        cc = str(fila["Centro de costo"] or "").strip()
        p["cc"] = inverso.get(cc, cc.split(" ")[0] if cc else "")


def _id_nombre(ident, nombre):
    return f"{ident} · {nombre}" if nombre else str(ident)


def _id_de_opcion(texto):
    return _solo_digitos(str(texto or "").split("·")[0])


def _beneficiarios_cargados_odoo():
    """Beneficiarios de la relacion de asegurados ya cargada en el paso 2
    (para elegirlos por nombre en la lista de cubiertos al 100 %)."""
    salida = OrderedDict()
    archivos = [st.session_state.get("odoo_factura"),
                st.session_state.get("odoo_relacion")]
    if not all(archivos):
        return salida
    try:
        _, relacion, _ = _leer_documentos_sura(archivos[0].getvalue(),
                                               archivos[1].getvalue())
    except Exception:
        return salida
    for x in relacion["asegurados"]:
        if not es_afiliado_sura(x["parentesco"]):
            salida[x["id"]] = (x["nombre"], x["afiliado_id"],
                               x["afiliado_nombre"])
    return salida


def _editor_coberturas_odoo(clave):
    """Parametro: beneficiarios que la empresa cubre al 100 % (terminos de
    contrato). Los demas beneficiarios: 50 % empresa y 50 % descuento al
    empleado (136595). Empleado y beneficiario se eligen por ID y nombre."""
    import pandas as pd
    coberturas = coberturas_odoo(clave)
    # Lo que habia al empezar a editar (para combinar al guardar).
    llave_base = f"odoo_cob_base_{st.session_state.get('odoo_cob_n', 0)}"
    base_edicion = st.session_state.setdefault(
        llave_base, {a: dict(v) for a, v in coberturas.items()})
    maestro = maestro_empresa_odoo(clave)
    cargados = _beneficiarios_cargados_odoo()
    total = sum(len(v) for v in coberturas.values())

    # Opciones "ID · NOMBRE": empleados de la relacion de cuentas y
    # beneficiarios guardados o de la relacion de asegurados cargada.
    empleados = OrderedDict(
        (i, _id_nombre(i, d["nombre"]))
        for i, d in sorted(maestro.items(), key=lambda kv: kv[1]["nombre"]))
    beneficiarios = OrderedDict()
    for a, v in coberturas.items():
        empleados.setdefault(a, _id_nombre(a, ""))
        for b, n in v.items():
            beneficiarios[b] = (n, a)
    for b, (n, a, an) in cargados.items():
        beneficiarios.setdefault(b, (n, a))
        empleados.setdefault(a, _id_nombre(a, an))
    opciones_ben = OrderedDict(
        (b, _id_nombre(b, n) + (f"  (de {maestro[a]['nombre']})"
                                if a in maestro else ""))
        for b, (n, a) in sorted(beneficiarios.items(),
                                key=lambda kv: kv[1][0]))

    with st.expander(f"Beneficiarios cubiertos al 100 % ({total}) · "
                     "términos de contrato"):
        st.markdown(
            "Por regla, la empresa asume el <b>50 %</b> de cada "
            "beneficiario y el otro 50 % se descuenta al empleado (cuenta "
            "<b>136595</b>). Aquí van los beneficiarios que, por su "
            "contrato, se cubren al <b>100 %</b>. Agrega una fila y escoge "
            "el <b>empleado</b> y el <b>beneficiario</b> (ID · nombre); "
            "borra la fila para que vuelva al 50 %. También puedes cambiar "
            "el % en la revisión de una factura y guardarlo desde allí.",
            unsafe_allow_html=True)
        if not cargados:
            st.caption("Para escoger un beneficiario que aún no está en la "
                       "lista, carga primero la factura y la relación de "
                       "asegurados (paso 2): sus beneficiarios aparecen aquí "
                       "con su nombre.")
        filas = [{"Empleado (ID · nombre)": empleados.get(a,
                                                          _id_nombre(a, "")),
                  "Beneficiario (ID · nombre)": opciones_ben.get(
                      b, _id_nombre(b, n))}
                 for a, v in coberturas.items() for b, n in v.items()]
        tabla = pd.DataFrame(filas, columns=["Empleado (ID · nombre)",
                                             "Beneficiario (ID · nombre)"])
        editada = st.data_editor(
            tabla,
            key=f"odoo_coberturas_{st.session_state.get('odoo_cob_n', 0)}",
            num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "Empleado (ID · nombre)": st.column_config.SelectboxColumn(
                    options=list(empleados.values()), width="large",
                    help="Empleado (afiliado) de la relación de cuentas y "
                         "centros de costo. Si lo dejas vacío se toma el "
                         "del beneficiario."),
                "Beneficiario (ID · nombre)": st.column_config.SelectboxColumn(
                    options=list(opciones_ben.values()), width="large",
                    help="Beneficiario tal como sale en la relación de "
                         "asegurados de SURA."),
            })
        if st.button("Guardar beneficiarios al 100 %",
                     key="odoo_guardar_coberturas"):
            nuevas = defaultdict(dict)
            avisos = []
            for _, fila in editada.iterrows():
                b = _id_de_opcion(fila.get("Beneficiario (ID · nombre)"))
                if not b:
                    continue
                nombre_b, afiliado_b = beneficiarios.get(b, ("", ""))
                a = _id_de_opcion(fila.get("Empleado (ID · nombre)")) or \
                    afiliado_b
                if afiliado_b and a != afiliado_b:
                    avisos.append(f"{nombre_b or b} es beneficiario de "
                                  f"{maestro.get(afiliado_b, {}).get('nombre', afiliado_b)}"
                                  "; se guardó con ese empleado.")
                    a = afiliado_b
                if a:
                    nuevas[a][b] = nombre_b
            donde = guardar_coberturas_odoo(clave, dict(nuevas),
                                            base=base_edicion)
            st.session_state["odoo_cob_n"] = \
                st.session_state.get("odoo_cob_n", 0) + 1
            st.session_state["odoo_cob_avisos"] = avisos
            st.toast(f"Beneficiarios al 100 % guardados en {donde}.")
            st.rerun()
        for aviso in st.session_state.pop("odoo_cob_avisos", []) or []:
            st.info(aviso)
    return coberturas


def _guardar_coberturas_de_factura(clave, partidas, coberturas):
    """Si en la revision se cambio el % de un beneficiario a 100 o a 50,
    ofrece guardarlo como regla para las proximas facturas."""
    propuestas = {k: dict(v) for k, v in coberturas.items()}
    cambios = []
    for p in partidas:
        if es_afiliado_sura(p["parentesco"]):
            continue
        actual = p["id"] in propuestas.get(p["afiliado_id"], {})
        nuevo = p["pct_empresa"] >= 100
        if nuevo != actual:
            cambios.append(f"{p['nombre']} → {'100 %' if nuevo else '50 %'}")
            if nuevo:
                propuestas.setdefault(p["afiliado_id"], {})[p["id"]] = \
                    p["nombre"]
            else:
                propuestas.get(p["afiliado_id"], {}).pop(p["id"], None)
    if not cambios:
        return
    st.info("Cambiaste la cobertura de: " + "; ".join(cambios) + ". Si es "
            "un término de contrato (y no solo de esta factura), guárdalo "
            "como regla.")
    if st.button("Guardar como regla para las próximas facturas",
                 key="odoo_guardar_desde_revision"):
        donde = guardar_coberturas_odoo(clave, propuestas, base=coberturas)
        st.session_state["odoo_cob_n"] = \
            st.session_state.get("odoo_cob_n", 0) + 1
        st.toast(f"Beneficiarios al 100 % guardados en {donde}.")
        st.rerun()


def modulo_odoo():
    banner_modulo(
        "Módulo 5 · Contabilidad en Odoo",
        "Automatizaciones Odoo",
        "Arma los archivos de importación de Odoo a partir de los documentos "
        "del proveedor. Primer proceso: facturas de Seguros SURA (salud "
        "colectivo y vida de grupo) de HIBRIDS, con la cuenta, el centro de "
        "costo y el descuento al empleado de cada asegurado.",
        ("Factura + relación en PDF", "Reglas de la empresa guardadas",
         "Salida: Excel para importar en Odoo"),
    )

    titulo_seccion(
        "Empresa y proceso", 1,
        "Por ahora está implementado <b>HIBRIDS</b> con las facturas de "
        "<b>Seguros de Vida Suramericana</b>. La relación de cuentas y "
        "centros de costo de la empresa ya está guardada en la plataforma: "
        "no hay que cargarla.")
    c1, c2 = st.columns(2)
    with c1:
        clave = st.selectbox(
            "Empresa", list(EMPRESAS_ODOO),
            format_func=lambda k: EMPRESAS_ODOO[k]["nombre"],
            key="odoo_empresa")
    with c2:
        st.selectbox("Proceso", ["Seguros SURA · salud colectivo y vida de "
                                 "grupo"], key="odoo_proceso",
                     help="El producto (salud colectivo o vida de grupo) "
                          "se reconoce solo en los PDF.")
    empresa = EMPRESAS_ODOO[clave]
    with st.expander("Relación de cuentas y centros de costo guardada "
                     f"({len(empresa['maestro'])} empleados)"):
        import pandas as pd
        st.dataframe(pd.DataFrame(
            [{"Identificación": i, "Nombre": n, "Centro de costo": cc,
              "Nombre centro": ncc, "Cuenta": c}
             for i, n, cc, ncc, c in empresa["maestro"]]),
            use_container_width=True, hide_index=True, height=300)
    coberturas = _editor_coberturas_odoo(clave)

    titulo_seccion(
        "Documentos de SURA", 2,
        "Los dos son <b>obligatorios</b> y se cargan <b>tal como llegan</b> "
        "de SURA, en PDF. Si los cargas en la casilla equivocada se "
        "detecta solo.")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga(
            "FACT", "Factura electrónica", "Obligatorio · PDF de SURA",
            "Factura electrónica de venta de Seguros de Vida Suramericana: "
            "da el número (referencia en Odoo), la fecha, la póliza, el "
            "subtotal, el IVA y el total.")
        f_fact = st.file_uploader("Factura SURA", type=["pdf"],
                                  key="odoo_factura",
                                  label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "REL", "Relación de asegurados", "Obligatorio · PDF de SURA",
            "Salud colectivo: relación de asegurados por afiliado con sus "
            "beneficiarios. Vida de grupo: recibo de cobro con la relación "
            "de asegurados. Da una línea por asegurado con su prima.")
        f_rel = st.file_uploader("Relación de asegurados", type=["pdf"],
                                 key="odoo_relacion",
                                 label_visibility="collapsed")
    if not (f_fact and f_rel):
        st.info("Carga la factura y la relación de asegurados para "
                "continuar.")
        return
    try:
        with st.spinner("Leyendo los PDF de SURA…"):
            factura, relacion, cruzados = _leer_documentos_sura(
                f_fact.getvalue(), f_rel.getvalue())
    except Exception as error:
        reportar_error("No se pudieron leer los documentos", error)
        return
    if cruzados:
        st.info("La factura y la relación estaban en casillas cruzadas; se "
                "usaron intercambiadas.")
    producto = relacion["producto"]
    st.success(
        f"{PRODUCTOS_SURA[producto]['nombre']} · póliza "
        f"{factura.get('poliza') or relacion.get('poliza')} · factura "
        f"{factura['numero']} del "
        + (f"{factura['fecha']:%d/%m/%Y}" if factura.get("fecha") else "—")
        + f" · {len(relacion['asegurados'])} asegurados · subtotal "
        f"{formato_cop(factura['subtotal'])}"
        + (f" + IVA {formato_cop(factura['iva'])}" if factura["iva"] else "")
        + f" = {formato_cop(factura['total'])}")

    titulo_seccion(
        "Periodo", 3,
        "El periodo de cobro va al final de cada etiqueta. En vida de grupo "
        "sale del recibo; en salud colectivo la relación no lo trae y se "
        "propone el ciclo del 15 al 15 que contiene la fecha de la factura. "
        "Puedes cambiarlo o dejarlo vacío.")
    periodo = relacion.get("periodo") or periodo_por_defecto_sura(
        factura.get("fecha") or relacion.get("fecha"))
    periodo_texto = st.text_input(
        "Periodo en las etiquetas", value=texto_periodo_sura(periodo),
        key=f"odoo_periodo_{factura['numero']}",
        help="Formato de las importaciones anteriores: 15-OCT-2026 a "
             "15-NOV-2026.").strip()

    huella = _huella(f_fact.getvalue(), f_rel.getvalue(), clave,
                     json.dumps(coberturas, sort_keys=True))
    if st.session_state.get("odoo_huella") != huella:
        st.session_state["odoo_huella"] = huella
        st.session_state["odoo_partidas"] = partidas_sura(
            factura, relacion, clave, coberturas)
        st.session_state["odoo_editor_n"] = \
            st.session_state.get("odoo_editor_n", 0) + 1
        st.session_state.pop("odoo_archivo", None)
    partidas = st.session_state["odoo_partidas"]

    titulo_seccion(
        "Revisión", 4,
        "Una fila por asegurado, en el orden de la relación. Puedes cambiar "
        "el <b>% que asume la empresa</b>, la <b>cuenta 5 / 7</b> y el "
        "<b>centro de costo</b>. Los empleados que no están en la relación "
        "de cuentas aparecen marcados y hay que completarlos antes de "
        "generar.")
    _glosario_pp(GLOSARIO_ODOO)
    tabla = _tabla_revision_odoo(partidas, clave)
    ayudas = {k: re.sub(r"<[^>]+>", "", v) for k, v in GLOSARIO_ODOO}
    editada = st.data_editor(
        tabla, key=f"odoo_editor_{st.session_state['odoo_editor_n']}",
        use_container_width=True, height=460, hide_index=True,
        column_config={
            "Asegurado (ID · nombre)": st.column_config.TextColumn(
                disabled=True, width="large"),
            "Parentesco": st.column_config.TextColumn(disabled=True),
            "Afiliado (ID · nombre)": st.column_config.TextColumn(
                disabled=True, width="large"),
            "Prima": st.column_config.NumberColumn(disabled=True,
                                                   format="%.2f"),
            "% empresa": st.column_config.NumberColumn(
                min_value=0, max_value=100, step=50, format="%.0f",
                help=ayudas["% empresa"]),
            "Cuenta 5 / 7": st.column_config.SelectboxColumn(
                options=["5", "7"], help=ayudas["Cuenta 5 / 7"]),
            "Centro de costo": st.column_config.SelectboxColumn(
                options=list(_opciones_cc_odoo(clave).values()),
                help=ayudas["Centro de costo"]),
            "Origen": st.column_config.TextColumn(disabled=True),
            "Motivo": st.column_config.TextColumn(disabled=True,
                                                  width="large"),
        })
    _aplicar_revision_odoo(partidas, editada, clave)
    _guardar_coberturas_de_factura(clave, partidas, coberturas)

    avisos = validar_sura(factura, relacion, partidas, clave)
    graves = [t for t, grave in avisos if grave]
    for texto, grave in avisos:
        (st.warning if grave else st.info)(texto)

    filas = lineas_odoo_sura(factura, relacion, partidas, periodo_texto)
    resumen = resumen_lineas_sura(filas)
    c = st.columns(4)
    c[0].metric("Líneas para Odoo", len(filas))
    c[1].metric("Total de las líneas", formato_cop(resumen["total"]),
                f"factura {formato_cop(factura['total'])}",
                delta_color="off")
    c[2].metric("Descuento a empleados (136595)",
                formato_cop(resumen["descuento_empleado"]))
    c[3].metric("Diferencia con la factura",
                formato_cop(round(resumen["total"] - factura["total"], 2)))

    titulo_seccion(
        "Generar y descargar", 5,
        "Genera el libro <b>SEGUROS DE VIDA SURA FACT.{número} IMP ODOO</b> "
        "con la hoja <b>Importar Odoo</b> (fecha, contacto, referencia y "
        "diario en la primera línea; una línea por asegurado, el descuento "
        "al empleado, el ajuste y el IVA) y la hoja <b>Control</b> con el "
        "cuadre contra la factura.")
    faltan = [p for p in partidas if not (p["cuenta_5_7"] and p["cc"])]
    if faltan:
        st.warning("Falta cuenta o centro de costo para: "
                   + ", ".join(sorted({p["afiliado_nombre"]
                                       for p in faltan})) + ".")
    if st.button("Generar archivo para Odoo", type="primary",
                 key="odoo_generar", use_container_width=True, disabled=bool(faltan or graves)):
        try:
            contenido = generar_excel_odoo_sura(factura, relacion, filas)
            st.session_state["odoo_archivo"] = (
                nombre_archivo_odoo_sura(factura), contenido)
        except Exception as error:
            reportar_error("No se pudo generar el archivo", error)
    if graves and not faltan:
        st.caption("Revisa los avisos en amarillo antes de generar.")
    if st.session_state.get("odoo_archivo"):
        nombre, contenido = st.session_state["odoo_archivo"]
        st.success(f"Listo: {nombre}")
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary", key="odoo_descargar", use_container_width=True)
