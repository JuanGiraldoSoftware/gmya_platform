"""Flujo de caja y relacion de anticipos de EMPRESA B S.A.S. (v6.18, sin
Streamlit). Es una programacion de pagos semanal: el flujo anterior + los
informes de HELISA (cartera, cuentas por pagar, anticipos realizados y
recibidos) dan el flujo nuevo y la relacion de anticipos nueva.

Contrato:
  leer_flujo_empresa_b(contenido, nombre) -> modelo del flujo anterior.
  leer_relacion_anticipos(contenido, nombre) -> modelo de la relacion.
  leer_anticipos_helisa(contenido) -> {"clase": realizados|recibidos,
      "docs": [...], "total": {...}} (informe de anticipos de HELISA).
  saldo_inicial_propuesto(anterior, fecha) -> {cuenta: saldo} con que
      arranca el flujo nuevo (saldo proyectado de la ultima semana pasada).
  armar_flujo_empresa_b(anterior, cxc, cxp, fecha, semanas=4, saldos=None,
      config=None) -> {"modelo", "alertas", "resumen", "nuevos", ...}
  armar_relacion_anticipos(anterior, realizados, recibidos, config=None)
      -> {"modelo", "alertas", "resumen"}
  excel_flujo_empresa_b(resultado, contenido_anterior) -> bytes (mismo libro y
      formato del flujo anterior: se reconstruye la hoja copiando el estilo
      de sus propias filas).
  excel_relacion_anticipos(resultado, contenido_anterior) -> bytes.
  nombre_flujo(nombre_anterior, fecha), nombre_relacion(nombre_anterior).

Reglas (deducidas comparando el flujo V18112026 -> V19112026 y la relacion
#2 -> #3 que hizo la firma):
  Semanas de lunes a domingo; la primera es la que contiene la fecha del
  flujo. Lo que estaba en semanas que ya pasaron NO se pasa: en cartera y
  cuentas por pagar el documento sigue solo si HELISA lo trae con saldo
  (si estaba proyectado en una semana pasada y sigue pendiente se avisa);
  las filas de ingresos y de anticipos a realizar que solo tenian valores
  pasados se limpian; los pagos fijos pagados pasan al mes siguiente con
  el valor pagado. Lo proyectado a futuro se corre a su misma semana.
  Saldo inicial de cada cuenta = saldo proyectado de la ultima semana que
  ya paso (editable con el saldo real de bancos).
  Documentos: se cruzan por numero normalizado; si no, por tercero +
  fecha + valor, o unico pendiente del tercero (se avisa el numero de
  HELISA). Si el saldo de HELISA es menor, la diferencia va a abonos.
  Terceros nuevos en HELISA: entran si tienen documentos de los ultimos 7
  dias antes del flujo anterior o posteriores; los demas se asumen dejados
  por fuera a proposito (socios, servicios en pagos fijos) y se avisan.
  Relacion de anticipos: solo lo que HELISA trae por aplicar; el total de
  cada seccion debe ser igual al VR.POR APLICAR de HELISA (se comprueba).
Depende de: gmya.comun.texto, gmya.modulos.pagos.lectura,
gmya.registro.privados
"""

import ast
import copy
import datetime
import difflib
import io
import operator
import re

from gmya.comun.texto import comparable
from gmya.modulos.pagos.lectura import (
    MESES_PP, correr_meses_texto, tiene_mes,
)
from gmya.registro.privados import guardar_privado, leer_privado

# terceros_fuera (nombres) y anticipos_por_mes ({nit: "TEXTO {mes} {anio}"})
# son datos privados del cliente: no van en el codigo, se editan en la
# pantalla y se guardan en ARCHIVO_CONFIG_EMPRESA_B (carpeta GMYA Tools).
ARCHIVO_CONFIG_EMPRESA_B = "empresa_b_config"
CONFIG_EMPRESA_B = {
    "terceros_fuera": [],
    # Anticipos que se agrupan por mes en la relacion (p. ej. comisiones).
    "anticipos_por_mes": {},
    # Filas de anticipos a realizar que se conservan aunque queden vacias.
    "filas_permanentes": ["AUTOMATICOS"],
    "dias_tercero_nuevo": 7,
}

def config_empresa_b():
    """CONFIG_EMPRESA_B + lo guardado (terceros fuera y anticipos por mes)."""
    config = dict(CONFIG_EMPRESA_B)
    guardado = leer_privado(ARCHIVO_CONFIG_EMPRESA_B, {}) or {}
    for k in ("terceros_fuera", "anticipos_por_mes"):
        if isinstance(guardado.get(k), type(CONFIG_EMPRESA_B[k])):
            config[k] = guardado[k]
    return config


def guardar_config_empresa_b(terceros_fuera, anticipos_por_mes):
    return guardar_privado(ARCHIVO_CONFIG_EMPRESA_B, {
        "terceros_fuera": [str(t).strip() for t in terceros_fuera
                           if str(t).strip()],
        "anticipos_por_mes": {str(k).strip(): str(v).strip()
                              for k, v in anticipos_por_mes.items()
                              if str(k).strip() and str(v).strip()}})


SUFIJOS = {"SAS", "SA", "S", "A", "LTDA", "CIA", "Y", "DE", "EICE", "ESP",
           "SOCIEDAD", "POR", "ACCIONES", "SIMPLIFICADA", "CF", "CO"}
TIPOS_DOC = ("FCC", "FCE", "FC", "DSE", "DSEC", "CC", "RC", "PE", "NC",
             "NCC", "ND", "FV", "FEV", "CE")


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def _t(v):
    return "" if v is None else str(v).strip()


def _n(v):
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _fecha(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", _t(v))
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)),
                                 int(m.group(1)))
        except ValueError:
            return None
    return None


def clave_doc(texto):
    """'FCC 00000000FEDW-1830', 'FCC FEDW-1820', 'FEDW-1830' -> la misma
    clave; 'RC  00000000083B' == 'RC-83B'. (letras, numero, sufijo)."""
    t = comparable(_t(texto))
    tipos = "|".join(sorted(TIPOS_DOC, key=len, reverse=True))
    resto = re.sub(rf"^(?:{tipos})(?:\s+|-)", "", t)
    if re.search(r"\d", resto):
        t = resto
    s = re.sub(r"[^A-Z0-9]", "", t).lstrip("0")
    m = re.match(r"^([A-Z]*?)0*(\d+)([A-Z]*)$", s)
    if not m:
        return (s, 0, "")
    return (m.group(1), int(m.group(2)), m.group(3))


def doc_corto(numero):
    """'RC  00000000083B' -> 'RC-83B'; 'FCC 00000000FEDW-1830' ->
    'FEDW-1830'; 'FEDU239' -> 'FEDU239'."""
    t = _t(numero)
    partes = t.split()
    if len(partes) > 1 and comparable(partes[0]) in TIPOS_DOC:
        tipo, resto = partes[0], "".join(partes[1:])
        resto = resto.lstrip("0") or "0"
        if re.match(r"^\d", resto):
            return f"{tipo}-{resto}" if tipo in ("RC", "PE", "CC", "CE") \
                else resto
        return resto
    return t


def nombre_clave(nombre):
    pal = [p for p in re.split(r"[^A-Z0-9]+", comparable(_t(nombre)))
           if p and p not in SUFIJOS]
    return " ".join(pal)


def mismo_tercero(a, b):
    x, y = nombre_clave(a), nombre_clave(b)
    if not x or not y:
        return False
    if x == y:
        return True
    tx, ty = set(x.split()), set(y.split())
    if len(tx & ty) >= 2 and (tx <= ty or ty <= tx):
        return True
    return difflib.SequenceMatcher(None, x, y).ratio() >= 0.86


def lunes(fecha):
    return fecha - datetime.timedelta(days=fecha.weekday())


def semanas_desde(fecha, n=4):
    ini = lunes(fecha)
    return [(ini + datetime.timedelta(days=7 * k),
             ini + datetime.timedelta(days=7 * k + 6)) for k in range(n)]


def etiqueta_semana(ini, fin):
    if ini.month == fin.month:
        return f"{ini.day:02d} AL {fin.day:02d} DE {MESES_PP[fin.month - 1]}"
    return (f"{ini.day:02d} {MESES_PP[ini.month - 1]} AL {fin.day:02d} DE "
            f"{MESES_PP[fin.month - 1]}")


def mes_semana(ini, fin):
    """Mes al que pertenece la semana (el de la mayoria de sus dias)."""
    dias = [ini + datetime.timedelta(days=k) for k in range(7)]
    return max({d.month for d in dias},
               key=lambda m: sum(1 for d in dias if d.month == m))


def numero_semana(ini, fin):
    mes = mes_semana(ini, fin)
    primer = datetime.date(fin.year if fin.month == mes else ini.year, mes, 1)
    primer_lunes = primer + datetime.timedelta(days=(-primer.weekday()) % 7)
    if primer_lunes.day > 4:          # la semana del 1 es la semana 1
        primer_lunes -= datetime.timedelta(days=7)
    return (ini - primer_lunes).days // 7 + 1


def _parse_semana(texto, anio):
    """'09 AL 15 DE NOVIEMBRE' / '30 NOVIEMBRE AL 06 DE DICIEMBRE'."""
    t = comparable(texto)
    m = re.match(r"(\d{1,2})\s*(?:DE\s*)?([A-Z]+)?\s*AL\s*(\d{1,2})\s*(?:DE\s*)?"
                 r"([A-Z]+)", t)
    if not m:
        return None
    mes_fin = next((i + 1 for i, x in enumerate(MESES_PP)
                    if x == m.group(4)), None)
    if not mes_fin:
        return None
    mes_ini = next((i + 1 for i, x in enumerate(MESES_PP)
                    if x == m.group(2)), mes_fin) if m.group(2) else mes_fin
    anio_ini = anio - 1 if mes_ini > mes_fin else anio
    try:
        return (datetime.date(anio_ini, mes_ini, int(m.group(1))),
                datetime.date(anio, mes_fin, int(m.group(3))))
    except ValueError:
        return None


def _sumar_mes(fecha):
    import calendar
    mes = fecha.month % 12 + 1
    anio = fecha.year + (1 if fecha.month == 12 else 0)
    return datetime.date(anio, mes, min(fecha.day,
                                        calendar.monthrange(anio, mes)[1]))


# ------------------------------------------------------------
# Evaluador de formulas simples (por si el libro no trae valores
# calculados: un archivo generado por la plataforma que no se abrio en
# Excel). Soporta referencias, + - * /, numeros y SUM(rango).
# ------------------------------------------------------------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg,
        ast.UAdd: operator.pos}


def _evaluador(ws_f, ws_v):
    from openpyxl.utils import column_index_from_string, get_column_letter
    memo = {}

    def valor(ref, pila=()):
        if ref in memo:
            return memo[ref]
        v = ws_v[ref].value if ws_v is not None else None
        f = ws_f[ref].value
        if v is None and isinstance(f, str) and f.startswith("="):
            if ref in pila:
                return 0.0
            v = formula(f[1:], pila + (ref,))
        if isinstance(v, str):
            try:
                v = float(v.replace(",", ""))
            except ValueError:
                v = 0.0
        memo[ref] = float(v or 0) if not isinstance(v, (datetime.date,)) \
            else 0.0
        return memo[ref]

    def rango(a, b, pila):
        ca, fa = re.match(r"([A-Z]+)(\d+)", a).groups()
        cb, fb = re.match(r"([A-Z]+)(\d+)", b).groups()
        tot = 0.0
        for c in range(column_index_from_string(ca),
                       column_index_from_string(cb) + 1):
            for r in range(int(fa), int(fb) + 1):
                tot += valor(f"{get_column_letter(c)}{r}", pila)
        return tot

    def formula(texto, pila):
        texto = texto.upper().replace("$", "")
        texto = re.sub(r"SUM\(([A-Z]+\d+):([A-Z]+\d+)\)",
                       lambda m: repr(rango(m.group(1), m.group(2), pila)),
                       texto)
        texto = re.sub(r"SUM\(([^)]*)\)", r"(\1)", texto)
        texto = re.sub(r"\b([A-Z]{1,3}\d+)\b",
                       lambda m: repr(valor(m.group(1), pila)), texto)
        try:
            return _ev(ast.parse(texto, mode="eval").body)
        except Exception:
            return 0.0

    def _ev(n):
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.BinOp):
            return _OPS[type(n.op)](_ev(n.left), _ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return _OPS[type(n.op)](_ev(n.operand))
        raise ValueError("formula no soportada")
    return valor


def _abrir(contenido):
    from openpyxl import load_workbook
    wb_f = load_workbook(io.BytesIO(contenido))
    wb_v = load_workbook(io.BytesIO(contenido), data_only=True)
    ws_f = wb_f[wb_f.sheetnames[0]]
    ws_v = wb_v[wb_v.sheetnames[0]]
    return wb_f, ws_f, ws_v


# ------------------------------------------------------------
# Lectura del flujo anterior
# ------------------------------------------------------------
TITULOS_INGRESO = ("PRESTAMO SOCIO", "VENTAS PROYECTADAS", "ANTICIPOS VENTAS")


def fecha_de_nombre(nombre):
    m = re.search(r"V\s*(\d{2})(\d{2})(\d{4})", _t(nombre))
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)),
                                 int(m.group(1)))
        except ValueError:
            return None
    return None


def leer_flujo_empresa_b(contenido, nombre=""):
    from openpyxl.utils import get_column_letter, column_index_from_string
    wb, ws, wsv = _abrir(contenido)
    val = _evaluador(ws, wsv)
    fecha = fecha_de_nombre(nombre)
    # Fila de titulos (Nit / Razon Social) y semanas.
    fila_tit = next((r for r in range(1, 15)
                     if comparable(_t(ws.cell(r, 1).value)) == "NIT"), None)
    if not fila_tit:
        raise ValueError("No parece el flujo de caja de EMPRESA B: no se encontró "
                         "la fila de títulos (Nit, Razon Social…).")
    col0 = column_index_from_string("K")
    for c in range(1, 30):
        if comparable(_t(ws.cell(fila_tit, c).value)).startswith("SALDO TOTAL"):
            col0 = c + 1
            break
    anio = (fecha or datetime.date.today()).year
    semanas, c = [], col0
    while _t(ws.cell(fila_tit, c).value):
        rango = _parse_semana(ws.cell(fila_tit, c).value, anio)
        if not rango:
            break
        semanas.append({"ini": rango[0], "fin": rango[1], "col": c})
        c += 2
    if not semanas:
        raise ValueError("No se encontraron las semanas del flujo (fila de "
                         "títulos, columnas «09 AL 15 DE …»).")
    if fecha is None:
        fecha = semanas[0]["ini"] + datetime.timedelta(days=3)
    cuentas = [_t(ws.cell(fila_tit - 3, col0).value) or "DAVIVIENDA",
               _t(ws.cell(fila_tit - 3, col0 + 1).value) or "CUENTA BOLD"]
    col_obs = semanas[-1]["col"] + 2
    letras = {k: get_column_letter(k) for k in range(1, col_obs + 3)}

    def celdas(r):
        return {letras[k]: ws.cell(r, k).value for k in range(1, 11)}

    def proyecciones(r):
        out = {}
        for i, s in enumerate(semanas):
            for j in (0, 1):
                ref = f"{letras[s['col'] + j]}{r}"
                f = ws[ref].value
                if f in (None, ""):
                    continue
                v = val(ref)
                if abs(v) < 0.005:
                    continue
                es_j = isinstance(f, str) and re.fullmatch(
                    rf"=\+?J{r}", f.replace(" ", "")) is not None
                out[(i, j)] = (round(v, 2), es_j)
        return out

    def fila_datos(r, tipo):
        d = celdas(r)
        return {"tipo": tipo, "fila": r, "celdas": d,
                "h": round(val(f"H{r}"), 2), "i": round(val(f"I{r}"), 2),
                "j": round(val(f"J{r}"), 2), "proy": proyecciones(r),
                "obs": ws.cell(r, col_obs).value,
                "obs2": ws.cell(r, col_obs + 1).value}

    secciones, r, actual = [], fila_tit + 1, None
    ultima = ws.max_row
    saldo_fila = bolsillos = None
    while r <= ultima:
        a = comparable(_t(ws.cell(r, 1).value))
        b = comparable(_t(ws.cell(r, 2).value))
        cc = comparable(_t(ws.cell(r, 3).value))
        e = comparable(_t(ws.cell(r, 5).value))
        if a.startswith(TITULOS_INGRESO):
            actual = {"tipo": "ingresos", "titulo": ws.cell(r, 1).value,
                      "fila_titulo": r, "filas": []}
            secciones.append(actual)
        elif a.startswith("TOTAL") and actual and actual["tipo"] == "ingresos" \
                and "total" not in actual:
            actual["total"] = ws.cell(r, 1).value
            actual["fila_total"] = r
        elif a == "CUENTAS POR COBRAR" or a.startswith("CUENTAS POR PAGAR"):
            actual = {"tipo": "cxc" if "COBRAR" in a else "cxp",
                      "titulo": ws.cell(r, 1).value, "fila_titulo": r,
                      "grupos": [], "fijos": []}
            secciones.append(actual)
            r += 1                      # fila de titulos de la tabla
            actual["fila_cab"] = r
        elif a.startswith("TOTAL CUENTAS POR"):
            actual["total"] = ws.cell(r, 1).value
            actual["fila_total"] = r
            actual = None
        elif a.startswith("ANTICIPOS A REALIZAR"):
            actual = {"tipo": "anticipos", "titulo": ws.cell(r, 1).value,
                      "fila_titulo": r, "filas": []}
            secciones.append(actual)
        elif a.startswith("TOTAL ANTICIPOS A REALIZAR"):
            actual["total"] = ws.cell(r, 1).value
            actual["fila_total"] = r
            actual = None
        elif a.startswith("TOTAL SALDO DISPONIBLE"):
            saldo_fila = r
        elif e.startswith("DISPONIBL"):
            bolsillos = r
        if actual and r not in (actual.get("fila_titulo"),
                                actual.get("fila_cab"),
                                actual.get("fila_total")):
            if actual["tipo"] == "ingresos" and "total" not in actual:
                actual["filas"].append(fila_datos(r, "ingreso"))
            elif actual["tipo"] == "anticipos":
                if any(_t(ws.cell(r, k).value) for k in range(2, 6)) or \
                        proyecciones(r):
                    actual["filas"].append(fila_datos(r, "anticipo"))
            elif actual["tipo"] in ("cxc", "cxp"):
                if a.startswith("PAGOS FIJOS") or actual.get("en_fijos"):
                    actual["en_fijos"] = True
                    if b == "TOTAL":
                        actual["fila_total_fijos"] = r
                        actual["en_fijos"] = False
                        actual["fijos_cerrado"] = True
                    elif not actual.get("fijos_cerrado"):
                        actual["fijos"].append(fila_datos(r, "fijo"))
                elif cc == "TOTAL":
                    if actual["grupos"]:
                        actual["grupos"][-1]["fila_total"] = r
                elif any(_t(ws.cell(r, k).value) for k in range(3, 9)):
                    nombre_t = _t(ws.cell(r, 2).value)
                    if nombre_t or not actual["grupos"] or \
                            "fila_total" in actual["grupos"][-1]:
                        actual["grupos"].append({
                            "nombre": nombre_t, "nit": ws.cell(r, 1).value,
                            "docs": []})
                    actual["grupos"][-1]["docs"].append(
                        fila_datos(r, actual["tipo"]))
        r += 1
    # Saldos proyectados por semana y cuenta (fila TOTAL SALDO DISPONIBLE).
    saldos = {}
    if saldo_fila:
        for i, s in enumerate(semanas):
            for j in (0, 1):
                saldos[(i, j)] = round(val(f"{letras[s['col'] + j]}"
                                           f"{saldo_fila}"), 2)
    bols = {}
    if bolsillos:
        for i, s in enumerate(semanas):
            for j in (0, 1):
                v = ws.cell(bolsillos, s["col"] + j).value
                if v not in (None, ""):
                    bols[j] = round(val(f"{letras[s['col'] + j]}{bolsillos}"),
                                    2)
    inicial = {j: round(val(f"{letras[col0 + j]}{fila_tit - 2}"), 2)
               for j in (0, 1)}
    return {"nombre": nombre, "fecha": fecha, "semanas": semanas,
            "cuentas": cuentas, "secciones": secciones, "saldos": saldos,
            "saldo_inicial": inicial, "bolsillos": bols,
            "fila_tit": fila_tit, "col0": col0, "col_obs": col_obs,
            "hoja": ws.title, "empresa": _t(ws.cell(1, 1).value)}


# ------------------------------------------------------------
# Informes de anticipos de HELISA
# ------------------------------------------------------------
def leer_anticipos_helisa(contenido):
    from gmya.comun.grilla import leer_grilla
    filas = leer_grilla(contenido)[0]
    cab, mapa = None, {}
    for k, f in enumerate(filas[:15]):
        cel = {c["col"]: comparable(_t(c["valor"])) for c in f["celdas"]}
        if "DOCUMENTO" in cel.values() and any(
                v.startswith("VR.POR APLICAR") or v.startswith("VR POR")
                for v in cel.values()):
            cab = k
            for col, t in cel.items():
                mapa[t] = col
            break
    if cab is None:
        raise ValueError("No parece el informe de anticipos de HELISA (no se "
                         "encontraron las columnas DOCUMENTO y VR.POR "
                         "APLICAR).")

    def col(*nombres):
        for t, c in mapa.items():
            if any(t.startswith(n) for n in nombres):
                return c
        return None
    c = {"fecha": col("FECHA"), "doc": col("DOCUMENTO"), "nit": col("IDENTIDAD"),
         "tercero": col("BENEFICIARIO", "TERCERO"), "concepto": col("CONCEPTO"),
         "cuenta": col("CUENTA"), "anticipo": col("VR.ANTICIPO", "VR ANTICIPO"),
         "aplicado": col("VR.APLICADO", "VR APLICADO"),
         "por_aplicar": col("VR.POR APLICAR", "VR POR APLICAR")}
    docs, total = [], None
    for f in filas[cab + 1:]:
        cel = {x["col"]: x["valor"] for x in f["celdas"]}
        if not _t(cel.get(c["doc"])):
            if any(isinstance(cel.get(c[k]), (int, float))
                   for k in ("anticipo", "por_aplicar")):
                total = {k: _n(cel.get(c[k])) for k in
                         ("anticipo", "aplicado", "por_aplicar")}
            continue
        docs.append({
            "fecha": _fecha(cel.get(c["fecha"])),
            "documento": _t(cel.get(c["doc"])),
            "doc": doc_corto(cel.get(c["doc"])),
            "clave": clave_doc(cel.get(c["doc"])),
            "nit": re.sub(r"\D", "", _t(cel.get(c["nit"]))).lstrip("0"),
            "tercero": _t(cel.get(c["tercero"])),
            "concepto": _t(cel.get(c["concepto"])),
            "cuenta": _t(cel.get(c["cuenta"])),
            "anticipo": _n(cel.get(c["anticipo"])),
            "aplicado": _n(cel.get(c["aplicado"])),
            "por_aplicar": _n(cel.get(c["por_aplicar"]))})
    cuentas = {d["cuenta"][:4] for d in docs}
    clase = "recibidos" if cuentas & {"2805", "2815"} or any(
        c.startswith("28") for c in cuentas) else "realizados"
    suma = round(sum(d["por_aplicar"] for d in docs), 2)
    return {"clase": clase, "docs": docs, "total": total or {
        "por_aplicar": suma}, "suma_por_aplicar": suma}


# ------------------------------------------------------------
# Lectura de la relacion de anticipos anterior
# ------------------------------------------------------------
def leer_relacion_anticipos(contenido, nombre=""):
    wb, ws, wsv = _abrir(contenido)
    val = _evaluador(ws, wsv)
    secciones, actual, grupo = [], None, None
    for r in range(1, ws.max_row + 1):
        b = comparable(_t(ws.cell(r, 2).value))
        d = comparable(_t(ws.cell(r, 4).value))
        if b.startswith("ANTICIPOS REALIZADOS") or b.startswith(
                "ANTICIPOS RECIBIDOS"):
            actual = {"clase": "realizados" if "REALIZADOS" in b
                      else "recibidos", "titulo": ws.cell(r, 2).value,
                      "fila_titulo": r, "grupos": []}
            secciones.append(actual)
            grupo = None
            continue
        if not actual:
            continue
        if b == "NIT":
            actual["fila_cab"] = r
            continue
        if b.startswith("TOTAL ANTICIPOS"):
            actual["total"] = ws.cell(r, 2).value
            actual["fila_total"] = r
            actual = None
            continue
        if d == "TOTAL":
            if grupo:
                grupo["fila_total"] = r
            grupo = None
            continue
        if not any(_t(ws.cell(r, k).value) for k in range(4, 8)):
            continue
        if grupo is None or _t(ws.cell(r, 3).value):
            grupo = {"nit": re.sub(r"\D", "", _t(ws.cell(r, 2).value))
                     .lstrip("0"), "nit_texto": ws.cell(r, 2).value,
                     "nombre": _t(ws.cell(r, 3).value), "filas": []}
            actual["grupos"].append(grupo)
        grupo["filas"].append({
            "fila": r, "doc": _t(ws.cell(r, 4).value),
            "clave": clave_doc(ws.cell(r, 4).value) if _t(ws.cell(r, 4).value)
            else None,
            "concepto": _t(ws.cell(r, 5).value), "fecha_raw": ws.cell(r, 6).value,
            "fecha": _fecha(ws.cell(r, 6).value),
            "g_raw": ws.cell(r, 7).value, "g": round(val(f"G{r}"), 2),
            "h": round(val(f"H{r}"), 2), "i": round(val(f"I{r}"), 2),
            "obs": ws.cell(r, 10).value})
    if not secciones:
        raise ValueError("No parece la relación de anticipos (no se "
                         "encontraron ANTICIPOS REALIZADOS / RECIBIDOS).")
    m = re.search(r"#\s*(\d+)", _t(nombre)) or re.search(r"_(\d+)\b",
                                                          _t(nombre))
    return {"nombre": nombre, "secciones": secciones, "hoja": ws.title,
            "empresa": _t(ws.cell(1, 2).value),
            "numero": int(m.group(1)) if m else None}


# ------------------------------------------------------------
# Relacion de anticipos nueva
# ------------------------------------------------------------
def _agrupar_por_mes(docs, config):
    """BOLD (comisiones): un renglon por mes con la suma del mes."""
    por_mes = config.get("anticipos_por_mes", {})
    salida, meses = [], {}
    for d in docs:
        plantilla = por_mes.get(d["nit"])
        if not plantilla or not d["fecha"]:
            salida.append(d)
            continue
        k = (d["nit"], d["fecha"].year, d["fecha"].month)
        if k not in meses:
            meses[k] = dict(d, doc="", clave=None, mensual=True, partes=[],
                            concepto=plantilla.format(
                                mes=MESES_PP[d["fecha"].month - 1],
                                anio=d["fecha"].year),
                            anticipo=0.0, aplicado=0.0, por_aplicar=0.0)
            salida.append(meses[k])
        m = meses[k]
        m["partes"].append(d)
        m["fecha"] = min(m["fecha"], d["fecha"])
        for c in ("anticipo", "aplicado", "por_aplicar"):
            m[c] = round(m[c] + d[c], 2)
    return salida


def armar_relacion_anticipos(anterior, realizados, recibidos, config=None):
    config = config or config_empresa_b()
    alertas, modelo = [], []
    resumen = {}
    for sec in anterior["secciones"]:
        helisa = realizados if sec["clase"] == "realizados" else recibidos
        if helisa is None:
            alertas.append(f"No se cargó el informe de anticipos "
                           f"{sec['clase']} de HELISA: la sección queda igual.")
            modelo.append(copy.deepcopy(sec))
            continue
        pend = [d for d in helisa["docs"] if abs(d["por_aplicar"]) >= 0.005]
        items = _agrupar_por_mes(pend, config)
        usados = set()
        grupos = []
        for g in sec["grupos"]:
            ng = {"nit": g["nit"], "nit_texto": g["nit_texto"],
                  "nombre": g["nombre"], "filas": [], "nits_helisa": set()}
            for f in g["filas"]:
                m = None
                for k, it in enumerate(items):
                    if k in usados:
                        continue
                    if f["clave"] and it.get("clave") and \
                            f["clave"] == it["clave"]:
                        m = k
                        break
                if m is None:
                    for k, it in enumerate(items):
                        if k in usados:
                            continue
                        mismo_nit = not g["nit"] or it["nit"] == g["nit"] or \
                            mismo_tercero(it["tercero"], g["nombre"])
                        if it.get("mensual") and mismo_nit and f["fecha"] and \
                                (f["fecha"].year, f["fecha"].month) == \
                                (it["fecha"].year, it["fecha"].month):
                            m = k
                            break
                        if not it.get("mensual") and not f["clave"] and \
                                mismo_nit and abs(it["anticipo"] - f["g"]) < \
                                .005 and (not f["fecha"] or not it["fecha"] or
                                          f["fecha"] == it["fecha"]):
                            m = k
                            break
                if m is None:
                    alertas.append(
                        f"Sale de la relación ({sec['clase']}): "
                        f"{g['nombre'] or g['nit']} · {f['doc'] or f['concepto']}"
                        f" · {f['g']:,.2f}: ya no está por aplicar en HELISA "
                        "(legalizado o cruzado).")
                    continue
                usados.add(m)
                it = items[m]
                ng["nits_helisa"].add(it["nit"])
                g_raw = f["g_raw"] if abs(f["g"] - it["anticipo"]) < .005 \
                    else it["anticipo"]
                if abs(f["g"] - it["anticipo"]) >= .005:
                    alertas.append(
                        f"{g['nombre']} · {it['concepto'] or it['doc']}: valor "
                        f"del anticipo actualizado de {f['g']:,.2f} a "
                        f"{it['anticipo']:,.2f} (HELISA).")
                ng["filas"].append(dict(f, g_raw=g_raw, g=it["anticipo"],
                                        h=it["aplicado"], nuevo=False,
                                        por_aplicar=it["por_aplicar"]))
            grupos.append(ng)
        # Nuevos: al grupo del mismo tercero (NIT de HELISA) o a uno nuevo.
        for k, it in enumerate(items):
            if k in usados:
                continue
            destino = next((g for g in grupos if it["nit"] in g["nits_helisa"]
                            or (g["nit"] and it["nit"] == g["nit"]
                                and not g["nits_helisa"])), None)
            if destino is None:
                destino = next((g for g in grupos if mismo_tercero(
                    it["tercero"], g["nombre"]) and not (
                        g["nits_helisa"] - {it["nit"]})), None)
            if destino is None:
                destino = {"nit": it["nit"], "nit_texto": int(it["nit"]) if
                           it["nit"].isdigit() else it["nit"],
                           "nombre": it["tercero"], "filas": [],
                           "nits_helisa": {it["nit"]}, "nuevo": True}
                grupos.append(destino)
            destino["nits_helisa"].add(it["nit"])
            destino["filas"].append({
                "doc": it["doc"], "concepto": it["concepto"],
                "fecha": it["fecha"], "fecha_raw": it["fecha"],
                "g_raw": it["anticipo"], "g": it["anticipo"],
                "h": it["aplicado"], "obs": None, "nuevo": True,
                "por_aplicar": it["por_aplicar"]})
        # La observacion del tercero (p. ej. "SALDO EN PLATAFORMA DE ENVIO")
        # pasa al primer anticipo nuevo si todos los anteriores salieron.
        for g, gp in zip(grupos, sec["grupos"]):
            if g["filas"] and not any(not f.get("nuevo") for f in g["filas"]):
                obs = next((f["obs"] for f in reversed(gp["filas"])
                            if _t(f.get("obs"))), None)
                if obs:
                    g["filas"][0]["obs"] = obs
        grupos = [g for g in grupos if g["filas"]]
        total = round(sum(f["g"] - f["h"] for g in grupos
                          for f in g["filas"]), 2)
        esperado = round(helisa["suma_por_aplicar"], 2)
        if abs(total - esperado) >= .005:
            alertas.append(f"Anticipos {sec['clase']}: la relación suma "
                           f"{total:,.2f} y HELISA {esperado:,.2f} por "
                           "aplicar: revisar.")
        resumen[sec["clase"]] = {"total": total, "helisa": esperado,
                                 "nuevos": sum(1 for g in grupos for f in
                                               g["filas"] if f.get("nuevo")),
                                 "grupos": len(grupos)}
        modelo.append(dict(sec, grupos=grupos))
    return {"modelo": modelo, "alertas": alertas, "resumen": resumen,
            "anterior": anterior}


# ------------------------------------------------------------
# Flujo de caja nuevo
# ------------------------------------------------------------
def _mapa_semanas(anterior, nuevas):
    """indice semana anterior -> indice nueva (o None si ya paso)."""
    m = {}
    for i, s in enumerate(anterior["semanas"]):
        m[i] = next((k for k, (a, b) in enumerate(nuevas)
                     if a == s["ini"]), None)
    return m


def _semana_de(fecha, nuevas):
    for k, (a, b) in enumerate(nuevas):
        if a <= fecha <= b:
            return k
    return None


def _correr(proy, mapa):
    """(futuro, pasado): proyecciones corridas a las semanas nuevas y las
    que quedaron en semanas que ya pasaron."""
    fut, pas = {}, {}
    for (i, j), v in proy.items():
        k = mapa.get(i)
        if k is None:
            pas[(i, j)] = v
        else:
            fut[(k, j)] = v
    return fut, pas


def _cuenta_preferida(filas, defecto=0):
    conteo = {}
    for f in filas:
        for (_, j) in f["proy"]:
            conteo[j] = conteo.get(j, 0) + 1
    return max(conteo, key=conteo.get) if conteo else defecto


def _concepto_nuevo(grupo_filas, doc):
    """Concepto de un documento nuevo a partir del ultimo del mismo
    tercero; si dice un mes, se corre al mes del documento."""
    previos = [f for f in grupo_filas if _t(f["celdas"].get("E"))]
    if not previos:
        return ""
    ref = max(previos, key=lambda f: _fecha(f["celdas"].get("F"))
              or datetime.date.min)
    texto = _t(ref["celdas"].get("E"))
    fref = _fecha(ref["celdas"].get("F"))
    if tiene_mes(texto) and fref and doc["fecha"]:
        meses = (doc["fecha"].year - fref.year) * 12 + doc["fecha"].month - \
            fref.month
        if meses > 0:
            texto = correr_meses_texto(texto, meses)
    return texto


def _numero_fila(f, tipo):
    c = f["celdas"]
    if tipo == "cxp":
        return _t(c.get("D")) or _t(c.get("C"))
    return _t(c.get("C"))


def _cruzar_grupos(grupos_prev, docs_h, tipo, fecha_ant, nuevas, mapa,
                   config, alertas, semanas_ant=None):
    """Une la cartera / cuentas por pagar anterior con HELISA."""
    def mapa_inv(i):
        if semanas_ant and 0 <= i < len(semanas_ant):
            return (semanas_ant[i]["ini"], semanas_ant[i]["fin"])
        return None
    libres = list(range(len(docs_h)))
    claves = {}
    for k, d in enumerate(docs_h):
        claves.setdefault(clave_doc(d["numero"]), []).append(k)
    resultado, sin_proy = [], []
    # 1) por numero
    asign = {}
    for gi, g in enumerate(grupos_prev):
        for fi, f in enumerate(g["docs"]):
            cand = [k for k in claves.get(clave_doc(_numero_fila(f, tipo)), [])
                    if k in libres]
            if cand:
                asign[(gi, fi)] = cand[0]
                libres.remove(cand[0])
    # Tercero de HELISA de cada grupo (por sus documentos cruzados o nombre)
    tercero_h = {}
    for (gi, fi), k in asign.items():
        tercero_h.setdefault(gi, docs_h[k]["proveedor"])
    for gi, g in enumerate(grupos_prev):
        if gi not in tercero_h:
            cand = {docs_h[k]["proveedor"] for k in libres
                    if mismo_tercero(docs_h[k]["proveedor"], g["nombre"])}
            if len(cand) == 1:
                tercero_h[gi] = cand.pop()
    # 2) mismo tercero + fecha + valor  3) unico pendiente del tercero
    for gi, g in enumerate(grupos_prev):
        th = tercero_h.get(gi)
        if not th:
            continue
        for fi, f in enumerate(g["docs"]):
            if (gi, fi) in asign:
                continue
            fe = _fecha(f["celdas"].get("F"))
            cand = [k for k in libres if docs_h[k]["proveedor"] == th and
                    docs_h[k]["fecha"] == fe and
                    abs(docs_h[k]["valor"] - f["j"]) < .005]
            if len(cand) == 1:
                asign[(gi, fi)] = cand[0]
                libres.remove(cand[0])
        # Unico pendiente de cada lado: es el mismo documento solo si el
        # saldo de HELISA es el mismo, o es el saldo menos lo que se
        # proyecto cobrar / pagar en las semanas que pasaron (abono). Si
        # no, son documentos distintos (uno salio y otro entro).
        pend_prev = [fi for fi in range(len(g["docs"])) if (gi, fi) not in
                     asign]
        pend_h = [k for k in libres if docs_h[k]["proveedor"] == th]
        if len(pend_prev) == 1 and len(pend_h) == 1:
            f = g["docs"][pend_prev[0]]
            d = docs_h[pend_h[0]]
            _, pas = _correr(f["proy"], mapa)
            pasado = round(sum(v for v, _ in pas.values()), 2)
            if abs(d["valor"] - f["j"]) < .005 or (
                    pasado and abs(d["valor"] - (f["j"] - pasado)) < .005):
                asign[(gi, pend_prev[0])] = pend_h[0]
                libres.remove(pend_h[0])
    # Grupos resultantes
    for gi, g in enumerate(grupos_prev):
        ng = {"nombre": g["nombre"], "nit": g["nit"], "docs": [],
              "tercero_h": tercero_h.get(gi), "previos": g["docs"]}
        for fi, f in enumerate(g["docs"]):
            numero = _numero_fila(f, tipo)
            if (gi, fi) not in asign:
                fut, _ = _correr(f["proy"], mapa)
                alertas.append(
                    f"Sale ({'cartera' if tipo == 'cxc' else 'por pagar'}): "
                    f"{g['nombre']} · {numero} · saldo {f['j']:,.2f}: ya no "
                    "está pendiente en HELISA (pagado o cruzado)"
                    + (" — estaba proyectado a futuro." if fut else "."))
                continue
            d = docs_h[asign[(gi, fi)]]
            fut, pas = _correr(f["proy"], mapa)
            nf = dict(f, proy=fut, helisa=d, nuevo=False, abono_nuevo=None)
            if clave_doc(numero) != clave_doc(d["numero"]):
                alertas.append(f"{g['nombre']} · {numero}: en HELISA figura "
                               f"como {d['numero'].strip()} (se deja el "
                               "número del flujo).")
            if abs(d["valor"] - f["j"]) >= .005:
                nuevo_i = round(f["h"] - d["valor"], 2)
                alertas.append(
                    f"{g['nombre']} · {numero}: saldo {f['j']:,.2f} → "
                    f"{d['valor']:,.2f} en HELISA; abonos = {nuevo_i:,.2f}.")
                nf["abono_nuevo"] = nuevo_i
                nf["proy"] = {}
            if pas and not fut:
                sin_proy.append((g["nombre"], numero, pas))
                if abs(d["valor"] - f["j"]) < .005 and not _t(f.get("obs")):
                    semanas_pas = sorted({i for i, _ in pas})
                    s0 = mapa_inv(semanas_pas[0])
                    nf["obs"] = ("SIGUE PENDIENTE EN HELISA: SE PROYECTÓ EN "
                                 + (etiqueta_semana(*s0) if s0 else
                                    "UNA SEMANA ANTERIOR"))
                if abs(d["valor"] - f["j"]) < .005:
                    alertas.append(
                        f"{g['nombre']} · {numero}: estaba proyectado en una "
                        "semana que ya pasó y sigue pendiente en HELISA por "
                        f"{d['valor']:,.2f}: confirmar el pago (queda sin "
                        "semana).")
            ng["docs"].append(nf)
        resultado.append(ng)
    # Documentos nuevos de HELISA
    fuera = [comparable(x) for x in config.get("terceros_fuera", [])]
    limite = (fecha_ant or nuevas[0][0]) - datetime.timedelta(
        days=config.get("dias_tercero_nuevo", 7))
    nuevos_terceros, excluidos = {}, {}
    for k in libres:
        d = docs_h[k]
        g = next((x for x in resultado if x["tercero_h"] == d["proveedor"]),
                 None) or next((x for x in resultado if mismo_tercero(
                     d["proveedor"], x["nombre"])), None)
        if g is None:
            if any(comparable(d["proveedor"]).startswith(x) or
                   mismo_tercero(d["proveedor"], x) for x in fuera):
                excluidos.setdefault(d["proveedor"], []).append(d)
                continue
            nuevos_terceros.setdefault(d["proveedor"], []).append(d)
            continue
        g["docs"].append(_fila_nueva(d, g, tipo, nuevas, resultado))
    for t, docs in nuevos_terceros.items():
        recientes = [d for d in docs if d["fecha"] and d["fecha"] >= limite]
        if not recientes:
            excluidos.setdefault(t, []).extend(docs)
            continue
        g = {"nombre": t, "nit": None, "docs": [], "tercero_h": t,
             "nuevo": True}
        for d in docs:
            g["docs"].append(_fila_nueva(d, g, tipo, nuevas, resultado))
        resultado.append(g)
        alertas.append(f"Tercero nuevo: {t} ({len(docs)} documento(s)): "
                       "falta el NIT y el concepto.")
    for t, docs in excluidos.items():
        alertas.append(
            f"No se incluye {t}: {len(docs)} documento(s) por "
            f"{sum(d['valor'] for d in docs):,.2f} en HELISA "
            + ("(configurado fuera del flujo: socios / pagos fijos)."
               if any(mismo_tercero(t, x) for x in config.get(
                   "terceros_fuera", [])) else
               "(no estaba en el flujo anterior y sus documentos son "
               "anteriores: se asume que se dejó por fuera a propósito)."))
    resultado.sort(key=lambda g: nombre_clave(g["nombre"]))
    return resultado, excluidos, sin_proy


def _fila_nueva(d, g, tipo, nuevas, resultado):
    cuenta = _cuenta_preferida(g["docs"], 0)
    k = None
    if d["vence"]:
        k = 0 if d["vence"] <= nuevas[0][1] else _semana_de(d["vence"],
                                                           nuevas)
    elif d["fecha"] and d["fecha"] <= nuevas[-1][1]:
        k = 0
    concepto = _concepto_nuevo(g.get("previos") or g["docs"], d)
    corto = doc_corto(d["numero"])
    return {"tipo": tipo, "nuevo": True, "helisa": d, "abono_nuevo": None,
            "celdas": {"C": (d.get("tipo") or "") if tipo == "cxp" else corto,
                       "D": corto if tipo == "cxp" else None,
                       "E": concepto, "F": d["fecha"] or d.get("fecha_texto"),
                       "G": d["vence"] or d.get("vence_texto"), "H": d["valor"],
                       "I": None},
            "h": d["valor"], "i": 0.0, "j": d["valor"],
            "proy": {(k, cuenta): (d["valor"], True)} if k is not None else {},
            "obs": None, "obs2": None, "sin_concepto": not concepto}


def saldo_inicial_propuesto(anterior, fecha):
    """Saldo con que arranca el flujo nuevo, por cuenta: el saldo proyectado
    de la ultima semana del flujo anterior que ya paso a la fecha (o el
    saldo inicial del anterior si ninguna paso)."""
    nuevas = semanas_desde(fecha, 1)
    pasadas = [i for i, s in enumerate(anterior["semanas"])
               if s["fin"] < nuevas[0][0]]
    if pasadas:
        return {j: anterior["saldos"].get((pasadas[-1], j), 0.0)
                for j in (0, 1)}
    return dict(anterior["saldo_inicial"])


def armar_flujo_empresa_b(anterior, cxc, cxp, fecha, semanas=4, saldos=None,
                     config=None):
    config = config or config_empresa_b()
    alertas = []
    nuevas = semanas_desde(fecha, semanas)
    mapa = _mapa_semanas(anterior, nuevas)
    pasadas = [i for i, s in enumerate(anterior["semanas"])
               if s["fin"] < nuevas[0][0]]
    # Saldo inicial: saldo proyectado de la ultima semana que paso.
    if pasadas:
        ult = pasadas[-1]
        inicial = {j: anterior["saldos"].get((ult, j), 0.0) for j in (0, 1)}
    else:
        inicial = dict(anterior["saldo_inicial"])
    if saldos:
        for j, v in saldos.items():
            if v is not None:
                inicial[j] = round(float(v), 2)
    secciones = []
    nuevos, cruces = [], {}
    for sec in anterior["secciones"]:
        if sec["tipo"] == "ingresos":
            filas = []
            for f in sec["filas"]:
                fut, pas = _correr(f["proy"], mapa)
                if pas and not fut:
                    filas.append({"vacia": True})
                    alertas.append(
                        f"Ingreso de semanas pasadas que se limpia: "
                        f"{_t(f['celdas'].get('E')) or _t(f['celdas'].get('D'))}"
                        f" ({sum(v for v, _ in pas.values()):,.2f}).")
                else:
                    filas.append(dict(f, proy=fut))
            secciones.append(dict(sec, filas=filas))
        elif sec["tipo"] in ("cxc", "cxp"):
            helisa = cxc if sec["tipo"] == "cxc" else cxp
            if helisa is None:
                alertas.append("No se cargó el listado de HELISA de "
                               f"{'cartera' if sec['tipo'] == 'cxc' else 'cuentas por pagar'}"
                               ": la sección se corre sin cruzar.")
                grupos = [dict(g, docs=[dict(f, proy=_correr(f["proy"],
                                                            mapa)[0])
                                        for f in g["docs"]]) for g in
                          sec["grupos"]]
                excl, sin = {}, []
            else:
                grupos, excl, sin = _cruzar_grupos(
                    sec["grupos"], helisa["documentos"], sec["tipo"],
                    anterior["fecha"], nuevas, mapa, config, alertas,
                    anterior["semanas"])
            cruces[sec["tipo"]] = {"excluidos": excl, "sin_semana": sin}
            for g in grupos:
                for f in g["docs"]:
                    if f.get("nuevo"):
                        nuevos.append((sec["tipo"], g, f))
            fijos = []
            for f in sec.get("fijos", []):
                fut, pas = _correr(f["proy"], mapa)
                if pas and not fut:
                    pagado = round(sum(v for v, _ in pas.values()), 2)
                    cuenta = next(iter(pas))[1]
                    c = dict(f["celdas"])
                    c["E"] = correr_meses_texto(c.get("E"), 1)
                    fe = _fecha(c.get("F"))
                    if fe:
                        c["F"] = _sumar_mes(fe)
                    gv = _fecha(c.get("G"))
                    if gv:
                        c["G"] = _sumar_mes(gv)
                    c["H"] = pagado
                    c["I"] = None
                    k = _semana_de(c["F"], nuevas) if isinstance(
                        c.get("F"), datetime.date) else None
                    if k is None and isinstance(c.get("F"), datetime.date) \
                            and c["F"] > nuevas[-1][1]:
                        k = len(nuevas) - 1
                        alertas.append(
                            f"Pago fijo {c['E']}: vence el {c['F']:%d/%m/%Y}, "
                            "después de la última semana; quedó en la última "
                            "semana del flujo.")
                    alertas.append(
                        f"Pago fijo pagado: {_t(f['celdas'].get('E'))} "
                        f"({pagado:,.2f}) → {c['E']}"
                        + (f" con el valor pagado (antes {f['h']:,.2f})"
                           if abs(pagado - f["h"]) >= .005 else "") + ".")
                    fijos.append(dict(f, celdas=c, h=pagado, i=0.0, j=pagado,
                                      proy={(k, cuenta): (pagado, True)}
                                      if k is not None else {},
                                      rodado=True, e_anterior=_t(
                                          f["celdas"].get("E"))))
                else:
                    fijos.append(dict(f, proy=fut))
            _actualizar_hermanos(fijos, alertas)
            secciones.append(dict(sec, grupos=grupos, fijos=fijos))
        elif sec["tipo"] == "anticipos":
            filas = []
            perm = [comparable(x) for x in config.get("filas_permanentes", [])]
            for f in sec["filas"]:
                fut, pas = _correr(f["proy"], mapa)
                texto = comparable(" ".join(_t(f["celdas"].get(x))
                                            for x in "BCDE"))
                if pas and not fut:
                    if any(p in texto for p in perm):
                        filas.append(dict(f, proy={}))
                    else:
                        alertas.append(
                            "Anticipo a realizar de semanas pasadas (sale): "
                            f"{_t(f['celdas'].get('B'))} · "
                            f"{_t(f['celdas'].get('E'))} "
                            f"({sum(v for v, _ in pas.values()):,.2f}).")
                    continue
                filas.append(dict(f, proy=fut))
            secciones.append(dict(sec, filas=filas))
    modelo = {"fecha": fecha, "semanas": nuevas, "cuentas":
              anterior["cuentas"], "inicial": inicial,
              "bolsillos": anterior["bolsillos"], "secciones": secciones,
              "empresa": anterior["empresa"], "hoja": anterior["hoja"]}
    resumen = calcular_totales(modelo)
    return {"modelo": modelo, "alertas": alertas, "nuevos": nuevos,
            "cruces": cruces, "resumen": resumen, "anterior": anterior}


def _base_concepto(texto):
    """'NOMINA 2DA QNA NOVIEMBRE 2026' -> 'NOMINA QNA' (sin mes, año ni
    ordinal) para reconocer pagos fijos del mismo tipo."""
    pal = [p for p in re.split(r"[^A-Z0-9]+", comparable(_t(texto))) if p]
    fuera = set(MESES_PP) | {"1RA", "2DA", "1ER", "2DO", "PRIMERA",
                             "SEGUNDA", "DE", "DEL"}
    return " ".join(p for p in pal if p not in fuera
                    and not re.fullmatch(r"(19|20)\d\d", p))


def _actualizar_hermanos(fijos, alertas):
    """Si un pago fijo se pago por un valor distinto a su provision (p. ej.
    la nomina de la quincena), los demas pendientes del mismo tipo toman
    ese valor (es el ultimo pago real), con aviso."""
    for r in [f for f in fijos if f.get("rodado")]:
        base = (_t(r["celdas"].get("B")), _base_concepto(r["celdas"].get("E")))
        for f in fijos:
            if f is r or f.get("rodado"):
                continue
            if (_t(f["celdas"].get("B")), _base_concepto(
                    f["celdas"].get("E"))) != base or not base[1]:
                continue
            if abs(f["h"] - r["h"]) < .005:
                continue
            alertas.append(f"Pago fijo {_t(f['celdas'].get('E'))}: "
                           f"provisión {f['h']:,.2f} → {r['h']:,.2f} (último "
                           f"valor pagado de {r.get('e_anterior') or _t(r['celdas'].get('E'))}).")
            c = dict(f["celdas"], H=r["h"])
            nuevo_j = round(r["h"] - (f["i"] or 0), 2)
            f["proy"] = {k: ((nuevo_j, True) if es_j else (v, es_j))
                         for k, (v, es_j) in f["proy"].items()}
            f.update(celdas=c, h=r["h"], j=nuevo_j)


def calcular_totales(modelo):
    """Totales por semana y cuenta (lo mismo que calculan las formulas del
    Excel): ingresos, cartera, cuentas por pagar, anticipos y saldo."""
    n = len(modelo["semanas"])
    claves = [(k, j) for k in range(n) for j in (0, 1)]

    def suma(filas):
        out = {c: 0.0 for c in claves}
        for f in filas:
            for c, (v, _) in f.get("proy", {}).items():
                if c in out:
                    out[c] += v
        return out
    ing = {c: 0.0 for c in claves}
    cxc = cxp = ant = {c: 0.0 for c in claves}
    for sec in modelo["secciones"]:
        if sec["tipo"] == "ingresos":
            s = suma([f for f in sec["filas"] if not f.get("vacia")])
            ing = {c: ing[c] + s[c] for c in claves}
        elif sec["tipo"] == "cxc":
            cxc = suma([f for g in sec["grupos"] for f in g["docs"]])
        elif sec["tipo"] == "cxp":
            cxp = suma([f for g in sec["grupos"] for f in g["docs"]]
                       + sec["fijos"])
        elif sec["tipo"] == "anticipos":
            ant = suma(sec["filas"])
    saldo, inicial = {}, {}
    for k in range(n):
        for j in (0, 1):
            ini = modelo["inicial"][j] if k == 0 else saldo[(k - 1, j)]
            inicial[(k, j)] = round(ini, 2)
            saldo[(k, j)] = round(ini + ing[(k, j)] + cxc[(k, j)]
                                  - cxp[(k, j)] - ant[(k, j)], 2)
    return {"ingresos": ing, "cxc": cxc, "cxp": cxp, "anticipos": ant,
            "inicial": inicial, "saldo": saldo}


def nombre_flujo(nombre_anterior, fecha):
    base = re.sub(r"\.(xlsx|xlsm|xls)$", "", _t(nombre_anterior),
                  flags=re.I)
    if re.search(r"V\s*\d{8}", base):
        base = re.sub(r"V\s*\d{8}", f"V{fecha:%d%m%Y}", base)
    else:
        base = f"FLUJO DE CAJA V{fecha:%d%m%Y} EMPRESA B S.A.S."
    return base.replace("_", " ").replace("  ", " ").strip() + ".xlsx"


def nombre_relacion(nombre_anterior, numero):
    base = re.sub(r"\.(xlsx|xlsm|xls)$", "", _t(nombre_anterior), flags=re.I)
    n = (numero or 0) + 1
    if re.search(r"#\s*\d+", base):
        base = re.sub(r"#\s*\d+", f"#{n}", base)
    else:
        base = re.sub(r"[_ ]\d+$", "", base).replace("_", " ").strip() + \
            f" #{n}"
    return base + ".xlsx"


# ------------------------------------------------------------
# Excel: se reconstruye la hoja dentro del MISMO libro anterior, copiando
# el estilo de sus propias filas (titulos, documentos, totales...), asi el
# formato de la firma queda igual.
# ------------------------------------------------------------
AMARILLO = "FFFFFF00"


def _copiar_estilo(origen, destino):
    if origen.has_style:
        destino._style = copy.copy(origen._style)


def _hoja_nueva(wb, ws_old):
    ws = wb.create_sheet(ws_old.title + "_n")
    for k, dim in ws_old.column_dimensions.items():
        ws.column_dimensions[k].width = dim.width
        ws.column_dimensions[k].hidden = dim.hidden
    ws.sheet_view.zoomScale = ws_old.sheet_view.zoomScale
    ws.sheet_view.showGridLines = ws_old.sheet_view.showGridLines
    ws.freeze_panes = ws_old.freeze_panes
    ws.page_setup.orientation = ws_old.page_setup.orientation
    ws.page_setup.fitToWidth = ws_old.page_setup.fitToWidth
    ws.sheet_properties.pageSetUpPr = copy.copy(
        ws_old.sheet_properties.pageSetUpPr)
    return ws


def _cerrar_hoja(wb, ws_old, ws):
    titulo = ws_old.title
    idx = wb.sheetnames.index(titulo)
    wb.remove(ws_old)
    ws.title = titulo
    wb.move_sheet(ws, offset=idx - wb.sheetnames.index(titulo))
    wb.active = wb.sheetnames.index(titulo)


def _fila_por_etiqueta(ws, texto, col=1, desde=1):
    for r in range(desde, ws.max_row + 1):
        if comparable(_t(ws.cell(r, col).value)).startswith(comparable(texto)):
            return r
    return None


def excel_flujo_empresa_b(resultado, contenido_anterior):
    from openpyxl import load_workbook
    from openpyxl.formula.translate import Translator
    from openpyxl.styles import PatternFill
    from openpyxl.utils import get_column_letter as L
    ant = resultado["anterior"]
    mod = resultado["modelo"]
    wb = load_workbook(io.BytesIO(contenido_anterior))
    wo = wb[ant["hoja"]]
    ws = _hoja_nueva(wb, wo)
    n_old, n = len(ant["semanas"]), len(mod["semanas"])
    col0 = ant["col0"]
    obs_old = ant["col_obs"]
    obs = col0 + 2 * n
    ultima_col = obs + 1
    amarillo = PatternFill("solid", fgColor=AMARILLO)

    def col_tpl(c):
        """Columna de la hoja anterior cuyo estilo usa la columna c."""
        if c < col0:
            return c
        if c >= obs:
            return obs_old + (c - obs)
        k, j = divmod(c - col0, 2)
        return col0 + 2 * min(k, n_old - 1) + j
    for c in range(col0, ultima_col + 1):
        w = wo.column_dimensions[L(col_tpl(c))].width
        if w:
            ws.column_dimensions[L(c)].width = w
    estado = {"r": 0}

    sin_relleno = PatternFill(fill_type=None)

    def fila(tpl, valores=None, alto=True, datos=False, tpl_ab=None):
        estado["r"] += 1
        r = estado["r"]
        for c in range(1, ultima_col + 1):
            origen = tpl_ab if (tpl_ab and c <= 2) else tpl
            _copiar_estilo(wo.cell(origen, col_tpl(c)), ws.cell(r, c))
            if datos and col0 <= c < obs:
                # Las marcas de color de las semanas eran de la semana
                # anterior: no se arrastran.
                ws.cell(r, c).fill = sin_relleno
        if alto and wo.row_dimensions[tpl].height:
            ws.row_dimensions[r].height = wo.row_dimensions[tpl].height
        for c, v in (valores or {}).items():
            ws.cell(r, c if isinstance(c, int) else
                    __import__("openpyxl").utils.column_index_from_string(c),
                    v)
        return r

    def semanas_cols():
        return [(k, j, col0 + 2 * k + j) for k in range(n) for j in (0, 1)]

    # --- Encabezado (filas 1 a 5) ---
    ft = ant["fila_tit"]
    for r0 in range(1, ft + 1):
        r = fila(r0)
        for c in range(1, col0):
            ws.cell(r, c, wo.cell(r0, c).value)
    for rng in wo.merged_cells.ranges:
        if rng.max_row <= ft and rng.max_col < col0:
            ws.merge_cells(str(rng))
    # meses (fila 1), cuentas (2), saldo inicial (3), SEMANA n (4), fechas (5)
    meses = {}
    for k, (a, b) in enumerate(mod["semanas"]):
        meses.setdefault(mes_semana(a, b), []).append(k)
    for mes, ks in meses.items():
        c1, c2 = col0 + 2 * ks[0], col0 + 2 * ks[-1] + 1
        for c in range(c1, c2 + 1):
            _copiar_estilo(wo.cell(1, col0), ws.cell(1, c))
        ws.cell(1, c1, MESES_PP[mes - 1])
        ws.merge_cells(start_row=1, start_column=c1, end_row=1, end_column=c2)
    fila_saldo = {}

    for k, j, c in semanas_cols():
        ws.cell(ft - 3, c, mod["cuentas"][j])
        if k == 0:
            ws.cell(ft - 2, c, mod["inicial"][j])
        a, b = mod["semanas"][k]
        if j == 0:
            ws.cell(ft - 1, c, f"SEMANA {numero_semana(a, b)}")
            ws.cell(ft, c, etiqueta_semana(a, b))
            ws.merge_cells(start_row=ft - 1, start_column=c, end_row=ft - 1,
                           end_column=c + 1)
            ws.merge_cells(start_row=ft, start_column=c, end_row=ft,
                           end_column=c + 1)

    def semana_valores(r, f):
        for (k, j), (v, es_j) in f.get("proy", {}).items():
            if k is None or k >= n:
                continue
            ws.cell(r, col0 + 2 * k + j, f"=+J{r}" if es_j else v)

    def total_cols(r, formula):
        for _, _, c in semanas_cols():
            ws.cell(r, c, formula(L(c)))

    def merge(r1, c1, r2, c2):
        if (r1, c1) != (r2, c2):
            ws.merge_cells(start_row=r1, start_column=c1, end_row=r2,
                           end_column=c2)

    def traducir(valor, r_old, r_new, letra):
        if isinstance(valor, str) and valor.startswith("="):
            try:
                return Translator(valor, origin=f"{letra}{r_old}") \
                    .translate_formula(f"{letra}{r_new}")
            except Exception:
                return valor
        return valor

    totales_ing = []
    filas_ref = {}
    secs = mod["secciones"]
    for si, sec in enumerate(secs):
        if sec["tipo"] == "ingresos":
            r = fila(sec["fila_titulo"], {1: sec["titulo"]})
            merge(r, 1, r, 10)
            tpl_f = sec["filas"][0]["fila"] if sec["filas"] and \
                sec["filas"][0].get("fila") else sec["fila_titulo"] + 1
            primera = estado["r"] + 1
            for f in sec["filas"]:
                if f.get("vacia"):
                    fila(tpl_f, datos=True)
                    continue
                vals = {k2: v for k2, v in f["celdas"].items()
                        if k2 in ("D", "E") and v not in (None, "")}
                rr = fila(f.get("fila") or tpl_f, vals, datos=True)
                semana_valores(rr, f)
                if f.get("obs"):
                    ws.cell(rr, obs, f["obs"])
            ultima = estado["r"]
            r = fila(sec["fila_total"], {1: sec["total"]})
            merge(r, 1, r, 10)
            total_cols(r, lambda x: f"=SUM({x}{primera}:{x}{max(ultima, primera)})")
            totales_ing.append(r)
            siguiente = secs[si + 1]["tipo"] if si + 1 < len(secs) else None
            if siguiente != "ingresos":
                tpl = _fila_por_etiqueta(wo, "TOTAL INGRESOS")
                r = fila(tpl, {1: wo.cell(tpl, 1).value})
                merge(r, 1, r, 10)
                orden = totales_ing[1:2] + totales_ing[:1] + totales_ing[2:]
                total_cols(r, lambda x: "=+" + "+".join(f"{x}{t}" for t in
                                                        orden))
                filas_ref["ingresos"] = r
        elif sec["tipo"] in ("cxc", "cxp"):
            r = fila(sec["fila_titulo"], {1: sec["titulo"]})
            merge(r, 1, r, 10)
            cab = fila(sec["fila_cab"])
            for c in range(1, 11):
                ws.cell(cab, c, wo.cell(sec["fila_cab"], c).value)
            for rng in wo.merged_cells.ranges:
                if rng.min_row == rng.max_row == sec["fila_cab"]:
                    merge(cab, rng.min_col, cab, rng.max_col)
            plant = [g for g in ant_grupos(ant, sec["tipo"])]
            tpl_primera = plant[0]["docs"][0]["fila"]
            tpl_cont = next((g["docs"][1]["fila"] for g in plant
                             if len(g["docs"]) > 1), tpl_primera)
            tpl_total = next((g["fila_total"] for g in plant
                              if g.get("fila_total")), tpl_primera + 1)
            for g in sec["grupos"]:
                if not g["docs"]:
                    continue
                inicio = estado["r"] + 1
                for di, f in enumerate(g["docs"]):
                    tpl = f.get("fila") or (tpl_primera if di == 0 else
                                            tpl_cont)
                    rr = fila(tpl, datos=True,
                              tpl_ab=tpl_primera if di == 0 else None)
                    cel = f["celdas"]
                    if di == 0:
                        ws.cell(rr, 1, g["nit"])
                        ws.cell(rr, 2, g["nombre"])
                        if not g["nit"]:
                            ws.cell(rr, 1).fill = amarillo
                    for letra in "CDEFGH":
                        v = cel.get(letra)
                        if v not in (None, ""):
                            ws[f"{letra}{rr}"] = traducir(v, f.get("fila", rr),
                                                          rr, letra)
                    if f.get("abono_nuevo") is not None:
                        ws[f"I{rr}"] = f["abono_nuevo"]
                    elif cel.get("I") not in (None, ""):
                        ws[f"I{rr}"] = traducir(cel["I"], f.get("fila", rr),
                                                rr, "I")
                    cambia = f.get("nuevo") or f.get("abono_nuevo") is not \
                        None
                    jv = cel.get("J")
                    if cambia or jv in (None, ""):
                        ws[f"J{rr}"] = f"=+H{rr}-I{rr}"
                    else:
                        ws[f"J{rr}"] = traducir(jv, f["fila"], rr, "J")
                    if f.get("nuevo") and not _t(cel.get("E")):
                        ws[f"E{rr}"].fill = amarillo
                    semana_valores(rr, f)
                    if f.get("obs") not in (None, ""):
                        ws.cell(rr, obs, traducir(f["obs"], f.get("fila", rr),
                                                  rr, L(obs)))
                    if f.get("obs2") not in (None, ""):
                        ws.cell(rr, obs + 1, f["obs2"])
                    if sec["tipo"] == "cxc":
                        merge(rr, 3, rr, 4)
                fin = estado["r"]
                rt = fila(tpl_total, {3: "TOTAL"})
                ws[f"J{rt}"] = f"=SUM(J{inicio}:J{fin})"
                if sec["tipo"] == "cxc":
                    merge(rt, 3, rt, 9)
                merge(inicio, 1, rt, 1)
                merge(inicio, 2, rt, 2)
            ultima_grupo = estado["r"]
            if sec["tipo"] == "cxp" and sec.get("fijos"):
                f_ini = estado["r"] + 1
                tpl_fijo = sec["fijos"][0]["fila"]
                for fi, f in enumerate(sec["fijos"]):
                    rr = fila(f.get("fila") or tpl_fijo, datos=True,
                              tpl_ab=tpl_fijo if fi == 0 else None)
                    if fi == 0:
                        ws.cell(rr, 1, "PAGOS FIJOS")
                    cel = f["celdas"]
                    for letra in "BEFGH":
                        v = cel.get(letra)
                        if v not in (None, ""):
                            ws[f"{letra}{rr}"] = traducir(v, f["fila"], rr,
                                                          letra)
                    if cel.get("I") not in (None, ""):
                        ws[f"I{rr}"] = traducir(cel["I"], f["fila"], rr, "I")
                    cambia = f.get("rodado") or abs(
                        f["h"] - (_n(cel.get("H")) if not isinstance(
                            cel.get("H"), str) else f["h"])) >= .005
                    jv = cel.get("J")
                    ws[f"J{rr}"] = f"=+H{rr}-I{rr}" if (cambia or jv in (
                        None, "") or f.get("rodado")) else traducir(
                        jv, f["fila"], rr, "J")
                    semana_valores(rr, f)
                    if f.get("obs") not in (None, ""):
                        ws.cell(rr, obs, f["obs"])
                    merge(rr, 2, rr, 4)
                    if cel.get("G") in (None, ""):
                        merge(rr, 6, rr, 7)
                f_fin = estado["r"]
                merge(f_ini, 1, f_fin, 1)
                rt = fila(sec["fila_total_fijos"], {2: "TOTAL"})
                ws[f"J{rt}"] = f"=SUM(J{f_ini}:J{f_fin})"
                merge(rt, 2, rt, 9)
                ultima_grupo = rt
            r = fila(sec["fila_total"], {1: sec["total"]})
            merge(r, 1, r, 10)
            total_cols(r, lambda x: f"=SUM({x}{cab}:{x}{ultima_grupo})")
            filas_ref[sec["tipo"]] = r
            if sec["tipo"] == "cxc":
                tpl = _fila_por_etiqueta(wo, "TOTAL PAGOS RECIBIDOS")
                rp = fila(tpl, {1: wo.cell(tpl, 1).value})
                merge(rp, 1, rp, 10)
                total_cols(rp, lambda x: f"=+{x}{r}+{x}"
                           f"{filas_ref.get('ingresos', r)}")
                tpl = _fila_por_etiqueta(wo, "TOTAL DISPONIBLE", desde=tpl)
                rd = fila(tpl, {1: wo.cell(tpl, 1).value})
                merge(rd, 1, rd, 10)
                total_cols(rd, lambda x: f"=+{x}{ft - 2}+{x}{rp}")
                filas_ref["disponible"] = rd
        elif sec["tipo"] == "anticipos":
            r = fila(sec["fila_titulo"], {1: sec["titulo"]})
            merge(r, 1, r, 10)
            inicio = r
            tpl_a = ant_anticipos_tpl(ant)
            for f in sec["filas"]:
                rr = fila(f.get("fila") or tpl_a, datos=True)
                for letra in "BCDE":
                    v = f["celdas"].get(letra)
                    if v not in (None, ""):
                        ws[f"{letra}{rr}"] = v
                semana_valores(rr, f)
                if f.get("obs") not in (None, ""):
                    ws.cell(rr, obs, f["obs"])
                merge(rr, 3, rr, 4)
            fin = estado["r"]
            r = fila(sec["fila_total"], {1: sec["total"]})
            merge(r, 1, r, 10)
            total_cols(r, lambda x: f"=SUM({x}{inicio}:{x}{max(fin, inicio)})")
            tpl = _fila_por_etiqueta(wo, "TOTAL A PAGAR")
            rp = fila(tpl, {1: wo.cell(tpl, 1).value})
            merge(rp, 1, rp, 10)
            total_cols(rp, lambda x: f"=+{x}{filas_ref['cxp']}+{x}{r}")
            tpl = _fila_por_etiqueta(wo, "TOTAL SALDO DISPONIBLE")
            rs = fila(tpl, {1: wo.cell(tpl, 1).value})
            merge(rs, 1, rs, 10)
            total_cols(rs, lambda x: f"={x}{filas_ref['disponible']}-{x}{rp}")
            fila_saldo["r"] = rs
            tpl_b = _fila_por_etiqueta(wo, "DISPONIBL", col=5)
            if tpl_b:
                rb = fila(tpl_b, {5: wo.cell(tpl_b, 5).value})
                for k, j, c in semanas_cols():
                    if j in mod["bolsillos"]:
                        ws.cell(rb, c, mod["bolsillos"][j])
                tpl_p = tpl_b + 1
                rpp = fila(tpl_p)
                merge(rpp, 1, rpp, 10)
                for k in range(n):
                    c = col0 + 2 * k + 1
                    ws.cell(rpp, c, f"=+{L(c - 1)}{rs}+{L(c)}{rs}")
    # Saldo inicial de las semanas siguientes = saldo de la anterior.
    for k, j, c in semanas_cols():
        if k > 0 and fila_saldo.get("r"):
            ws.cell(ft - 2, c, f"=+{L(c - 2)}{fila_saldo['r']}")
    _cerrar_hoja(wb, wo, ws)
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def ant_grupos(ant, tipo):
    for s in ant["secciones"]:
        if s["tipo"] == tipo:
            return [g for g in s["grupos"] if g["docs"]]
    return []


def ant_anticipos_tpl(ant):
    for s in ant["secciones"]:
        if s["tipo"] == "anticipos" and s["filas"]:
            return s["filas"][0]["fila"]
    return 1


def excel_relacion_anticipos(resultado, contenido_anterior):
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill
    ant = resultado["anterior"]
    wb = load_workbook(io.BytesIO(contenido_anterior))
    wo = wb[ant["hoja"]]
    ws = _hoja_nueva(wb, wo)
    ultima_col = max(wo.max_column, 12)
    estado = {"r": 0}
    nuevo_fill = None

    def fila(tpl, valores=None, tpl_bc=None):
        estado["r"] += 1
        r = estado["r"]
        for c in range(1, ultima_col + 1):
            origen = tpl_bc if (tpl_bc and c in (2, 3)) else tpl
            _copiar_estilo(wo.cell(origen, c), ws.cell(r, c))
        if wo.row_dimensions[tpl].height:
            ws.row_dimensions[r].height = wo.row_dimensions[tpl].height
        for c, v in (valores or {}).items():
            ws.cell(r, c, v)
        return r

    def merge(r1, c1, r2, c2):
        if (r1, c1) != (r2, c2):
            ws.merge_cells(start_row=r1, start_column=c1, end_row=r2,
                           end_column=c2)

    def merges_de(tpl):
        return [(m.min_col, m.max_col) for m in wo.merged_cells.ranges
                if m.min_row == m.max_row == tpl]
    secs_prev = {s["clase"]: s for s in ant["secciones"]}

    def copiar_filas(r_ini, r_fin):
        base = estado["r"] + 1 - r_ini
        for r0 in range(r_ini, r_fin + 1):
            r = fila(r0)
            for c in range(1, ultima_col + 1):
                v = wo.cell(r0, c).value
                if v not in (None, ""):
                    ws.cell(r, c, v)
        for m in wo.merged_cells.ranges:
            if m.min_row >= r_ini and m.max_row <= r_fin:
                merge(m.min_row + base, m.min_col, m.max_row + base,
                      m.max_col)
    for si, sec in enumerate(resultado["modelo"]):
        prev = secs_prev[sec["clase"]]
        hasta = prev.get("fila_cab") or prev["fila_titulo"]
        if si == 0:
            copiar_filas(1, hasta)
        else:
            fila(prev["fila_titulo"] - 1)
            copiar_filas(prev["fila_titulo"], hasta)
        gprev = [g for g in prev["grupos"] if g["filas"]]
        tpl_1 = gprev[0]["filas"][0]["fila"] if gprev else prev["fila_titulo"]
        tpl_c = next((g["filas"][1]["fila"] for g in gprev
                      if len(g["filas"]) > 1), tpl_1)
        tpl_t = next((g["fila_total"] for g in gprev if g.get("fila_total")),
                     tpl_1)
        totales = []
        for g in sec["grupos"]:
            ini = estado["r"] + 1
            for fi, f in enumerate(g["filas"]):
                rr = fila(f.get("fila") or (tpl_1 if fi == 0 else tpl_c),
                          tpl_bc=tpl_1 if fi == 0 else None)
                if fi == 0:
                    ws.cell(rr, 2, g["nit_texto"])
                    ws.cell(rr, 3, g["nombre"])
                ws.cell(rr, 4, f.get("doc") or None)
                ws.cell(rr, 5, f["concepto"])
                ws.cell(rr, 6, f.get("fecha_raw") if not f.get("nuevo")
                        else f["fecha"])
                if f.get("nuevo") and f["fecha"]:
                    ws.cell(rr, 6).number_format = "DD/MM/YYYY"
                ws.cell(rr, 7, f["g_raw"])
                if f["h"] or (not f.get("nuevo") and f.get("fila") and
                              wo.cell(f["fila"], 8).value not in (None, "")):
                    ws.cell(rr, 8, f["h"])
                ws.cell(rr, 9, f"=+G{rr}-H{rr}")
                if f.get("obs") not in (None, ""):
                    ws.cell(rr, 10, f["obs"])
            fin = estado["r"]
            rt = fila(tpl_t, {4: "TOTAL"})
            ws.cell(rt, 9, f"=SUM(I{ini}:I{fin})")
            for c1, c2 in merges_de(tpl_t):
                merge(rt, c1, rt, c2)
            merge(ini, 2, rt, 2)
            merge(ini, 3, rt, 3)
            totales.append(rt)
        rt = fila(prev["fila_total"], {2: prev["total"]})
        ws.cell(rt, 9, "=+" + "+".join(f"I{t}" for t in totales) if totales
                else 0)
        for c1, c2 in merges_de(prev["fila_total"]) or [(2, 8)]:
            merge(rt, c1, rt, c2)
    _cerrar_hoja(wb, wo, ws)
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()
