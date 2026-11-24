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

Depende de: gmya.config, gmya.ui.componentes, gmya.modulos.dian.parametros,
gmya.modulos.pagos.lectura (numero de empresas en la portada)
"""

from collections import OrderedDict

import streamlit as st

import html

from gmya.config import VERSION
from gmya.ui.componentes import tarjeta, titulo_seccion
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
    ("terceros", "Creación de terceros"),
    ("facturas", "Renombrar facturas"),
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
    "terceros": ":material/person_add:",
    "facturas": ":material/drive_file_rename_outline:",
    "uso": ":material/insights:",
    "reporte": ":material/bug_report:",
}


# (clave, titulo, cuerpo, etiqueta, explicacion, texto del boton, primario)
_TARJETAS_INICIO = [
    # v6.12: una frase por modulo; los pasos de cada uno estan en su propia
    # pantalla y en el (?) de la tarjeta.
    ("busqueda", "Búsqueda de archivos",
     "<p>Encuentra los documentos de cada empresa en Google Drive "
     "(001. Empresas activas) por nombre, tipo y fecha.</p>",
     "Acceso rápido",
     "Escribe parte del nombre o elige la empresa, filtra por tipo y fecha; "
     "un clic abre el archivo o su carpeta. Solo lectura: no mueve ni borra "
     "nada en el Drive.",
     "Abrir búsqueda", True),
    ("planillas", "Planillas de seguridad social",
     "<p>Separa las planillas PILA en TXT por cotizante o en grupos "
     "personalizados.</p>",
     "Módulo 1",
     "Carga uno o varios TXT, elige Individualizar o Selección "
     "personalizada y descarga el ZIP con el informe. Conserva la cabecera "
     "de la planilla.",
     "Abrir planillas", False),
    ("bancos", "Conciliación bancaria",
     "<p>Extractos bancarios vs. HELISA, en PDF o Excel, varias cuentas a "
     "la vez.</p>",
     "Módulo 2",
     "Reconoce el banco, valida contra el resumen del extracto, agrupa GMF, "
     "IVA y comisiones, busca la causa probable de cada diferencia y "
     "propone los asientos de ajuste.",
     "Abrir conciliación bancaria", False),
    ("dian", "Conciliación DIAN",
     "<p>Reporte de documentos DIAN vs. comprobantes de HELISA, documento "
     "por documento.</p>",
     "Módulo 3",
     "Cruza compras, ventas, notas y documentos soporte; marca NO DIAN, "
     "redondeos, gastos no deducibles y acuses. Formato completo o "
     "simplificado; el periodo se detecta solo.",
     "Abrir conciliación DIAN", False),
    ("pagos", "Programación de pagos",
     "<p>Programación de pagos por empresa (EMPRESA C, EMPRESA D, EMPRESA F y "
     "EMPRESA E) desde HELISA y la programación anterior.</p>",
     "Módulo 4",
     "Corre las fechas de pago, conserva textos y observaciones, arrastra lo "
     "que sigue pendiente y pasa los pagos fijos al mes siguiente.",
     "Abrir programación de pagos", False),
    ("odoo", "Automatizaciones Odoo",
     "<p>Archivos de importación de Odoo desde los documentos del "
     "proveedor (EMPRESA A · Seguros SURA).</p>",
     "Módulo 5",
     "Salud colectivo y vida de grupo: cuenta 5105/7305 según el centro de "
     "costo, 50 % de los beneficiarios como descuento al empleado, IVA y "
     "ajuste por aproximación.",
     "Abrir automatizaciones Odoo", False),
    ("nomina", "Pagos de nómina",
     "<p>Formato de pagos del banco, conciliación de nómina y nómina "
     "electrónica.</p>",
     "Módulo 6",
     "En el formato del banco solo cambia la columna ValorTransaccion: nunca "
     "agrega ni borra empleados. La nómina electrónica arma el layout de "
     "carga con su validación por fila.",
     "Abrir pagos de nómina", False),
    ("terceros", "Creación de terceros",
     "<p>Qué clientes de Alegra o Medifony faltan en HELISA, con el archivo "
     "para crearlos.</p>",
     "Módulo 7",
     "Cruza por documento (sin ceros ni caracteres invisibles), quita "
     "repetidos, prepara la consulta de cédulas y avisa posibles terceros ya "
     "creados con otro número.",
     "Abrir creación de terceros", False),
    ("facturas", "Renombrar facturas",
     "<p>Nombra cada factura «PROVEEDOR NÚMERO» desde una carpeta o subiendo "
     "los archivos.</p>",
     "Módulo 8",
     "Lee PDF, XML de la DIAN y ZIP; valida el número con la resolución y "
     "el NIT con su dígito; copia, renombra o entrega un ZIP con registro.",
     "Abrir renombrar facturas", False),
]


def ir_a(modulo):
    if modulo == "reporte":
        # El reporte propone el modulo desde el que se llego.
        st.session_state["reporte_origen"] = st.session_state.get(
            "modulo_gmya", "")
    st.session_state["modulo_gmya"] = modulo


# Icono y tono de cada modulo en Inicio (gmya/ui/visual.py).
ICONO_TARJETA = {
    "busqueda": ("buscar", "magenta"), "planillas": ("personas", "verde"),
    "bancos": ("banco", "teal"), "dian": ("recibo", "indigo"),
    "pagos": ("pagos", "magenta"), "odoo": ("subir", "pizarra"),
    "nomina": ("nomina", "ambar"),
    "terceros": ("usuario", "indigo"),
    "facturas": ("documentos", "teal"),
}


def _portada():
    """Portada oscura de Inicio: saludo y datos de la plataforma."""
    try:
        from gmya.modulos.pagos.lectura import EMPRESAS_PROG_PAGOS
        empresas = len(EMPRESAS_PROG_PAGOS)
    except Exception:
        empresas = "—"
    persona = (st.session_state.get("reg_admin_de") or "").strip()
    nombre = persona.split()[0].title() if persona else ""
    saludo = f"Hola, {html.escape(nombre)}" if nombre else \
        "Plataforma de automatización contable"
    datos = [(len(MODULOS) - 1, "módulos"), (empresas,
             "empresas con pagos"), ("100 %", "local en este equipo")]
    st.markdown(
        '<div class="gm-hero"><div class="gm-hero-txt">'
        '<div class="gm-eyebrow">GMYA Tools · ' + html.escape(VERSION)
        + '</div><h1>' + saludo + '</h1><p>Herramientas de la firma para '
        'el cierre mensual de nuestros clientes: conciliaciones, '
        'programación de pagos, nómina y archivos de importación. Cada '
        'módulo sigue el mismo orden: cargar, ajustar, generar y revisar.'
        '</p></div><div class="gm-hero-datos">' + "".join(
            f'<div class="gm-hero-dato"><b>{v}</b><span>{e}</span></div>'
            for v, e in datos) + '</div></div>', unsafe_allow_html=True)


def modulo_inicio():
    _portada()

    titulo_seccion(
        "Recorrido por la plataforma", None,
        "Todos los módulos siguen el mismo orden: <b>1. cargar</b> los "
        "documentos, <b>2. ajustar parámetros</b> si hace falta, "
        "<b>3. generar</b> y <b>4. revisar</b> el resultado antes de "
        "descargar. Los archivos se procesan en este equipo.")

    st.markdown(
        '<div class="gm-novedad"><span class="gm-pill">Novedades</span>'
        '<span>Programación de pagos de <b>EMPRESA E</b> (por pagar y por cobrar)'
        ' · <b>Nómina electrónica</b> con el layout de carga · Conciliación '
        'DIAN con comparador de números de documento.</span></div>',
        unsafe_allow_html=True)
    st.write("")

    # v6.11: cuadricula uniforme de 3 columnas (antes filas irregulares).
    # Las claves de los botones (ir_<modulo>) no cambian.
    for fila in range(0, len(_TARJETAS_INICIO), 3):
        columnas = st.columns(3)
        for col, datos in zip(columnas, _TARJETAS_INICIO[fila:fila + 3]):
            clave, titulo, cuerpo, etiqueta, explicacion, boton, primario = \
                datos
            with col:
                ico, tono = ICONO_TARJETA.get(clave, ("rayo", "magenta"))
                tarjeta(titulo, cuerpo, etiqueta=etiqueta,
                        explicacion=explicacion, clase="inicio",
                        icono=ico, tono=tono)
                # El boton es el pie de la tarjeta (sin espacio entre ambos).
                st.button(boton + "  →", key="ir_" + clave, on_click=ir_a,
                          args=(clave,), type="secondary",
                          use_container_width=True)
        st.write("")

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
