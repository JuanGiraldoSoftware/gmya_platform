"""Grupos de cotejo y textos para el visor de diferencias bancarias.

Depende de: gmya.comun.numeros, gmya.ui.visor, gmya.modulos.bancos.sugerencias, gmya.modulos.bancos.excel
"""

import html
import re

from gmya.comun.numeros import formato_cop
from gmya.ui.visor import PALETA_COTEJOS, VERDE_CONCILIADA
from gmya.modulos.bancos.sugerencias import CONFIANZA_ORDEN
from gmya.modulos.bancos.excel import (
    ACCIONES_PARTIDA, ESTADOS_PARTIDA, partidas_cruce,
)


def grupos_cotejo(analisis, incluir_conciliadas=False):
    """
    Agrupa las partidas que se cotejaron entre si (una sugerencia junta
    las partidas del extracto y de HELISA que explica). A cada grupo le da
    un numero y un color, y los anota en cada movimiento (_etiqueta,
    _color) para pintarlos igual en los dos documentos.
    """
    diferencias = diferencias_para_visor(analisis)
    grupos, vistos = [], {}
    for p in diferencias:
        sug = max(p["sugerencias"],
                  key=lambda s: CONFIANZA_ORDEN[s["confianza"]]) \
            if p["sugerencias"] else None
        clave = sug["id"] if sug else id(p)
        if clave in vistos:
            continue
        extracto = list(sug["extracto"]) if sug and sug["extracto"] else \
            ([p["e"]] if p["e"] is not None else [])
        libro = list(sug["libro"]) if sug and sug["libro"] else list(p["l"])
        if p["e"] is not None and p["e"] not in extracto:
            extracto.insert(0, p["e"])
        for l in p["l"]:
            if l not in libro:
                libro.append(l)
        numero = len(grupos) + 1
        if extracto and libro:
            estado = ("VALOR DIFERENTE" if p["estado"] in (
                "diferencia", "agrupado_diferencia") else
                "EN LOS DOS DOCUMENTOS")
        elif extracto:
            estado = "NO ESTÁ EN HELISA"
        else:
            estado = "NO ESTÁ EN EL EXTRACTO"
        grupo = {
            "numero": numero, "etiqueta": str(numero),
            "color": PALETA_COTEJOS[(numero - 1) % len(PALETA_COTEJOS)],
            "estado": estado,
            "tipo": sug["tipo"] if sug else "",
            "extracto": extracto, "libro": libro,
            "sugerencia": sug, "partida": p,
        }
        vistos[clave] = grupo
        grupos.append(grupo)
    if incluir_conciliadas:
        n, conjuntos = 0, {}
        for p in partidas_cruce(analisis):
            if ESTADOS_PARTIDA[p["estado"]][1] != "verde":
                continue
            if p["conjunto"]:
                # Varios cargos del banco contra un solo registro de HELISA
                clave = tuple(p["e"]["pareja"])
                if clave in conjuntos:
                    conjuntos[clave]["extracto"].append(p["e"])
                    continue
            n += 1
            grupo = {
                "numero": None, "etiqueta": f"C{n}",
                "color": VERDE_CONCILIADA,
                "estado": ESTADOS_PARTIDA[p["estado"]][0], "tipo": "",
                "extracto": [p["e"]] if p["e"] is not None else [],
                "libro": list(p["l"]), "sugerencia": None, "partida": p,
            }
            if p["conjunto"]:
                conjuntos[tuple(p["e"]["pareja"])] = grupo
            grupos.append(grupo)
    for m in analisis["movs"] + analisis["libro_movs"]:
        m.pop("_color", None)
        m.pop("_etiqueta", None)
    for g in grupos:
        for m in g["extracto"] + g["libro"]:
            if "_etiqueta" in m:
                continue
            m["_color"] = g["color"]
            m["_etiqueta"] = g["etiqueta"]
    return grupos


def diferencias_para_visor(analisis):
    """Lista ordenada de partidas que no cuadran (para recorrer una a una)."""
    filas = partidas_cruce(analisis)
    return [p for p in filas if ESTADOS_PARTIDA[p["estado"]][1] != "verde"]


def _corto(texto, maximo=420):
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    return texto if len(texto) <= maximo else texto[:maximo - 1] + "…"


def texto_cotejo(grupo):
    """HTML de la explicacion de un cotejo (para el globo del visor)."""
    e = html.escape
    sug = grupo.get("sugerencia")
    partes = [f"<b>{e(grupo['etiqueta'])} · {e(grupo['estado'])}</b>"
              + (f" · {e(grupo['tipo'])}" if grupo.get("tipo") else "")]
    lineas = []
    for m in grupo["extracto"][:4]:
        lineas.append(f"Extracto {m['fecha']:%d/%m}: "
                      f"{e(_corto(m.get('descripcion', ''), 60))} "
                      f"{formato_cop(m['valor'])}")
    for l in grupo["libro"][:4]:
        lineas.append(f"HELISA {l['fecha']:%d/%m}: {e(l.get('tipo', ''))} "
                      f"{e(str(l.get('numero', '')))} "
                      f"{e(_corto(l.get('tercero', ''), 40))} "
                      f"{formato_cop(l['valor'])}")
    extra = len(grupo["extracto"]) + len(grupo["libro"]) - len(lineas)
    if extra > 0:
        lineas.append(f"… y {extra} partida(s) más")
    if not grupo["extracto"]:
        lineas.append("<i>No aparece en el extracto.</i>")
    if not grupo["libro"]:
        lineas.append("<i>No aparece en HELISA.</i>")
    partes.append("<br>".join(lineas))
    if sug:
        if sug.get("que_no_cuadra"):
            partes.append(f"<b>Qué no cuadra:</b> "
                          f"{e(_corto(sug['que_no_cuadra']))}")
        partes.append(f"<b>Posible causa ({e(sug['confianza'])}):</b> "
                      f"{e(_corto(sug['explicacion']))}")
        partes.append(f"<b>Qué hacer:</b> {e(_corto(sug['accion'], 300))}")
    elif grupo["numero"] is None:
        partes.append("Conciliada: el valor del extracto y el de HELISA "
                      "coinciden.")
    else:
        partes.append("<b>Qué hacer:</b> "
                      + e(ACCIONES_PARTIDA.get(grupo["partida"]["estado"],
                                               "Revisar el soporte.")))
    return "<br>".join(partes)


def tips_cotejos(grupos):
    """{etiqueta del cotejo: html de la explicacion}."""
    return {g["etiqueta"]: texto_cotejo(g) for g in grupos}
