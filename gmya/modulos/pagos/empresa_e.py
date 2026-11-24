"""Programacion de EMPRESA E SAS: cuentas por pagar y por cobrar.

Contrato:
  leer_empresa_e_anterior(contenido, nombre, modo) -> {documentos, manuales,
      anticipos, fecha, titulo, empresa}: la programacion anterior de EMPRESA E
      («RELACION DE FACTURAS PENDIENTES POR PAGAR / COBRAR AL ...»), con
      NIT, tercero, tipo, numero, concepto, fechas, valor inicial, saldo y
      observaciones; secciones manuales (IMPUESTOS, SEGURIDAD SOCIAL) y
      anticipos.
  armar_empresa_e(helisa, anterior, fecha, modo, marcar_vencidas) -> partidas:
      todo lo pendiente en el listado de HELISA (leer_cxp_helisa) con el
      saldo de HELISA; NIT, concepto, valor inicial y observacion pasan de la
      anterior; lo que ya no esta en HELISA sale (pagado).
  generar_excel_empresa_e(partidas, ctx) -> bytes con el formato de EMPRESA E.
REGLAS: no se inventa nada: un documento nuevo queda sin concepto ni valor
inicial (se marcan para completarlos) y se avisa.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.planillas.logica,
gmya.modulos.pagos.lectura, gmya.modulos.pagos.empresa_d
"""

import datetime
import io
import re
from collections import OrderedDict, defaultdict

from gmya.comun.texto import alfanumerico, comparable
from gmya.comun.numeros import formato_cop, numero
from gmya.modulos.planillas.logica import nombre_seguro
from gmya.modulos.pagos.lectura import abrir_libro_anterior, MESES_PP, _texto
from gmya.modulos.pagos.empresa_d import (
    _fecha_en_texto, fecha_abreviada, RE_DOC_HELISA, tipo_doc_cxp,
)


def _fecha(v):
    """date, o None; acepta fecha de Excel, dd/mm/aaaa, aaaa/mm/dd y
    dd/MMM/aaaa."""
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    t = _texto(v)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        try:
            return datetime.date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", t)
    if m:
        try:
            return datetime.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return fecha_abreviada(t) if t else None


def numero_corto(numero_doc):
    """'FC  00000FE-7127' / '00000FE-7127' / 'FE-7127' -> 'FE7127'."""
    t = str(numero_doc or "").strip().upper()
    partes = t.split(None, 1)
    if len(partes) == 2 and re.fullmatch(r"[A-Z]{1,6}", partes[0]):
        t = partes[1]
    return alfanumerico(t).lstrip("0")


# ------------------------------------------------------------
# Lectura de la programacion anterior de EMPRESA E
# ------------------------------------------------------------
def leer_empresa_e_anterior(contenido, nombre_archivo="", modo="pagar"):
    libro = abrir_libro_anterior(contenido)
    hoja = next(iter(libro["hojas"]))
    filas = libro["hojas"][hoja]
    titulo_i = None
    for i, f in enumerate(filas[:15]):
        t = [comparable(_texto(v)) for v in f]
        if any(x.startswith("NUMERO") for x in t) and \
                any("SALDO" in x for x in t):
            titulo_i = i
            break
    if titulo_i is None:
        raise ValueError("No se encontró la fila de títulos (NUMERO, SALDO) "
                         "en la programación anterior de EMPRESA E.")
    cab = [comparable(_texto(v)).replace("\n", " ") for v in filas[titulo_i]]

    def col(*pref, despues=-1):
        for j, t in enumerate(cab):
            if j > despues and any(t.startswith(p) for p in pref):
                return j
        return None
    c_num = col("NUMERO")
    c_tipo = col("TIPO")
    if c_tipo is None:
        # CxP: el titulo NUMERO cubre dos columnas (tipo y numero).
        c_tipo, c_num = c_num, c_num + 1
    c = {"nit": col("NIT", "IDENTIDAD"),
         "tercero": col("RAZON SOCIAL", "CLIENTE", "BENEFICIARIO"),
         "tipo": c_tipo, "numero": c_num,
         "concepto": col("CONCEPTO", despues=c_num),
         "emision": col("FECHA EMISION", "FECHA EMI"),
         "vence": col("FECHA VENC", "FECHA  VENC", "FECHA VENCE"),
         "valor": col("VALOR"), "abonos": col("ABONOS"),
         "saldo": col("SALDO")}
    c["obs"] = col("OBSERVACION")
    if c["obs"] is None and c["saldo"] is not None:
        c["obs"] = c["saldo"] + 1
    titulo = " ".join(_texto(v) for f in filas[:titulo_i] for v in f
                      if _texto(v))
    empresa = _texto(filas[0][0]) if filas and filas[0] else ""
    fecha = _fecha_en_texto(titulo.replace(" DE ", " ")) or \
        _fecha_en_texto(hoja) or _fecha_en_texto(nombre_archivo)
    m = re.search(r"AL\s+(\d{1,2})\s+DE\s+([A-Z]+)\s+DE\s+(\d{4})",
                  comparable(titulo))
    if m:
        mes = next((i + 1 for i, n in enumerate(MESES_PP)
                    if n == m.group(2)), None)
        if mes:
            fecha = datetime.date(int(m.group(3)), mes, int(m.group(1)))

    def v(f, k):
        j = c.get(k)
        return f[j] if j is not None and j < len(f) else None

    documentos, manuales, anticipos = [], [], []
    seccion, nit, tercero = "", "", ""
    en_anticipos, c_ant = False, None
    for i, f in enumerate(filas[titulo_i + 1:], start=titulo_i + 2):
        textos = [_texto(x) for x in f]
        if not any(textos):
            continue
        cab0 = comparable(textos[0]) if textos else ""
        todo = comparable(" ".join(textos))
        if cab0.startswith(("TOTAL CUENTAS", "TOTAL ANTICIPOS")):
            if cab0.startswith("TOTAL ANTICIPOS"):
                break
            continue
        if cab0.startswith("ANTICIPOS"):
            en_anticipos, titulo_ant = True, textos[0]
            continue
        if en_anticipos:
            if "IDENTIDAD" in todo and "DOCUMENTO" in todo:
                c_ant = [comparable(x) for x in textos]
                continue
            if "TOTAL" in comparable(v(f, "tipo")) or not c_ant:
                continue

            def a(*pref):
                j = next((j for j, t in enumerate(c_ant)
                          if any(t.startswith(p) for p in pref)), None)
                return f[j] if j is not None and j < len(f) else None
            if _texto(a("IDENTIDAD")):
                nit = _texto(a("IDENTIDAD"))
                tercero = _texto(a("BENEFICIARIO", "CLIENTE"))
            valor = a("VR.POR APLICAR", "VR POR APLICAR", "SALDO")
            if not isinstance(valor, (int, float)):
                continue
            anticipos.append({
                "titulo": titulo_ant.strip(), "nit": nit,
                "tercero": tercero, "tipo": _texto(a("TIPO")),
                "numero": _texto(a("DOCUMENTO")),
                "fecha": _fecha(a("FECHA")), "fecha_texto": _texto(
                    a("FECHA")), "concepto": _texto(a("CONCEPTO")),
                "valor_inicial": a("VR.ANTICIPO", "VR ANTICIPO"),
                "valor": round(float(valor), 2),
                "obs": _texto(f[len(c_ant)] if len(f) > len(c_ant)
                              else None) or _texto(f[9] if len(f) > 9
                                                   else None),
                "fila": i})
            continue
        # Seccion (columna A en CxP: PROVEEDORES, IMPUESTOS, SEGURIDAD...)
        if c["nit"] and c["nit"] > 0 and textos[0] and not cab0.startswith(
                ("TOTAL", "GRAN TOTAL")):
            seccion = re.sub(r"\s+", "", textos[0]) \
                if "\n" in textos[0] else textos[0].strip()
        if "TOTAL" in comparable(v(f, "tipo")) or "GRAN TOTAL" in todo:
            # Subtotal: una observacion escrita en esa fila es del
            # documento anterior si este no tiene.
            obs_sub = _texto(v(f, "obs"))
            if obs_sub and documentos and not documentos[-1]["obs"]:
                documentos[-1]["obs"] = obs_sub
            continue
        if _texto(v(f, "nit")):
            nit = _texto(v(f, "nit"))
            if isinstance(v(f, "nit"), float) and v(f, "nit").is_integer():
                nit = str(int(v(f, "nit")))
            tercero = _texto(v(f, "tercero"))
        tipo = _texto(v(f, "tipo"))
        num = _texto(v(f, "numero"))
        saldo = v(f, "saldo")
        if not isinstance(saldo, (int, float)):
            continue
        base = {"seccion": seccion, "nit": nit, "tercero": tercero,
                "emision": _fecha(v(f, "emision")),
                "emision_texto": _texto(v(f, "emision")),
                "vence": _fecha(v(f, "vence")),
                "vence_texto": _texto(v(f, "vence")),
                "valor_inicial": v(f, "valor") if isinstance(
                    v(f, "valor"), (int, float)) else None,
                "abonos": v(f, "abonos") if isinstance(
                    v(f, "abonos"), (int, float)) else None,
                "saldo": round(float(saldo), 2),
                "obs": _texto(v(f, "obs")), "fila": i}
        documento = tipo and (num or RE_DOC_HELISA.match(tipo.upper())) and \
            not (tipo and len(tipo) > 8 and not num)
        if documento:
            documentos.append(dict(base, tipo=tipo, numero=num,
                                   concepto=_texto(v(f, "concepto"))))
        elif tipo or _texto(v(f, "concepto")):
            manuales.append(dict(base, descripcion=tipo or _texto(
                v(f, "concepto"))))
    if not documentos:
        raise ValueError("La programación anterior de EMPRESA E no trae "
                         "documentos.")
    return {"archivo": nombre_archivo, "hoja": hoja, "fecha": fecha,
            "titulo": titulo, "empresa": empresa, "documentos": documentos,
            "manuales": manuales, "anticipos": anticipos, "modo": modo,
            "tabla": filas, "libro": libro}


# ------------------------------------------------------------
# Armado
# ------------------------------------------------------------
VENCIDAS_EMPRESA_E = {"pagar": {"FC": "FACTURA VENCIDA",
                           "DSE": "CUENTA DE COBRO VENCIDA"},
                 "cobrar": {"FEV": "FACTURA VENCIDA",
                            "FV": "FACTURA VENCIDA"}}


def armar_empresa_e(helisa, anterior, fecha, modo="pagar", marcar_vencidas=True):
    por_num = defaultdict(list)
    for d in anterior["documentos"]:
        por_num[numero_corto(d["numero"])].append(d)
    nit_de = {}
    for d in anterior["documentos"]:
        if d["nit"]:
            nit_de[alfanumerico(d["tercero"])] = (d["nit"], d["tercero"],
                                                  d["seccion"])
    usados = set()
    partidas = []
    seccion_def = "PROVEEDORES" if modo == "pagar" else "CLIENTES"
    for d in helisa["documentos"]:
        corto = numero_corto(d["numero"])
        candidatos = [a for a in por_num.get(corto, []) if id(a) not in usados]
        if len(candidatos) > 1:
            candidatos = [a for a in candidatos if alfanumerico(
                a["tercero"])[:8] == alfanumerico(d["proveedor"])[:8]] or \
                candidatos[:1]
        ant = candidatos[0] if candidatos else None
        revisar = []
        if ant:
            usados.add(id(ant))
            nit, tercero, seccion = ant["nit"], ant["tercero"], ant["seccion"]
            concepto, valor_inicial = ant.get("concepto", ""), \
                ant.get("valor_inicial")
            obs, tipo, num = ant["obs"], ant["tipo"], ant["numero"]
            origen, motivo = "HELISA", "Pendiente en HELISA y en la anterior."
            if valor_inicial is not None and d["valor"] > valor_inicial + \
                    0.005:
                revisar.append("El saldo de HELISA es mayor que el valor "
                               "inicial de la anterior: revisar.")
        else:
            previo = nit_de.get(alfanumerico(d["proveedor"]))
            nit, tercero, seccion = previo if previo else (
                "", d["proveedor"], seccion_def)
            concepto, valor_inicial, obs = "", None, ""
            tipo = tipo_doc_cxp(d["numero"])
            partes = str(d["numero"]).split(None, 1)
            num = partes[1] if len(partes) > 1 else d["numero"]
            origen, motivo = "HELISA · nueva", "Documento nuevo en HELISA."
            revisar.append("Nuevo: escribir el CONCEPTO y el VALOR INICIAL "
                           "(HELISA solo trae el saldo)." +
                           ("" if previo else " Tercero nuevo: falta el "
                            "NIT."))
        if not d["fecha"] and d.get("fecha_texto"):
            revisar.append(f"Fecha incompleta en HELISA "
                           f"(«{d.get('fecha_texto')}»).")
        partidas.append({
            "id": f"C{len(partidas) + 1:03d}", "incluir": abs(d["valor"]) >= 1,
            "seccion": seccion or seccion_def, "nit": nit,
            "tercero": tercero, "tipo": tipo, "numero": num,
            "concepto": concepto, "emision": d["fecha"],
            "emision_texto": d.get("fecha_texto", ""), "vence": d["vence"],
            "vence_texto": d.get("vence_texto", ""),
            "valor_inicial": valor_inicial, "saldo": d["valor"],
            "obs": obs, "obs_sugerida": False, "origen": origen,
            "motivo": motivo if abs(d["valor"]) >= 1 else
            "Saldo de centavos: no se incluye; ajustar en HELISA.",
            "revisar": revisar, "orden": d.get("orden", 0)})
    if marcar_vencidas:
        textos = VENCIDAS_EMPRESA_E.get(modo, {})
        for p in partidas:
            if p["incluir"] and not p["obs"] and p["vence"] and \
                    p["vence"] < fecha and comparable(p["tipo"]) in textos:
                p["obs"] = textos[comparable(p["tipo"])]
                p["obs_sugerida"] = True
    for a in anterior["documentos"]:
        if id(a) in usados:
            continue
        partidas.append({
            "id": f"C{len(partidas) + 1:03d}", "incluir": False,
            "seccion": a["seccion"], "nit": a["nit"], "tercero": a["tercero"],
            "tipo": a["tipo"], "numero": a["numero"],
            "concepto": a.get("concepto", ""), "emision": a["emision"],
            "emision_texto": a["emision_texto"], "vence": a["vence"],
            "vence_texto": a["vence_texto"],
            "valor_inicial": a.get("valor_inicial"), "saldo": a["saldo"],
            "obs": a["obs"], "obs_sugerida": False,
            "origen": "Programación anterior",
            "motivo": "Ya no está en el listado de HELISA: se pagó o se "
                      "anuló.", "revisar": [], "orden": 10 ** 6})
    return partidas


def orden_empresa_e(partidas):
    return sorted(partidas, key=lambda p: (comparable(p["seccion"]) !=
                                           comparable(partidas[0]["seccion"]
                                                      if partidas else ""),
                                           comparable(p["tercero"]),
                                           p.get("orden", 0)))


def nombre_archivo_empresa_e(modo, fecha, empresa="EMPRESA E SAS"):
    base = ("PROGR. DE Cuentas x Pagar" if modo == "pagar" else
            "PROGR. Cuentas x Cobrar")
    return nombre_seguro(f"{base} AL {fecha:%d-%m-%Y} {empresa}") + ".xlsx"


# ------------------------------------------------------------
# Excel
# ------------------------------------------------------------
def generar_excel_empresa_e(partidas, ctx):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as L
    modo = ctx.get("modo", "pagar")
    fecha = ctx["fecha"]
    libro = Workbook()
    ws = libro.active
    ws.title = (f"PROGR AL {fecha:%d-%m-%Y}" if modo == "pagar" else
                f"PROG. C. X COBRAR AL {fecha:%d-%m-%Y}")[:31]
    fino = Side(style="thin", color="000000")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    gris = PatternFill("solid", fgColor="D9D9D9")
    sub = PatternFill("solid", fgColor="FFF2CC")
    amarillo = PatternFill("solid", fgColor="FFFF00")
    pesos = '_-$* #,##0.00_-;"-$"* #,##0.00_-;_-$* "-"??_-;_-@_-'
    if modo == "pagar":
        cols = ["CONCEPTO", "NIT", "RAZON SOCIAL", "NUMERO", "",
                "CONCEPTO", "Fecha Emision", "Fecha Vence",
                "VALOR DE LA FACTURA", "ABONOS REALIZADOS", "Saldo FACTURA",
                "OBSERVACIONES"]
        C = {"sec": 1, "nit": 2, "ter": 3, "tipo": 4, "num": 5, "con": 6,
             "emi": 7, "ven": 8, "val": 9, "abo": 10, "sal": 11, "obs": 12}
        titulo = "RELACION DE FACTURAS PENDIENTES POR PAGAR"
    else:
        cols = ["NIT", "CLIENTE", "TIPO", "NUMERO", "FECHA EMISION",
                "FECHA VENCIMIENTO", "CONCEPTO",
                "VALOR INICIAL DE LA FACTURA", "SALDO PENDIENTE POR RECIBIR",
                "OBSERVACIONES"]
        C = {"sec": None, "nit": 1, "ter": 2, "tipo": 3, "num": 4, "emi": 5,
             "ven": 6, "con": 7, "val": 8, "abo": None, "sal": 9, "obs": 10}
        titulo = "RELACION DE FACTURAS PENDIENTES POR COBRAR"
    ancho = len(cols)
    ws.cell(1, 1, ctx.get("empresa") or "EMPRESA E SAS").font = \
        Font(bold=True, size=14)
    ws.cell(2, 1, f"{titulo} AL {fecha.day:02d} DE "
                  f"{MESES_PP[fecha.month - 1]} DE {fecha.year}").font = \
        Font(bold=True, size=12)
    for j, t in enumerate(cols, start=1):
        celda = ws.cell(3, j, t or None)
        celda.font = Font(bold=True)
        celda.fill = gris
        celda.border = borde
        celda.alignment = Alignment(horizontal="center", vertical="center",
                                    wrap_text=True)
    if modo == "pagar":
        ws.merge_cells(start_row=3, start_column=4, end_row=3, end_column=5)

    def fecha_celda(p, campo):
        f = p.get(campo)
        return f if isinstance(f, datetime.date) else (
            p.get(f"{campo}_texto") or None)

    fila = 4
    totales_seccion = []
    incluidas = [p for p in partidas if p.get("incluir")]
    secciones = OrderedDict()
    for p in incluidas:
        secciones.setdefault(p["seccion"] or "", []).append(p)
    for seccion, lista in secciones.items():
        inicio_sec = fila
        filas_sub = []
        grupos = OrderedDict()
        for p in sorted(lista, key=lambda p: (comparable(p["tercero"]),
                                              p.get("orden", 0))):
            grupos.setdefault(alfanumerico(p["tercero"]), []).append(p)
        for _, docs in grupos.items():
            primera = fila
            for k, p in enumerate(docs):
                if k == 0:
                    ws.cell(fila, C["nit"], int(p["nit"]) if str(
                        p["nit"]).isdigit() else (p["nit"] or None))
                    ws.cell(fila, C["ter"], p["tercero"])
                ws.cell(fila, C["tipo"], p["tipo"])
                ws.cell(fila, C["num"], p["numero"])
                ws.cell(fila, C["con"], p.get("concepto") or None)
                for campo, cc in (("emision", "emi"), ("vence", "ven")):
                    x = ws.cell(fila, C[cc], fecha_celda(p, campo))
                    if isinstance(x.value, datetime.date):
                        x.number_format = "dd/mm/yyyy"
                vi = ws.cell(fila, C["val"], p.get("valor_inicial"))
                vi.number_format = pesos
                if p.get("valor_inicial") is None:
                    vi.fill = amarillo
                if not p.get("concepto"):
                    ws.cell(fila, C["con"]).fill = amarillo
                if C["abo"]:
                    if p.get("valor_inicial") is not None:
                        ws.cell(fila, C["abo"],
                                f"={L(C['val'])}{fila}-{L(C['sal'])}{fila}")
                    ws.cell(fila, C["abo"]).number_format = pesos
                ws.cell(fila, C["sal"], p["saldo"]).number_format = pesos
                ws.cell(fila, C["obs"], p.get("obs") or None).font = Font(
                    color="FF0000")
                for j in range(1, ancho + 1):
                    ws.cell(fila, j).border = borde
                fila += 1
            ws.cell(fila, C["tipo"], "TOTAL").font = Font(bold=True)
            ws.cell(fila, C["sal"],
                    f"=SUM({L(C['sal'])}{primera}:{L(C['sal'])}{fila - 1})")
            ws.cell(fila, C["sal"]).number_format = pesos
            ws.cell(fila, C["sal"]).font = Font(bold=True)
            for j in range(1, ancho + 1):
                ws.cell(fila, j).fill = sub
                ws.cell(fila, j).border = borde
            filas_sub.append(fila)
            fila += 1
        if C["sec"]:
            ws.cell(fila, C["nit"], f"GRAN TOTAL {seccion} A PAGAR").font = \
                Font(bold=True)
            ws.cell(fila, C["sal"], "=" + "+".join(
                f"{L(C['sal'])}{r}" for r in filas_sub))
            ws.cell(fila, C["sal"]).number_format = pesos
            ws.cell(fila, C["sal"]).font = Font(bold=True)
            totales_seccion.append(fila)
            ws.cell(inicio_sec, C["sec"], seccion)
            if fila - 1 > inicio_sec:
                ws.merge_cells(start_row=inicio_sec, start_column=C["sec"],
                               end_row=fila - 1, end_column=C["sec"])
            ws.cell(inicio_sec, C["sec"]).alignment = Alignment(
                vertical="center", horizontal="center", wrap_text=True)
            fila += 1
        else:
            totales_seccion.extend(filas_sub)
    # Secciones manuales (IMPUESTOS, SEGURIDAD SOCIAL...)
    manuales = OrderedDict()
    for m in ctx.get("manuales") or []:
        if m.get("incluir", True):
            manuales.setdefault(m.get("seccion") or "OTROS", []).append(m)
    for seccion, lista in manuales.items():
        inicio = fila
        for k, m in enumerate(lista):
            if k == 0:
                ws.cell(fila, C["nit"], m.get("nit") or None)
                ws.cell(fila, C["ter"], m.get("tercero") or None)
            ws.cell(fila, C["tipo"], m.get("descripcion"))
            ws.cell(fila, C["emi"], m.get("fecha_texto") or None)
            ws.cell(fila, C["val"], m.get("valor_inicial")).number_format = \
                pesos
            ws.cell(fila, C["sal"], float(m.get("valor") or 0)
                    ).number_format = pesos
            ws.cell(fila, C["obs"], m.get("obs") or None).font = Font(
                color="FF0000")
            for j in range(1, ancho + 1):
                ws.cell(fila, j).border = borde
            fila += 1
        ws.cell(fila, C["tipo"], "TOTAL").font = Font(bold=True)
        ws.cell(fila, C["sal"],
                f"=SUM({L(C['sal'])}{inicio}:{L(C['sal'])}{fila - 1})")
        ws.cell(fila, C["sal"]).number_format = pesos
        for j in range(1, ancho + 1):
            ws.cell(fila, j).fill = sub
        totales_seccion.append(fila)
        if C["sec"]:
            ws.cell(inicio, C["sec"], seccion)
            ws.merge_cells(start_row=inicio, start_column=C["sec"],
                           end_row=fila, end_column=C["sec"])
            ws.cell(inicio, C["sec"]).alignment = Alignment(
                vertical="center", horizontal="center", wrap_text=True)
        fila += 1
    fila += 1
    etiqueta = (f"TOTAL CUENTAS POR PAGAR AL {fecha:%d-%m-%Y}"
                if modo == "pagar" else
                f"TOTAL CUENTAS PENDIENTES POR COBRAR AL {fecha:%d-%m-%Y}")
    ws.cell(fila, 1, etiqueta).font = Font(bold=True, size=12)
    ws.cell(fila, C["sal"], "=" + ("+".join(f"{L(C['sal'])}{r}"
                                            for r in totales_seccion) or "0"))
    ws.cell(fila, C["sal"]).number_format = pesos
    ws.cell(fila, C["sal"]).font = Font(bold=True, size=12)
    for j in range(1, ancho + 1):
        ws.cell(fila, j).fill = sub
    # Anticipos
    anticipos = [a for a in (ctx.get("anticipos") or [])
                 if a.get("incluir", True)]
    if anticipos:
        fila += 3
        ws.cell(fila, 1, anticipos[0].get("titulo") or
                "ANTICIPOS PENDIENTES POR LEGALIZAR").font = Font(bold=True)
        fila += 1
        for j, t in enumerate(["IDENTIDAD", "BENEFICIARIO", "TIPO DE DOC",
                               "DOCUMENTO", "FECHA", "", "CONCEPTO",
                               "VR.ANTICIPO", "VR.POR APLICAR",
                               "OBSERVACIONES"], start=1):
            ws.cell(fila, j, t or None).font = Font(bold=True)
            ws.cell(fila, j).fill = gris
        fila += 1
        totales = []
        grupos = OrderedDict()
        for a in anticipos:
            grupos.setdefault(alfanumerico(a.get("tercero") or ""), []
                              ).append(a)
        for _, lista in grupos.items():
            inicio = fila
            for k, a in enumerate(lista):
                if k == 0:
                    ws.cell(fila, 1, a.get("nit") or None)
                    ws.cell(fila, 2, a.get("tercero") or None)
                ws.cell(fila, 3, a.get("tipo") or None)
                ws.cell(fila, 4, a.get("numero") or None)
                ws.cell(fila, 5, a.get("fecha_texto") or None)
                ws.cell(fila, 7, a.get("concepto") or None)
                ws.cell(fila, 8, a.get("valor_inicial")).number_format = pesos
                ws.cell(fila, 9, float(a.get("valor") or 0)).number_format = \
                    pesos
                ws.cell(fila, 10, a.get("obs") or None).font = Font(
                    color="FF0000")
                fila += 1
            ws.cell(fila, 3, "TOTAL").font = Font(bold=True)
            ws.cell(fila, 9, f"=SUM(I{inicio}:I{fila - 1})").number_format = \
                pesos
            totales.append(fila)
            fila += 1
        fila += 1
        ws.cell(fila, 1, f"TOTAL ANTICIPOS PENDIENTES POR LEGALIZAR AL "
                         f"{fecha:%d-%m-%Y}").font = Font(bold=True)
        ws.cell(fila, 9, "=" + "+".join(f"I{r}" for r in totales)
                ).number_format = pesos
    anchos = ([14, 14, 34, 6, 16, 38, 12, 12, 16, 14, 16, 44]
              if modo == "pagar" else
              [14, 36, 7, 16, 12, 12, 40, 18, 18, 44])
    for j, a in enumerate(anchos, start=1):
        ws.column_dimensions[L(j)].width = a
    ws.freeze_panes = "A4"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def resumen_empresa_e(partidas, fecha):
    inc = [p for p in partidas if p.get("incluir")]
    return {"incluidas": len(inc), "excluidas": len(partidas) - len(inc),
            "terceros": len({alfanumerico(p["tercero"]) for p in inc}),
            "total": round(sum(p["saldo"] for p in inc), 2),
            "vencido": round(sum(p["saldo"] for p in inc
                                 if p.get("vence") and p["vence"] < fecha), 2),
            "sin_concepto": sum(1 for p in inc if not p.get("concepto")),
            "sin_valor": sum(1 for p in inc if p.get("valor_inicial") is None)}
