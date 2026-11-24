"""Cuentas por pagar EMPRESA D (CXP de HELISA vs CXP anterior).

Contrato:
  leer_cxp_helisa / leer_cxp_anterior -> documentos.
  armar_cxp_empresa_d(helisa, anterior, fecha, marcar_vencidas=True) -> filas; todo documento FCC/DSEC vencido
      (vence < fecha de corte) queda marcado como vencido con observacion
      vacia, aunque en la programacion anterior no venciera.
  generar_excel_cxp(partidas, ctx) -> libro "CUENTAS X PAGAR AL ...".

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.planillas.logica, gmya.modulos.pagos.lectura, gmya.modulos.pagos.excel
"""

import datetime
import io
import re
from collections import OrderedDict, defaultdict

from gmya.comun.texto import alfanumerico, comparable, solo_nit
from gmya.comun.numeros import formato_cop, numero
from gmya.modulos.planillas.logica import nombre_seguro
from gmya.modulos.pagos.lectura import (
    abrir_libro_anterior, fecha_celda_pp, _filas_valores, _mes_de_palabra,
    MESES_PP, _texto,
)
from gmya.modulos.pagos.excel import _libro_base, MES_ABR_PP


# ------------------------------------------------------------
# EMPRESA D: cuentas por pagar con observaciones
# ------------------------------------------------------------
# La programacion de EMPRESA D es el listado "Lista de facturas por pagar de
# acreedores" de HELISA, reorganizado (proveedor, documento, fechas, lo que
# se paga) con una columna de OBSERVACIONES que el equipo mantiene. Para
# actualizarla se toma el listado nuevo de HELISA y se le pasan las
# observaciones de la programacion anterior.
MESES_ABR_ES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AGO": 8, "SEP": 9, "SET": 9, "OCT": 10,
                "NOV": 11, "DIC": 12}
RE_FECHA_ABR = re.compile(r"^\s*(\d{1,2})[/-]([A-Za-z]{3})[/-](\d{4})\s*$")
# v6.10: HELISA corta a veces el anio de las fechas de marzo ("13/MAR/202");
# el documento se conserva con la fecha tal como viene y se avisa (nunca se
# adivina el anio).
RE_FECHA_TRUNCA = re.compile(
    r"^\s*(\d{1,2})[/-]([A-Za-z]{3})[/-](\d{1,3})\s*$")
PALABRAS_NO_PROVEEDOR = ("TOTAL", "LISTA DE", "PAGINA", "DATOS DEL",
                         "ESTE INFORME", "(NIT", "NIT:", "PAGOS:",
                         "TIPO DE CARTERA", "PLANILLA PARA")
# Documento contable de HELISA ("FC  0000FE-781", "DSEC000DSEM410",
# "RC 163-I", "PE-1813"); un texto como "SEGURIDAD SOCIAL MES DE JUNIO" o
# "LIBRANZA MES DE OCTUBRE" no lo es.
RE_DOC_HELISA = re.compile(r"^[A-Z]{1,6}[\s\-]*\S*\d")


def es_fecha_texto(valor):
    return isinstance(valor, str) and bool(
        RE_FECHA_ABR.match(valor) or RE_FECHA_TRUNCA.match(valor))


def fecha_abreviada(valor):
    """'28/AGO/2026' -> date; tambien acepta fechas normales."""
    m = RE_FECHA_ABR.match(str(valor or ""))
    if m and comparable(m.group(2)) in MESES_ABR_ES:
        try:
            return datetime.date(int(m.group(3)),
                                 MESES_ABR_ES[comparable(m.group(2))],
                                 int(m.group(1)))
        except ValueError:
            return None
    return fecha_celda_pp(valor)


def _fecha_en_texto(texto):
    """'... a octubre 14 de 2026' / 'el 20 de Octubre del año 2026'."""
    t = comparable(texto)
    m = re.search(r"([A-Z]+)\s+(\d{1,2})\s+DE\s+(\d{4})", t)
    if m and _mes_de_palabra(m.group(1)):
        try:
            return datetime.date(int(m.group(3)), _mes_de_palabra(m.group(1)),
                                 int(m.group(2)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})\s+DE\s+([A-Z]+)\s+DEL?\s+(?:ANO\s+)?(\d{4})", t)
    if m and _mes_de_palabra(m.group(2)):
        try:
            return datetime.date(int(m.group(3)), _mes_de_palabra(m.group(2)),
                                 int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", t)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)),
                                 int(m.group(1)))
        except ValueError:
            pass
    return None


def tipo_doc_cxp(numero_doc):
    """'FCC FE-187' -> 'FCC'; 'DSEC000000DSEM410' -> 'DSEC'."""
    m = re.match(r"\s*([A-Z]{2,4})", str(numero_doc or "").upper())
    if not m:
        return ""
    t = m.group(1)
    return "DSEC" if t.startswith("DSEC") else t


def _leer_bloques_cxp(filas, columnas=None):
    """
    Recorre un listado de cuentas por pagar agrupado por proveedor (fila
    con el nombre y debajo sus documentos). columnas: dict con indices de
    numero, fecha, vence, valor y obs; si es None se deducen por fila
    (listado de HELISA, donde las columnas cambian de lugar).
    """
    proveedor, docs = None, []
    for n, fila in enumerate(filas, start=1):
        textos = [(i, v) for i, v in enumerate(fila) if v not in (None, "")]
        if not textos:
            continue
        primero = comparable(_texto(textos[0][1]))
        if any(_texto(v).upper().startswith(("TOTAL A PAGAR",
                                             "TOTAL A COBRAR"))
               for _, v in textos):
            continue
        if columnas:
            num = _texto(fila[columnas["numero"]]) \
                if columnas["numero"] < len(fila) else ""
            fecha = fecha_abreviada(fila[columnas["fecha"]]) \
                if columnas["fecha"] < len(fila) else None
            if not num:
                if textos[0][0] == 0 and not any(
                        primero.startswith(p) for p in PALABRAS_NO_PROVEEDOR):
                    proveedor = _texto(textos[0][1])
                continue
            def v(clave):
                i = columnas.get(clave)
                return fila[i] if i is not None and i < len(fila) else None
            docs.append({"proveedor": proveedor, "numero": num,
                         "fecha": fecha, "vence": fecha_abreviada(v("vence")),
                         "fecha_texto": _texto(v("fecha")),
                         "vence_texto": _texto(v("vence")),
                         "valor": round(numero(v("valor")), 2),
                         "obs": _texto(v("obs")), "fila": n})
            continue
        fechas = [(i, fecha_abreviada(v), _texto(v)) for i, v in textos
                  if es_fecha_texto(v)]
        if len(fechas) >= 2:
            num = next((_texto(v) for i, v in textos
                        if i < fechas[0][0] and isinstance(v, str)), "")
            numeros = [v for i, v in textos if i > fechas[1][0]
                       and isinstance(v, (int, float))]
            docs.append({"proveedor": proveedor, "numero": num,
                         "fecha": fechas[0][1], "vence": fechas[1][1],
                         "fecha_texto": fechas[0][2],
                         "vence_texto": fechas[1][2],
                         "valor": round(float(numeros[-1]), 2)
                         if numeros else 0.0, "obs": "", "fila": n})
            continue
        if textos[0][0] == 0 and isinstance(textos[0][1], str) and not any(
                primero.startswith(p) for p in PALABRAS_NO_PROVEEDOR):
            proveedor = _texto(textos[0][1])
    return docs


def leer_cxp_helisa(contenido):
    """
    'Lista de facturas por pagar de acreedores' de HELISA tal como se
    descarga. {empresa, nit, fecha_corte, fecha_informe, documentos, tabla}.
    """
    filas = _filas_valores(contenido)
    empresa, nit, corte, elaborado, nit_texto = "", "", None, None, ""
    clase = "pagar"
    # v6.18: la empresa es el primer texto del informe (antes se tomaba el
    # primer texto con "S.A.S" y en EMPRESA B S.A.S. salia un cliente).
    for fila in filas[:3]:
        primero = next((_texto(v) for v in fila if _texto(v)), "")
        if primero and not comparable(primero).startswith(("(NIT", "NIT")):
            empresa = primero
            break
    for fila in filas:
        for v in fila:
            t = _texto(v)
            ct = comparable(t)
            if not t:
                continue
            if ct.startswith("(NIT") or ct.startswith("NIT"):
                nit = solo_nit(re.sub(r"[^\d,\-.]", "", t).replace(",", ""))
                nit_texto = t
            elif ct.startswith("LISTA DE FACTURAS"):
                corte = _fecha_en_texto(t)
            elif ct.startswith("PLANILLA PARA COBROS"):
                # v6.10: cartera (cuentas por cobrar) de HELISA.
                corte = _fecha_en_texto(t)
                clase = "cobrar"
            elif ct.startswith("ESTE INFORME SE ELABORO"):
                elaborado = _fecha_en_texto(t)
            elif not empresa and re.search(r"S\.?A\.?S|LTDA|S\.A", ct):
                empresa = t
    documentos = [d for d in _leer_bloques_cxp(filas) if d["numero"]]
    if not documentos:
        raise ValueError("No parece el listado de cuentas por pagar de "
                         "HELISA (no se encontraron documentos con fecha de "
                         "emisión y vencimiento).")
    for i, d in enumerate(documentos):
        d["orden"] = i
        d["tipo"] = tipo_doc_cxp(d["numero"])
    return {"empresa": empresa, "nit": nit, "nit_texto": nit_texto,
            "fecha_corte": corte, "clase": clase,
            "fecha_informe": elaborado, "documentos": documentos,
            "tabla": filas,
            "total": round(sum(d["valor"] for d in documentos), 2)}


def leer_cxp_anterior(contenido, nombre_archivo=""):
    """La programacion anterior de EMPRESA D (CUENTAS X PAGAR AL ...)."""
    libro = abrir_libro_anterior(contenido)
    nombre_hoja = next(iter(libro["hojas"]))
    filas = libro["hojas"][nombre_hoja]
    titulo = None
    for i, fila in enumerate(filas[:30]):
        textos = [comparable(_texto(v)) for v in fila]
        if any(t.startswith("NUMERO DE DOCUMENTO") for t in textos):
            titulo = i
            break
    if titulo is None:
        raise ValueError("En la programación anterior no se encontró la fila "
                         "de títulos (NUMERO DE DOCUMENTO, FECHA EMISION…).")
    textos = [comparable(_texto(v)) for v in filas[titulo]]

    def col(*opciones):
        for i, t in enumerate(textos):
            if any(t.startswith(o) for o in opciones):
                return i
        return None
    columnas = {"numero": col("NUMERO DE DOCUMENTO"),
                "fecha": col("FECHA EMISION"),
                "vence": col("FECHA VENC"), "valor": col("LO QUE SE PAGA",
                                                         "LO QUE SE COBRA",
                                                         "VALOR"),
                "obs": col("OBSERVACION")}
    if None in (columnas["numero"], columnas["valor"]):
        raise ValueError("La programación anterior no tiene las columnas "
                         "NUMERO DE DOCUMENTO y LO QUE SE PAGA.")
    columnas["fecha"] = columnas["fecha"] if columnas["fecha"] is not None \
        else columnas["numero"] + 1
    cuerpo = filas[titulo + 1:]
    # v6.10: el listado principal termina en el total general (TOTAL CUENTAS
    # POR PAGAR / COBRAR AL ..., CUENTAS PENDIENTES POR ...). Lo que viene
    # despues (anticipos pendientes por legalizar) se lee aparte.
    fin = len(cuerpo)
    for i, fila in enumerate(cuerpo):
        t = comparable(_texto(fila[0])) if fila else ""
        if t.startswith(("TOTAL CUENTAS POR", "CUENTAS PENDIENTES POR")):
            fin = i
            break
    principal = cuerpo[:fin]
    # Filas manuales dentro del listado (EMPRESA F: SEGURIDAD SOCIAL, IMPUESTOS,
    # PAGOS FIJOS): no son documentos de HELISA; se guardan para copiarlas.
    manuales, seccion = [], ""
    limpio = []
    for i, fila in enumerate(principal):
        num = _texto(fila[columnas["numero"]]) \
            if columnas["numero"] < len(fila) else ""
        cab = _texto(fila[0]) if fila else ""
        if num and not RE_DOC_HELISA.match(num.upper()):
            if cab:
                seccion = cab
            def v(clave):
                j = columnas.get(clave)
                return fila[j] if j is not None and j < len(fila) else None
            manuales.append({
                "seccion": seccion.strip(), "descripcion": num,
                "fecha": fecha_abreviada(v("fecha")) or (
                    v("fecha").date() if hasattr(v("fecha"), "date")
                    else None),
                "fecha_texto": _texto(v("fecha")),
                "valor": round(numero(v("valor")), 2),
                "obs": _texto(v("obs")), "fila": titulo + 2 + i})
            limpio.append([None] * len(fila))
            continue
        if not num and manuales and cab and not comparable(cab).startswith(
                "TOTAL"):
            seccion = cab
        limpio.append(fila)
    docs = _leer_bloques_cxp(limpio, columnas)
    for d in docs:
        d["fila"] += titulo + 1
    anticipos = _leer_anticipos(cuerpo[fin + 1:], titulo + 2 + fin, columnas)
    # Observaciones combinadas (una celda para varias facturas).
    grupos = []
    for r1, c1, r2, c2 in libro.get("combinadas", {}).get(nombre_hoja, []):
        if columnas["obs"] is not None and c1 - 1 <= columnas["obs"] <= \
                c2 - 1 and r2 > r1:
            miembros = [d for d in docs if r1 <= d["fila"] <= r2]
            if miembros:
                grupos.append(miembros)
                for d in miembros[1:]:
                    d["obs"] = d["obs"] or ""
    fecha = None
    for fila in filas[:titulo]:
        for v in fila:
            if comparable(_texto(v)).startswith("LISTA DE FACTURAS"):
                fecha = _fecha_en_texto(_texto(v))
    fecha = fecha or _fecha_en_texto(nombre_hoja) or \
        _fecha_en_texto(nombre_archivo)
    return {"archivo": nombre_archivo, "hoja": nombre_hoja, "fecha": fecha,
            "documentos": docs, "grupos_obs": grupos, "libro": libro,
            "manuales": manuales, "anticipos": anticipos,
            "tabla": filas,
            "hojas_auxiliares": [h for h in libro["hojas"]
                                 if h != nombre_hoja]}


def _leer_anticipos(filas, primera_fila, columnas):
    """v6.10: bloque «ANTICIPOS ... PENDIENTES POR LEGALIZAR» que algunas
    programaciones (EMPRESA F) llevan despues del total. Se copia tal cual."""
    titulo, tercero, items = "", "", []
    for i, fila in enumerate(filas):
        textos = [_texto(v) for v in fila]
        if not any(textos):
            continue
        cab = textos[0] if textos else ""
        ccab = comparable(cab)
        if ccab.startswith("ANTICIPOS") and "PENDIENTES POR LEGALIZAR AL" \
                not in ccab:
            titulo = cab.strip()
            continue
        if ccab.startswith(("DATOS DEL", "ANTICIPOS PENDIENTES")):
            continue
        num = textos[columnas["numero"]] if columnas["numero"] < len(
            textos) else ""
        if comparable(num).endswith("TOTAL") or comparable(num).startswith(
                ("FC TOTAL", "TOTAL")):
            continue
        valor = fila[columnas["valor"]] if columnas["valor"] < len(fila) \
            else None
        if cab:
            tercero = cab
        if not isinstance(valor, (int, float)) or not num:
            continue
        f = fila[columnas["fecha"]] if columnas["fecha"] < len(fila) \
            else None
        obs = fila[columnas["obs"]] if columnas.get("obs") is not None and \
            columnas["obs"] < len(fila) else None
        items.append({"titulo": titulo, "tercero": tercero, "numero": num,
                      "fecha": fecha_abreviada(f) or (
                          f.date() if hasattr(f, "date") else None),
                      "fecha_texto": _texto(f),
                      "valor": round(float(valor), 2), "obs": _texto(obs),
                      "fila": primera_fila + i})
    return items


def _numero_corto(numero_doc, valor):
    """('FC', 'SA95174293', 13400.0) para 'FC  00000000SA95174293'."""
    partes = str(numero_doc or "").split(None, 1)
    tipo = tipo_doc_cxp(numero_doc)
    resto = alfanumerico(partes[1] if len(partes) > 1 else
                         str(numero_doc)[len(tipo):])
    return (tipo, resto.lstrip("0"), round(float(valor or 0), 2))


def _clave_cxp(proveedor, numero_doc):
    return (alfanumerico(proveedor), alfanumerico(numero_doc))


PALABRAS_OBS_PENDIENTE = ("?", "DEBE", "ACUERDO", "ABONA", "CRUCE",
                          "RECLAM", "NOTA CREDITO")


# Observacion de vencida por tipo de documento (EMPRESA D, por defecto).
VENCIDAS_EMPRESA_D = {"FCC": "FACTURA VENCIDA", "DSEC": "CUENTA DE COBRO VENCIDA"}


def armar_cxp_empresa_d(helisa, anterior, fecha, marcar_vencidas=True,
                     opciones=None):
    """Partidas de la nueva programacion (EMPRESA D, EMPRESA F...) con su
    sugerencia. opciones (v6.10, por empresa):
      vencidas     {tipo: texto} de la observacion de vencido.
      tipos_fuera  {tipo: motivo}: tipos que la empresa no lleva en el
                   listado (EMPRESA F: NMP/LP/LC van en SEGURIDAD SOCIAL y
                   PAGOS FIJOS); salen marcados, se pueden volver a incluir.
    """
    opciones = opciones or {}
    vencidas = opciones.get("vencidas") or VENCIDAS_EMPRESA_D
    tipos_fuera = opciones.get("tipos_fuera") or {}
    # Terceros que la empresa resume en otra seccion (EMPRESA F: entidades de
    # seguridad social -> SEGURIDAD SOCIAL): (expresion regular, motivo).
    terceros_fuera = opciones.get("terceros_fuera")
    ant_por_clave = {_clave_cxp(d["proveedor"], d["numero"]): d
                     for d in anterior["documentos"]}
    # v6.10: segundo cruce cuando el proveedor o los ceros del numero se
    # escribieron distinto en la anterior ("ALMACENES ÉXITO SA / FC
    # SA95174293" vs HELISA "ALMACENES EXITO S A / FC 00000000SA95174293"):
    # mismo tipo, mismo numero sin ceros a la izquierda y mismo valor, solo
    # si hay un unico candidato.
    por_numero = defaultdict(list)
    for d in anterior["documentos"]:
        por_numero[_numero_corto(d["numero"], d["valor"])].append(d)
    grupo_de = {}
    for i, g in enumerate(anterior.get("grupos_obs", [])):
        for d in g:
            grupo_de[_clave_cxp(d["proveedor"], d["numero"])] = i
    docs = helisa["documentos"]
    # Pares que se anulan dentro del mismo proveedor (factura + nota).
    anulados = set()
    por_prov = defaultdict(list)
    for d in docs:
        por_prov[alfanumerico(d["proveedor"])].append(d)
    for lista in por_prov.values():
        negativos = [d for d in lista if d["valor"] < 0]
        for neg in negativos:
            par = next((d for d in lista if d["valor"] > 0 and id(d) not in
                        anulados and abs(d["valor"] + neg["valor"]) < 0.01),
                       None)
            if par:
                anulados.update({id(par), id(neg)})
    obs_prov = defaultdict(bool)
    for d in anterior["documentos"]:
        if d["obs"]:
            obs_prov[alfanumerico(d["proveedor"])] = True
    partidas = []
    for d in docs:
        clave = _clave_cxp(d["proveedor"], d["numero"])
        ant = ant_por_clave.get(clave)
        if ant is None:
            candidatos = por_numero.get(_numero_corto(d["numero"],
                                                      d["valor"]), [])
            if len(candidatos) == 1:
                ant = candidatos[0]
                ant_por_clave[clave] = ant
        incluir, revisar = True, []
        aviso_exclusion = ""
        if id(d) in anulados:
            incluir = False
            motivo = ("Se anula con otro documento del mismo proveedor "
                      "(factura y nota por el mismo valor): saldo cero.")
            # v6.7: no se asume: se avisa para confirmarlo en HELISA.
            aviso_exclusion = (f"{d['proveedor']} {d['numero']} "
                               f"({formato_cop(d['valor'])}) se anula con "
                               "otro documento del mismo valor: confirmar "
                               "que la nota corresponde a esa factura.")
        elif abs(d["valor"]) < 1:
            incluir = False
            motivo = ("Saldo de centavos: no se programa un pago de "
                      "centavos; debe ajustarse en HELISA.")
            aviso_exclusion = (f"{d['proveedor']} {d['numero']} tiene un "
                               f"saldo de {formato_cop(d['valor'])} en "
                               "HELISA: no se programa; ajustarlo en "
                               "contabilidad para que no siga apareciendo.")
        elif d["tipo"] in tipos_fuera and not ant:
            incluir = False
            motivo = tipos_fuera[d["tipo"]]
        elif terceros_fuera and not ant and re.search(
                terceros_fuera[0], comparable(d["proveedor"])):
            incluir = False
            motivo = terceros_fuera[1]
        elif ant:
            motivo = "Pendiente en HELISA y en la programación anterior."
        else:
            motivo = "Documento nuevo en el listado de HELISA."
            if anterior.get("fecha") and d["fecha"] and \
                    d["fecha"] < anterior["fecha"]:
                revisar.append(
                    f"Es del {d['fecha']:%d/%m/%Y}, anterior a la "
                    f"programación pasada ({anterior['fecha']:%d/%m/%Y}), y "
                    "no estaba en ella: confirma si se había dejado por "
                    "fuera a propósito o si llegó tarde a HELISA.")
        obs = ant["obs"] if ant else ""
        if not d["fecha"] and d.get("fecha_texto") or \
                not d["vence"] and d.get("vence_texto"):
            revisar.append(
                f"Fecha incompleta en HELISA («{d.get('fecha_texto')}» / "
                f"«{d.get('vence_texto')}»): el año viene cortado; se deja "
                "tal cual, sin calcular vencimiento. Confirmar en HELISA.")
        if d["valor"] < 0 and incluir:
            revisar.append("Valor negativo (abono, pago o nota) que resta del "
                           "total del proveedor: confirma que siga vigente.")
        if obs and any(p in comparable(obs) for p in PALABRAS_OBS_PENDIENTE):
            revisar.append(f"La observación anterior deja algo por resolver: "
                           f"«{obs}».")
        dias = (fecha - d["vence"]).days if d["vence"] else 0
        if incluir and dias > 90 and not obs_prov[alfanumerico(
                d["proveedor"])] and not obs:
            revisar.append(f"Vencida hace {dias} días y sin observación.")
        partidas.append({
            "id": f"M{len(partidas) + 1:03d}", "seccion": "factura",
            "proveedor": d["proveedor"], "numero": d["numero"],
            "tipo": d["tipo"], "fecha": d["fecha"], "vence": d["vence"],
            "fecha_texto": d.get("fecha_texto", ""),
            "vence_texto": d.get("vence_texto", ""),
            "valor": d["valor"], "saldo": d["valor"], "pagar": d["valor"],
            "obs": obs, "obs_sugerida": False, "incluir": incluir,
            "motivo": motivo, "origen": "HELISA" if ant else "HELISA · nueva",
            "revisar": revisar if incluir else [], "orden": d["orden"],
            "fila_helisa": d["fila"], "fila_ant": ant["fila"] if ant else None,
            "grupo_obs": grupo_de.get(clave), "hijos": [],
            "aviso_exclusion": aviso_exclusion,
        })
    # Etiqueta de vencida (v6.0.3): TODO documento incluido que ya vencio a
    # la fecha de la programacion y no tiene otra observacion queda con
    # «FACTURA VENCIDA» (FCC) o «CUENTA DE COBRO VENCIDA» (DSEC), tambien
    # los que venian de la programacion anterior sin observacion porque
    # entonces aun no vencian. Las observaciones que ya tenga se respetan.
    if marcar_vencidas:
        for p in partidas:
            if not (p["incluir"] and p["vence"] and p["vence"] < fecha and
                    p["tipo"] in vencidas and p["valor"] > 0):
                continue
            if p["obs"].strip():
                continue
            p["obs"] = vencidas[p["tipo"]]
            p["obs_sugerida"] = True
            p["motivo"] += (f" Venció el {p['vence']:%d/%m/%Y}: se marca "
                            "como vencida.")
    # Lo que estaba en la anterior y ya no esta en HELISA: se pago.
    usados = {id(ant_por_clave[c]) for c in
              (_clave_cxp(d["proveedor"], d["numero"]) for d in docs)
              if c in ant_por_clave}
    for d in anterior["documentos"]:
        if id(d) in usados:
            continue
        partidas.append({
            "id": f"M{len(partidas) + 1:03d}", "seccion": "factura",
            "proveedor": d["proveedor"], "numero": d["numero"],
            "tipo": tipo_doc_cxp(d["numero"]), "fecha": d["fecha"],
            "vence": d["vence"], "fecha_texto": d.get("fecha_texto", ""),
            "vence_texto": d.get("vence_texto", ""),
            "valor": d["valor"], "saldo": d["valor"],
            "pagar": d["valor"], "obs": d["obs"], "obs_sugerida": False,
            "incluir": False, "motivo": "Ya no está en el listado de HELISA: "
                                        "se pagó o se anuló.",
            "origen": "Programación anterior", "revisar": [],
            "orden": 10 ** 6, "fila_helisa": None, "fila_ant": d["fila"],
            "grupo_obs": None, "hijos": []})
    return partidas


def comparar_seguridad_social(partidas, manuales, patron_entidades):
    """v6.10: compara, mes a mes, la SEGURIDAD SOCIAL que se lleva a mano en
    la programacion con los documentos de las entidades de seguridad social
    que HELISA trae pendientes (salieron del listado y el tercero cumple
    patron_entidades). Solo informa: no cambia ningun valor.
    Devuelve ([(mes 'JUNIO 2026', helisa, programacion)], [partidas de
    nomina a personas que salieron del listado y no son de ninguna
    entidad])."""
    helisa = defaultdict(float)
    sin_fecha = 0.0
    personas = []
    for p in partidas:
        if p.get("incluir") or p.get("origen") == "Programación anterior":
            continue
        if not re.search(patron_entidades, comparable(p["proveedor"])):
            if "NOMINA" in comparable(p.get("motivo")):
                personas.append(p)
            continue
        f = p.get("fecha")
        if f:
            helisa[(f.year, f.month)] += p["valor"]
        else:
            sin_fecha += p["valor"]
    manual = defaultdict(float)
    for m in manuales or []:
        if "SEGURIDAD" not in comparable(m.get("seccion")):
            continue
        t = comparable(m.get("descripcion"))
        mes = next((i + 1 for i, nombre in enumerate(MESES_PP)
                    if nombre in t), None)
        anio = re.search(r"(20\d{2})", t)
        if mes and anio:
            manual[(int(anio.group(1)), mes)] += float(m.get("valor") or 0)
    filas = []
    for clave in sorted(set(helisa) | set(manual)):
        filas.append((f"{MESES_PP[clave[1] - 1]} {clave[0]}",
                      round(helisa.get(clave, 0.0), 2),
                      round(manual.get(clave, 0.0), 2)))
    if sin_fecha:
        filas.append(("Fecha incompleta en HELISA", round(sin_fecha, 2),
                      0.0))
    return filas, personas


def groupby_proveedor(partidas):
    grupos = OrderedDict()
    for p in partidas:
        grupos.setdefault(alfanumerico(p["proveedor"]), []).append(p)
    return grupos


def orden_cxp(partidas):
    return sorted(partidas, key=lambda p: (comparable(p["proveedor"]),
                                           p.get("orden", 0)))


def nombre_archivo_cxp(nombre_empresa, fecha, prefijo="CUENTAS X PAGAR"):
    return nombre_seguro(f"{prefijo} AL {fecha:%d-%m-%Y} "
                         f"{nombre_empresa}") + ".xlsx"


def generar_excel_cxp(partidas, ctx):
    """
    Libro 'CUENTAS X PAGAR AL dd-mm-aaaa' con el mismo formato de la
    programacion de EMPRESA D: proveedor, documento, fechas, lo que se paga y
    observaciones; total por proveedor y total general.
    """
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    fecha = ctx["fecha"]
    anterior = ctx.get("anterior")
    # v6.10: cuentas por cobrar (cartera) con el mismo formato.
    cobrar = ctx.get("modo") == "cobrar"
    quien = "CLIENTE" if cobrar else "PROVEEDOR"
    verbo = "cobrar" if cobrar else "pagar"
    libro = _libro_base(anterior)
    ws = libro.create_sheet((ctx.get("hoja") or
                             f"CUENTAS X PAGAR AL {fecha:%d-%m-%Y}")[:31], 0)
    libro.active = 0
    ws.sheet_view.tabSelected = True
    fino = Side(style="thin", color="000000")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    gris = PatternFill("solid", fgColor="C0C0C0")
    gris2 = PatternFill("solid", fgColor="969696")
    azul = PatternFill("solid", fgColor="99CCFF")
    sub = PatternFill("solid", fgColor="FFCC00")
    pesos = '_-$* #,##0.00_-;"-$"* #,##0.00_-;_-$* "-"??_-;_-@_-'

    def put(f, c, valor=None, negrita=False, tam=11, relleno=None,
            formato=None, alin=None, ajustar=False, color="000000",
            con_borde=True):
        celda = ws.cell(f, c)
        if valor is not None:
            celda.value = valor
        celda.font = Font(name="Calibri", size=tam, bold=negrita,
                          color=color)
        if con_borde:
            celda.border = borde
        if relleno is not None:
            celda.fill = relleno
        if formato:
            celda.number_format = formato
        celda.alignment = Alignment(horizontal=alin, vertical="center",
                                    wrap_text=ajustar)
        return celda

    nombre_empresa = ctx.get("nombre_empresa", "")
    nit_txt = ctx.get("nit_texto") or (f"(Nit: {ctx['nit']})"
                                        if ctx.get("nit") else "")
    fecha_larga = (f"{MESES_PP[fecha.month - 1].lower()} {fecha.day} de "
                   f"{fecha.year}")
    titulos = [nombre_empresa, nit_txt,
               (f"Planilla para cobros de clientes a {fecha_larga}"
                if cobrar else
                f"Lista de facturas por pagar de acreedores a {fecha_larga}")]
    for f, texto in enumerate(titulos, start=1):
        ws.merge_cells(start_row=f, start_column=1, end_row=f, end_column=6)
        for c in range(1, 7):
            put(f, c, relleno=gris, con_borde=False)
        put(f, 1, texto, True, 22, gris, alin="center", con_borde=False)
    for c, t in enumerate([f"DATOS DEL {quien}", "NUMERO DE DOCUMENTO",
                           "FECHA EMISION", "FECHA VENCIMIENTO",
                           f"LO QUE SE {'COBRA' if cobrar else 'PAGA'}",
                           "OBSERVACIONES"], start=1):
        put(4, c, t, True, 11, azul if c == 6 else gris2, alin="center",
            ajustar=True)
    fila = 5
    filas_total = []
    incluidas = [p for p in orden_cxp(partidas) if p.get("incluir")]
    for prov, lista in groupby_proveedor(incluidas).items():
        inicio = fila
        put(fila, 1, lista[0]["proveedor"], alin="left")
        for c in range(2, 7):
            put(fila, c)
        fila += 1
        primera = fila
        fila_de = {}
        for p in lista:
            put(fila, 1)
            put(fila, 2, p["numero"])
            for c, campo in ((3, "fecha"), (4, "vence")):
                v = p.get(campo)
                # v6.10: fecha incompleta de HELISA: se escribe tal cual.
                put(fila, c, (f"{v.day:02d}/{MES_ABR_PP[v.month - 1]}/"
                              f"{v.year}") if v else
                    (p.get(f"{campo}_texto") or None))
            valor = float(p.get("pagar") if p.get("pagar") is not None
                          else p["valor"])
            put(fila, 5, valor, formato=pesos,
                color="FF0000" if valor < 0 else "000000")
            put(fila, 6, p.get("obs") or None, color="FF0000", alin="left",
                ajustar=True)
            fila_de[p["id"]] = fila
            fila += 1
        ultima = fila - 1
        if ultima > inicio:
            ws.merge_cells(start_row=inicio, start_column=1, end_row=ultima,
                           end_column=1)
        ws.cell(inicio, 1).alignment = Alignment(horizontal="left",
                                                 vertical="top",
                                                 wrap_text=True)
        # Observaciones que en la anterior cubrian varias facturas.
        grupos = defaultdict(list)
        for p in lista:
            if p.get("grupo_obs") is not None:
                grupos[p["grupo_obs"]].append(fila_de[p["id"]])
        for filas_g in grupos.values():
            filas_g.sort()
            if len(filas_g) < 2:
                continue
            # Se combina de la primera a la ultima factura del grupo; los
            # documentos nuevos que quedan en medio quedan cubiertos si no
            # tienen observacion propia.
            rango = range(filas_g[0], filas_g[-1] + 1)
            propias = [r for r in rango if r not in filas_g and
                       ws.cell(r, 6).value]
            if propias:
                continue
            texto = next((ws.cell(r, 6).value for r in filas_g
                          if ws.cell(r, 6).value), None)
            for r in rango:
                ws.cell(r, 6).value = None
            ws.cell(filas_g[0], 6).value = texto
            ws.merge_cells(start_row=filas_g[0], start_column=6,
                           end_row=filas_g[-1], end_column=6)
        for c in range(1, 6):
            put(fila, c, relleno=sub, negrita=True)
        put(fila, 4, f"Total a {verbo} a {lista[0]['proveedor']}", True,
            relleno=sub, alin="right")
        put(fila, 5, f"=SUM(E{primera}:E{ultima})", True, relleno=sub,
            formato=pesos, alin="right")
        put(fila, 6)
        filas_total.append(fila)
        fila += 1
    # v6.10: secciones que no salen de HELISA (EMPRESA F: SEGURIDAD SOCIAL,
    # IMPUESTOS, PAGOS FIJOS), con los valores revisados en la pantalla.
    def fecha_txt(item):
        v = item.get("fecha")
        if isinstance(v, datetime.date):
            return f"{v.day:02d}/{MES_ABR_PP[v.month - 1]}/{v.year}"
        return item.get("fecha_texto") or None

    secciones = OrderedDict()
    for m in ctx.get("manuales") or []:
        if m.get("incluir", True):
            secciones.setdefault(m.get("seccion") or "OTROS", []).append(m)
    for nombre_sec, items in secciones.items():
        inicio = fila
        for k, m in enumerate(items):
            put(fila, 1, nombre_sec if k == 0 else None, alin="left")
            put(fila, 2, m.get("descripcion"), alin="left", ajustar=True)
            put(fila, 3, fecha_txt(m))
            put(fila, 4)
            put(fila, 5, float(m.get("valor") or 0), formato=pesos)
            put(fila, 6, m.get("obs") or None, color="FF0000", alin="left",
                ajustar=True)
            fila += 1
        if fila - 1 > inicio:
            ws.merge_cells(start_row=inicio, start_column=1, end_row=fila - 1,
                           end_column=1)
        ws.cell(inicio, 1).alignment = Alignment(horizontal="left",
                                                 vertical="top",
                                                 wrap_text=True)
        for c in range(1, 6):
            put(fila, c, relleno=sub, negrita=True)
        put(fila, 4, f"Total {nombre_sec.lower()}", True, relleno=sub,
            alin="right")
        put(fila, 5, f"=SUM(E{inicio}:E{fila - 1})", True, relleno=sub,
            formato=pesos, alin="right")
        put(fila, 6)
        filas_total.append(fila)
        fila += 1
    fila += 4 if not secciones else 1
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
    for c in range(1, 6):
        put(fila, c, relleno=sub, con_borde=False)
    etiqueta_total = ctx.get("total_label") or \
        f"CUENTAS PENDIENTES POR PAGAR AL {fecha:%d-%m-%Y}"
    put(fila, 1, etiqueta_total, True,
        18, sub, alin="center", ajustar=True, con_borde=False)
    put(fila, 5, "=" + "+".join(f"E{r}" for r in filas_total) if filas_total
        else 0, True, 18, sub, pesos, con_borde=False)
    ws.row_dimensions[fila].height = 48
    # v6.10: anticipos pendientes por legalizar (se copian de la anterior).
    anticipos = [a for a in (ctx.get("anticipos") or [])
                 if a.get("incluir", True)]
    if anticipos:
        fila += 3
        put(fila, 1, anticipos[0].get("titulo") or
            "ANTICIPOS PENDIENTES POR LEGALIZAR", True, 12, gris,
            alin="left", con_borde=False)
        fila += 1
        for c, t in enumerate([f"DATOS DEL {quien}", "NUMERO DE DOCUMENTO",
                               "FECHA EMISION", "FECHA VENCIMIENTO",
                               "VALOR", "OBSERVACIONES"], start=1):
            put(fila, c, t, True, 11, azul if c == 6 else gris2,
                alin="center", ajustar=True)
        fila += 1
        totales_ant = []
        por_tercero = OrderedDict()
        for a in anticipos:
            por_tercero.setdefault(a.get("tercero") or "", []).append(a)
        for tercero, items in por_tercero.items():
            inicio = fila
            for k, a in enumerate(items):
                put(fila, 1, tercero if k == 0 else None, alin="left",
                    ajustar=True)
                put(fila, 2, a.get("numero"))
                put(fila, 3, fecha_txt(a))
                put(fila, 4)
                put(fila, 5, float(a.get("valor") or 0), formato=pesos)
                put(fila, 6, a.get("obs") or None, color="FF0000",
                    alin="left", ajustar=True)
                fila += 1
            for c in range(1, 6):
                put(fila, c, relleno=sub, negrita=True)
            put(fila, 4, "Total", True, relleno=sub, alin="right")
            put(fila, 5, f"=SUM(E{inicio}:E{fila - 1})", True, relleno=sub,
                formato=pesos, alin="right")
            put(fila, 6)
            totales_ant.append(fila)
            fila += 1
        fila += 1
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila,
                       end_column=4)
        for c in range(1, 6):
            put(fila, c, relleno=sub, con_borde=False)
        put(fila, 1, f"ANTICIPOS PENDIENTES POR LEGALIZAR AL "
                     f"{fecha:%d-%m-%Y}", True, 14, sub, alin="center",
            ajustar=True, con_borde=False)
        put(fila, 5, "=" + "+".join(f"E{r}" for r in totales_ant), True, 14,
            sub, pesos, con_borde=False)
    for letra, ancho in {"A": 39.2, "B": 20.7, "C": 12.4, "D": 12.3,
                         "E": 25.6, "F": 42.4}.items():
        ws.column_dimensions[letra].width = ancho
    ws.freeze_panes = "A5"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "4:4"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def resumen_cxp(partidas, fecha=None):
    fecha = fecha or datetime.date.today()
    incluidas = [p for p in partidas if p.get("incluir")]
    return {"incluidas": len(incluidas),
            "excluidas": len(partidas) - len(incluidas),
            "proveedores": len(groupby_proveedor(incluidas)),
            "total": round(sum(p.get("pagar") or 0 for p in incluidas), 2),
            "vencido": round(sum(p.get("pagar") or 0 for p in incluidas
                                 if p.get("vence") and
                                 p["vence"] < fecha), 2)}
