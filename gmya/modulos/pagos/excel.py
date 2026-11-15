"""Excel de la programacion de pagos (misma plantilla de la semana anterior).

Contrato:
  generar_excel_prog_pagos(partidas, ctx) -> libro .xlsx (ver docstring).
  resumen_prog_pagos(...) -> totales para la pantalla.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.planillas.logica, gmya.modulos.pagos.lectura, gmya.modulos.pagos.reglas
"""

import html
import io
from collections import OrderedDict

from gmya.comun.texto import comparable
from gmya.comun.numeros import formato_cop
from gmya.modulos.planillas.logica import nombre_seguro
from gmya.modulos.pagos.lectura import (
    fecha_celda_pp, FORMATO_PESOS_PP, MESES_PP, _texto,
)
from gmya.modulos.pagos.reglas import orden_partidas


# ------------------------------------------------------------
# Libro de salida (PROG PAGOS ACTUAL)
# ------------------------------------------------------------
MES_ABR_PP = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP",
              "OCT", "NOV", "DIC"]


def nombre_hoja_prog(empresa, fecha, anterior):
    base = (empresa or {}).get("hoja", "PROG PAGOS")
    n = 1
    if anterior and anterior.get("fecha") and anterior.get("numero_prog") \
            and (anterior["fecha"].year, anterior["fecha"].month) == \
            (fecha.year, fecha.month):
        n = anterior["numero_prog"] + 1
    return f"{base} {MES_ABR_PP[fecha.month - 1]} #{n}"[:31], n


def nombre_archivo_prog(nombre_empresa, fecha):
    return nombre_seguro(f"PROG PAGOS {fecha:%d-%m-%Y} {nombre_empresa}") \
        + ".xlsx"


def _libro_base(anterior):
    """Libro con las hojas auxiliares de la anterior copiadas tal cual."""
    from openpyxl import Workbook, load_workbook
    libro_ant = (anterior or {}).get("libro") or {}
    auxiliares = (anterior or {}).get("hojas_auxiliares", [])
    if libro_ant.get("xlsx"):
        libro = load_workbook(io.BytesIO(libro_ant["xlsx"]))
        for hoja in list(libro.worksheets):
            if hoja.title not in auxiliares:
                libro.remove(hoja)
        # Nombres definidos que apuntaban a hojas quitadas.
        try:
            for nombre in list(libro.defined_names):
                destino = str(libro.defined_names[nombre].attr_text)
                if not any(f"'{h}'" in destino or f"{h}!" in destino
                           for h in libro.sheetnames):
                    del libro.defined_names[nombre]
        except Exception:
            pass
        for hoja in libro.worksheets:
            hoja.sheet_view.tabSelected = False
        return libro
    libro = Workbook()
    libro.remove(libro.active)
    if libro_ant.get("xls") and auxiliares:
        try:
            _copiar_hojas_xlrd(libro_ant["xls"], auxiliares, libro)
        except Exception:
            pass
    return libro


def _copiar_hojas_xlrd(contenido, nombres, libro):
    """Copia (valores y formato basico) hojas de un .xls con xlrd. Se usa
    solo si en el equipo no hay Excel ni LibreOffice para convertirlo."""
    import xlrd
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    origen = xlrd.open_workbook(file_contents=contenido, formatting_info=True)
    for nombre in nombres:
        h = origen.sheet_by_name(nombre)
        ws = libro.create_sheet(nombre[:31])
        for c, info in h.colinfo_map.items():
            ws.column_dimensions[get_column_letter(c + 1)].width = \
                info.width / 256
        for f in range(h.nrows):
            for c in range(h.ncols):
                celda = h.cell(f, c)
                if celda.ctype == xlrd.XL_CELL_EMPTY:
                    continue
                valor = celda.value
                if celda.ctype == xlrd.XL_CELL_DATE:
                    valor = xlrd.xldate.xldate_as_datetime(valor,
                                                           origen.datemode)
                destino = ws.cell(f + 1, c + 1, valor)
                xf = origen.xf_list[celda.xf_index]
                fuente = origen.font_list[xf.font_index]
                destino.font = Font(name=fuente.name, size=fuente.height / 20,
                                    bold=bool(fuente.bold))
                destino.number_format = origen.format_map[
                    xf.format_key].format_str
                patron = xf.background
                if patron.fill_pattern == 1:
                    rgb = origen.colour_map.get(patron.pattern_colour_index)
                    if rgb:
                        destino.fill = PatternFill(
                            "solid", fgColor="%02X%02X%02X" % rgb)
                destino.alignment = Alignment(wrap_text=bool(
                    xf.alignment.text_wrapped))
        for f1, f2, c1, c2 in h.merged_cells:
            ws.merge_cells(start_row=f1 + 1, end_row=f2,
                           start_column=c1 + 1, end_column=c2)


def generar_excel_prog_pagos(partidas, ctx):
    """
    Libro PROG PAGOS ACTUAL. ctx: empresa (dict de EMPRESAS_PROG_PAGOS),
    nombre_empresa, fecha, fechas_pago, disponible (por fecha), ingresos
    (por fecha), trm, anterior (lectura de la anterior, para copiar las
    hojas auxiliares).
    """
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as L

    fecha = ctx["fecha"]
    fechas = list(ctx["fechas_pago"])
    empresa = ctx.get("empresa") or {}
    anterior = ctx.get("anterior")
    libro = _libro_base(anterior)
    nombre_hoja, _ = nombre_hoja_prog(empresa, fecha, anterior)
    ws = libro.create_sheet(nombre_hoja, 0)
    libro.active = 0
    ws.sheet_view.tabSelected = True

    n_pag = len(fechas)
    c_pag = [12 + i for i in range(n_pag)]          # L, M, N...
    c_obs = 12 + n_pag
    ultima = c_obs

    fino = Side(style="thin", color="000000")
    medio = Side(style="medium", color="000000")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    gris = PatternFill("solid", fgColor="F0F0F0")
    amarillo = PatternFill("solid", fgColor="FFFF00")
    sub = PatternFill("solid", fgColor="FFCC00")
    f_ant = PatternFill("solid", fgColor="99CCFF")
    f_fijo = PatternFill("solid", fgColor="FFFF99")
    f_hijo = PatternFill("solid", fgColor="FFFF00")
    pesos = FORMATO_PESOS_PP
    fmt_fecha = "DD/MM/YYYY"

    def put(f, c, valor=None, negrita=False, tam=8, relleno=None,
            formato=None, alin=None, ajustar=False, color=None):
        celda = ws.cell(f, c)
        if valor is not None:
            celda.value = valor
        celda.font = Font(name="Calibri", size=tam, bold=negrita,
                          color=color)
        celda.border = borde
        if relleno is not None:
            celda.fill = relleno
        if formato:
            celda.number_format = formato
        celda.alignment = Alignment(horizontal=alin, vertical="center",
                                    wrap_text=ajustar)
        return celda

    def valor_fecha(v):
        f = fecha_celda_pp(v)
        return (f, fmt_fecha) if f else (_texto(v) or None, None)

    # --- Encabezado -----------------------------------------------------
    nombre_empresa = ctx.get("nombre_empresa") or empresa.get("nombre", "")
    for f, texto, tam in ((1, nombre_empresa, 12),
                          (2, "PRESUPUESTO DE PAGOS Y FLUJO DE CAJA", 12),
                          (3, f"TOTAL DISPONIBLE {MESES_PP[fecha.month - 1]} "
                              f"{fecha.day} DEL {fecha.year}", 12)):
        ws.merge_cells(start_row=f, start_column=2, end_row=f, end_column=11)
        for c in range(2, 12):
            put(f, c, relleno=gris)
        put(f, 2, texto, True, tam, gris, alin="center")
    ws.merge_cells(start_row=4, start_column=2, end_row=4, end_column=10)
    for c in range(2, 11):
        put(4, c, relleno=gris)
    put(4, 2, ctx.get("titulo_gastos") or empresa.get(
        "titulo_gastos", "PRESUPUESTO DE PAGOS"), True, 14, gris,
        alin="center")
    put(4, 11, "VALOR TOTAL PENDIENTE", True, 9, gris, alin="center",
        ajustar=True)
    ingresos = list(ctx.get("ingresos") or []) + [0] * n_pag
    disponible = list(ctx.get("disponible") or []) + [0] * n_pag
    for i, c in enumerate(c_pag):
        put(2, c, float(ingresos[i] or 0), True, 10, gris, pesos, "center",
            color="FF0000")
        put(3, c, float(disponible[i] or 0), True, 10, gris, pesos, "center")
        put(4, c, f"PAGOS AL {fechas[i]:%d/%m/%Y}", True, 9, amarillo,
            alin="center", ajustar=True)
    titulos = ["CUENTA", "NIT", "RAZON SOCIAL", "NUMERO", None, "CONCEPTO",
               "Fecha Emision", "Fecha Vence", "Valor Factura",
               "Abonos realizados", "Saldo Total"] + \
        ["Saldo a Pagar"] * n_pag + ["OBSERVACIONES"]
    for c, t in enumerate(titulos, start=1):
        put(5, c, t, True, 9, gris, alin="center", ajustar=True)
    ws.merge_cells(start_row=5, start_column=4, end_row=5, end_column=5)
    ws.row_dimensions[4].height = 24.5
    ws.row_dimensions[5].height = 24.5

    fila = 6

    def pagos_de(p, f):
        for i, c in enumerate(c_pag):
            put(f, c, None, formato=pesos, relleno=None)
        if p.get("programar") is not None and 0 <= p["programar"] < n_pag:
            ws.cell(f, c_pag[p["programar"]]).value = f"=+K{f}"

    def observacion(p, f):
        put(f, c_obs, p.get("obs") or None, color="FF0000" if p.get("obs")
            else None, ajustar=True)

    def subtotal(f, inicio, fin, texto, relleno=sub):
        for c in range(1, ultima + 1):
            put(f, c, relleno=relleno, negrita=True)
        put(f, 3, texto, True, 8, relleno)
        for c in (9, 10, 11):
            put(f, c, f"=SUBTOTAL(9,{L(c)}{inicio}:{L(c)}{fin})", True, 8,
                relleno, pesos, "right")

    incluidas = [p for p in orden_partidas(partidas) if p.get("incluir")]

    # --- Facturas por proveedor -----------------------------------------
    facturas = [p for p in incluidas if p["seccion"] == "factura"]
    grupos = OrderedDict()
    for p in facturas:
        grupos.setdefault(comparable(p["proveedor"]), []).append(p)
    for lista in grupos.values():
        inicio = fila
        for p in lista:
            fe, ffe = valor_fecha(p.get("fecha"))
            ve, fve = valor_fecha(p.get("vence"))
            put(fila, 1, p.get("cuenta") or None, alin="center")
            nit = p.get("nit") or ""
            put(fila, 2, int(nit) if nit.isdigit() else (nit or None),
                alin="right")
            put(fila, 3, p.get("proveedor"))
            put(fila, 4, p.get("tipo") or None, alin="center")
            put(fila, 5, p.get("numero") or None)
            put(fila, 6, p.get("concepto") or None, ajustar=True)
            put(fila, 7, fe, formato=ffe, alin="center")
            put(fila, 8, ve, formato=fve, alin="center")
            put(fila, 9, float(p.get("valor") or 0), formato=pesos,
                alin="right")
            put(fila, 10, f"=+I{fila}-K{fila}", formato=pesos, alin="right")
            put(fila, 11, float(p.get("saldo") or 0), formato=pesos,
                alin="right")
            pagos_de(p, fila)
            observacion(p, fila)
            lineas = max(1, -(-len(p.get("concepto") or "") // 46))
            ws.row_dimensions[fila].height = 11.5 * min(lineas, 6) + 2
            fila += 1
        subtotal(fila, inicio, fila - 1, f"Total {lista[0]['proveedor']}")
        fila += 1

    # --- Anticipos y pagos fijos ----------------------------------------
    def bloque_simple(p, f, relleno):
        for c in range(1, ultima + 1):
            put(f, c, relleno=relleno)
        put(f, 4, p.get("concepto") or None, relleno=relleno, ajustar=True)
        ws.merge_cells(start_row=f, start_column=4, end_row=f, end_column=6)
        fe, ffe = valor_fecha(p.get("fecha"))
        put(f, 7, fe, relleno=relleno, formato=ffe, alin="center")
        ws.merge_cells(start_row=f, start_column=7, end_row=f, end_column=8)

    anticipos = [p for p in incluidas if p["seccion"] == "anticipo"]
    grupos = OrderedDict()
    for p in anticipos:
        grupos.setdefault(comparable(p["proveedor"]), []).append(p)
    for lista in grupos.values():
        inicio = fila
        for p in lista:
            bloque_simple(p, fila, f_ant)
            put(fila, 2, p.get("bloque") or "ANTICIPO", relleno=f_ant)
            put(fila, 3, p.get("proveedor"), relleno=f_ant)
            put(fila, 9, float(p.get("valor") or 0), relleno=f_ant,
                formato=pesos, alin="right")
            put(fila, 10, float(p.get("abono") or 0) or None, relleno=f_ant,
                formato=pesos, alin="right")
            put(fila, 11, f"=+I{fila}-J{fila}", relleno=f_ant, formato=pesos,
                alin="right")
            pagos_de(p, fila)
            observacion(p, fila)
            fila += 1
        subtotal(fila, inicio, fila - 1, f"Total {lista[0]['proveedor']}")
        fila += 1

    fijos = [p for p in incluidas if p["seccion"] == "fijo"]
    grupos = OrderedDict()
    for p in fijos:
        grupos.setdefault(comparable(p["grupo"]), []).append(p)
    for lista in grupos.values():
        inicio = fila
        for p in lista:
            bloque_simple(p, fila, f_fijo)
            hijos = p.get("hijos") or []
            if hijos:
                put(fila, 9, f"=SUBTOTAL(9,I{fila + 1}:I{fila + len(hijos)})",
                    relleno=f_fijo, formato=pesos, alin="right")
            else:
                put(fila, 9, float(p.get("valor") or 0), relleno=f_fijo,
                    formato=pesos, alin="right")
            put(fila, 10, float(p.get("abono") or 0) or None, relleno=f_fijo,
                formato=pesos, alin="right")
            put(fila, 11, f"=+I{fila}-J{fila}", relleno=f_fijo, formato=pesos,
                alin="right")
            if comparable(p.get("concepto")).startswith("SALDO"):
                ws.cell(fila, 4).font = Font(name="Calibri", size=8, bold=True)
            pagos_de(p, fila)
            observacion(p, fila)
            fila += 1
            for h in hijos:
                bloque_simple(h, fila, f_hijo)
                put(fila, 9, float(h.get("valor") or 0), relleno=f_hijo,
                    formato=pesos, alin="right")
                for c in [10, 11] + c_pag:
                    put(fila, c, formato=pesos)
                put(fila, c_obs)
                fila += 1
        fin = fila - 1
        for c, valor in ((2, lista[0].get("bloque") or "PAGOS FIJOS"),
                         (3, lista[0]["grupo"])):
            put(inicio, c, valor, relleno=f_fijo, alin="center",
                ajustar=True)
            if fin > inicio:
                ws.merge_cells(start_row=inicio, start_column=c, end_row=fin,
                               end_column=c)
        subtotal(fila, inicio, fin, f"Total {lista[0]['grupo']}")
        fila += 1

    # --- Totales ---------------------------------------------------------
    ultima_dato = fila - 1
    f_tot, f_dif, f_trm = fila, fila + 1, fila + 2
    for f, texto in ((f_tot, "Gran Total"), (f_dif, "DIFERENCIA (SALDO EN "
                                                    "BANCOS)"),
                     (f_trm, "FLUJO NECESARIO PARA GASTOS DE CAMPO")):
        for c in range(2, ultima + 1):
            put(f, c, relleno=f_ant if f == f_tot else None)
        put(f, 2, texto, True, 10, f_ant if f == f_tot else None,
            alin="center")
    ws.merge_cells(start_row=f_tot, start_column=2, end_row=f_tot,
                   end_column=11)
    ws.merge_cells(start_row=f_dif, start_column=2, end_row=f_dif,
                   end_column=11)
    ws.merge_cells(start_row=f_trm, start_column=2, end_row=f_trm,
                   end_column=9)
    put(f_trm, 10, "TRM", True, 10, amarillo)
    put(f_trm, 11, float(ctx.get("trm") or 0) or None, True, 10, amarillo,
        pesos)
    for c in c_pag:
        col = L(c)
        put(f_tot, c, f"=SUM({col}6:{col}{ultima_dato})", True, 10, None,
            pesos, "center")
        put(f_dif, c, f"=+({col}2+{col}3)-{col}{f_tot}", True, 10, None,
            pesos)
        put(f_trm, c, f'=IF($K${f_trm}>0,{col}{f_dif}/$K${f_trm},"")', True,
            11, None, pesos, "right")

    anchos = {"A": 7.5, "B": 11, "C": 24, "D": 5.5, "E": 12, "F": 36,
              "G": 10, "H": 10, "I": 14, "J": 12, "K": 15}
    for letra, ancho in anchos.items():
        ws.column_dimensions[letra].width = ancho
    for c in c_pag:
        ws.column_dimensions[L(c)].width = 14
    ws.column_dimensions[L(c_obs)].width = 26
    ws.freeze_panes = "D6"
    ws.auto_filter.ref = f"A5:{L(ultima)}{ultima_dato}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "5:5"

    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def resumen_prog_pagos(partidas, fechas_pago):
    """Totales por fecha de pago y conteos para la pantalla."""
    incluidas = [p for p in partidas if p.get("incluir")]
    por_fecha = [0.0] * len(fechas_pago)
    sin_fecha = 0.0
    for p in incluidas:
        i = p.get("programar")
        if i is not None and 0 <= i < len(fechas_pago):
            por_fecha[i] += p.get("saldo") or 0
        else:
            sin_fecha += p.get("saldo") or 0
    return {
        "incluidas": len(incluidas),
        "excluidas": len(partidas) - len(incluidas),
        "pendiente": round(sum(p.get("saldo") or 0 for p in incluidas), 2),
        "por_fecha": [round(x, 2) for x in por_fecha],
        "sin_fecha": round(sin_fecha, 2),
    }




# ------------------------------------------------------------
# Marcas del visor de la programacion (filas incluidas para revisar)
# ------------------------------------------------------------

COLOR_REVISION_PP = (255, 192, 0)


def marcas_revision_pp(partidas, ordenar=None):
    """
    Marcas {fila: (color, etiqueta)} para el documento anterior y el de
    HELISA, globos y leyenda. Solo se marcan partidas INCLUIDAS que tienen
    algo que confirmar (lista 'revisar').
    """
    ordenar = ordenar or orden_partidas
    marcas_ant, marcas_hel, tips, leyenda = {}, {}, {}, []
    n = 0
    for p in ordenar(partidas):
        if not p.get("incluir") or not p.get("revisar"):
            continue
        n += 1
        etiqueta = str(n)
        for fila, destino in ((p.get("fila_ant"), marcas_ant),
                              (p.get("fila_helisa"), marcas_hel)):
            if fila:
                destino.setdefault(fila, (COLOR_REVISION_PP, etiqueta))
        quien = html.escape(str(p.get("proveedor") or p.get("grupo") or ""))
        doc = html.escape(str(p.get("numero") or p.get("concepto") or ""))
        tips[etiqueta] = (
            f"<b>#{n} · {quien}</b><br>{doc[:90]} · "
            f"{formato_cop(p.get('pagar', p.get('saldo')) or 0)}<br>"
            + "<br>".join("• " + html.escape(r) for r in p["revisar"])
            + "<br><i>Si no corresponde, desmárcala en la tabla de revisión "
              "(columna Incluir).</i>")
        leyenda.append({"#": n, "Proveedor / grupo": p.get("proveedor") or
                        p.get("grupo") or "",
                        "Documento": p.get("numero") or "",
                        "Qué revisar": " ".join(p["revisar"]),
                        "Fila anterior": p.get("fila_ant") or "",
                        "Fila HELISA": p.get("fila_helisa") or ""})
    return marcas_ant, marcas_hel, tips, leyenda
