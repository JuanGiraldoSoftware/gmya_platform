"""Excel de resultado de la conciliacion DIAN (openpyxl).

Contrato:
  construir_excel_dian(analisis) -> libro .xlsx con hojas de resumen,
      detalle por concepto y ACUSES. Colores de alerta: ROJO_ALERTA y
      MORADO_ALERTA (dian/parametros).

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.dian.parametros, gmya.modulos.dian.lectura, gmya.modulos.dian.acuses, gmya.modulos.dian.analisis
"""

import datetime
import io
import re
from collections import OrderedDict

from gmya.comun.texto import comparable, solo_nit
from gmya.comun.numeros import numero
from gmya.modulos.dian.parametros import (
    alerta_documento_dian, AMARILLO, dentro_de, TOLERANCIA_IVA_DOCUMENTO, AZUL_ALERTA, AZUL_NO_DIAN, CIAN_REVISADO,
    CONVENCIONES_DIAN, dato, FORMATO_CONTABLE, LETRA_ROJA_ALERTA,
    MORADO_ALERTA, resaltar_si_no_es_cero, ROJO_ALERTA, VERDE_ENCABEZADO,
)
from gmya.modulos.dian.lectura import _texto_fila
from gmya.modulos.dian.acuses import explicar_acuse_faltante
from gmya.modulos.dian.analisis import observacion_documento, usa_acuses


# ============================================================
# LIBRO EXCEL DE SALIDA
# ============================================================
def construir_excel_dian(analisis):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    reporte = analisis["reporte"]
    etiqueta = analisis["etiqueta"]
    encabezados = reporte["encabezados"]

    def relleno(color):
        return PatternFill("solid", fgColor=color)

    fuente_cuerpo = Font(name="Calibri", size=10, color="000000")
    fuente_negrita = Font(name="Calibri", size=10, bold=True, color="000000")
    fuente_roja = Font(name="Calibri", size=10, color="FF0000")
    fuente_encabezado = Font(name="Calibri", size=10, bold=True,
                             color="FFFFFF")
    borde_medio = Border(bottom=Side(style="medium"))
    derecha = Alignment(horizontal="right")
    centro = Alignment(horizontal="center", vertical="center",
                       wrap_text=True)

    columnas_valor = set(reporte["columnas_valor"])
    tablas_usadas = set()

    wb = Workbook()
    wb.remove(wb.active)

    def nombre_tabla(base):
        base = re.sub(r"[^A-Za-z0-9_]", "_", base)
        if not re.match(r"[A-Za-z_]", base):
            base = "T_" + base
        nombre, n = base, 2
        while nombre in tablas_usadas:
            nombre, n = f"{base}_{n}", n + 1
        tablas_usadas.add(nombre)
        return nombre

    def escribir_tabla_dian(hoja, cabecera, filas, anchos, nombre,
                            estilos_fila=None):
        hoja.append(cabecera)
        for celda in hoja[1]:
            celda.font = fuente_encabezado
            celda.fill = relleno(VERDE_ENCABEZADO)
            celda.alignment = centro
            if celda.value in columnas_valor:
                celda.number_format = FORMATO_CONTABLE
        for fila in filas:
            hoja.append(fila)
        for r in range(2, hoja.max_row + 1):
            for c, titulo in enumerate(cabecera, start=1):
                celda = hoja.cell(r, c)
                celda.font = fuente_cuerpo
                if titulo in columnas_valor:
                    celda.number_format = FORMATO_CONTABLE
            if estilos_fila:
                estilos_fila(r)
        ultima = max(hoja.max_row, 2)
        if hoja.max_row == 1:
            hoja.append([None] * len(cabecera))
        ref = f"A1:{get_column_letter(len(cabecera))}{ultima}"
        tabla = Table(displayName=nombre_tabla(nombre), ref=ref)
        tabla.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showRowStripes=True)
        hoja.add_table(tabla)
        for letra, ancho in anchos.items():
            hoja.column_dimensions[letra].width = ancho
        hoja.freeze_panes = "A2"
        return ultima

    def anchos_por_titulo(cabecera):
        base = {}
        original = {encabezados[i]: reporte["anchos"].get(
            get_column_letter(i + 1)) for i in range(len(encabezados))}
        preferidos = {
            "Tipo de documento": 30, "CUFE/CUDE": 12, "Folio": 10,
            "Prefijo": 8, "Divisa": 7, "Forma de Pago": 8,
            "Medio de Pago": 8, "Fecha Emisión": 11, "Fecha Recepción": 19,
            "NIT Emisor": 12, "Nombre Emisor": 32, "NIT Receptor": 12,
            "Nombre Receptor": 32, "Total": 15, "Estado": 23, "Grupo": 9,
            "FORMA DE PAGO2": 11, "ACUSE 1": 9, "ACUSE 2": 9, "ACUSE 3": 9,
            "DOCUMENTO HELISA": 20, "CONCILIACION HELISA": 34,
        }
        for i, titulo in enumerate(cabecera, start=1):
            ancho = preferidos.get(titulo) or original.get(titulo) or \
                (12 if titulo in columnas_valor else 10)
            base[get_column_letter(i)] = ancho
        return base

    # ---------------- Hoja 1: reporte DIAN original ----------------
    # Las facturas con alerta tambien se pintan en el reporte original.
    alertas_reporte = {}
    for resultado in analisis["resultados"]:
        for j, factura in enumerate(resultado["dian"]):
            color, _, alerta = alerta_documento_dian(resultado, j, factura,
                                                     reporte)
            if alerta or color == ROJO_ALERTA:
                alertas_reporte[id(factura)] = color
    registros = reporte["registros"]
    hoja = wb.create_sheet(reporte["hoja"][:31] or "DIAN")

    def estilo_reporte(r, hoja=hoja):
        color = alertas_reporte.get(id(registros[r - 2])) \
            if r - 2 < len(registros) else None
        if color:
            for c in range(1, len(encabezados) + 1):
                hoja.cell(r, c).fill = relleno(color)

    escribir_tabla_dian(hoja, encabezados, registros,
                        anchos_por_titulo(encabezados), reporte["hoja"],
                        estilo_reporte if alertas_reporte else None)
    hoja.column_dimensions["B"].width = 12

    referencias = {}

    # ---------------- Hojas por concepto ----------------
    for resultado in analisis["resultados"]:
        concepto = resultado["concepto"]
        clave = concepto["clave"]
        titulo_hoja = f"{clave} DIAN {etiqueta}"[:31]
        hoja = wb.create_sheet(titulo_hoja)
        hoja.sheet_properties.tabColor = CIAN_REVISADO

        if resultado["modo"] == "resumen":
            cabecera = encabezados + ["CONCILIACION HELISA"]
            alertas = [alerta_documento_dian(resultado, j, f, reporte)
                       for j, f in enumerate(resultado["dian"])]
            filas = [list(f[:len(encabezados)]) + [a[1]]
                     for f, a in zip(resultado["dian"], alertas)]

            def estilo_resumen(r, cabecera=cabecera, alertas=alertas,
                               hoja=hoja):
                color, _, alerta = alertas[r - 2]
                if not color:
                    return
                for c in range(1, len(cabecera) + 1):
                    hoja.cell(r, c).fill = relleno(color)
                if alerta:
                    hoja.cell(r, len(cabecera)).font = Font(
                        name="Calibri", size=10, bold=True,
                        color=LETRA_ROJA_ALERTA)

            ultima = escribir_tabla_dian(
                hoja, cabecera, filas, anchos_por_titulo(cabecera),
                f"{clave}_DIAN_{etiqueta}", estilo_resumen)
            hoja.column_dimensions[get_column_letter(len(cabecera))].width = 60
            col_iva = encabezados.index("IVA") + 1 \
                if "IVA" in encabezados else None
            col_total = encabezados.index("Total") + 1
            primera_valor = col_iva or col_total
            col_etiqueta = primera_valor - 1
            _bloque_totales_resumen(
                hoja, resultado, ultima, col_etiqueta, primera_valor,
                col_iva, col_total, etiqueta, clave,
                fuente_negrita, fuente_cuerpo, fuente_roja, borde_medio,
                derecha, relleno)
            fila_dif = _resaltar_diferencia_concepto(
                hoja, resultado, col_etiqueta, col_total, analisis)
            fila_nota = fila_dif + 2
            tolerancia = float(analisis["parametros"].get(
                "tolerancia_estado", 0.0))
            if not dentro_de(resultado["diferencia_total"], tolerancia):
                if resultado.get("posibles"):
                    nota = ("El informe Resumen de HELISA no trae el detalle "
                            "por factura: las filas en MORADO son las que "
                            "explican la diferencia por valor. Confirmar con "
                            "el Comprobante diario - Detalle.")
                elif resultado["diferencia_total"] > 0:
                    nota = ("Hay facturas DIAN que no están en HELISA, pero el "
                            "informe Resumen no permite saber cuáles (ninguna "
                            "combinación de 1 a 3 documentos explica la "
                            "diferencia). Cargar el Comprobante diario - "
                            "Detalle o la RELACION para verlas resaltadas.")
                else:
                    nota = ("HELISA tiene más valor que la DIAN: hay "
                            "documentos registrados que no están en el "
                            "reporte DIAN. Cargar el Comprobante diario - "
                            "Detalle o la RELACION para verlos resaltados.")
                celda = hoja.cell(fila_nota, 1, "⚠ " + nota)
                celda.font = Font(name="Calibri", size=10, bold=True,
                                  color=LETRA_ROJA_ALERTA)
                celda.fill = relleno(ROJO_ALERTA)
                fila_nota += 1
            if resultado.get("alerta_asumidos"):
                celda = hoja.cell(fila_nota, 1,
                                  "⚠ " + resultado["alerta_asumidos"])
                celda.font = Font(name="Calibri", size=10, bold=True,
                                  color=LETRA_ROJA_ALERTA)
                celda.fill = relleno(ROJO_ALERTA)
                fila_nota += 1
            _convenciones(hoja, fila_nota + 1, relleno)
            continue

        # ---- Facturas de compra (detalle) ----
        posicion = encabezados.index("Forma de Pago") + 1
        con_acuses = usa_acuses(concepto)
        extra = (["FORMA DE PAGO2", "ACUSE 1", "ACUSE 2", "ACUSE 3"]
                 if con_acuses else ["FORMA DE PAGO2"])
        cabecera = (encabezados[:posicion] + extra + encabezados[posicion:]
                    + ["DOCUMENTO HELISA", "CONCILIACION HELISA"])
        formas = {str(k): v for k, v in
                  analisis["parametros"]["formas_pago"].items()}
        filas = []
        estados = []
        for j, factura in enumerate(resultado["dian"]):
            forma = formas.get(str(dato(reporte, factura, "Forma de Pago"))
                               .strip(), "")
            acuse = list(resultado["acuses"].get(id(factura), ["", "", ""])
                         if con_acuses else [])
            if con_acuses:
                acuse = (acuse + ["", "", ""])[:3]
            doc = resultado["dian_a_helisa"].get(j)
            color, estado_txt, alerta = alerta_documento_dian(
                resultado, j, factura, reporte)
            fila = (list(factura[:posicion]) + [forma] + acuse
                    + list(factura[posicion:len(encabezados)])
                    + [doc["documento"] if doc else None, estado_txt])
            filas.append(fila)
            estados.append((color, alerta))

        def estilo_fila(r, cabecera=cabecera, estados=estados, hoja=hoja):
            color, alerta = estados[r - 2]
            for c in range(1, len(cabecera) + 1):
                hoja.cell(r, c).fill = relleno(color)
            if alerta or color == ROJO_ALERTA:
                hoja.cell(r, len(cabecera)).font = Font(
                    name="Calibri", size=10, bold=True,
                    color=LETRA_ROJA_ALERTA)
            c_forma = cabecera.index("Forma de Pago") + 1
            if formas.get(str(hoja.cell(r, c_forma).value).strip()) == \
                    "CREDITO":
                hoja.cell(r, c_forma).font = Font(name="Calibri", size=10,
                                                  color="0070C0")
            for nombre in ("ACUSE 1", "ACUSE 2", "ACUSE 3"):
                if nombre not in cabecera:
                    continue
                celda = hoja.cell(r, cabecera.index(nombre) + 1)
                if celda.value == "NO":
                    celda.font = Font(name="Calibri", size=10,
                                      color="FF0000", bold=True)

        ultima = escribir_tabla_dian(hoja, cabecera, filas,
                                     anchos_por_titulo(cabecera),
                                     f"{clave}_DIAN_{etiqueta}", estilo_fila)
        for nombre in extra:
            celda = hoja.cell(1, cabecera.index(nombre) + 1)
            celda.fill = relleno(CIAN_REVISADO)
            celda.font = fuente_negrita

        hoja_helisa = f"{clave} HELISA {etiqueta}"[:31]
        fila_total_helisa = _hoja_detalle_helisa(
            wb, hoja_helisa, resultado, relleno)
        referencias[clave] = (hoja_helisa, fila_total_helisa)

        _bloque_totales_compras(
            hoja, resultado, cabecera, ultima, hoja_helisa,
            fila_total_helisa, etiqueta, clave, columnas_valor,
            fuente_negrita, fuente_cuerpo, fuente_roja, borde_medio,
            derecha, relleno)
        c_iva_fc = cabecera.index("IVA") + 1
        fila_dif = _resaltar_diferencia_concepto(
            hoja, resultado, c_iva_fc - 1,
            cabecera.index("Total") + 1, analisis)

        # Documentos de HELISA que no estan en la DIAN (no tienen fila en
        # la tabla DIAN; se listan aqui, en azul, para verlos en la misma
        # hoja).
        fila = fila_dif + 2
        faltan = [d for d in resultado["documentos_helisa"]
                  if d["estado"] == "no_dian"]
        if faltan:
            c_doc = cabecera.index("DOCUMENTO HELISA") + 1
            c_obs = cabecera.index("CONCILIACION HELISA") + 1
            emitido = comparable(concepto["grupo"]) == "EMITIDO"
            c_nit = cabecera.index("NIT Receptor" if emitido
                                   else "NIT Emisor") + 1
            c_fecha = cabecera.index("Fecha Emisión") + 1 \
                if "Fecha Emisión" in cabecera else None
            c_total_fc = cabecera.index("Total") + 1
            celda = hoja.cell(fila, 1, "EN HELISA PERO NO EN EL REPORTE DIAN")
            celda.font = fuente_negrita
            for doc in faltan:
                fila += 1
                if c_fecha:
                    hoja.cell(fila, c_fecha, doc["fecha"])
                hoja.cell(fila, c_nit, doc["nit"])
                hoja.cell(fila, c_nit + 1, doc["beneficiario"])
                hoja.cell(fila, c_iva_fc, doc["iva"]).number_format = \
                    FORMATO_CONTABLE
                hoja.cell(fila, c_total_fc, doc["total_debito"]) \
                    .number_format = FORMATO_CONTABLE
                hoja.cell(fila, c_doc, doc["documento"])
                hoja.cell(fila, c_obs, observacion_documento(
                    doc, resultado["info_dian"]) or "NO REPORTADA EN DIAN")
                for c in range(1, len(cabecera) + 1):
                    hoja.cell(fila, c).fill = relleno(AZUL_ALERTA)
                    hoja.cell(fila, c).font = fuente_cuerpo
                hoja.cell(fila, c_obs).font = Font(
                    name="Calibri", size=10, bold=True,
                    color=LETRA_ROJA_ALERTA)
            fila += 1
        if resultado.get("alerta_asumidos"):
            fila += 1
            celda = hoja.cell(fila, 1, "⚠ " + resultado["alerta_asumidos"])
            celda.font = Font(name="Calibri", size=10, bold=True,
                              color=LETRA_ROJA_ALERTA)
            celda.fill = relleno(ROJO_ALERTA)
            fila += 1
        _convenciones(hoja, fila + 1, relleno)

    # Orden: DIAN, conceptos (FV, NCV, NDV, DSE, NADSE, NC, FC), resumen
    _hoja_resumen(wb, analisis, relleno)
    _hoja_acuses(wb, analisis, relleno)

    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _hoja_acuses(wb, analisis, relleno):
    """
    Hoja ACUSES: para cada factura a credito, que evento se tomo como
    ACUSE 1, 2 y 3 (folio y fecha) o por que quedo en NO; y los eventos
    emitidos que no quedaron asignados a ninguna factura del reporte.
    """
    from openpyxl.styles import Alignment, Font
    reporte = analisis["reporte"]
    con_info = [r for r in analisis["resultados"] if r.get("info_acuses")]
    if not con_info:
        return
    hoja = wb.create_sheet("ACUSES")
    negrita = Font(name="Calibri", size=10, bold=True)
    normal = Font(name="Calibri", size=10)
    blanca = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    roja = Font(name="Calibri", size=10, bold=True, color=LETRA_ROJA_ALERTA)
    ajuste = Alignment(wrap_text=True, vertical="top")
    hoja.cell(1, 1, "ACUSES DE FACTURAS A CRÉDITO").font = Font(
        name="Calibri", size=12, bold=True)
    info0 = con_info[0]["info_acuses"]
    prefijos = info0["prefijos"]
    explicacion = [
        "Cómo se determinan: el reporte DIAN no indica a qué factura "
        "corresponde cada evento (Application response), así que se cruza "
        "por proveedor: NIT Receptor del evento = NIT Emisor de la factura.",
        "La clase de acuse sale del prefijo del folio del evento: "
        + ", ".join(f"ACUSE {i + 1} = {p}" for i, p in enumerate(prefijos)
                    if p) + ". Si ACUSE 1 y ACUSE 2 tienen el mismo "
        "prefijo, cada factura toma dos eventos seguidos.",
        "Un evento solo sirve para una factura emitida ese mismo día o "
        "antes, y se usa una sola vez. Los eventos rechazados no cuentan.",
        "Eventos considerados hasta: " + (f"{info0['corte']:%d/%m/%Y}"
                                          if info0.get("corte") else "-")
        + (". Incluye reportes posteriores cargados para acuses."
           if info0.get("hay_posteriores") else
           ". Si el acuse se dio después de esa fecha no aparece: carga un "
           "reporte DIAN posterior en 'Eventos posteriores'."),
    ]
    fila = 2
    for texto in explicacion:
        fila += 1
        hoja.cell(fila, 1, texto).font = normal
    fila += 2
    cabecera = ["CONCEPTO", "FACTURA", "FECHA", "NIT PROVEEDOR", "PROVEEDOR",
                "TOTAL", "ACUSE 1", "ACUSE 2", "ACUSE 3", "OBSERVACIÓN"]
    for c, titulo in enumerate(cabecera, start=1):
        celda = hoja.cell(fila, c, titulo)
        celda.font = blanca
        celda.fill = relleno(VERDE_ENCABEZADO)
    hoja.freeze_panes = hoja.cell(fila + 1, 1)
    for resultado in con_info:
        info = resultado["info_acuses"]
        clave = resultado["concepto"]["clave"]
        for factura in resultado["dian"]:
            marcas = info["marcas"].get(id(factura)) or []
            if "OK" not in marcas and "NO" not in marcas:
                continue
            asignados = info["eventos"].get(id(factura)) or [None] * 3
            fila += 1
            prefijo = dato(reporte, factura, "Prefijo") or ""
            folio = dato(reporte, factura, "Folio") or ""
            valores = [clave, f"{prefijo}{folio}",
                       dato(reporte, factura, "Fecha Emisión"),
                       solo_nit(dato(reporte, factura, "NIT Emisor")),
                       dato(reporte, factura, "Nombre Emisor"),
                       numero(dato(reporte, factura, "Total"))]
            motivos = []
            for k in range(3):
                e = asignados[k]
                if e:
                    valores.append(f"{e['folio']} ({e['fecha']:%d/%m/%Y})"
                                   if e["fecha"] else e["folio"])
                elif marcas[k] == "NO":
                    valores.append("NO")
                    motivos.append(f"ACUSE {k + 1}: " + explicar_acuse_faltante(
                        info, reporte, factura, k))
                else:
                    valores.append("")
            agrupados = OrderedDict()
            for m in motivos:
                nombre, texto = m.split(": ", 1)
                agrupados.setdefault(texto, []).append(nombre)
            valores.append(" · ".join(
                f"{' y '.join(n)}: {t}" for t, n in agrupados.items())
                or "Con acuses")
            for c, valor in enumerate(valores, start=1):
                celda = hoja.cell(fila, c, valor)
                celda.font = normal
                if c == 6:
                    celda.number_format = FORMATO_CONTABLE
                if c in (7, 8, 9) and valor == "NO":
                    celda.font = roja
            hoja.cell(fila, 10).alignment = ajuste
            if motivos:
                for c in range(1, len(cabecera) + 1):
                    hoja.cell(fila, c).fill = relleno(AMARILLO)

    libres = info0["libres"]
    if libres:
        fila += 2
        hoja.cell(fila, 1, "EVENTOS EMITIDOS SIN FACTURA EN ESTE REPORTE "
                           "(de facturas de otros periodos o de contado)"
                  ).font = negrita
        fila += 1
        for c, titulo in enumerate(["EVENTO", "FECHA", "NIT PROVEEDOR",
                                    "PROVEEDOR", "ORIGEN"], start=1):
            celda = hoja.cell(fila, c, titulo)
            celda.font = blanca
            celda.fill = relleno(VERDE_ENCABEZADO)
        for e in sorted(libres, key=lambda e: (e["nombre"], e["momento"]
                                               or datetime.datetime.min)):
            fila += 1
            for c, valor in enumerate(
                    [e["folio"], e["fecha"], e["nit"], e["nombre"],
                     "Reporte posterior" if e["origen"] != "reporte"
                     else "Reporte DIAN"], start=1):
                celda = hoja.cell(fila, c, valor)
                celda.font = normal
                if c == 2:
                    celda.number_format = "DD/MM/YYYY"
    for c, ancho in enumerate([10, 16, 12, 14, 34, 15, 20, 20, 20, 70],
                              start=1):
        hoja.column_dimensions[chr(64 + c)].width = ancho


def _resaltar_diferencia_concepto(hoja, resultado, col_etiqueta, col_total,
                                  analisis):
    """Pinta en rojo la fila DIFERENCIA del concepto si no da 0."""
    from openpyxl.utils import get_column_letter as L
    _, celda = resultado["celda_diferencia"]
    fila = int(re.sub(r"\D", "", celda))
    tolerancia = float(analisis["parametros"].get("tolerancia_estado", 0.0))
    resaltar_si_no_es_cero(
        hoja, f"{L(col_etiqueta + 1)}{fila}:{L(col_total)}{fila}", tolerancia)
    return fila


def _convenciones(hoja, fila, relleno, convenciones=None):
    """Leyenda de colores al pie de la hoja."""
    from openpyxl.styles import Font
    hoja.cell(fila, 1, "CONVENCIONES DE COLOR").font = Font(
        name="Calibri", size=10, bold=True)
    for color, texto in convenciones or CONVENCIONES_DIAN:
        fila += 1
        hoja.cell(fila, 1).fill = relleno(color)
        hoja.cell(fila, 2, texto).font = Font(name="Calibri", size=10)
    return fila


def _bloque_totales_resumen(hoja, resultado, ultima, col_etiqueta,
                            primera_valor, col_iva, col_total, etiqueta,
                            clave, fuente_negrita, fuente_cuerpo,
                            fuente_roja, borde_medio, derecha, relleno):
    from openpyxl.utils import get_column_letter as L

    fila = ultima + 2
    f_dian = fila
    hoja.cell(fila, col_etiqueta, f"TOTAL {clave} DIAN {etiqueta}")
    hoja.cell(fila, col_etiqueta).font = fuente_negrita
    hoja.cell(fila, col_etiqueta).alignment = derecha
    for c in range(primera_valor, col_total + 1):
        celda = hoja.cell(fila, c, f"=SUM({L(c)}2:{L(c)}{ultima})")
        celda.font = fuente_negrita
        celda.number_format = FORMATO_CONTABLE

    fila += 1
    f_helisa = fila
    hoja.cell(fila, col_etiqueta, f"TOTAL {clave} HELISA {etiqueta}")
    hoja.cell(fila, col_etiqueta).alignment = derecha
    if col_iva and resultado.get("iva_helisa") is not None:
        hoja.cell(fila, col_iva, resultado["iva_helisa"]).number_format = \
            FORMATO_CONTABLE
    hoja.cell(fila, col_total, resultado["total_helisa"]).number_format = \
        FORMATO_CONTABLE

    f_final = f_helisa
    if resultado["ajustes"]:
        for ajuste in resultado["ajustes"]:
            fila += 1
            hoja.cell(fila, col_etiqueta, ajuste["etiqueta"])
            hoja.cell(fila, col_etiqueta).alignment = derecha
            hoja.cell(fila, col_total, ajuste["valor"]).number_format = \
                FORMATO_CONTABLE
            for c in (col_etiqueta, col_total):
                hoja.cell(fila, c).fill = relleno(AMARILLO)
        fila += 1
        f_final = fila
        hoja.cell(fila, col_etiqueta, f"TOTAL {clave} HELISA")
        hoja.cell(fila, col_etiqueta).alignment = derecha
        columnas = [col_total] + ([col_iva] if col_iva and
                                  resultado.get("iva_helisa") is not None
                                  else [])
        for c in columnas:
            celda = hoja.cell(fila, c,
                              f"=SUM({L(c)}{f_helisa}:{L(c)}{fila - 1})")
            celda.number_format = FORMATO_CONTABLE
        for c in [col_etiqueta] + columnas:
            hoja.cell(fila, c).font = fuente_negrita
            hoja.cell(fila, c).border = borde_medio

    fila += 1
    hoja.cell(fila, col_etiqueta, "DIFERENCIA").font = fuente_roja
    hoja.cell(fila, col_etiqueta).alignment = derecha
    columnas = [col_total]
    if col_iva and resultado.get("iva_helisa") is not None:
        columnas.insert(0, col_iva)
    for c in columnas:
        celda = hoja.cell(fila, c, f"=+{L(c)}{f_dian}-{L(c)}{f_final}")
        celda.font = fuente_roja
        celda.number_format = FORMATO_CONTABLE
    resultado["celda_diferencia"] = (hoja.title, f"{L(col_total)}{fila}")


def _bloque_totales_compras(hoja, resultado, cabecera, ultima, hoja_helisa,
                            fila_total_helisa, etiqueta, clave,
                            columnas_valor, fuente_negrita, fuente_cuerpo,
                            fuente_roja, borde_medio, derecha, relleno):
    from openpyxl.utils import get_column_letter as L

    c_iva = cabecera.index("IVA") + 1
    c_total = cabecera.index("Total") + 1
    c_inc = cabecera.index("INC") + 1 if "INC" in cabecera else None
    c_etq = c_iva - 1
    ref = f"'{hoja_helisa}'!"
    t = fila_total_helisa

    fila = ultima + 2
    f_dian = fila
    hoja.cell(fila, c_etq, f"TOTAL {clave} DIAN {etiqueta}")
    for c in range(c_iva, c_total + 1):
        celda = hoja.cell(fila, c, f"=SUM({L(c)}2:{L(c)}{ultima})")
        celda.font = fuente_negrita
        celda.number_format = FORMATO_CONTABLE
    hoja.cell(fila, c_etq).font = fuente_negrita

    fila += 1
    f_helisa = fila
    hoja.cell(fila, c_etq, f"TOTAL {clave} HELISA {etiqueta}")
    col = resultado["columnas_helisa"]
    hoja.cell(fila, c_iva, f"=+{ref}{col['iva']}{t}")
    if c_inc:
        hoja.cell(fila, c_inc, f"=+{ref}{col['inc']}{t}")
    hoja.cell(fila, c_total, f"=+{ref}{col['total']}{t}")

    fila += 1
    f_no_dian = fila
    hoja.cell(fila, c_etq, "TOTAL FACT NO DIAN HELISA")
    hoja.cell(fila, c_iva, f"=-{ref}{col['iva_nd']}{t}")
    hoja.cell(fila, c_total, f"=-{ref}{col['nd']}{t}")
    for c in range(c_etq, c_total + 1):
        hoja.cell(fila, c).fill = relleno(AZUL_NO_DIAN)
    f_ultimo_ajuste = f_no_dian

    # v6.10.1: impuesto al consumo que HELISA discrimina y la DIAN trae
    # dentro del total con INC en 0 (p. ej. COLOMBIA TELECOMUNICACIONES).
    inc_nd = resultado.get("inc_no_discriminado") or 0.0
    if inc_nd and c_inc:
        fila += 1
        f_ultimo_ajuste = fila
        hoja.cell(fila, c_etq, "MENOS INC NO DISCRIMINADO EN DIAN")
        hoja.cell(fila, c_inc, -inc_nd)
        for c in range(c_etq, c_total + 1):
            hoja.cell(fila, c).fill = relleno(AZUL_NO_DIAN)
        nombres = ", ".join(sorted({
            str(d.get("beneficiario") or "").strip()
            for d in resultado.get("documentos_helisa") or []
            if d.get("inc_no_discriminado")}))[:120]
        hoja.cell(fila, c_total + 1,
                  f"Impuesto al consumo discriminado en HELISA que la DIAN "
                  f"reporta dentro del total (INC en 0): {nombres}. "
                  "Revisar.").font = fuente_cuerpo

    fila += 1
    f_final = fila
    hoja.cell(fila, c_etq, f"TOTAL {clave} HELISA")
    for c in range(c_iva, c_total + 1):
        hoja.cell(fila, c,
                  f"=SUM({L(c)}{f_helisa}:{L(c)}{f_ultimo_ajuste})")
    for c in range(c_etq, c_total + 1):
        hoja.cell(fila, c).font = fuente_negrita
        hoja.cell(fila, c).border = borde_medio

    fila += 1
    hoja.cell(fila, c_etq, "DIFERENCIA")
    for c in range(c_iva, c_total + 1):
        hoja.cell(fila, c, f"=+{L(c)}{f_dian}-{L(c)}{f_final}")
    for c in range(c_etq, c_total + 1):
        hoja.cell(fila, c).font = fuente_roja

    for r in range(f_dian, fila + 1):
        hoja.cell(r, c_etq).alignment = derecha
        for c in range(c_iva, c_total + 1):
            hoja.cell(r, c).number_format = FORMATO_CONTABLE
    resultado["celda_diferencia"] = (hoja.title, f"{L(c_total)}{fila}")


def _estilo_helisa(celda_xl, estilo):
    from openpyxl.styles import Alignment, Font, PatternFill
    if not estilo:
        celda_xl.font = Font(name="Times New Roman", size=8)
        return
    color = estilo.get("color") or "000000"
    celda_xl.font = Font(name=estilo.get("fuente") or "Times New Roman",
                         size=estilo.get("tamano") or 8,
                         bold=estilo.get("negrita", False),
                         italic=estilo.get("cursiva", False),
                         color=color if len(color) == 6 else "000000")
    if estilo.get("relleno") and len(estilo["relleno"]) == 6:
        celda_xl.fill = PatternFill("solid", fgColor=estilo["relleno"])
    if estilo.get("horizontal") in ("left", "right", "center"):
        celda_xl.alignment = Alignment(horizontal=estilo["horizontal"],
                                       vertical="top")


def _hoja_detalle_helisa(wb, titulo, resultado, relleno):
    """
    Copia el Comprobante diario - Detalle de HELISA sin los encabezados de
    pagina repetidos y agrega las columnas de conciliacion:
      U IVA | V INP. CONSUMO | W IVA NO DIAN | X NO DIAN | Y OBSERVACIONES
    """
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter as L

    informe = resultado["informe"]
    columnas = informe["columnas"]
    docs = {d["documento"]: d for d in resultado["documentos_helisa"]}
    info_dian = resultado["info_dian"]
    hoja = wb.create_sheet(titulo)
    desplazamiento = 1                     # columna A = numeracion
    c_deb = columnas["debitos"] + desplazamiento
    c_cre = columnas["creditos"] + desplazamiento
    max_col = max([c["col"] for f in informe["filas_titulo"]
                   + [informe["fila_encabezado"]] for c in f["celdas"]]
                  + [c["col"] + c.get("span", 0)
                     for _, f, _ in informe["cuerpo"] for c in f["celdas"]]
                  + [columnas["creditos"] or 0]) + desplazamiento
    C_IVA = max(21, max_col + 2)
    C_INC, C_IVA_ND, C_ND, C_OBS = C_IVA + 1, C_IVA + 2, C_IVA + 3, C_IVA + 4
    negrita = Font(name="Calibri", size=11, bold=True)
    normal = Font(name="Calibri", size=11)
    centro = Alignment(horizontal="center")

    def volcar(fila_xml, r, forzar_ceros=False):
        for celda in fila_xml["celdas"]:
            c = celda["col"] + desplazamiento
            valor = celda["valor"]
            x = hoja.cell(r, c, valor)
            _estilo_helisa(x, celda["estilo"])
            if isinstance(valor, float):
                x.number_format = FORMATO_CONTABLE
            if celda["span"]:
                hoja.merge_cells(start_row=r, start_column=c,
                                 end_row=r, end_column=c + celda["span"])
        if forzar_ceros:
            for c in (c_deb, c_cre):
                if hoja.cell(r, c).value in (None, ""):
                    hoja.cell(r, c, 0.0).number_format = FORMATO_CONTABLE
        if fila_xml.get("alto"):
            hoja.row_dimensions[r].height = fila_xml["alto"]

    r = 0
    for fila_xml in informe["filas_titulo"]:
        texto = comparable(_texto_fila(fila_xml))
        if not texto or re.fullmatch(r"PAGINA \d+ DE \d+", texto):
            continue
        r += 1
        volcar(fila_xml, r)

    r += 1
    fila_cab = r
    volcar(informe["fila_encabezado"], r)
    for c, texto in ((C_IVA, "IVA"), (C_INC, "INP. CONSUMO"),
                     (C_IVA_ND, "IVA NO DIAN"), (C_ND, "NO DIAN"),
                     (C_OBS, "OBSERVACIONES")):
        x = hoja.cell(r, c, texto)
        x.font = negrita
        x.alignment = centro
        if c in (C_IVA_ND, C_ND):
            x.fill = relleno(AZUL_NO_DIAN)

    for tipo, fila_xml, clave in informe["cuerpo"]:
        r += 1
        volcar(fila_xml, r, forzar_ceros=(tipo == "mov"))
        doc = docs.get(clave)
        if doc is None:
            continue
        color = None
        if doc["estado"] == "no_dian":
            color = AZUL_ALERTA
        elif doc["no_deducible"] or doc["estado"] == "diferencia" or \
                doc.get("nivel") == 4 or doc.get("nit_distinto_revisar") or (
                    doc.get("dif_iva") is not None
                    and not dentro_de(doc["dif_iva"],
                                      TOLERANCIA_IVA_DOCUMENTO)):
            color = AMARILLO

        if tipo == "mov":
            mov = next((m for m in doc["movimientos"]
                        if m["fila"] is fila_xml), None)
            if mov:
                c_lado, c_otro = ((c_cre, c_deb)
                                  if mov.get("lado_iva") == "credito"
                                  else (c_deb, c_cre))
                formula = f"=+{L(c_lado)}{r}-{L(c_otro)}{r}"
            if mov and (mov["es_iva"] or (doc.get("iva_verificado")
                                          and mov.get("es_iva_amplio"))):
                hoja.cell(r, C_IVA, formula)
                if doc["estado"] == "no_dian":
                    hoja.cell(r, C_IVA_ND, f"=+{L(C_IVA)}{r}")
            if mov and mov["es_consumo"]:
                hoja.cell(r, C_INC, formula)
            if color:
                for c in range(1, C_OBS + 1):
                    hoja.cell(r, c).fill = relleno(color)
        elif tipo == "total":
            if doc["estado"] == "no_dian":
                hoja.cell(r, C_ND, f"=+{L(c_cre)}{r}")
            elif doc.get("ajuste_nd"):
                # Lo que se compara con la DIAN (total DIAN, o el neto si
                # hay cruce interno de cuentas): NO DIAN = total − eso.
                comparado = round(doc["total_debito"] - doc["ajuste_nd"], 2)
                hoja.cell(r, C_ND, f"=+{L(c_cre)}{r}-{comparado}")
            obs = observacion_documento(doc, info_dian)
            if obs:
                hoja.cell(r, C_OBS, obs)
            if color:
                for c in range(1, C_OBS + 1):
                    hoja.cell(r, c).fill = relleno(color)
        for c in range(C_IVA, C_OBS + 1):
            x = hoja.cell(r, c)
            if c < C_OBS:
                x.number_format = FORMATO_CONTABLE
            if tipo == "total" and c == C_ND and doc.get("ajuste_nd"):
                x.font = Font(name="Calibri", size=11, color="FF0000")
            elif tipo == "total" and c == C_OBS and color:
                x.font = Font(name="Calibri", size=11, bold=True,
                              color=LETRA_ROJA_ALERTA)
            else:
                x.font = negrita if tipo == "total" else normal

    ultima_detalle = r
    r += 2
    fila_total = r
    if informe["total_general"]:
        volcar(informe["total_general"], r)
    for c in (C_IVA, C_INC, C_IVA_ND, C_ND):
        x = hoja.cell(r, c, f"=SUM({L(c)}{fila_cab + 1}:{L(c)}{r - 1})")
        x.font = negrita
        x.number_format = FORMATO_CONTABLE
        if c in (C_IVA_ND, C_ND):
            x.fill = relleno(AZUL_NO_DIAN)

    r += 1
    for fila_xml in informe["pie"]:
        r += 1
        volcar(fila_xml, r)
    _convenciones(hoja, r + 2, relleno, [
        (AZUL_ALERTA, "Registrado en HELISA pero no está en el reporte DIAN"),
        (AMARILLO, "Está en la DIAN pero hay que revisar: valor, IVA, folio "
                   "o gasto no deducible (ver OBSERVACIONES)")])

    # Numeracion (columna A) desde el encabezado hasta el ultimo documento
    for n, fila in enumerate(range(fila_cab, ultima_detalle + 1), start=1):
        x = hoja.cell(fila, 1, n)
        x.font = Font(name="Calibri", size=11,
                      bold=hoja.cell(fila, c_deb).font.b
                      if hoja.cell(fila, c_deb).font else False)

    anchos = informe.get("anchos") or []
    for i, ancho in enumerate(anchos, start=1):
        if ancho:
            hoja.column_dimensions[L(i + desplazamiento)].width = \
                max(2.4, ancho / 4.8)
    hoja.column_dimensions["A"].width = 5
    for c, ancho in ((C_IVA, 13), (C_INC, 13), (C_IVA_ND, 12), (C_ND, 13),
                     (C_OBS, 34)):
        hoja.column_dimensions[L(c)].width = ancho
    for c in (c_deb, c_cre):
        hoja.column_dimensions[L(c)].width = 15
    hoja.auto_filter.ref = f"A{fila_cab}:{L(C_OBS)}{ultima_detalle}"
    hoja.freeze_panes = f"A{fila_cab + 1}"
    resultado["columnas_helisa"] = {
        "iva": L(C_IVA), "inc": L(C_INC), "iva_nd": L(C_IVA_ND),
        "nd": L(C_ND), "total": L(c_cre)}
    return fila_total


def _hoja_resumen(wb, analisis, relleno):
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter as L

    hoja = wb.create_sheet("RESUMEN CONCILIACION")
    hoja.sheet_properties.tabColor = "E0118F"
    hoja.sheet_view.showGridLines = False
    tinta = "272526"
    magenta = "E0118F"
    blanco = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    titulo = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    negrita = Font(name="Calibri", size=10, bold=True, color="000000")
    normal = Font(name="Calibri", size=10, color="000000")
    delgado = Side(style="thin", color="BFBFBF")
    borde = Border(left=delgado, right=delgado, top=delgado, bottom=delgado)

    hoja.merge_cells("A1:I1")
    hoja["A1"] = "CONCILIACIÓN DIAN vs. HELISA"
    hoja["A1"].font = titulo
    hoja["A1"].fill = relleno(tinta)
    hoja.row_dimensions[1].height = 28
    hoja.merge_cells("A2:I2")
    hoja["A2"] = (f"{analisis['empresa']}  ·  NIT {analisis['nit']}  ·  "
                  f"MES: {analisis['etiqueta']}")
    hoja["A2"].font = blanco
    hoja["A2"].fill = relleno(magenta)

    cab = ["CONCEPTO", "DOCUMENTOS DIAN", "TOTAL DIAN", "TOTAL HELISA",
           "AJUSTES HELISA", "TOTAL HELISA CONCILIADO", "DIFERENCIA TOTAL",
           "DIFERENCIA IVA", "ESTADO"]
    fila = 4
    for c, texto in enumerate(cab, start=1):
        x = hoja.cell(fila, c, texto)
        x.font = blanco
        x.fill = relleno(VERDE_ENCABEZADO)
        x.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
        x.border = borde
    hoja.row_dimensions[fila].height = 30

    for resultado in analisis["resultados"]:
        fila += 1
        c = resultado["concepto"]
        ajustes = resultado["total_helisa_ajustado"] - resultado[
            "total_helisa"]
        hoja_dif, celda_dif = resultado.get("celda_diferencia", (None, None))
        valores = [
            f"{c['clave']} - {c['nombre'].upper()}",
            len(resultado["dian"]),
            resultado["total_dian"],
            resultado["total_helisa"],
            ajustes,
            resultado["total_helisa_ajustado"],
            f"=+'{hoja_dif}'!{celda_dif}" if hoja_dif else
            resultado["diferencia_total"],
            resultado["diferencia_iva"],
            estado_concepto(resultado, analisis["parametros"]),
        ]
        for col, valor in enumerate(valores, start=1):
            x = hoja.cell(fila, col, valor)
            x.font = normal
            x.border = borde
            if col >= 3 and col <= 8:
                x.number_format = FORMATO_CONTABLE
        resaltar_si_no_es_cero(
            hoja, f"G{fila}:H{fila}",
            float(analisis["parametros"].get("tolerancia_estado", 0.0)))
        estado = hoja.cell(fila, 9)
        estado.font = Font(name="Calibri", size=10, bold=True,
                           color="FFFFFF")
        estado.fill = relleno({"CONCILIADO": "348441",
                               "CUADRA, CON PENDIENTES": "BF8F00"}.get(
                                   estado.value, "C00000"))
        estado.alignment = Alignment(horizontal="center")

    # Partidas por revisar
    fila += 2
    hoja.cell(fila, 1, "PARTIDAS PARA REVISAR").font = Font(
        name="Calibri", size=12, bold=True, color=magenta)
    fila += 1
    cab2 = ["CONCEPTO", "DOCUMENTO", "FECHA", "NIT", "TERCERO", "VALOR",
            "HALLAZGO"]
    for c, texto in enumerate(cab2, start=1):
        x = hoja.cell(fila, c, texto)
        x.font = blanco
        x.fill = relleno(tinta)
        x.border = borde
    partidas = partidas_para_revisar(analisis)
    for p in partidas:
        fila += 1
        for c, valor in enumerate([p["concepto"], p["documento"], p["fecha"],
                                   p["nit"], p["tercero"], p["valor"],
                                   p["hallazgo"]], start=1):
            x = hoja.cell(fila, c, valor)
            x.font = normal
            x.border = borde
            x.fill = relleno(p.get("color") or AMARILLO)
            if c == 6:
                x.number_format = FORMATO_CONTABLE
        hoja.cell(fila, 7).font = Font(name="Calibri", size=10, bold=True,
                                       color=LETRA_ROJA_ALERTA)
    if not partidas:
        fila += 1
        hoja.cell(fila, 1, "Sin partidas pendientes.").font = normal

    # Documentos DIAN que no se concilian en este informe
    fila += 2
    hoja.cell(fila, 1, "DOCUMENTOS DIAN NO INCLUIDOS EN LA CONCILIACIÓN "
              "(INFORMATIVO)").font = Font(name="Calibri", size=12,
                                           bold=True, color=magenta)
    fila += 1
    for c, texto in enumerate(["GRUPO", "TIPO DE DOCUMENTO", "CANTIDAD",
                               "TOTAL"], start=1):
        x = hoja.cell(fila, c, texto)
        x.font = blanco
        x.fill = relleno(tinta)
        x.border = borde
    for item in analisis["no_conciliados"]:
        fila += 1
        for c, valor in enumerate([item["grupo"], item["tipo"],
                                   item["cantidad"], item["total"]], start=1):
            x = hoja.cell(fila, c, valor)
            x.font = normal
            x.border = borde
            if c == 4:
                x.number_format = FORMATO_CONTABLE

    # Avisos y parametros
    fila += 2
    hoja.cell(fila, 1, "AVISOS Y PARÁMETROS").font = Font(
        name="Calibri", size=12, bold=True, color=magenta)
    for aviso in analisis["avisos"]:
        fila += 1
        hoja.cell(fila, 1, "Aviso: " + aviso).font = Font(
            name="Calibri", size=10, color="C00000")
    p = analisis["parametros"]
    for texto, valor in [
        ("Tolerancia de redondeo por factura (COP)",
         p["tolerancia_redondeo"]),
        ("Prefijo eventos ACUSE 1", p.get("prefijo_acuse_1") or "-"),
        ("Prefijo eventos ACUSE 2", p.get("prefijo_acuse_2") or "-"),
        ("Prefijo eventos ACUSE 3", p.get("prefijo_acuse_3") or "-"),
        ("Cuentas de IVA (palabras)", ", ".join(p["palabras_iva"])),
        ("Cuentas impuesto al consumo", ", ".join(p["palabras_consumo"])),
        ("Gasto no deducible", ", ".join(p["palabras_no_deducible"])),
    ]:
        fila += 1
        hoja.cell(fila, 1, texto).font = negrita
        hoja.cell(fila, 2, valor).font = normal

    for c, ancho in enumerate([44, 22, 16, 18, 40, 18, 46, 16, 14],
                              start=1):
        hoja.column_dimensions[L(c)].width = ancho


def pendientes_concepto(resultado):
    """v6.6: cuantas partidas del concepto quedan por revisar aunque el
    total cuadre (documentos con diferencia, no contabilizados, NO DIAN,
    folio o NIT distinto, IVA distinto, sin acuse, posibles en Resumen)."""
    if resultado["modo"] == "resumen":
        return len(resultado.get("posibles") or {})
    n = 0
    for doc in resultado.get("documentos_helisa") or []:
        if doc["estado"] not in ("ok", "redondeo") or doc.get("nivel") == 4 \
                or doc.get("no_deducible") \
                or doc.get("nit_distinto_revisar") \
                or not dentro_de(doc.get("dif_iva") or 0,
                                 TOLERANCIA_IVA_DOCUMENTO):
            n += 1
    cruzados = resultado.get("dian_a_helisa") or {}
    n += sum(1 for j in range(len(resultado["dian"])) if j not in cruzados)
    n += sum(1 for marcas in (resultado.get("acuses") or {}).values()
             if "NO" in (marcas or []))
    if resultado.get("alerta_asumidos"):
        n += 1
    return n


def estado_concepto(resultado, parametros):
    """CONCILIADO solo si el total y el IVA cuadran Y no queda ninguna
    partida pendiente en el concepto (regla: nada queda conciliado con
    algo pendiente)."""
    tolerancia = float(parametros.get("tolerancia_estado", 0.0))
    ok = dentro_de(resultado["diferencia_total"], tolerancia) and (
        resultado["diferencia_iva"] is None
        or dentro_de(resultado["diferencia_iva"], tolerancia))
    if not ok:
        return "REVISAR"
    return "CONCILIADO" if pendientes_concepto(resultado) == 0 \
        else "CUADRA, CON PENDIENTES"


def partidas_para_revisar(analisis):
    reporte = analisis["reporte"]
    partidas = []
    for resultado in analisis["resultados"]:
        clave = resultado["concepto"]["clave"]
        if resultado["modo"] == "resumen":
            if abs(resultado["diferencia_total"]) >= 0.01:
                partidas.append({
                    "concepto": clave, "documento": "TOTAL", "fecha": "",
                    "nit": "", "tercero": "",
                    "valor": resultado["diferencia_total"],
                    "hallazgo": "Diferencia entre el total DIAN y el total "
                                "HELISA del informe resumen",
                    "color": ROJO_ALERTA})
            if resultado["diferencia_iva"] and \
                    abs(resultado["diferencia_iva"]) >= 0.01:
                partidas.append({
                    "concepto": clave, "documento": "IVA", "fecha": "",
                    "nit": "", "tercero": "",
                    "valor": resultado["diferencia_iva"],
                    "hallazgo": "Diferencia de IVA DIAN vs. HELISA",
                    "color": AMARILLO})
            lado = ("Receptor" if comparable(resultado["concepto"]["grupo"])
                    == "EMITIDO" else "Emisor")
            for j, texto in sorted((resultado.get("posibles") or {}).items()):
                factura = resultado["dian"][j]
                prefijo = dato(reporte, factura, "Prefijo") or ""
                folio = dato(reporte, factura, "Folio") or ""
                partidas.append({
                    "concepto": clave, "documento": f"{prefijo}{folio}",
                    "fecha": dato(reporte, factura, "Fecha Emisión"),
                    "nit": solo_nit(dato(reporte, factura, f"NIT {lado}")),
                    "tercero": dato(reporte, factura, f"Nombre {lado}"),
                    "valor": numero(dato(reporte, factura, "Total")),
                    "hallazgo": texto, "color": MORADO_ALERTA})
            continue

        for doc in resultado["documentos_helisa"]:
            if doc["estado"] in ("ok", "redondeo") and \
                    doc.get("nivel") != 4 and not doc["no_deducible"] and \
                    not doc.get("inc_no_discriminado") and \
                    not doc.get("dif_inc") and \
                    dentro_de(doc.get("dif_iva") or 0,
                              TOLERANCIA_IVA_DOCUMENTO):
                continue
            hallazgo = observacion_documento(doc, resultado["info_dian"])
            if doc["estado"] == "no_dian":
                hallazgo += (" — Registrada en HELISA, no aparece en el "
                             "reporte DIAN del mes")
            valor = doc["total_debito"] if doc["estado"] in \
                ("no_dian", "ok") else doc["diferencia"]
            partidas.append({
                "concepto": clave, "documento": doc["documento"],
                "fecha": doc["fecha"], "nit": doc["nit"],
                "tercero": doc["beneficiario"], "valor": valor,
                "hallazgo": hallazgo,
                "color": AZUL_ALERTA if doc["estado"] == "no_dian"
                else AMARILLO})

        lado = ("Receptor" if comparable(resultado["concepto"]["grupo"])
                == "EMITIDO" else "Emisor")
        for j, factura in enumerate(resultado["dian"]):
            prefijo = dato(reporte, factura, "Prefijo") or ""
            folio = dato(reporte, factura, "Folio") or ""
            base = {"concepto": clave, "documento": f"{prefijo}{folio}",
                    "fecha": dato(reporte, factura, "Fecha Emisión"),
                    "nit": solo_nit(dato(reporte, factura, f"NIT {lado}")),
                    "tercero": dato(reporte, factura, f"Nombre {lado}"),
                    "valor": numero(dato(reporte, factura, "Total"))}
            hallazgos = []
            color = AMARILLO
            if j not in resultado["dian_a_helisa"]:
                hallazgos.append("Documento DIAN no contabilizado en HELISA")
                color = ROJO_ALERTA
            acuse = resultado["acuses"].get(id(factura), [])
            if "NO" in acuse:
                faltan = [f"ACUSE {i + 1}" for i, a in enumerate(acuse)
                          if a == "NO"]
                motivo = explicar_acuse_faltante(
                    resultado.get("info_acuses"), reporte, factura,
                    acuse.index("NO"))
                hallazgos.append("Factura a crédito sin evento: "
                                 + ", ".join(faltan)
                                 + (f" ({motivo})" if motivo else ""))
            if hallazgos:
                # Un documento con varios hallazgos va en UNA sola fila.
                partidas.append({**base, "hallazgo": " · ".join(hallazgos),
                                 "color": color})
    return partidas
