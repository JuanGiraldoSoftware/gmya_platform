"""Excel de resultado de la conciliacion bancaria.

Contrato:
  construir_excel(analisis) / construir_excel_bancos(resultado) -> libro
      .xlsx de la conciliacion.

Depende de: gmya.comun.numeros, gmya.modulos.dian.parametros, gmya.modulos.bancos.lectura, gmya.modulos.bancos.conciliacion, gmya.modulos.bancos.sugerencias
"""

import io
from decimal import Decimal

from gmya.comun.numeros import CERO
from gmya.modulos.dian.parametros import resaltar_si_no_es_cero
from gmya.modulos.bancos.lectura import descripcion_periodo, FORMATO_MONTO
from gmya.modulos.bancos.conciliacion import (
    avisos_totales, categoria_gasto, contabilizado_en_libro, etiqueta_cuenta,
    sumar, UMBRAL_PAREJA_DUDOSA, UMBRAL_PAREJA_SEGURA,
)
from gmya.modulos.bancos.sugerencias import CONFIANZA_ORDEN


# ------------------------------------------------------------
# Libro Excel de salida de la conciliacion bancaria
# ------------------------------------------------------------
ESTADOS_PARTIDA = {
    "conciliado": ("CONCILIADA", "verde"),
    "agrupado": ("CONCILIADA (AGRUPADA)", "verde"),
    "diferencia": ("VALOR DIFERENTE", "amarillo"),
    "agrupado_diferencia": ("VALOR DIFERENTE (AGRUPADA EN HELISA)",
                            "amarillo"),
    "sin_libro": ("NO ESTÁ EN HELISA", "rojo"),
    "sin_extracto": ("NO ESTÁ EN EL EXTRACTO", "rojo"),
}
ORDEN_ESTADOS = ["NO ESTÁ EN HELISA", "NO ESTÁ EN EL EXTRACTO",
                 "VALOR DIFERENTE", "VALOR DIFERENTE (AGRUPADA EN HELISA)",
                 "CONCILIADA", "CONCILIADA (AGRUPADA)"]

ACCIONES_PARTIDA = {
    "sin_libro": "Buscar el soporte del movimiento y contabilizarlo en "
                 "HELISA.",
    "sin_extracto": "Si es un cheque o transferencia en tránsito, "
                    "conciliarlo el período siguiente; si no, revisar "
                    "fecha, valor o cuenta bancaria del registro.",
    "diferencia": "Verificar el comprobante y corregir el valor "
                  "registrado. No asumir que sea una comisión.",
    "agrupado_diferencia": "Revisar el asiento de gastos bancarios de "
                           "HELISA contra los cargos del extracto.",
    "conciliado": "",
    "agrupado": "",
}


def partidas_cruce(analisis):
    """
    Una fila por partida, extracto frente a HELISA. Los registros de HELISA
    sin extracto van solos; en las notas conjuntas el valor de HELISA se
    muestra una sola vez (primera fila del grupo).
    """
    movs, lib = analisis["movs"], analisis["libro_movs"]
    sugerencias = {s["id"]: s for s in analisis.get("sugerencias", [])}
    filas = []
    primeros = set()
    for m in movs:
        ls = [lib[j] for j in m["pareja"]]
        conjunto = m["estado"] in ("agrupado", "agrupado_diferencia")
        clave = tuple(m["pareja"])
        primera = True
        if conjunto:
            primera = clave not in primeros
            primeros.add(clave)
        valor_l = sum((l["valor"] for l in ls), CERO) if ls else None
        if conjunto and not primera:
            valor_l = None
        diferencia = None
        if m["estado"] == "diferencia":
            diferencia = m["valor"] - valor_l
        elif m["estado"] == "agrupado_diferencia" and primera:
            grupo = [x for x in movs if x["estado"] == m["estado"]
                     and x["pareja"] == m["pareja"]]
            diferencia = sumar(grupo) - valor_l
        filas.append({"estado": m["estado"], "fecha": m["fecha"], "e": m,
                      "l": ls, "valor_e": m["valor"], "valor_l": valor_l,
                      "diferencia": diferencia, "conjunto": conjunto,
                      "sugerencias": [sugerencias[i] for i in
                                      m.get("sugerencias", [])
                                      if i in sugerencias]})
    for l in lib:
        if l["estado"] == "sin_extracto":
            filas.append({"estado": "sin_extracto", "fecha": l["fecha"],
                          "e": None, "l": [l], "valor_e": None,
                          "valor_l": l["valor"], "diferencia": None,
                          "conjunto": False,
                          "sugerencias": [sugerencias[i] for i in
                                          l.get("sugerencias", [])
                                          if i in sugerencias]})
    filas.sort(key=lambda f: (f["fecha"], ORDEN_ESTADOS.index(
        ESTADOS_PARTIDA[f["estado"]][0])))
    return filas



CATEGORIAS_GASTO = ["GMF 4x1000", "Comisión", "IVA sobre comisión",
                    "Retención en la fuente"]
TARIFA_IVA_CONTROL = 0.19


def construir_excel(analisis):
    """Compatibilidad: libro de una sola cuenta."""
    return construir_excel_bancos({
        "cuentas": [{"etiqueta": etiqueta_cuenta(analisis["extracto"],
                                                 analisis["seccion"]),
                     "analisis": analisis, "archivo_extracto": "",
                     "archivo_libro": "", "puntaje": None, "motivos": []}],
        "avisos": [], "leidos": []})


def construir_excel_bancos(resultado):
    """
    Libro de salida de la conciliacion bancaria (una o varias cuentas):
      1 Resumen        advertencias, saldos por cuenta, conciliacion libro
                       vs. extracto, gastos bancarios por categoria,
                       desglose de comisiones, control del IVA, resultado
                       del cruce, revision de lectura y documentos leidos.
      2 Detalle gastos movimientos del extracto que son gastos bancarios o
                       intereses, con categoria, subcategoria y si estan
                       contabilizados (base de las formulas del Resumen).
      3 Conciliación   linea a linea, extracto frente a HELISA, por cuenta.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as L

    cuentas = resultado["cuentas"]
    n = len(cuentas)
    c_total = 2 + n
    TINTA, MAGENTA = "272526", "E0118F"
    COLORES = {"rojo": "FFC7CE", "amarillo": "FFEB9C", "verde": "E2EFDA"}
    TEXTO_ESTADO = {"rojo": "9C0006", "amarillo": "7F6000",
                    "verde": "1F5C2E"}

    def relleno(color):
        return PatternFill("solid", fgColor=color)

    blanco_negrita = Font(bold=True, color="FFFFFF")
    negrita = Font(bold=True)
    roja = Font(bold=True, color="C00000")
    centro = Alignment(horizontal="center", vertical="center",
                       wrap_text=True)
    envolver = Alignment(wrap_text=True, vertical="top")
    delgado = Side(style="thin", color="BFBFBF")
    borde = Border(left=delgado, right=delgado, top=delgado, bottom=delgado)
    borde_total = Border(top=Side(style="medium", color=TINTA),
                         bottom=Side(style="double", color=TINTA))

    def numero(valor):
        return float(valor) if isinstance(valor, Decimal) else valor

    def monto(hoja, fila, columna, valor, fuente=None):
        if valor is None:
            return hoja.cell(fila, columna)
        celda = hoja.cell(fila, columna, numero(valor))
        celda.number_format = FORMATO_MONTO
        if fuente:
            celda.font = fuente
        return celda

    def encabezado(hoja, fila, textos, color=TINTA, alto=30, inicio=1):
        for i, texto in enumerate(textos, start=inicio):
            celda = hoja.cell(fila, i, texto)
            celda.font = blanco_negrita
            celda.fill = relleno(color)
            celda.alignment = centro
            celda.border = borde
        hoja.row_dimensions[fila].height = alto

    def titulo_hoja(hoja, texto, subtitulo, columnas):
        columnas = max(columnas, 2)
        hoja.merge_cells(start_row=1, start_column=1, end_row=1,
                         end_column=columnas)
        hoja.cell(1, 1, texto).font = Font(bold=True, size=14,
                                           color="FFFFFF")
        hoja.cell(1, 1).fill = relleno(TINTA)
        hoja.row_dimensions[1].height = 24
        hoja.merge_cells(start_row=2, start_column=1, end_row=2,
                         end_column=columnas)
        hoja.cell(2, 1, subtitulo).font = Font(bold=True, color="FFFFFF")
        hoja.cell(2, 1).fill = relleno(MAGENTA)
        hoja.cell(2, 1).alignment = Alignment(wrap_text=True,
                                              vertical="center")
        hoja.row_dimensions[2].height = 32

    def titulo_bloque(hoja, fila, texto, columnas):
        hoja.cell(fila, 1, texto).font = Font(bold=True, size=11,
                                              color=MAGENTA)
        for c in range(1, columnas + 1):
            hoja.cell(fila, c).border = Border(
                bottom=Side(style="medium", color=MAGENTA))

    def fila_valores(hoja, fila, texto, valores, fuente=None, total=True):
        """Concepto + un valor por cuenta + total (formula)."""
        hoja.cell(fila, 1, texto).alignment = envolver
        if fuente:
            hoja.cell(fila, 1).font = fuente
        for k, valor in enumerate(valores):
            monto(hoja, fila, 2 + k, valor, fuente)
        if total:
            monto(hoja, fila, c_total,
                  f"=SUM(B{fila}:{L(c_total - 1)}{fila})", fuente)
        for c in range(1, c_total + 1):
            hoja.cell(fila, c).border = borde

    # ---------------- datos por cuenta ----------------
    datos = []
    for cuenta in cuentas:
        a = cuenta["analisis"]
        movs, lib = a["movs"], a["libro_movs"]
        gastos = []
        for m in movs:
            cat = categoria_gasto(m)
            if cat:
                gastos.append((m, cat[0], cat[1]))
        pend = {c: sum((m["valor"] for m, cat, _ in gastos
                        if cat == c and m["estado"] == "sin_libro"), CERO)
                for c in CATEGORIAS_GASTO + ["Intereses ganados"]}
        en_gasto = {id(m) for m, _, _ in gastos}
        otros_pend = sum((m["valor"] for m in movs if m["estado"] ==
                          "sin_libro" and id(m) not in en_gasto), CERO)
        notas = {}
        for m, _, _ in gastos:
            if m["estado"] != "sin_libro":
                for j in m.get("pareja", []):
                    notas[j] = lib[j]["valor"]
        datos.append({"cuenta": cuenta, "a": a, "gastos": gastos,
                      "pend": pend, "otros_pend": otros_pend,
                      "notas": -sum(notas.values(), CERO)})

    etiquetas = [c["etiqueta"] for c in cuentas]
    primera = cuentas[0]["analisis"] if cuentas else None
    periodos = [c["analisis"]["extracto"]["periodo"] for c in cuentas]
    inicio = min(p[0] for p in periodos)
    fin = max(p[1] for p in periodos)
    tipo_periodo, rango, _ = descripcion_periodo(inicio, fin)
    empresa = next((c["analisis"]["libro"]["empresa"] for c in cuentas
                    if c["analisis"]["libro"].get("empresa")), "")
    nit = next((c["analisis"]["libro"]["nit"] for c in cuentas
                if c["analisis"]["libro"].get("nit")), "")
    bancos = sorted({c["analisis"]["extracto"]["banco"] for c in cuentas
                     if not c["analisis"]["extracto"].get("vacio")})
    identificacion = " | ".join(x for x in [
        empresa, f"NIT {nit}" if nit else "", ", ".join(bancos),
        f"{n} cuenta{'s' if n != 1 else ''}",
        f"{tipo_periodo} ({rango}) · {inicio:%d/%m/%Y} a {fin:%d/%m/%Y}"]
        if x)

    wb = Workbook()

    # ============================== DETALLE ==============================
    # (se arma primero para conocer el rango de las formulas)
    det = wb.active
    det.title = "Detalle gastos"
    columnas_det = ["#", "Cuenta", "Fecha", "Descripción en el extracto",
                    "Categoría", "Subcategoría", "Valor",
                    "Contabilizado en HELISA", "Ubicación"]
    titulo_hoja(det, f"DETALLE DE GASTOS BANCARIOS E INTERESES - "
                     f"{rango.upper()}",
                f"{empresa} - Movimientos del extracto que son gastos "
                "bancarios o intereses, y si ya están en HELISA. Verde = "
                "contabilizado · Amarillo = con valor diferente · Rojo = "
                "falta contabilizar",
                len(columnas_det))
    encabezado(det, 4, columnas_det)
    fila = 4
    numero_fila = 0
    for d in datos:
        lib = d["a"]["libro_movs"]
        for m, cat, sub in d["gastos"]:
            fila += 1
            numero_fila += 1
            estado = contabilizado_en_libro(m, lib)
            valores = [numero_fila, d["cuenta"]["etiqueta"], m["fecha"],
                       m["descripcion"], cat, sub, abs(m["valor"]), estado,
                       m.get("ubicacion") or ""]
            for c, valor in enumerate(valores, start=1):
                celda = det.cell(fila, c, numero(valor))
                celda.border = borde
            det.cell(fila, 3).number_format = "DD/MM/YYYY"
            det.cell(fila, 7).number_format = FORMATO_MONTO
            color = "verde" if estado.startswith("Sí") else (
                "rojo" if estado == "No" else "amarillo")
            # Toda la fila se pinta: verde = ya esta en HELISA, rojo = falta
            # contabilizar, amarillo = esta con valor diferente.
            for c in range(1, len(columnas_det) + 1):
                det.cell(fila, c).fill = relleno(COLORES[color])
            det.cell(fila, 8).font = Font(bold=color != "verde",
                                          color=TEXTO_ESTADO[color])
    ultima_det = max(fila, 5)
    if numero_fila == 0:
        det.cell(5, 1, "No se identificaron gastos bancarios ni intereses "
                       "en los extractos.")
    det.auto_filter.ref = f"A4:I{ultima_det}"
    det.freeze_panes = "A5"
    fila = ultima_det + 1
    det.cell(fila, 6, "TOTAL GASTOS (sin intereses)").font = negrita
    monto(det, fila, 7, f'=SUMIFS(G5:G{ultima_det},E5:E{ultima_det},'
                        f'"<>Intereses ganados")', negrita)
    fila += 1
    det.cell(fila, 6, "TOTAL INTERESES GANADOS").font = negrita
    monto(det, fila, 7, f'=SUMIFS(G5:G{ultima_det},E5:E{ultima_det},'
                        f'"Intereses ganados")', negrita)
    fila += 1
    det.cell(fila, 6, "Pendiente de contabilizar (No)").font = negrita
    monto(det, fila, 7, f'=SUMIFS(G5:G{ultima_det},H5:H{ultima_det},"No")',
          negrita)
    resaltar_si_no_es_cero(det, f"G{fila}", 0)
    for c, ancho in enumerate([5, 22, 11, 40, 20, 28, 15, 34, 10],
                              start=1):
        det.column_dimensions[L(c)].width = ancho

    rango_g = f"'Detalle gastos'!$G$5:$G${ultima_det}"
    rango_b = f"'Detalle gastos'!$B$5:$B${ultima_det}"
    rango_e = f"'Detalle gastos'!$E$5:$E${ultima_det}"
    rango_f = f"'Detalle gastos'!$F$5:$F${ultima_det}"

    # ============================== RESUMEN ==============================
    hoja = wb.create_sheet("Resumen", 0)
    hoja.sheet_view.showGridLines = False
    titulo_hoja(hoja, "CONCILIACIÓN BANCARIA Y SOPORTE DE GASTOS "
                      "BANCARIOS", identificacion, c_total)
    fila = 3

    avisos = avisos_totales(resultado)
    if avisos:
        fila += 1
        titulo_bloque(hoja, fila, "ADVERTENCIAS: REVISA ANTES DE USAR",
                      max(c_total, 6))
        ancho_aviso = max(c_total, 6)
        caracteres = int((62 + 24 * (ancho_aviso - 1)) * 1.05)
        for aviso in avisos:
            fila += 1
            hoja.merge_cells(start_row=fila, start_column=1, end_row=fila,
                             end_column=ancho_aviso)
            celda = hoja.cell(fila, 1, "⚠ " + aviso)
            celda.font = Font(bold=True, color="9C0006")
            celda.fill = relleno("FFC7CE")
            celda.alignment = envolver
            hoja.row_dimensions[fila].height = 16 * (
                1 + (len(aviso) + 2) // caracteres)
        fila += 1

    # --- 1. Saldos ---
    fila += 1
    titulo_bloque(hoja, fila, "1. SALDOS Y MOVIMIENTOS DEL MES", c_total)
    fila += 1
    encabezado(hoja, fila, ["Concepto"] + etiquetas + ["Total"])
    f_cab = fila
    fila += 1
    hoja.cell(fila, 1, "Archivo del extracto / cuenta de HELISA")
    for k, c in enumerate(cuentas):
        sec = c["analisis"]["seccion"]
        texto = (f"{c['archivo_extracto'] or '(sin extracto)'} / "
                 f"{sec.get('etiqueta') or '(sin HELISA)'}")
        hoja.cell(fila, 2 + k, texto).alignment = Alignment(
            wrap_text=True, horizontal="center", vertical="top")
    for c in range(1, c_total + 1):
        hoja.cell(fila, c).border = borde
    hoja.row_dimensions[fila].height = 30

    def suma(movs, cond):
        return sum((m["valor"] for m in movs if cond(m)), CERO)

    filas_saldos = [
        ("Saldo inicial según extracto", [d["a"]["conc"]["saldo_ini_ext"]
                                          for d in datos]),
        ("Saldo inicial según HELISA",
         [d["a"]["conc"]["saldo_ini_lib"] for d in datos]),
        ("Entradas de dinero en el extracto (créditos)",
         [suma(d["a"]["movs"], lambda m: m["valor"] > 0) for d in datos]),
        ("Salidas de dinero en el extracto (débitos)",
         [-suma(d["a"]["movs"], lambda m: m["valor"] < 0) for d in datos]),
        ("Entradas registradas en HELISA (débitos)",
         [suma(d["a"]["libro_movs"], lambda m: m["valor"] > 0)
          for d in datos]),
        ("Salidas registradas en HELISA (créditos)",
         [-suma(d["a"]["libro_movs"], lambda m: m["valor"] < 0)
          for d in datos]),
        ("Saldo final según extracto", [d["a"]["conc"]["saldo_fin_ext"]
                                        for d in datos]),
        ("Saldo final según HELISA",
         [d["a"]["conc"]["saldo_fin_lib"] for d in datos]),
    ]
    filas_ref = {}
    for texto, valores in filas_saldos:
        fila += 1
        fila_valores(hoja, fila, texto, valores,
                     negrita if texto.startswith("Saldo final") else None)
        filas_ref[texto] = fila
    fila += 1
    f_ext, f_lib = (filas_ref["Saldo final según extracto"],
                    filas_ref["Saldo final según HELISA"])
    fila_valores(hoja, fila, "Diferencia de saldo final (extracto − HELISA)",
                 [f"=ROUND({L(2 + k)}{f_ext}-{L(2 + k)}{f_lib},2)"
                  for k in range(n)], negrita)

    # --- 2. Conciliacion libro vs extracto ---
    fila += 2
    titulo_bloque(hoja, fila, "2. CONCILIACIÓN: HELISA vs. EXTRACTO",
                  c_total)
    fila += 1
    encabezado(hoja, fila, ["Concepto"] + etiquetas + ["Total"])
    fila += 1
    f_ini = fila
    fila_valores(hoja, fila, "Saldo según HELISA (dato de HELISA)", [d["a"]["conc"]["saldo_fin_lib"]
                                        for d in datos], negrita)
    for c in range(2, c_total):
        hoja.cell(fila, c).fill = relleno("FFF2CC")
        hoja.cell(fila, c).font = Font(bold=True, color="0000FF")
    conceptos = [
        ("(-) GMF 4x1000 no contabilizado", "GMF 4x1000"),
        ("(-) Comisiones y cuotas no contabilizadas", "Comisión"),
        ("(-) IVA sobre comisiones no contabilizado", "IVA sobre comisión"),
        ("(-) Retención en la fuente no contabilizada",
         "Retención en la fuente"),
        ("(+) Intereses ganados no contabilizados", "Intereses ganados"),
    ]
    for texto, cat in conceptos:
        valores = [d["pend"][cat] for d in datos]
        if cat == "Retención en la fuente" and not any(valores):
            continue
        fila += 1
        fila_valores(hoja, fila, texto, valores)
        resaltar_si_no_es_cero(hoja, f"B{fila}:{L(c_total)}{fila}", 0,
                               "FFEB9C", "7F6000")
    for texto, valores in [
        ("(+/-) Otros movimientos del extracto que no están en HELISA "
         "(pagos, consignaciones, transferencias)",
         [d["otros_pend"] for d in datos]),
        ("(-/+) Registros de HELISA que no están en el extracto (cheques o "
         "transferencias en tránsito, errores)",
         [-d["a"]["conc"]["lib_sin_ext"] for d in datos]),
        ("(+/-) Correcciones por valores diferentes",
         [-d["a"]["conc"]["diferencia_valores"] for d in datos]),
        ("(+/-) Diferencia en los saldos iniciales (viene del mes anterior)",
         [-d["a"]["conc"]["diferencia_saldo_inicial"] for d in datos]),
    ]:
        fila += 1
        fila_valores(hoja, fila, texto, valores)
        resaltar_si_no_es_cero(hoja, f"B{fila}:{L(c_total)}{fila}", 0,
                               "FFEB9C", "7F6000")
    fila += 1
    f_calc = fila
    fila_valores(hoja, fila, "Saldo conciliado (calculado)",
                 [f"=SUM({L(2 + k)}{f_ini}:{L(2 + k)}{fila - 1})"
                  for k in range(n)], negrita)
    for c in range(1, c_total + 1):
        hoja.cell(fila, c).border = borde_total
    fila += 1
    f_banco = fila
    fila_valores(hoja, fila, "Saldo según extracto bancario (dato del "
                             "banco)", [d["a"]["conc"]["saldo_fin_ext"]
                                        for d in datos], negrita)
    for c in range(2, c_total):
        hoja.cell(fila, c).fill = relleno("FFF2CC")
        hoja.cell(fila, c).font = Font(bold=True, color="0000FF")
    fila += 1
    fila_valores(hoja, fila, "DIFERENCIA NO EXPLICADA (debe ser 0)",
                 [f"=ROUND({L(2 + k)}{f_calc}-{L(2 + k)}{f_banco},2)"
                  for k in range(n)], roja)
    resaltar_si_no_es_cero(hoja, f"B{fila}:{L(c_total)}{fila}", 0)
    f_dif = fila
    fila += 1
    hoja.cell(fila, 1, f'=IF(ROUND({L(c_total)}{f_dif},2)=0,"La '
                       f'conciliación cuadra en todas las cuentas.",'
                       f'"Revisar: hay diferencia sin explicar; mira las '
                       f'advertencias y la hoja Conciliación.")').font = \
        Font(italic=True, color="595959")

    # --- 3. Gastos bancarios por categoria ---
    fila += 2
    titulo_bloque(hoja, fila, "3. GASTOS BANCARIOS POR CATEGORÍA "
                              "(soporte de la nota bancaria)", c_total)
    fila += 1
    encabezado(hoja, fila, ["Categoría"] + etiquetas + ["Total"])
    filas_cat = {}
    hay_retencion = any(d["pend"]["Retención en la fuente"] or any(
        cat == "Retención en la fuente" for _, cat, _ in d["gastos"])
        for d in datos)
    for cat in CATEGORIAS_GASTO:
        if cat == "Retención en la fuente" and not hay_retencion:
            continue
        fila += 1
        fila_valores(hoja, fila, cat, [
            f'=SUMIFS({rango_g},{rango_b},{L(2 + k)}${f_cab},{rango_e},'
            f'$A{fila})' for k in range(n)])
        filas_cat[cat] = fila
    fila += 1
    f_tot_g = fila
    primera_cat = min(filas_cat.values())
    fila_valores(hoja, fila, "TOTAL GASTOS BANCARIOS",
                 [f"=SUM({L(2 + k)}{primera_cat}:{L(2 + k)}{fila - 1})"
                  for k in range(n)], negrita)
    fila += 1
    f_int = fila
    fila_valores(hoja, fila, "(+) Intereses ganados (ingreso)", [
        f'=SUMIFS({rango_g},{rango_b},{L(2 + k)}${f_cab},{rango_e},'
        f'"Intereses ganados")' for k in range(n)])
    fila += 1
    f_neto = fila
    fila_valores(hoja, fila, "EFECTO NETO EN HELISA (gasto − ingreso)",
                 [f"={L(2 + k)}{f_tot_g}-{L(2 + k)}{f_int}"
                  for k in range(n)], negrita)
    fila += 1
    f_nota = fila
    fila_valores(hoja, fila, "Registrado en HELISA (notas bancarias que "
                             "cruzan con estos cargos)",
                 [d["notas"] for d in datos])
    fila += 1
    fila_valores(hoja, fila, "PENDIENTE POR REGISTRAR EN HELISA "
                             "(efecto neto − registrado)",
                 [f"=ROUND({L(2 + k)}{f_neto}-{L(2 + k)}{f_nota},2)"
                  for k in range(n)], roja)
    resaltar_si_no_es_cero(hoja, f"B{fila}:{L(c_total)}{fila}", 0,
                           "FFC7CE", "9C0006")

    # --- 4. Desglose de comisiones ---
    subcats = []
    for d in datos:
        for _, cat, sub in d["gastos"]:
            if cat == "Comisión" and sub not in subcats:
                subcats.append(sub)
    fila += 2
    titulo_bloque(hoja, fila, "4. DESGLOSE DE COMISIONES Y CUOTAS", c_total)
    fila += 1
    encabezado(hoja, fila, ["Subcategoría"] + etiquetas + ["Total"])
    f_sub_ini = fila + 1
    f_cuota_tarjeta = None
    for sub in subcats or ["(sin comisiones)"]:
        fila += 1
        fila_valores(hoja, fila, sub, [
            f'=SUMIFS({rango_g},{rango_b},{L(2 + k)}${f_cab},{rango_f},'
            f'$A{fila})' for k in range(n)])
        if sub == "Cuota manejo tarjeta débito":
            f_cuota_tarjeta = fila
    fila += 1
    fila_valores(hoja, fila, "Total comisiones (debe igualar la fila "
                             "Comisión)",
                 [f"=SUM({L(2 + k)}{f_sub_ini}:{L(2 + k)}{fila - 1})"
                  for k in range(n)], negrita)

    # --- 5. Control de IVA ---
    fila += 2
    titulo_bloque(hoja, fila, "5. CONTROL DE RAZONABILIDAD DEL IVA",
                  c_total)
    fila += 1
    encabezado(hoja, fila, ["Concepto"] + etiquetas + ["Total"])
    fila += 1
    f_tarifa = fila
    hoja.cell(fila, 1, "Tarifa de IVA aplicada en el control (supuesto)")
    celda = hoja.cell(fila, 2, TARIFA_IVA_CONTROL)
    celda.number_format = "0%"
    celda.fill = relleno("FFF2CC")
    celda.font = Font(bold=True, color="0000FF")
    for c in range(1, c_total + 1):
        hoja.cell(fila, c).border = borde
    f_com = filas_cat.get("Comisión")
    fila += 1
    f_base = fila
    fila_valores(hoja, fila, "Comisiones gravadas (sin cuota de manejo de "
                             "tarjeta)", [
        f"={L(2 + k)}{f_com}" + (f"-{L(2 + k)}{f_cuota_tarjeta}"
                                 if f_cuota_tarjeta else "")
        for k in range(n)])
    fila += 1
    f_esp = fila
    fila_valores(hoja, fila, "IVA esperado", [
        f"=ROUND({L(2 + k)}{f_base}*$B${f_tarifa},2)" for k in range(n)])
    fila += 1
    f_cob = fila
    fila_valores(hoja, fila, "IVA cobrado por el banco", [
        f"={L(2 + k)}{filas_cat['IVA sobre comisión']}" for k in range(n)])
    fila += 1
    fila_valores(hoja, fila, "Diferencia (0 = coincide)", [
        f"=ROUND({L(2 + k)}{f_cob}-{L(2 + k)}{f_esp},2)" for k in range(n)],
        negrita)
    resaltar_si_no_es_cero(hoja, f"B{fila}:{L(c_total)}{fila}", 0,
                           "FFEB9C", "7F6000")
    fila += 1
    hoja.cell(fila, 1, "La cuota de manejo de la tarjeta débito no suele "
                       "mostrar IVA aparte en el extracto: verificar si ya "
                       "lo incluye. Una diferencia distinta de 0 puede ser "
                       "una comisión cobrada en otra cuenta o una tarifa "
                       "diferente.").font = Font(italic=True,
                                                  color="595959")

    # --- 6. Resultado del cruce ---
    fila += 2
    titulo_bloque(hoja, fila, "6. RESULTADO DEL CRUCE LÍNEA A LÍNEA "
                              "(cantidad de partidas)", c_total)
    fila += 1
    encabezado(hoja, fila, ["Estado"] + etiquetas + ["Total"])
    cruces = [partidas_cruce(d["a"]) for d in datos]
    for estado in ORDEN_ESTADOS:
        clave = next(k for k, (et, _) in ESTADOS_PARTIDA.items()
                     if et == estado)
        color = ESTADOS_PARTIDA[clave][1]
        fila += 1
        fila_valores(hoja, fila, estado, [
            sum(1 for p in cr if p["estado"] == clave) for cr in cruces])
        for c in range(2, c_total + 1):
            hoja.cell(fila, c).number_format = "0"
            hoja.cell(fila, c).alignment = Alignment(horizontal="center")
        hoja.cell(fila, 1).fill = relleno(COLORES[color])
        hoja.cell(fila, 1).font = Font(bold=True, color=TEXTO_ESTADO[color])
        if color != "verde":
            # Cantidad de partidas pendientes o con diferencia: se pinta si
            # hay alguna.
            resaltar_si_no_es_cero(hoja, f"B{fila}:{L(c_total)}{fila}", 0,
                                   COLORES[color], TEXTO_ESTADO[color])

    # --- 7. Revision de la lectura ---
    fila += 2
    titulo_bloque(hoja, fila, "7. REVISIÓN DE LA LECTURA DE LOS "
                              "DOCUMENTOS", max(c_total, 6))
    fila += 1
    encabezado(hoja, fila, ["Revisión", "Cuenta", "Esperado", "Obtenido",
                            "Estado", "Nota"], alto=20)
    for d in datos:
        for control, esperado, obtenido, estado, nota in \
                d["a"]["validaciones"]:
            fila += 1
            hoja.cell(fila, 1, control).alignment = envolver
            hoja.cell(fila, 2, d["cuenta"]["etiqueta"]).alignment = envolver
            for col, valor in ((3, esperado), (4, obtenido)):
                if isinstance(valor, Decimal):
                    monto(hoja, fila, col, valor)
                else:
                    hoja.cell(fila, col, valor).alignment = envolver
            celda = hoja.cell(fila, 5, "BIEN" if estado == "OK"
                              else "REVISAR")
            celda.alignment = centro
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = relleno("1F7A3A" if estado == "OK" else "C00000")
            hoja.cell(fila, 6, nota).alignment = envolver
            for c in range(1, 7):
                hoja.cell(fila, c).border = borde

    # --- 8. Documentos leidos y emparejamiento ---
    fila += 2
    titulo_bloque(hoja, fila, "8. DOCUMENTOS LEÍDOS Y CUENTAS EMPAREJADAS",
                  max(c_total, 6))
    fila += 1
    encabezado(hoja, fila, ["Archivo", "Cargado como", "Identificado como",
                            "Observación"], alto=20)
    for doc in resultado.get("leidos", []):
        fila += 1
        valores = [doc["nombre"], doc["cargado_como"].capitalize(),
                   {"libro": "HELISA", "extracto": "Extracto",
                    "desconocido": "No reconocido"}[doc["tipo"]],
                   "; ".join(doc["errores"]) if doc["tipo"] ==
                   "desconocido" else ("Se usó en la otra ranura" if
                                       doc["tipo"] != doc["cargado_como"]
                                       else "")]
        for c, valor in enumerate(valores, start=1):
            hoja.cell(fila, c, valor).alignment = envolver
            hoja.cell(fila, c).border = borde
    fila += 2
    encabezado(hoja, fila, ["Cuenta", "Extracto", "Cuenta de HELISA",
                            "Coincidencia", "Motivos"], alto=20)
    for c in cuentas:
        fila += 1
        puntos = c.get("puntaje")
        if puntos is None:
            nivel = "Sin pareja"
        elif puntos >= UMBRAL_PAREJA_SEGURA:
            nivel = "Alta"
        elif puntos >= UMBRAL_PAREJA_DUDOSA:
            nivel = "Parcial"
        else:
            nivel = "Baja: parecen cuentas distintas"
        valores = [c["etiqueta"], c.get("archivo_extracto") or "(ninguno)",
                   c["analisis"]["seccion"].get("etiqueta") or "(ninguna)",
                   nivel, ", ".join(c.get("motivos") or [])]
        for col, valor in enumerate(valores, start=1):
            hoja.cell(fila, col, valor).alignment = envolver
            hoja.cell(fila, col).border = borde
        hoja.cell(fila, 4).fill = relleno(
            COLORES["verde"] if nivel == "Alta" else COLORES["amarillo"]
            if nivel == "Parcial" else COLORES["rojo"])

    fila += 2
    titulo_bloque(hoja, fila, "NOTAS", max(c_total, 6))
    for nota in [
        "Celdas con fondo amarillo y letra azul = datos tomados de los "
        "documentos (saldos de HELISA y del extracto); el resto son "
        "fórmulas.",
        "Los bloques 3 y 4 suman la hoja 'Detalle gastos': si cambias una "
        "categoría allí, el resumen se recalcula.",
        f"Se cruzan valores iguales con hasta "
        f"{primera['parametros']['ventana_dias'] if primera else 15} días de "
        "diferencia en la fecha.",
        "Este soporte es de conciliación; el tratamiento contable y "
        "tributario (GMF, IVA de comisiones) debe confirmarlo el contador.",
    ]:
        fila += 1
        hoja.cell(fila, 1, nota).font = Font(italic=True, color="595959")

    hoja.column_dimensions["A"].width = 62
    for c in range(2, max(c_total, 6) + 1):
        hoja.column_dimensions[L(c)].width = 24

    # ============================ CONCILIACION ===========================
    hoja = wb.create_sheet("Conciliación")
    columnas = ["Cuenta", "Estado", "Fecha", "Ubicación",
                "Descripción en el extracto", "Valor extracto", "Fecha",
                "Ubicación", "Comprobante", "Tercero", "Valor HELISA",
                "Diferencia (extracto - HELISA)", "Observación"]
    titulo_hoja(hoja, "CONCILIACIÓN LÍNEA A LÍNEA: EXTRACTO vs. HELISA",
                "Verde = conciliada · Amarillo = está en los dos con valor "
                "diferente · Rojo = no está en uno de los dos. La ubicación "
                "es la página del PDF o la fila del Excel donde está la "
                "partida.", len(columnas))
    hoja.merge_cells("C3:F3")
    hoja["C3"] = "EXTRACTO BANCARIO"
    hoja.merge_cells("G3:K3")
    hoja["G3"] = "HELISA"
    for celda, color in ((hoja["C3"], TINTA), (hoja["G3"], MAGENTA)):
        celda.font = blanco_negrita
        celda.fill = relleno(color)
        celda.alignment = centro
    encabezado(hoja, 4, columnas)

    def observacion(p):
        if ESTADOS_PARTIDA[p["estado"]][1] == "verde":
            if p["conjunto"]:
                if p["e"] is not None and p["e"].get("grupo_nm"):
                    return p["e"]["nota"]
                return "Cruza con un solo registro de HELISA que agrupa " \
                       "varios cargos del banco."
            l = p["l"][0] if p["l"] else None
            if l and p["e"] and l["fecha"] != p["e"]["fecha"]:
                return (f"Cruza por valor; fechas con "
                        f"{abs((l['fecha'] - p['e']['fecha']).days)} días "
                        "de diferencia.")
            return ""
        if p["sugerencias"]:
            mejor = max(p["sugerencias"],
                        key=lambda s: CONFIANZA_ORDEN[s["confianza"]])
            texto = mejor["explicacion"]
            if mejor["confianza"] == "Baja":
                texto = "Causa no identificada. " + texto
            return f"{texto} Qué hacer: {mejor['accion']}"
        return ACCIONES_PARTIDA.get(p["estado"], "")

    fila = 4
    for d, filas_cruce in zip(datos, cruces):
        for p in filas_cruce:
            fila += 1
            etiqueta, color = ESTADOS_PARTIDA[p["estado"]]
            e, ls = p["e"], p["l"]
            hoja.cell(fila, 1, d["cuenta"]["etiqueta"])
            hoja.cell(fila, 2, etiqueta).font = Font(
                bold=True, color=TEXTO_ESTADO[color])
            if e is not None:
                hoja.cell(fila, 3, e["fecha"]).number_format = "DD/MM/YYYY"
                hoja.cell(fila, 4, e.get("ubicacion"))
                hoja.cell(fila, 5, e["descripcion"])
                monto(hoja, fila, 6, p["valor_e"])
            if ls:
                if len(ls) == 1:
                    hoja.cell(fila, 7, ls[0]["fecha"]).number_format = \
                        "DD/MM/YYYY"
                    hoja.cell(fila, 8, ls[0].get("ubicacion"))
                    hoja.cell(fila, 10, ls[0]["tercero"])
                else:
                    hoja.cell(fila, 8, ", ".join(sorted(
                        {l.get("ubicacion") or "" for l in ls} - {""})))
                    hoja.cell(fila, 10, ", ".join(sorted(
                        {l["tercero"] for l in ls})))
                comprobantes = list(dict.fromkeys(
                    f"{l['tipo']} {l['numero']}" for l in ls))
                hoja.cell(fila, 9, ", ".join(comprobantes)
                          + (f" ({len(ls)} registros)"
                             if len(ls) > len(comprobantes) else ""))
                monto(hoja, fila, 11, p["valor_l"])
            if p["diferencia"] is not None:
                monto(hoja, fila, 12, p["diferencia"])
            hoja.cell(fila, 13, observacion(p))
            for c in range(1, len(columnas) + 1):
                celda = hoja.cell(fila, c)
                celda.fill = relleno(COLORES[color])
                celda.border = borde
                celda.alignment = Alignment(
                    vertical="top", wrap_text=c in (1, 2, 5, 10, 13),
                    horizontal="center" if c in (4, 8) else None)
    ultima = max(fila, 5)
    if fila == 4:
        hoja.cell(5, 1, "No hay movimientos.")
    hoja.auto_filter.ref = f"A4:{L(len(columnas))}{ultima}"
    hoja.freeze_panes = "C5"
    for c, ancho in enumerate([20, 24, 11, 10, 42, 16, 11, 10, 16, 30, 16,
                               16, 70], start=1):
        hoja.column_dimensions[L(c)].width = ancho

    fila = ultima + 2
    titulo_bloque(hoja, fila, "TOTALES", len(columnas))
    fila += 1
    encabezado(hoja, fila, ["", "Estado", "Partidas", "", "",
                            "Valor extracto", "", "", "", "", "Valor HELISA",
                            "Diferencia"], alto=20)
    rango_a = f"$B$5:$B${ultima}"
    inicio_t = fila + 1
    for estado in ORDEN_ESTADOS:
        clave = next(k for k, (et, _) in ESTADOS_PARTIDA.items()
                     if et == estado)
        color = ESTADOS_PARTIDA[clave][1]
        fila += 1
        hoja.cell(fila, 2, estado).font = Font(bold=True,
                                               color=TEXTO_ESTADO[color])
        hoja.cell(fila, 2).fill = relleno(COLORES[color])
        hoja.cell(fila, 3, f"=COUNTIF({rango_a},B{fila})")
        for col in (6, 11, 12):
            monto(hoja, fila, col, f"=SUMIF({rango_a},B{fila},"
                                   f"{L(col)}$5:{L(col)}${ultima})")
    fila += 1
    hoja.cell(fila, 2, "TOTAL").font = negrita
    hoja.cell(fila, 3, f"=SUM(C{inicio_t}:C{fila - 1})").font = negrita
    for col in (6, 11, 12):
        monto(hoja, fila, col, f"=SUM({L(col)}{inicio_t}:{L(col)}"
                               f"{fila - 1})", negrita)
    for col in (2, 3, 6, 11, 12):
        hoja.cell(fila, col).border = borde_total
    fila += 1
    hoja.cell(fila, 2, "Total de las filas filtradas").font = Font(
        italic=True)
    hoja.cell(fila, 3, f"=SUBTOTAL(103,B5:B{ultima})")
    for col in (6, 11, 12):
        monto(hoja, fila, col, f"=SUBTOTAL(109,{L(col)}5:{L(col)}{ultima})")

    for hoja_imp in wb.worksheets:          # imprimir a lo ancho de la hoja
        hoja_imp.sheet_properties.pageSetUpPr.fitToPage = True
        hoja_imp.page_setup.fitToWidth = 1
        hoja_imp.page_setup.fitToHeight = 0
        hoja_imp.page_setup.orientation = "landscape"
    wb.move_sheet("Conciliación", offset=-1)   # Resumen, Conciliación,
    salida = io.BytesIO()                      # Detalle gastos
    wb.save(salida)
    return salida.getvalue()
