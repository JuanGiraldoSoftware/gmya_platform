"""Pantalla de inicio y catalogo del menu.

Contrato:
  MODULOS        OrderedDict clave -> nombre visible (orden del menu).
  PANTALLAS_FUERA_DEL_MENU  pantallas validas que no van en el menu
                 (p. ej. "reporte", que se abre desde la barra superior).
  ICONOS_MODULO  clave -> icono material.
  ir_a(clave)    callback de los botones del menu.
  modulo_inicio()
Para agregar un modulo nuevo: crear gmya/modulos/<nuevo>/, agregarlo a
MODULOS e ICONOS_MODULO y a PANTALLAS en app.py.

Depende de: gmya.ui.componentes, gmya.modulos.dian.parametros
"""

from collections import OrderedDict

import streamlit as st

from gmya.ui.componentes import banner_modulo, tarjeta, titulo_seccion
from gmya.modulos.dian.parametros import (
    AZUL_ALERTA, MORADO_ALERTA, ROJO_ALERTA,
)


# ============================================================
# INICIO (RECORRIDO POR LA PLATAFORMA)
# ============================================================
MODULOS = OrderedDict([
    ("inicio", "Inicio"),
    ("busqueda", "Búsqueda de archivos"),
    ("planillas", "Planillas de seguridad social"),
    ("bancos", "Conciliación bancaria"),
    ("dian", "Conciliación DIAN"),
    ("pagos", "Programación de pagos"),
    ("odoo", "Automatizaciones Odoo"),
    ("nomina", "Pagos de nómina"),
])
# v6.8: "Reportar un error" ya no va en el menu de modulos: es un boton de
# la barra superior (app.py). Sigue teniendo pantalla en PANTALLAS.
PANTALLAS_FUERA_DEL_MENU = OrderedDict([
    ("reporte", "Reportar un error"),
])
ICONOS_MODULO = {
    "inicio": ":material/home:",
    "planillas": ":material/groups:",
    "bancos": ":material/account_balance:",
    "dian": ":material/receipt_long:",
    "busqueda": ":material/travel_explore:",
    "pagos": ":material/payments:",
    "odoo": ":material/upload_file:",
    "nomina": ":material/badge:",
    "uso": ":material/insights:",
    "reporte": ":material/bug_report:",
}


def ir_a(modulo):
    if modulo == "reporte":
        # El reporte propone el modulo desde el que se llego.
        st.session_state["reporte_origen"] = st.session_state.get(
            "modulo_gmya", "")
    st.session_state["modulo_gmya"] = modulo


def modulo_inicio():
    banner_modulo(
        "Servicios contables · Tecnología aplicada",
        "Plataforma de automatización contable",
        "Herramientas de la firma para los procesos repetitivos de cierre "
        "mensual de nuestros clientes. Escoge un módulo en el menú lateral; "
        "en cada paso encontrarás un ícono ? con la explicación. Si algo "
        "sale mal, usa «Reportar un error» en la barra superior.",
        ("7 módulos", "Sin envío de datos a terceros", "Salidas en Excel y "
                                                         "TXT"),
    )

    titulo_seccion(
        "Recorrido por la plataforma", None,
        "Todos los módulos siguen el mismo orden: <b>1. cargar</b> los "
        "documentos, <b>2. ajustar parámetros</b> si hace falta, "
        "<b>3. generar</b> y <b>4. revisar</b> el resultado antes de "
        "descargar. Los archivos se procesan en este equipo.")

    c0, _ = st.columns([1, 2])
    with c0:
        tarjeta(
            "Búsqueda de archivos",
            "<p>Encuentra los documentos de cada empresa en Google Drive "
            "(001. Empresas activas).</p><ol><li>Escribe parte del nombre o "
            "elige la empresa.</li><li>Filtra por tipo (Excel, PDF…) y "
            "fecha.</li><li>Un clic abre el archivo o su carpeta en el "
            "Explorador.</li></ol>",
            etiqueta="Acceso rápido",
            explicacion="Solo lectura: no mueve ni borra nada en el Drive.")
        st.write("")
        st.button("Abrir búsqueda de archivos", key="ir_busqueda",
                  on_click=ir_a, args=("busqueda",), type="primary",
                  use_container_width=True)
    st.write("")

    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta(
            "Planillas de seguridad social",
            "<p>Separa las planillas PILA en TXT por cotizante o en grupos "
            "personalizados.</p><ol><li>Carga uno o varios TXT.</li>"
            "<li>Elige Individualizar o Selección personalizada.</li>"
            "<li>Descarga el ZIP con el informe de procesamiento.</li></ol>",
            etiqueta="Módulo 1",
            explicacion="Ideal para enviar a cada empleado o centro de costo "
                        "solo sus registros, conservando la cabecera de la "
                        "planilla.")
        st.write("")
        st.button("Abrir planillas", key="ir_planillas",
                  on_click=ir_a, args=("planillas",),
                  use_container_width=True)
    with c2:
        tarjeta(
            "Conciliación bancaria",
            "<p>Extractos bancarios vs. HELISA, en PDF "
            "o Excel, varias cuentas a la vez.</p><ol><li>Carga todos los "
            "extractos y HELISA.</li><li>Ajusta la ventana de fechas y la "
            "tolerancia.</li><li>Descarga el Excel con el resumen por "
            "cuenta, el soporte de gastos bancarios y la conciliación línea "
            "a línea.</li></ol>",
            etiqueta="Módulo 2",
            explicacion="Reconoce el banco, valida contra el resumen del "
                        "extracto, agrupa GMF, IVA y comisiones, busca la "
                        "causa probable de cada diferencia (fechas, "
                        "digitación, registros agrupados, tránsito...) y "
                        "propone los asientos de ajuste.")
        st.write("")
        st.button("Abrir conciliación bancaria", key="ir_bancos",
                  on_click=ir_a, args=("bancos",),
                  use_container_width=True)
    with c3:
        tarjeta(
            "Conciliación DIAN",
            "<p>Reporte de documentos DIAN vs. comprobantes de diario "
            "HELISA.</p><ol><li>Carga el reporte DIAN (.xlsx).</li>"
            "<li>Carga la relación de documentos de HELISA (todos los "
            "tipos en un solo archivo) o un informe por concepto.</li><li>Descarga el "
            "formato completo o el simplificado; el periodo (mes, corte o "
            "semana) se detecta solo.</li></ol>",
            etiqueta="Módulo 3", oscura=True,
            explicacion="Cruza factura por factura las compras, marca "
                        "facturas NO DIAN, redondeos, gastos no deducibles y "
                        "acuses de facturas a crédito.")
        st.write("")
        st.button("Abrir conciliación DIAN", key="ir_dian",
                  on_click=ir_a, args=("dian",), type="primary",
                  use_container_width=True)

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        tarjeta(
            "Programación de pagos",
            "<p>Arma la programación de pagos por empresa (NATURE, MEDFAM "
            "y CAFETO, que además tiene cuentas por cobrar).</p><ol><li>Escoge la empresa (las que están en gris "
            "aún no están implementadas).</li><li>Carga los informes de "
            "HELISA y la programación anterior.</li><li>Revisa lo sugerido "
            "y lo marcado en el visor y descarga el Excel con fecha y "
            "empresa.</li></ol>",
            etiqueta="Módulo 4",
            explicacion="Corre las fechas de pago, conserva textos y "
                        "observaciones, arrastra lo que sigue pendiente y "
                        "pasa los pagos fijos al mes siguiente.")
        st.write("")
        st.button("Abrir programación de pagos", key="ir_pagos",
                  on_click=ir_a, args=("pagos",),
                  use_container_width=True)
    with c2:
        tarjeta(
            "Automatizaciones Odoo",
            "<p>Archivos de importación de Odoo a partir de los documentos "
            "del proveedor (HIBRIDS · Seguros SURA).</p><ol><li>Carga la "
            "factura y la relación de asegurados en PDF.</li><li>Revisa la "
            "cuenta, el centro de costo y el descuento al empleado de cada "
            "asegurado.</li><li>Descarga el Excel listo para importar en "
            "Odoo.</li></ol>",
            etiqueta="Módulo 5",
            explicacion="Salud colectivo y vida de grupo: cuenta 5105/7305 "
                        "según el centro de costo, 50 % de los beneficiarios "
                        "como descuento al empleado, IVA y ajuste por "
                        "aproximación.")
        st.write("")
        st.button("Abrir automatizaciones Odoo", key="ir_odoo",
                  on_click=ir_a, args=("odoo",),
                  use_container_width=True)

    st.write("")
    c1, _ = st.columns(2)
    with c1:
        tarjeta(
            "Pagos de nómina",
            "<p>Actualiza el formato de pagos del banco con las planillas "
            "de pago, o concilia la nómina (HELISA vs liquidación vs "
            "contabilidad).</p><ol><li>Carga el Excel del banco y una o varias "
            "planillas en PDF (nómina, prima, vacaciones…).</li><li>Revisa "
            "las alertas y la tabla de empleados.</li><li>Descarga el mismo "
            "Excel con el valor a pagar actualizado.</li></ol>",
            etiqueta="Módulo 6",
            explicacion="Cruza por cédula y nombre, suma los conceptos de "
                        "cada empleado y solo cambia la columna "
                        "ValorTransaccion: nunca agrega ni borra empleados.")
        st.write("")
        st.button("Abrir pagos de nómina", key="ir_nomina",
                  on_click=ir_a, args=("nomina",),
                  use_container_width=True)

    titulo_seccion(
        "Convenciones de los resultados", None,
        "Los colores se usan igual en la pantalla y en los Excel generados.")
    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta("Cian", "<p>Documento DIAN revisado y encontrado en "
                "HELISA.</p>", etiqueta="Conciliado", color="#66FFFF")
    with c2:
        tarjeta("Amarillo", "<p>Está en los dos pero hay que revisar: "
                "valor, IVA, folio, gasto no deducible o acuse en NO.</p>",
                etiqueta="Revisar", color="#FFFF00")
    with c3:
        tarjeta("Azul", "<p>Factura registrada en HELISA que no aparece "
                "en el reporte DIAN (NO DIAN).</p>", etiqueta="NO DIAN",
                color="#" + AZUL_ALERTA)
    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta("Rojo", "<p>Documento DIAN <b>no contabilizado</b> en "
                "HELISA (seguro: se cruzó con el detalle).</p>",
                etiqueta="No contabilizado", color="#" + ROJO_ALERTA)
    with c2:
        tarjeta("Morado", "<p><b>Posible</b> no contabilizado: deducido "
                "del informe Resumen por valor; confirmar con el "
                "Detalle.</p>", etiqueta="Posible", color="#" + MORADO_ALERTA)
    with c3:
        tarjeta("Letra roja", "<p>En los totales, la fila DIFERENCIA "
                "distinta de cero y los acuses en NO.</p>",
                etiqueta="Diferencia", color="#FF0000")
