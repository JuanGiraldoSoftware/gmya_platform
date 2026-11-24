"""Revision de movimientos del banco vs HELISA en el formato de la firma
(v6.19, sin Streamlit). Modelo: BANCOLOMBIA 01 AL 31-10-2026.xls (el
archivo de movimientos del banco pintado por estado, con REVISIONES).

Contrato:
  clasificar(mov, libro_movs) -> {"clase", "documento", "revision",
      "revisar"}. clase: "correcto" (salida que esta en HELISA), "ingreso"
      (entrada que esta en HELISA), "gasto" (GMF, comisiones, IVA bancario,
      intereses: van en la nota bancaria) o "sin_helisa".
  datos_revision(analisis) -> filas (en el orden del archivo del banco),
      totales por clase, por_revisar, helisa_sin_banco, gastos, iva,
      consecutivos, saldos.
  excel_revision(resultado) -> bytes. Por cuenta una hoja con los
      movimientos del banco (columnas del archivo, DOCUMENTO HELISA y
      REVISIONES) y la leyenda; al final la hoja RESUMEN.
  nombre_revision(resultado) -> nombre del archivo.
Reglas: los colores son los de la firma (CORRECTO verde, INGRESOS rosado,
GASTOS BANCARIOS amarillo, NO ESTA EN HELISA naranja). Lo que hay que
revisar (tercero distinto, valor diferente, fechas separadas, no esta en
HELISA) va en REVISIONES en rojo; nada se da por bueno en silencio.
Depende de: gmya.comun.numeros, gmya.modulos.bancos.lectura,
gmya.modulos.bancos.conciliacion
"""

import io
import re
from collections import OrderedDict
from decimal import Decimal

from gmya.comun.numeros import CERO, formato_cop
from gmya.modulos.bancos.lectura import CATEGORIAS_BANCARIAS
from gmya.modulos.bancos.conciliacion import (
    VENTANA_FECHA_REVISAR, categoria_gasto,
)

CLASES = OrderedDict([
    ("correcto", ("CORRECTO", "FF99CC00")),
    ("ingreso", ("INGRESOS", "FFFF99CC")),
    ("gasto", ("GASTOS BANCARIOS", "FFFFFF00")),
    ("sin_helisa", ("NO ESTA EN HELISA", "FFFFCC99")),
])
TARIFA_IVA = Decimal("0.19")


def _es_gasto(mov):
    cat = mov.get("categoria")
    return cat in CATEGORIAS_BANCARIAS or categoria_gasto(mov) is not None \
        or (cat == "rendimientos" and mov["valor"] > 0)


def _docs(movs):
    return ", ".join(sorted({f"{m['tipo']} {m['numero']}" for m in movs},
                            key=lambda t: (t.split()[0], int(re.sub(
                                r"\D", "", t) or 0))))


def clasificar(mov, libro_movs):
    pares = [libro_movs[j] for j in mov.get("pareja") or []
             if j < len(libro_movs)]
    documento = _docs(pares)
    estado = mov["estado"]
    partes, revisar = [], False
    if _es_gasto(mov):
        clase = "gasto"
        if pares:
            partes.append(f"Registrado en HELISA: {documento}")
        if estado == "agrupado_diferencia":
            partes.append("REVISAR: " + mov.get("nota", ""))
            revisar = True
    elif estado == "sin_libro":
        clase = "sin_helisa"
        partes.append("NO ESTÁ EN HELISA")
        revisar = True
    else:
        clase = "ingreso" if mov["valor"] > 0 else "correcto"
        if estado in ("diferencia", "agrupado_diferencia"):
            valor_h = sum((p["valor"] for p in pares), CERO)
            partes.append(f"REVISAR: VALOR DIFERENTE: banco "
                          f"{formato_cop(mov['valor'])} vs HELISA "
                          f"{formato_cop(valor_h)}")
            revisar = True
        if mov.get("grupo_nm"):
            hermanos = {k for p in pares for k in (p.get("pareja") or [])}
            partes.append(
                f"AGRUPADO: {max(len(hermanos), 1)} movimiento"
                f"{'s' if len(hermanos) > 1 else ''} del banco = "
                f"{len(pares)} línea{'s' if len(pares) > 1 else ''} de "
                f"HELISA")
        if mov.get("tercero_distinto") == "revisar":
            partes.append("REVISAR: " + mov["nota_tercero"])
            revisar = True
        elif mov.get("tercero_distinto") == "info":
            partes.append(mov["nota_tercero"])
        dias = mov.get("dias_fecha")
        if dias is not None and abs(dias) >= VENTANA_FECHA_REVISAR:
            fecha_h = min(p["fecha"] for p in pares)
            partes.append(
                f"REVISAR FECHA: en HELISA {fecha_h:%d/%m/%Y} y en el banco "
                f"{mov['fecha']:%d/%m/%Y} ({abs(dias)} días)")
            revisar = True
    if mov.get("nota_banco"):
        partes.append(f"Nota del archivo: {mov['nota_banco']}")
    return {"clase": clase, "documento": documento,
            "revision": " · ".join(p for p in partes if p),
            "revisar": revisar}


def _consecutivos(libro_movs):
    """Numeros que faltan dentro del rango de cada tipo de comprobante (pocos:
    si faltan muchos, la numeracion es compartida con otras cuentas)."""
    por_tipo = {}
    for m in libro_movs:
        num = re.sub(r"\D", "", str(m.get("numero") or ""))
        if num:
            por_tipo.setdefault(m["tipo"], set()).add(int(num))
    salida = {}
    for tipo, nums in por_tipo.items():
        if len(nums) < 3:
            continue
        faltan = sorted(set(range(min(nums), max(nums) + 1)) - nums)
        if 0 < len(faltan) <= 10:
            salida[tipo] = faltan
    return salida


def datos_revision(analisis):
    movs, lib = analisis["movs"], analisis["libro_movs"]
    filas = []
    for mov in movs:
        filas.append(dict(clasificar(mov, lib), mov=mov))
    # Orden del archivo del banco (el de movimientos de Bancolombia viene
    # del mas reciente al mas antiguo); si no, por fecha.
    if filas and all("orden" in f["mov"] for f in filas):
        filas.sort(key=lambda f: f["mov"]["orden"])
    else:
        filas.sort(key=lambda f: f["mov"]["fecha"])
    totales = OrderedDict((c, [0, CERO]) for c in CLASES)
    for f in filas:
        totales[f["clase"]][0] += 1
        totales[f["clase"]][1] += f["mov"]["valor"]

    gastos = OrderedDict()
    for f in filas:
        if f["clase"] != "gasto":
            continue
        cat = categoria_gasto(f["mov"]) or ("Otros cargos", f["mov"][
            "descripcion"])
        g = gastos.setdefault(cat, {"concepto": cat[0], "detalle": cat[1],
                                    "n": 0, "valor": CERO,
                                    "registrado": CERO})
        g["n"] += 1
        g["valor"] += f["mov"]["valor"]
        if f["mov"]["estado"] != "sin_libro":
            g["registrado"] += f["mov"]["valor"]
    orden = ("GMF 4x1000", "Comisión", "IVA sobre comisión",
             "Retención en la fuente", "Intereses ganados")
    gastos = OrderedDict(sorted(
        gastos.items(), key=lambda kv: (orden.index(kv[1]["concepto"])
                                        if kv[1]["concepto"] in orden
                                        else len(orden), kv[1]["detalle"])))
    comisiones = -sum((g["valor"] for g in gastos.values()
                       if g["concepto"] == "Comisión"
                       and "manejo" not in g["detalle"].lower()), CERO)
    iva_cobrado = -sum((g["valor"] for g in gastos.values()
                        if g["concepto"].startswith("IVA")), CERO)
    iva = {"base": comisiones, "esperado": (comisiones * TARIFA_IVA).quantize(
        Decimal("0.01")), "cobrado": iva_cobrado}
    iva["diferencia"] = iva["cobrado"] - iva["esperado"]

    sin_banco = [m for m in lib if m["estado"] == "sin_extracto"]
    return {
        "filas": filas, "totales": totales,
        "por_revisar": [f for f in filas if f["revisar"]],
        "informativas": [f for f in filas if not f["revisar"]
                         and f["mov"].get("tercero_distinto") == "info"],
        "helisa_sin_banco": [m for m in sin_banco
                             if not m.get("posterior_corte")],
        "posterior_corte": [m for m in sin_banco if m.get("posterior_corte")],
        "helisa_conciliado": sum((m["valor"] for m in lib
                                  if m["estado"] == "conciliado"), CERO),
        "gastos": list(gastos.values()), "iva": iva,
        "consecutivos": _consecutivos(lib),
        "conc": analisis["conc"],
    }


# ------------------------------------------------------------
# Excel
# ------------------------------------------------------------
def _hoja_titulo(extracto):
    p = extracto.get("periodo")
    cuenta = re.sub(r"\D", "", str(extracto.get("cuenta") or ""))[-4:]
    banco = (extracto.get("banco") or "BANCO").upper().split()[0]
    texto = f"{banco} {cuenta}".strip()
    if p:
        texto += f" {p[0]:%d} AL {p[1]:%d-%m}"
    return re.sub(r"[\[\]:*?/\\]", "-", texto)[:31]


def nombre_revision(resultado):
    cuentas = resultado["cuentas"]
    periodos = [c["analisis"]["extracto"]["periodo"] for c in cuentas
                if c["analisis"]["extracto"].get("periodo")]
    rango = ""
    if periodos:
        ini = min(p[0] for p in periodos)
        fin = max(p[1] for p in periodos)
        rango = f" {ini:%d} AL {fin:%d-%m-%Y}"
    if len(cuentas) == 1:
        e = cuentas[0]["analisis"]["extracto"]
        cuenta = e.get("cuenta") or ""
        if e.get("formato") == "Movimientos Bancolombia" and len(cuenta) == 11:
            cuenta = f"{cuenta[:3]}-{cuenta[3:9]}-{cuenta[9:]}"
        base = f"REVISION MOVIMIENTOS {(e.get('banco') or '').upper()} " \
            f"{cuenta}".strip()
    else:
        base = f"REVISION MOVIMIENTOS {len(cuentas)} CUENTAS"
    return re.sub(r"\s+", " ", base + rango).strip() + ".xlsx"


def _valor_crudo(v):
    if isinstance(v, str):
        t = v.strip()
        if re.fullmatch(r"\d+", t):
            return int(t)
        return t
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def excel_revision(resultado):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    def relleno(color):
        return PatternFill("solid", fgColor=color)
    negrita = Font(bold=True)
    rojo = Font(bold=True, color="FFC00000")
    formato = "#,##0.00;-#,##0.00"
    libro = Workbook()
    libro.remove(libro.active)
    resumenes = []
    for cuenta in resultado["cuentas"]:
        a = cuenta["analisis"]
        if not a["movs"]:
            continue
        datos = datos_revision(a)
        resumenes.append((cuenta, datos))
        nombre = _hoja_titulo(a["extracto"])
        while nombre in libro.sheetnames:
            nombre = nombre[:28] + f" {len(libro.sheetnames) + 1}"
        hoja = libro.create_sheet(nombre)
        crudo = all(f["mov"].get("crudo") for f in datos["filas"])
        if crudo:
            cab = ["Column1", "Column2", "Column4", "Column6", "Column7",
                   "Column8", "Column9"]
            anchos = [15, 10, 11, 16, 10, 34, 10]
            col_valor = 4
        else:
            cab = ["FECHA", "DESCRIPCIÓN", "VALOR"]
            anchos = [12, 46, 18]
            col_valor = 3
        cab += ["DOCUMENTO HELISA", "REVISIONES"]
        anchos += [20, 90]
        hoja.append(cab)
        for celda in hoja[1]:
            celda.fill = relleno(CLASES["correcto"][1])
            celda.font = negrita
        n_datos = len(cab) - 2
        for f in datos["filas"]:
            m = f["mov"]
            if crudo:
                fila = [_valor_crudo(v) for v in m["crudo"]]
                fila[3] = float(m["valor"])
            else:
                fila = [m["fecha"], m["descripcion"], float(m["valor"])]
            hoja.append(fila + [f["documento"] or None, f["revision"] or None])
            r = hoja.max_row
            for c in range(1, n_datos + 1):
                hoja.cell(r, c).fill = relleno(CLASES[f["clase"]][1])
            hoja.cell(r, col_valor).number_format = formato
            if not crudo:
                hoja.cell(r, 1).number_format = "DD/MM/YYYY"
            if f["revisar"]:
                hoja.cell(r, len(cab)).font = rojo
        # Leyenda (como el modelo de la firma, a la derecha).
        col_ley = len(cab) + 2
        for i, (clave, (texto, color)) in enumerate(CLASES.items(), start=2):
            hoja.cell(i, col_ley).fill = relleno(color)
            hoja.cell(i, col_ley + 1, texto)
            hoja.cell(i, col_ley + 2, datos["totales"][clave][0])
            hoja.cell(i, col_ley + 3, float(datos["totales"][clave][1]))
            hoja.cell(i, col_ley + 3).number_format = formato
        hoja.cell(1, col_ley + 1, "CONVENCIONES").font = negrita
        hoja.cell(1, col_ley + 2, "Mov.").font = negrita
        hoja.cell(1, col_ley + 3, "Valor").font = negrita
        from openpyxl.utils import get_column_letter
        for i, ancho in enumerate(anchos, start=1):
            hoja.column_dimensions[get_column_letter(i)].width = ancho
        hoja.column_dimensions[get_column_letter(col_ley)].width = 4
        hoja.column_dimensions[get_column_letter(col_ley + 1)].width = 22
        hoja.column_dimensions[get_column_letter(col_ley + 3)].width = 18
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = f"A1:{get_column_letter(len(cab))}" \
            f"{hoja.max_row if hoja.max_row > 1 else 2}"
    if not resumenes:
        hoja = libro.create_sheet("RESUMEN")
        hoja["A1"] = "No hay movimientos del banco para revisar."
    else:
        _hoja_resumen(libro, resumenes, relleno, negrita, rojo, formato,
                      Alignment)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _hoja_resumen(libro, resumenes, relleno, negrita, rojo, formato,
                  Alignment):
    hoja = libro.create_sheet("RESUMEN")
    hoja.column_dimensions["A"].width = 14
    hoja.column_dimensions["B"].width = 52
    hoja.column_dimensions["C"].width = 18
    hoja.column_dimensions["D"].width = 18
    hoja.column_dimensions["E"].width = 80

    def fila(*valores, fuente=None, fill=None, num=()):
        hoja.append(list(valores))
        r = hoja.max_row
        for c in num:
            hoja.cell(r, c).number_format = formato
        if fuente:
            for celda in hoja[r]:
                celda.font = fuente
        if fill:
            hoja.cell(r, 1).fill = relleno(fill)
        return r

    def titulo(texto):
        hoja.append([])
        r = fila(texto, fuente=negrita)
        for c in range(1, 6):
            hoja.cell(r, c).fill = relleno("FFD9D9D9")
        hoja.merge_cells(start_row=r, start_column=1, end_row=r,
                         end_column=5)

    for cuenta, d in resumenes:
        a = cuenta["analisis"]
        e, s = a["extracto"], a["seccion"]
        p, pl = e.get("periodo"), a["libro"].get("periodo")
        empresa = a["libro"].get("empresa") or ""
        r = fila(f"REVISIÓN DE MOVIMIENTOS · {cuenta['etiqueta']}"
                 + (f" · {empresa}" if empresa else ""),
                 fuente=Font_titulo())
        hoja.merge_cells(start_row=r, start_column=1, end_row=r,
                         end_column=5)
        fila("Banco", f"{cuenta['archivo_extracto'] or '(sin archivo)'}"
             + (f" · movimientos del {p[0]:%d/%m/%Y} al {p[1]:%d/%m/%Y}"
                if p else ""))
        fila("HELISA", f"{cuenta['archivo_libro'] or '(sin archivo)'} · "
             f"{s.get('etiqueta') or s.get('cuenta') or ''}"
             + (f" · {pl[0]:%d/%m/%Y} al {pl[1]:%d/%m/%Y}" if pl else ""))

        titulo("1. Movimientos del banco por estado")
        fila("Color", "Estado", "Movimientos", "Valor", fuente=negrita)
        for clave, (texto, color) in CLASES.items():
            n, v = d["totales"][clave]
            fila("", texto, n, float(v), fill=color, num=(4,))
        total_n = sum(t[0] for t in d["totales"].values())
        total_v = sum((t[1] for t in d["totales"].values()), CERO)
        fila("", "Total movimientos del banco", total_n, float(total_v),
             fuente=negrita, num=(4,))
        en_helisa = sum((f["mov"]["valor"] for f in d["filas"]
                         if f["mov"]["estado"] != "sin_libro"), CERO)
        r = fila("", "Control: movimientos del banco que están en HELISA vs "
                 "registros de HELISA cruzados", float(en_helisa),
                 float(d["helisa_conciliado"]), num=(3, 4))
        dif = en_helisa - d["helisa_conciliado"]
        hoja.cell(r, 5, "Cuadra" if dif == 0 else
                  f"Diferencia {formato_cop(dif)}: ver VALOR DIFERENTE")
        if dif:
            hoja.cell(r, 5).font = rojo

        titulo(f"2. Para revisar ({len(d['por_revisar'])})")
        if d["por_revisar"]:
            fila("Fecha", "Movimiento del banco", "Valor",
                 "Documento HELISA", "Qué revisar", fuente=negrita)
            for f in d["por_revisar"]:
                m = f["mov"]
                r = fila(m["fecha"], m["descripcion"], float(m["valor"]),
                         f["documento"] or "—", f["revision"], num=(3,))
                hoja.cell(r, 1).number_format = "DD/MM/YYYY"
                hoja.cell(r, 1).fill = relleno(CLASES[f["clase"]][1])
                hoja.cell(r, 5).font = rojo
        else:
            fila("", "Nada por revisar.")
        if d["informativas"]:
            fila("", "Para confirmar (pagos por PSE a un recaudador u "
                 "operador):", fuente=negrita)
            for f in d["informativas"]:
                m = f["mov"]
                r = fila(m["fecha"], m["descripcion"], float(m["valor"]),
                         f["documento"], f["revision"], num=(3,))
                hoja.cell(r, 1).number_format = "DD/MM/YYYY"

        titulo(f"3. En HELISA y no en el banco "
               f"({len(d['helisa_sin_banco'])})")
        if d["helisa_sin_banco"]:
            fila("Fecha", "Documento · tercero", "Valor", "", "Nota",
                 fuente=negrita)
            for m in d["helisa_sin_banco"]:
                r = fila(m["fecha"], f"{m['tipo']} {m['numero']} · "
                         f"{m.get('tercero') or ''}", float(m["valor"]), "",
                         "En tránsito o sin movimiento en el banco: "
                         "confirmar", num=(3,))
                hoja.cell(r, 1).number_format = "DD/MM/YYYY"
        else:
            fila("", "Todo lo de HELISA está en el banco.")
        if d["posterior_corte"]:
            total = sum((m["valor"] for m in d["posterior_corte"]), CERO)
            fila("", f"Registrados en HELISA después del último movimiento "
                 f"del banco: {len(d['posterior_corte'])}", float(total),
                 "", "No se revisan en este corte", num=(3,))

        titulo("4. Gastos bancarios del periodo")
        fila("", "Concepto", "Valor", "En HELISA", "", fuente=negrita)
        for g in d["gastos"]:
            fila("", f"{g['concepto']} · {g['detalle']} ({g['n']})",
                 float(g["valor"]), float(g["registrado"]), "", num=(3, 4))
        total_g = sum((g["valor"] for g in d["gastos"]), CERO)
        reg_g = sum((g["registrado"] for g in d["gastos"]), CERO)
        r = fila("", "Neto (por registrar en HELISA = total − en HELISA)",
                 float(total_g), float(reg_g),
                 "Por registrar en HELISA (nota bancaria): "
                 f"{formato_cop(abs(total_g - reg_g))}",
                 fuente=negrita, num=(3, 4))
        iva = d["iva"]
        if iva["base"]:
            r = fila("", "Control IVA: 19 % de las comisiones "
                     f"({formato_cop(iva['base'])})", float(iva["esperado"]),
                     float(iva["cobrado"]),
                     "Cuadra" if not iva["diferencia"] else
                     f"REVISAR: el banco cobró {formato_cop(iva['diferencia'])}"
                     " de diferencia", num=(3, 4))
            if iva["diferencia"]:
                hoja.cell(r, 5).font = rojo

        titulo("5. Saldos")
        c = d["conc"]
        if c.get("sin_saldos"):
            fila("", "El archivo del banco no trae saldos: escribe el saldo "
                 "inicial del extracto en la plataforma (Opciones avanzadas) "
                 "para cerrar la conciliación de saldos.", fuente=rojo)
            fila("", "Saldo inicial HELISA", float(c["saldo_ini_lib"]),
                 num=(3,))
            fila("", "Saldo final HELISA", float(c["saldo_fin_lib"]),
                 num=(3,))
            fila("", "Neto de los movimientos del banco", float(total_v),
                 num=(3,))
        else:
            for etiqueta, clave in (
                    ("Saldo inicial del banco", "saldo_ini_ext"),
                    ("Saldo final del banco", "saldo_fin_ext"),
                    ("Saldo inicial HELISA", "saldo_ini_lib"),
                    ("Saldo final HELISA", "saldo_fin_lib"),
                    ("(+) Diferencia de saldos iniciales",
                     "diferencia_saldo_inicial"),
                    ("(+) HELISA sin movimiento en el banco", "lib_sin_ext"),
                    ("(−) Banco sin registrar en HELISA", "ext_sin_lib"),
                    ("Saldo HELISA calculado", "calculado")):
                fila("", etiqueta, float(c[clave]), num=(3,))
            r = fila("", "Diferencia no explicada (debe ser 0)",
                     float(c["no_explicada"]), fuente=negrita, num=(3,))
            if c["no_explicada"]:
                hoja.cell(r, 3).font = rojo

        titulo("6. Otras observaciones")
        obs = []
        for tipo, faltan in d["consecutivos"].items():
            obs.append(f"Consecutivos {tipo} que no aparecen en esta cuenta: "
                       + ", ".join(str(n) for n in faltan)
                       + " (anulados o registrados en otra cuenta: "
                       "confirmar).")
        obs += a.get("avisos") or []
        for texto in obs or ["Sin observaciones."]:
            r = fila("", texto)
            hoja.cell(r, 2).alignment = Alignment(wrap_text=False)
        hoja.append([])
        hoja.append([])


def Font_titulo():
    from openpyxl.styles import Font
    return Font(bold=True, size=12)
