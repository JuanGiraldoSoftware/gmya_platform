"""Acuses de recibo (eventos RADIAN) de facturas de compra.

Contrato:
  asignar_acuses_detalle(reporte, facturas, parametros) -> asigna los eventos a cada factura de forma
      consecutiva por factura (no por prefijo) y marca los faltantes.
  sugerir_prefijos_acuse(...) -> prefijos de eventos posibles.
  explicar_acuse_faltante(...) -> texto de la causa probable.

Depende de: gmya.comun.texto, gmya.modulos.dian.parametros, gmya.modulos.dian.lectura
"""

import datetime
import re
from collections import Counter, OrderedDict, defaultdict

from gmya.comun.texto import comparable, solo_nit
from gmya.modulos.dian.parametros import dato, TIPO_EVENTO
from gmya.modulos.dian.lectura import fecha_dian


# ------------------------------------------------------------
# Acuses (eventos RADIAN emitidos por la empresa)
# ------------------------------------------------------------
def prefijo_folio(folio):
    m = re.match(r"^(.*?)(\d+)$", str(folio or "").strip())
    return m.group(1) if m else str(folio or "")


# v6.9: algunos proveedores de facturacion (p. ej. el de DUMA) arman el folio
# del evento con la factura, el tipo de evento y el NIT del proveedor:
# "FE293RECEIVED901338688" = factura FE293, acuse de recibo. Asi el evento
# se liga a SU factura sin inferir nada.
TIPOS_EVENTO_FOLIO = ("RECEIVED", "SERVICES", "ACCEPTED", "REJECTED",
                      "CLAIM", "TACITACCEPTANCE")
_RE_EVENTO_FOLIO = re.compile(
    r"^(?P<factura>.+?)(?P<tipo>" + "|".join(TIPOS_EVENTO_FOLIO)
    + r")(?P<nit>\d*)$", re.I)


def evento_con_factura(folio):
    """(factura, tipo) si el folio del evento nombra la factura, si no
    None."""
    m = _RE_EVENTO_FOLIO.match(re.sub(r"\s+", "", str(folio or "")))
    if not m:
        return None
    factura = re.sub(r"[^A-Z0-9]", "", m.group("factura").upper())
    return (factura, m.group("tipo").upper()) if factura else None


def _momento_dian(reporte, registro):
    """Fecha y hora del documento (la Fecha Recepcion trae la hora)."""
    texto = str(dato(reporte, registro, "Fecha Recepción") or "").strip()
    try:
        return datetime.datetime.fromisoformat(texto[:19])
    except ValueError:
        pass
    f = fecha_dian(dato(reporte, registro, "Fecha Emisión"))
    return datetime.datetime.combine(f, datetime.time()) if f else None


def eventos_de_reporte(reporte, origen="reporte"):
    """
    Eventos (Application response) que la EMPRESA emitio a sus proveedores
    (Grupo = Emitido). Los rechazados no cuentan como acuse.
    """
    salida = []
    for r in reporte["registros"]:
        if comparable(dato(reporte, r, "Tipo de documento")) != \
                comparable(TIPO_EVENTO):
            continue
        if comparable(dato(reporte, r, "Grupo")) != "EMITIDO":
            continue
        if "RECHAZ" in comparable(dato(reporte, r, "Estado")):
            continue
        folio = (str(dato(reporte, r, "Prefijo") or "").strip()
                 + str(dato(reporte, r, "Folio") or "").strip())
        momento = _momento_dian(reporte, r)
        ligado = evento_con_factura(folio)
        salida.append({
            "cude": str(dato(reporte, r, "CUFE/CUDE") or "").strip(),
            "nit": solo_nit(dato(reporte, r, "NIT Receptor")),
            "nombre": str(dato(reporte, r, "Nombre Receptor") or ""),
            "folio": folio,
            # Con la factura en el folio, el "prefijo" es el tipo de
            # evento (RECEIVED, SERVICES, ACCEPTED).
            "prefijo": ligado[1] if ligado else prefijo_folio(folio),
            "factura": ligado[0] if ligado else None,
            "fecha": fecha_dian(dato(reporte, r, "Fecha Emisión"))
            or (momento.date() if momento else None),
            "momento": momento, "origen": origen,
        })
    return salida


def eventos_emitidos(reporte):
    """Eventos del reporte DIAN mas los de reportes posteriores cargados
    solo para acuses (reporte['eventos_adicionales']), sin repetidos."""
    vistos, salida = set(), []
    for e in eventos_de_reporte(reporte) + list(
            reporte.get("eventos_adicionales") or []):
        clave = e["cude"] or (e["folio"], e["nit"])
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(e)
    return salida


def _rafagas_eventos(eventos, minutos=30):
    """Agrupa los eventos de un mismo proveedor emitidos seguidos (el
    acuse y el recibo de una factura se emiten con minutos de
    diferencia)."""
    por_nit = defaultdict(list)
    for e in eventos:
        por_nit[e["nit"]].append(e)
    rafagas = []
    for lista in por_nit.values():
        lista.sort(key=lambda e: (e["momento"] or datetime.datetime.min,
                                  e["folio"]))
        actual = []
        for e in lista:
            if actual and e["momento"] and actual[-1]["momento"] and \
                    (e["momento"] - actual[-1]["momento"]).total_seconds() \
                    <= minutos * 60:
                actual.append(e)
            else:
                if actual:
                    rafagas.append(actual)
                actual = [e]
        if actual:
            rafagas.append(actual)
    return rafagas


def sugerir_prefijos_acuse(reporte):
    """
    Sugerencia automatica de prefijos para ACUSE 1 y ACUSE 2:
      - Se toman los prefijos frecuentes de los eventos emitidos.
      - El orden sale de como se emiten: para cada factura primero va el
        acuse de recibo (ACUSE 1) y luego el recibo del bien o servicio
        (ACUSE 2).
      - Si la empresa usa UN solo consecutivo para todos los eventos y
        los emite de a dos por factura, el mismo prefijo sirve para los
        dos acuses (el primero de la pareja es el ACUSE 1).
    Devuelve [prefijo_1, prefijo_2] (None donde no hay sugerencia).
    """
    eventos = eventos_emitidos(reporte)
    conteo = Counter(e["prefijo"] for e in eventos if e["prefijo"])
    if not conteo:
        return [None, None]
    # v6.9: eventos que nombran la factura: ACUSE 1 = acuse de recibo
    # (RECEIVED) y ACUSE 2 = recibo del bien o servicio (SERVICES).
    if any(e.get("factura") for e in eventos):
        return [p if p in conteo else None
                for p in ("RECEIVED", "SERVICES")]
    rafagas = _rafagas_eventos(eventos)
    posicion = defaultdict(list)
    for rafaga in rafagas:
        for i, e in enumerate(rafaga):
            posicion[e["prefijo"]].append(i)

    def media(p):
        return sum(posicion[p]) / len(posicion[p]) if posicion[p] else 9

    # Los dos prefijos mas usados; entre ellos, el que se emite primero
    # para cada factura es el ACUSE 1.
    frecuentes = sorted(conteo, key=lambda p: (-conteo[p], media(p), p))[:2]
    frecuentes = [p for p in frecuentes
                  if conteo[p] >= 0.25 * conteo[frecuentes[0]]]
    orden = sorted(frecuentes, key=lambda p: (media(p), len(p), p))
    if len(orden) >= 2:
        return orden[:2]
    unico = orden[0]
    en_parejas = sum(len(r) for r in rafagas if len(r) >= 2
                     and all(e["prefijo"] == unico for e in r))
    if en_parejas >= 0.5 * conteo[unico]:
        return [unico, unico]
    return [unico, None]


def prefijos_eventos(reporte):
    """Prefijos de folio de los eventos emitidos, con su cantidad: primero
    los sugeridos para los acuses y luego los demas."""
    conteo = Counter(e["prefijo"] for e in eventos_emitidos(reporte)
                     if e["prefijo"])
    sugeridos = [p for p in dict.fromkeys(sugerir_prefijos_acuse(reporte))
                 if p]
    resto = sorted((p for p in conteo if p not in sugeridos),
                   key=lambda p: (-conteo[p], p))
    return [(p, conteo[p]) for p in sugeridos + resto]


def asignar_acuses_detalle(reporte, facturas, parametros):
    """
    Como se determinan los acuses de una factura a CREDITO
    (Forma de Pago 2 en el reporte DIAN):
      1. Se toman los eventos (Application response) EMITIDOS por la
         empresa, del reporte DIAN y de los reportes posteriores cargados
         para acuses; los rechazados no cuentan.
      2. El reporte DIAN no dice a que factura corresponde cada evento
         (no trae el CUFE de la factura), por eso el cruce es por
         proveedor: NIT Receptor del evento = NIT Emisor de la factura.
      3. La clase de acuse se reconoce por el prefijo del folio del
         evento (p. ej. RFE = acuse de recibo, RFSM = recibo del bien).
         Si el prefijo de ACUSE 1 y ACUSE 2 es el mismo (un solo
         consecutivo), cada factura toma dos eventos seguidos.
      4. Un evento solo puede ser de una factura emitida el mismo dia o
         antes del evento. Cada evento se usa una sola vez; si un
         proveedor tiene varias facturas, a cada una se le asigna el
         primer evento libre posterior a su fecha.
    Devuelve {"marcas": {id(factura): ["OK"/"NO"/"", x3]},
              "eventos": {id(factura): [evento o None, x3]},
              "libres": [eventos sin factura], "corte": fecha del ultimo
              evento o descarga, "proveedores": {nit: [eventos]}}.
    """
    prefijos = [parametros.get("prefijo_acuse_1"),
                parametros.get("prefijo_acuse_2"),
                parametros.get("prefijo_acuse_3")]
    eventos = eventos_emitidos(reporte)
    por_clave = defaultdict(list)
    proveedores = defaultdict(list)
    for e in eventos:
        por_clave[(e["nit"], e["prefijo"])].append(e)
        proveedores[e["nit"]].append(e)
    for lista in por_clave.values():
        lista.sort(key=lambda e: (e["momento"] or datetime.datetime.min,
                                  e["folio"]))

    formas = {str(k): v for k, v in parametros["formas_pago"].items()}
    marcas, asignados = {}, {}
    usados = set()

    def forma_de(f):
        return formas.get(str(dato(reporte, f, "Forma de Pago")).strip(), "")

    for factura in facturas:
        forma = forma_de(factura)
        if forma != "CREDITO":
            marcas[id(factura)] = [forma or "", forma or "", forma or ""]

    credito = [f for f in facturas if forma_de(f) == "CREDITO"]
    # De la mas reciente a la mas antigua: la factura mas nueva tiene menos
    # eventos posibles (solo los de su fecha en adelante) y escoge primero;
    # los eventos mas antiguos quedan para las facturas mas antiguas.
    credito.sort(key=lambda f: (
        fecha_dian(dato(reporte, f, "Fecha Emisión")) or datetime.date.min,
        str(dato(reporte, f, "Folio"))), reverse=True)
    for factura in credito:
        asignados[id(factura)] = [None, None, None]

    # v6.9: eventos que nombran su factura en el folio: se asignan directo
    # a esa factura (mismo proveedor y mismo prefijo+folio), sin inferir.
    ligados = defaultdict(list)
    for e in eventos:
        if e.get("factura"):
            ligados[(e["nit"], e["factura"], e["prefijo"])].append(e)
    if ligados:
        for factura in credito:
            nit = solo_nit(dato(reporte, factura, "NIT Emisor"))
            numero_f = re.sub(r"[^A-Z0-9]", "", (
                str(dato(reporte, factura, "Prefijo") or "")
                + str(dato(reporte, factura, "Folio") or "")).upper())
            for k, prefijo in enumerate(prefijos):
                if not prefijo:
                    continue
                for e in ligados.get((nit, numero_f, prefijo), []):
                    if id(e) not in usados:
                        usados.add(id(e))
                        asignados[id(factura)][k] = e
                        break

    # Columnas por prefijo: con un solo consecutivo (mismo prefijo en
    # ACUSE 1 y 2) cada factura toma eventos seguidos, uno por columna.
    # Los eventos que nombran OTRA factura no se usan para esta.
    columnas = OrderedDict()
    for k, prefijo in enumerate(prefijos):
        if prefijo:
            columnas.setdefault(prefijo, []).append(k)
    for prefijo, ks in columnas.items():
        for factura in credito:
            nit = solo_nit(dato(reporte, factura, "NIT Emisor"))
            fecha_f = fecha_dian(dato(reporte, factura, "Fecha Emisión"))
            libres = [e for e in por_clave.get((nit, prefijo), [])
                      if id(e) not in usados and not e.get("factura")
                      and not (fecha_f and e["fecha"]
                               and e["fecha"] < fecha_f)]
            vacias = [k for k in ks if asignados[id(factura)][k] is None]
            for k, elegido in zip(vacias, libres):
                usados.add(id(elegido))
                asignados[id(factura)][k] = elegido

    for factura in credito:
        marcas[id(factura)] = [
            "" if not prefijos[k] else
            ("OK" if asignados[id(factura)][k] else "NO") for k in range(3)]

    fechas = [e["fecha"] for e in eventos if e["fecha"]]
    corte = max(fechas + ([reporte["fecha_descarga"]]
                          if reporte.get("fecha_descarga") else []),
                default=None)
    libres = [e for e in eventos if id(e) not in usados]
    return {"marcas": marcas, "eventos": asignados, "libres": libres,
            "corte": corte, "proveedores": dict(proveedores),
            "prefijos": prefijos,
            "hay_posteriores": bool(reporte.get("eventos_adicionales"))}


def asignar_acuses(reporte, facturas, parametros):
    """{id(factura): ["OK"/"NO"/"", ...]} (ver asignar_acuses_detalle)."""
    return asignar_acuses_detalle(reporte, facturas, parametros)["marcas"]


def explicar_acuse_faltante(info, reporte, factura, k):
    """Por que una factura a credito quedo sin el ACUSE k+1."""
    if not info:
        return ""
    prefijo = info["prefijos"][k]
    nit = solo_nit(dato(reporte, factura, "NIT Emisor"))
    fecha_f = fecha_dian(dato(reporte, factura, "Fecha Emisión"))
    del_nit = info["proveedores"].get(nit, [])
    mismos = [e for e in del_nit if e["prefijo"] == prefijo]
    numero_f = re.sub(r"[^A-Z0-9]", "", (
        str(dato(reporte, factura, "Prefijo") or "")
        + str(dato(reporte, factura, "Folio") or "")).upper())
    propios = [e for e in del_nit if e.get("factura") == numero_f]
    if any(e.get("factura") for e in del_nit):
        # v6.9: los eventos nombran la factura: la causa es exacta.
        if propios:
            tipos = sorted({e["prefijo"] for e in propios})
            texto = (f"la factura {numero_f} tiene eventos "
                     f"{', '.join(tipos)} pero no {prefijo}")
        else:
            texto = (f"no hay ningún evento que nombre la factura "
                     f"{numero_f} en el reporte")
    elif not del_nit:
        texto = "no hay ningún evento emitido a este proveedor en el reporte"
    elif not mismos:
        otros = sorted({e["prefijo"] for e in del_nit})
        texto = (f"hay eventos a este proveedor pero con otro prefijo "
                 f"({', '.join(otros)}): revisar los prefijos de acuses")
    else:
        anteriores = [e for e in mismos if fecha_f and e["fecha"]
                      and e["fecha"] < fecha_f]
        if len(anteriores) == len(mismos):
            texto = ("los eventos a este proveedor son anteriores a la "
                     "factura (son de otras facturas)")
        else:
            texto = ("los eventos a este proveedor ya quedaron asignados a "
                     "otras facturas suyas")
            # v6.7: el reporte DIAN no liga evento con factura: si el
            # proveedor tiene varias facturas a credito y faltan eventos,
            # el NO puede corresponder a otra de sus facturas.
            texto += (f" (ASIGNACIÓN INCIERTA: {len(mismos)} evento"
                      f"{'' if len(mismos) == 1 else 's'} con prefijo "
                      f"{prefijo} para varias facturas de este proveedor; "
                      "confirmar en el portal DIAN cuál factura no tiene el "
                      "acuse)")
    if info.get("corte") and fecha_f and \
            (info["corte"] - fecha_f).days <= 5:
        texto += (f"; la factura es de los últimos días del reporte (eventos "
                  f"hasta {info['corte']:%d/%m/%Y}): el acuse pudo emitirse "
                  "después, carga un reporte DIAN posterior en 'Eventos "
                  "posteriores'")
    return texto
