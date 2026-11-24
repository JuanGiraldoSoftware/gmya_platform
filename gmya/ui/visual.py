"""Piezas visuales de la plataforma (v6.13): iconos, indicadores (KPI),
panel de resumen oscuro con dona y graficos sencillos en SVG/HTML.

Todo es HTML generado aqui (sin dependencias nuevas ni internet): se
muestra con st.markdown y toma los estilos de gmya/ui/estilos.py (clases
gm-kpi*, gm-panel*, gm-graf*). Los colores de los graficos salen de las
variables del sistema de diseno.

Contrato:
  icono(nombre, tam=20) -> <svg> de trazo (currentColor). ICONOS: nombres.
  html_kpis(items, columnas=4) -> fila de indicadores. Cada item:
      {"etiqueta", "valor", "icono", "tono", "detalle"?, "estado"?}
      tono: magenta | indigo | teal | ambar | verde | pizarra | carbon
      estado (opcional): ok | alerta | error -> insignia con icono y texto.
  kpis(items, columnas=4) -> lo muestra.
  html_panel_resumen(titulo, subtitulo, segmentos, centro, centro_sub,
      datos=()) -> panel oscuro con dona + leyenda (+ datos a la derecha).
      segmentos: [(etiqueta, cantidad, estado)] con estado ok | alerta |
      error | info | neutro (colores validados para el fondo oscuro).
  panel_resumen(...) -> lo muestra.
  html_barras(datos, unidad="", maximo=None) -> barras horizontales.
  html_area(serie, unidad="") -> serie diaria (area + linea) con globos.
  grafico(titulo, cuerpo_html, nota="") -> tarjeta con titulo y grafico.
Reglas: los numeros llevan siempre su texto (la dona tiene leyenda con
cantidad y %); el color nunca es la unica senal.

  v6.16: html_antiguedad(tramos, nota) (cartera / cuentas por pagar por
      tramo de vencimiento), html_comparativo(filas, a, b) (dos series por
      fila, p. ej. DIAN vs HELISA o a pagar vs disponible), html_puente(pasos)
      (puente / cascada horizontal: de un saldo a otro con cada ajuste).
      Los % de dona y leyendas suman 100 (mayor residuo) y nunca dicen 0 %
      para una cantidad distinta de cero.
Depende de: gmya.comun.estadistica (y streamlit)
"""

import html
import math

import streamlit as st

from gmya.comun.estadistica import porcentajes, texto_porcentaje
from gmya.comun.numeros import a_centavos

# ------------------------------------------------------------------
# Iconos (trazo 1.75, 24x24, propios; inspirados en la linea de Lucide)
# ------------------------------------------------------------------
ICONOS = {
    "inicio": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "buscar": '<circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4.5 4.5"/>',
    "personas": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M16.2 14.6c2.5.2 4.4 1.9 5.1 4.9"/>',
    "banco": '<path d="M3 9.5 12 4l9 5.5"/><path d="M4 20h16"/><path d="M6 11v6M10 11v6M14 11v6M18 11v6"/>',
    "recibo": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    "pagos": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><circle cx="16.5" cy="14.5" r="1.2"/>',
    "subir": '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
    "nomina": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2.5"/><path d="M5.5 17c.6-1.9 1.9-3 3.5-3s2.9 1.1 3.5 3"/><path d="M14 10h4M14 13.5h4"/>',
    "grafico": '<path d="M3 20h18"/><path d="M6 20V11M11 20V5M16 20v-7M20 20v-4"/>',
    "archivo": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
    "capas": '<path d="m12 3-9 5 9 5 9-5z"/><path d="m3 13 9 5 9-5"/>',
    "ok": '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.8 2.8L16.5 9.5"/>',
    "alerta": '<path d="M12 3.5 2.8 19.5h18.4z"/><path d="M12 10v4.2"/><path d="M12 17.2v.1"/>',
    "error": '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    "reloj": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "dinero": '<circle cx="12" cy="12" r="9"/><path d="M14.6 9.3c-.6-.8-1.5-1.3-2.6-1.3-1.5 0-2.6.8-2.6 2s1.1 1.7 2.6 2 2.7.9 2.7 2.1-1.2 2-2.7 2c-1.2 0-2.2-.5-2.8-1.4M12 6.5V8M12 16v1.5"/>',
    "balanza": '<path d="M12 4v16M6 20h12M5 8h14"/><path d="m5 8-2.5 6a2.5 2.5 0 0 0 5 0zM19 8l-2.5 6a2.5 2.5 0 0 0 5 0z"/>',
    "bicho": '<rect x="7.5" y="8" width="9" height="12" rx="4.5"/><path d="M12 8v12M7.5 13H4M20 13h-3.5M8 10 5 7.5M16 10l3-2.5M8 17l-3 2.5M16 17l3 2.5M9.5 8.2 8.5 5.5M14.5 8.2l1-2.7"/>',
    "usuario": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4.2-6 8-6s7 2 8 6"/>',
    "rayo": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "escudo": '<path d="M12 3 4 6v6c0 4.5 3.4 7.7 8 9 4.6-1.3 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "documentos": '<path d="M8 3h7l4 4v11H8z"/><path d="M15 3v4h4"/><path d="M5 7v14h11"/>',
}


def icono(nombre, tam=20, grosor=1.75):
    cuerpo = ICONOS.get(nombre) or ICONOS["archivo"]
    return (f'<svg class="gm-ico-svg" width="{tam}" height="{tam}" '
            f'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{grosor}" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{cuerpo}</svg>')


TONOS = ("magenta", "indigo", "teal", "ambar", "verde", "pizarra", "carbon")
ESTADOS = {"ok": ("ok", "Cuadra"), "alerta": ("alerta", "Revisar"),
           "error": ("error", "Pendiente")}


def _e(texto):
    return html.escape(str(texto), quote=False)


def _insignia(estado, texto=None):
    if not estado:
        return ""
    ico, defecto = ESTADOS.get(estado, ("alerta", "Revisar"))
    return (f'<span class="gm-insignia {estado}">{icono(ico, 13, 2)}'
            f'{_e(texto or defecto)}</span>')


def html_kpis(items, columnas=4):
    tarjetas = []
    for it in items:
        tono = it.get("tono") if it.get("tono") in TONOS else "magenta"
        detalle = (f'<div class="gm-kpi-det">{it["detalle"]}</div>'
                   if it.get("detalle") else "")
        tarjetas.append(
            f'<div class="gm-kpi">'
            f'<div class="gm-kpi-cab"><span class="gm-kpi-ico t-{tono}">'
            f'{icono(it.get("icono") or "grafico", 18)}</span>'
            f'<span class="gm-kpi-et">{_e(it["etiqueta"])}</span>'
            f'{_insignia(it.get("estado"), it.get("estado_texto"))}</div>'
            f'<div class="gm-kpi-val">{_e(it["valor"])}</div>{detalle}</div>')
    return (f'<div class="gm-kpis" style="--gm-cols:{int(columnas)}">'
            + "".join(tarjetas) + "</div>")


def kpis(items, columnas=4):
    st.markdown(html_kpis(items, columnas), unsafe_allow_html=True)


# Colores de estado validados sobre el fondo oscuro #1C1A1C (separacion
# para daltonismo >= 7,8 en pares vecinos; siempre con leyenda de texto).
COLOR_ESTADO_OSCURO = {"ok": "#1FA35F", "alerta": "#C27C10",
                       "info": "#7380EE", "error": "#E65A50",
                       "neutro": "#5E585B"}


def _dona(segmentos, centro, centro_sub, tam=168, grosor=18):
    total = sum(max(0, n) for _, n, _ in segmentos)
    r = (tam - grosor) / 2
    c = tam / 2
    circ = 2 * math.pi * r
    partes = [f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" '
              f'stroke="rgba(255,255,255,.08)" stroke-width="{grosor}"/>']
    if total:
        visibles = [(e, n, s) for e, n, s in segmentos if n > 0]
        pcs = dict(zip(range(len(visibles)), porcentajes(
            [n for _, n, _ in visibles])))
        hueco = 3 if len(visibles) > 1 else 0          # separacion 2-3 px
        inicio = 0.0
        for k, (etiqueta, n, estado) in enumerate(visibles):
            largo = circ * n / total
            trazo = max(largo - hueco, 0.8)
            color = COLOR_ESTADO_OSCURO.get(estado, "#9C9498")
            partes.append(
                f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" '
                f'stroke="{color}" stroke-width="{grosor}" '
                f'stroke-dasharray="{trazo:.2f} {circ - trazo:.2f}" '
                f'stroke-dashoffset="{-inicio:.2f}" '
                f'transform="rotate(-90 {c} {c})">'
                f'<title>{_e(etiqueta)}: {_num(n)} '
                f'({texto_porcentaje(pcs[k], n)})</title>'
                f'</circle>')
            inicio += largo
    return (f'<div class="gm-dona" style="width:{tam}px;height:{tam}px">'
            f'<svg width="{tam}" height="{tam}" viewBox="0 0 {tam} {tam}" '
            f'role="img" aria-label="{_e(centro_sub)}: {_e(centro)}">'
            + "".join(partes) + '</svg>'
            f'<div class="gm-dona-centro"><b>{_e(centro)}</b>'
            f'<span>{_e(centro_sub)}</span></div></div>')


def html_panel_resumen(titulo, subtitulo, segmentos, centro, centro_sub,
                       datos=()):
    pcs = porcentajes([max(0, n) for _, n, _ in segmentos])
    leyenda = "".join(
        f'<li><span class="gm-ley-color" style="background:'
        f'{COLOR_ESTADO_OSCURO.get(estado, "#9C9498")}"></span>'
        f'<span class="gm-ley-et">{_e(etiqueta)}</span>'
        f'<span class="gm-ley-n">{_num(n)} <small>'
        f'({texto_porcentaje(pc, n)})</small></span></li>'
        for (etiqueta, n, estado), pc in zip(segmentos, pcs))
    lado = "".join(
        f'<div class="gm-panel-dato"><span>{_e(e)}</span>'
        f'<b>{_e(v)}</b>{f"<small>{_e(s)}</small>" if s else ""}</div>'
        for e, v, *resto in datos for s in [resto[0] if resto else ""])
    return (f'<div class="gm-panel">'
            f'<div class="gm-panel-cab"><div><div class="gm-panel-tit">'
            f'{_e(titulo)}</div><div class="gm-panel-sub">{_e(subtitulo)}'
            f'</div></div></div>'
            f'<div class="gm-panel-cuerpo">{_dona(segmentos, centro, centro_sub)}'
            f'<ul class="gm-leyenda-dona">{leyenda}</ul>'
            + (f'<div class="gm-panel-datos">{lado}</div>' if lado else "")
            + '</div></div>')


def panel_resumen(*args, **kwargs):
    st.markdown(html_panel_resumen(*args, **kwargs), unsafe_allow_html=True)


def _num(v, unidad=""):
    texto = f"{v:,.0f}".replace(",", ".") if isinstance(v, (int, float)) \
        else str(v)
    return f"{texto}{unidad}"


def html_barras(datos, unidad="", maximo=None):
    """Barras horizontales de una sola serie (magenta de la marca)."""
    datos = [(e, v) for e, v in datos]
    if not datos:
        return '<div class="gm-graf-vacio">Sin datos en el periodo.</div>'
    tope = maximo or max(v for _, v in datos) or 1
    filas = "".join(
        f'<div class="gm-barra-fila" title="{_e(e)}: {_num(v, unidad)}">'
        f'<span class="gm-barra-et">{_e(e)}</span>'
        f'<span class="gm-barra-pista"><span class="gm-barra" '
        f'style="width:{max(v / tope * 100, 1.5 if v else 0):.1f}%"></span>'
        f'</span><span class="gm-barra-v">{_num(v, unidad)}</span></div>'
        for e, v in datos)
    return f'<div class="gm-barras">{filas}</div>'


def html_area(serie, unidad="", alto=240, ancho=640):
    """Serie diaria: area + linea de 2 px, rejilla tenue, etiquetas de eje
    y un punto con globo (<title>) por dia."""
    if not serie:
        return '<div class="gm-graf-vacio">Sin datos en el periodo.</div>'
    izq, der, arr, aba = 34, 10, 10, 24
    w, h = ancho - izq - der, alto - arr - aba
    tope = max(v for _, v in serie) or 1
    paso = 10 ** max(0, len(str(int(tope))) - 1)
    tope = math.ceil(tope / paso) * paso
    n = len(serie)

    def xy(i, v):
        x = izq + (w * i / (n - 1) if n > 1 else w / 2)
        return x, arr + h - h * v / tope

    pts = [xy(i, v) for i, (_, v) in enumerate(serie)]
    linea = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = (f"M{pts[0][0]:.1f},{arr + h} L" + " L".join(
        f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{arr + h} Z")
    rejilla = "".join(
        f'<line x1="{izq}" x2="{izq + w}" y1="{arr + h - h * k / 2:.1f}" '
        f'y2="{arr + h - h * k / 2:.1f}" class="gm-graf-rej"/>'
        f'<text x="{izq - 6}" y="{arr + h - h * k / 2 + 4:.1f}" '
        f'class="gm-graf-eje" text-anchor="end">{_num(tope * k / 2)}</text>'
        for k in (0, 1, 2))
    marcas = sorted({0, n - 1, n // 2} | ({n // 4, 3 * n // 4} if n > 8
                                         else set()))
    ejex = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{alto - 6}" class="gm-graf-eje" '
        f'text-anchor="{"start" if i == 0 else "end" if i == n - 1 else "middle"}">'
        f'{_e(serie[i][0])}</text>' for i in marcas if 0 <= i < n)
    puntos = "".join(
        f'<g class="gm-graf-pto"><circle cx="{x:.1f}" cy="{y:.1f}" r="9" '
        f'class="gm-graf-hit"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" '
        f'class="gm-graf-dot"/><title>{_e(e)}: {_num(v, unidad)}</title></g>'
        for (x, y), (e, v) in zip(pts, serie))
    return (f'<svg class="gm-graf-area" viewBox="0 0 {ancho} {alto}" '
            f'preserveAspectRatio="xMidYMid meet" role="img">{rejilla}'
            f'<path d="{area}" class="gm-graf-relleno"/>'
            f'<polyline points="{linea}" class="gm-graf-linea"/>'
            f'{puntos}{ejex}</svg>')


def grafico(titulo, cuerpo_html, nota="", icono_nombre="grafico"):
    st.markdown(
        f'<div class="gm-graf"><div class="gm-graf-cab">'
        f'<span class="gm-kpi-ico t-magenta">{icono(icono_nombre, 16)}</span>'
        f'<b>{_e(titulo)}</b>'
        + (f'<span class="gm-graf-nota">{_e(nota)}</span>' if nota else "")
        + f'</div>{cuerpo_html}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
# v6.14 · Panel de diferencias (reemplaza al visor como vista principal)
# ------------------------------------------------------------------
# Modelo de datos (lo arman los adaptadores de cada modulo):
#   concepto = {
#     "clave", "nombre", "sub", "lado_a" ("HELISA"), "lado_b" ("DIAN"),
#     "total_a", "total_b",
#     "dona": [(etiqueta, n, estado)], "centro", "centro_sub",
#     "datos": [(etiqueta, valor_texto)],
#     "composicion": [{"etiqueta", "valor" (aporte a A - B), "tipo":
#                      "explicada" | "pendiente", "n"}],
#     "partidas": [{"id", "titulo", "sub", "causa", "tipo": "valor" |
#                   "solo_a" | "solo_b" | "otro", "a", "b", "nota",
#                   "detalle": [(campo, valor_a, valor_b)]}],
#     "grupos": [{"etiqueta", "n", "valor", "nota", "tipo"}],
#   }
# Regla: la suma de la composicion es exactamente total_a - total_b; si no,
# completar_composicion() agrega la fila "Sin explicar" (y se ve).

COLOR_COMPOSICION = {"explicada": "#7380EE", "pendiente": "#C27C10"}
TIPO_PARTIDA = {"valor": ("alerta", "ambar"), "solo_a": ("archivo", "indigo"),
                "solo_b": ("error", "error"), "otro": ("buscar", "pizarra")}


def pesos(v, decimales=True):
    """$1.234.567,89 (sin ,00); negativos con signo menos."""
    if v is None:
        return "—"
    v = float(a_centavos(v))
    texto = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",") \
        .replace("X", ".")
    if texto.endswith(",00") or not decimales:
        texto = texto.rsplit(",", 1)[0]
    return ("-$" if v < -0.004 else "$") + texto


def completar_composicion(c):
    """Agrega 'Sin explicar' si la composicion no suma A - B (centavo)."""
    brecha = round((c.get("total_a") or 0) - (c.get("total_b") or 0), 2)
    suma = round(sum(x["valor"] for x in c.get("composicion", [])), 2)
    resto = round(brecha - suma, 2)
    if abs(resto) >= 0.005:
        c.setdefault("composicion", []).append(
            {"etiqueta": "Sin explicar (la plataforma no encontró la causa)",
             "valor": resto, "tipo": "pendiente", "n": None})
    return c


def pendiente_de(c):
    return round(sum(x["valor"] for x in c.get("composicion", [])
                     if x["tipo"] == "pendiente"), 2)


def html_composicion(c):
    a, b = c.get("lado_a", "HELISA"), c.get("lado_b", "DIAN")
    brecha = round((c.get("total_a") or 0) - (c.get("total_b") or 0), 2)
    filas = [x for x in c.get("composicion", []) if abs(x["valor"]) >= 0.005]
    total_abs = sum(abs(x["valor"]) for x in filas) or 1
    if not filas:
        return (f'<div class="gm-comp gm-comp-ok">{icono("ok", 18)}<div><b>'
                f'{_e(a)} y {_e(b)} cuadran exacto</b><span>{_e(a)} '
                f'{pesos(c.get("total_a"))} = {_e(b)} {pesos(c.get("total_b"))}'
                f'</span></div></div>')
    barra = "".join(
        f'<span title="{_e(x["etiqueta"])}: {pesos(x["valor"])}" '
        f'style="flex:{max(abs(x["valor"]) / total_abs, .006):.4f};'
        f'background:{COLOR_COMPOSICION[x["tipo"]]}"></span>' for x in filas)
    pcs_comp = dict(zip(map(id, filas), porcentajes([x["valor"] for x in filas])))

    def _pc(x):
        return texto_porcentaje(pcs_comp[id(x)], x["valor"])

    def _linea(x):
        ok = x["tipo"] == "explicada"
        n = f' <small>· {x["n"]} doc.</small>' if x.get("n") else ""
        return (f'<div class="gm-comp-fila"><i style="background:'
                f'{COLOR_COMPOSICION[x["tipo"]]}"></i>'
                f'<span>{_e(x["etiqueta"])}{n}</span>'
                f'<span class="gm-insignia {"ok" if ok else "alerta"}">'
                f'{icono("ok" if ok else "alerta", 12, 2)}'
                f'{"Explicada" if ok else "Por revisar"}</span>'
                f'<span class="gm-comp-pc">{_pc(x)}</span>'
                f'<span class="gm-comp-v">{pesos(x["valor"])}</span></div>')
    lineas = "".join(_linea(x) for x in filas)
    pend = pendiente_de(c)
    if c.get("revision"):
        # Revision (programacion de pagos): composicion del total, no A - B.
        lineas = lineas.replace(">Explicada<", ">Sin novedad<").replace(
            ">Por revisar<", ">Por confirmar<")
        return (f'<div class="gm-comp"><div class="gm-comp-cab"><b>¿Cómo se '
                f'compone la programación?</b><span>Total incluido <b>'
                f'{pesos(c.get("total_a"))}</b></span></div>'
                f'<div class="gm-comp-barra">{barra}</div>{lineas}'
                f'<div class="gm-comp-tot"><span>Por confirmar antes de '
                f'enviar</span><b class="{"cero" if abs(pend) < .005 else ""}">'
                f'{pesos(pend)}</b></div></div>')
    return (f'<div class="gm-comp"><div class="gm-comp-cab"><b>¿Qué explica la '
            f'diferencia?</b><span>{_e(a)} {pesos(c.get("total_a"))} − {_e(b)} '
            f'{pesos(c.get("total_b"))} = <b>{pesos(brecha)}</b></span></div>'
            f'<div class="gm-comp-barra">{barra}</div>{lineas}'
            f'<div class="gm-comp-tot"><span>'
            f'{_e(c.get("pie_comp") or "Queda por revisar en la conciliación")}</span><b class="{"cero" if abs(pend) < .005 else ""}">'
            f'{pesos(pend)}</b></div></div>')


def html_partida(p, maximo):
    ico, tono = TIPO_PARTIDA.get(p.get("tipo"), ("buscar", "pizarra"))
    a, b = p.get("a"), p.get("b")
    delta = round((a or 0) - (b or 0), 2) if (a is not None or b is not None) \
        else None
    if delta is not None and maximo:
        ancho = min(abs(delta) / maximo * 50, 50)
        lado = "der" if delta > 0 else "izq"
        barra = (f'<span class="gm-delta"><i></i><span class="gm-delta-b {lado}" '
                 f'style="width:{max(ancho, 1.2):.2f}%"></span></span>')
    else:
        barra = '<span class="gm-delta vacio"></span>'
    la, lb = p.get("lado_a", "HELISA"), p.get("lado_b", "DIAN")
    def _v(x):
        return pesos(x) if isinstance(x, (int, float)) else _e(x)

    def _difiere(fila):
        if len(fila) > 3 and fila[3] is not None:
            return bool(fila[3])
        va, vb = fila[1], fila[2]
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            return abs(va - vb) >= 0.005
        return False

    det = "".join(f'<span>{_e(f[0])}</span><span>{_v(f[1])}</span>'
                  f'<span class="{"dif" if _difiere(f) else ""}">{_v(f[2])}'
                  f'</span>' for f in p.get("detalle", []))
    if delta is not None and a and b:
        base = max(abs(a), abs(b), 1)
        pct = ("<small>" + f"{abs(delta) / base * 100:.1f}".replace(".", ",")
               + " % del valor</small>")
    elif delta is not None:
        pct = f'<small>solo en {_e(la if a is not None else lb)}</small>'
    else:
        pct = ""
    if p.get("revision"):
        det = "".join(f'<span>{_e(f[0])}</span><span>{_v(f[1])}</span>'
                      for f in p.get("detalle", []))
        return (f'<details class="gm-pa"><summary>'
                f'<span class="gm-kpi-ico t-{tono}">{icono(ico, 16)}</span>'
                f'<span class="gm-pa-txt"><b>{_e(p["titulo"])}</b>'
                f'<span class="gm-pa-tag {p.get("tipo", "otro")}">'
                f'{_e(p["causa"])}</span><span class="gm-pa-sub">'
                f'{_e(p.get("sub", ""))}</span>'
                + (f'<span class="gm-pa-nota">{_e(p["nota"])}</span>'
                   if p.get("nota") else "")
                + f'</span><span class="gm-pa-vals"><span>{_e(la)} <b>'
                f'{pesos(a)}</b></span></span><span class="gm-delta vacio">'
                f'</span><span class="gm-pa-d"><b>{pesos(a)}</b></span>'
                f'</summary>'
                + (f'<div class="gm-pa-det"><div class="gm-pa-tabla r2">'
                   f'{det}</div></div>' if det else "") + '</details>')
    return (f'<details class="gm-pa"><summary>'
            f'<span class="gm-kpi-ico t-{tono}">{icono(ico, 16)}</span>'
            f'<span class="gm-pa-txt"><b>{_e(p["titulo"])}</b>'
            f'<span class="gm-pa-tag {p.get("tipo", "otro")}">{_e(p["causa"])}</span>'
            f'<span class="gm-pa-sub">{_e(p.get("sub", ""))}</span>'
            + (f'<span class="gm-pa-nota">{_e(p["nota"])}</span>' if p.get("nota")
               else "")
            + f'</span><span class="gm-pa-vals"><span>{_e(lb)} <b>{pesos(b)}</b>'
            f'</span><span>{_e(la)} <b>{pesos(a)}</b></span></span>{barra}'
            f'<span class="gm-pa-d"><b>{pesos(delta) if delta is not None else "—"}'
            f'</b>{pct}</span></summary>'
            + ((f'<div class="gm-pa-det"><div class="gm-pa-tabla r2">'
                + "".join(f'<span>{_e(f[0])}</span><span>{_v(f[1])}</span>'
                          for f in p.get("detalle", [])) + '</div></div>')
               if p.get("detalle_simple") else
               f'<div class="gm-pa-det"><div class="gm-pa-tabla"><span></span>'
               f'<span class="h">{_e(la)}</span><span class="h">{_e(lb)}</span>'
               f'{det}</div></div>' if det else "")
            + '</details>')


def html_partidas(partidas):
    if not partidas:
        return ('<div class="gm-graf-vacio">No hay partidas con esos '
                'filtros.</div>')
    maximo = max((abs((p.get("a") or 0) - (p.get("b") or 0))
                  for p in partidas), default=0) or 1
    return ('<div class="gm-pa-lista">' + "".join(
        html_partida(p, maximo) for p in partidas) + "</div>")


def html_grupos(grupos):
    return "".join(
        f'<div class="gm-grupo"><span class="gm-kpi-ico t-'
        + {"explicada": "verde", "info": "indigo"}.get(g.get("tipo"), "ambar")
        + '">' + icono({"explicada": "ok", "info": "usuario"}.get(
            g.get("tipo"), "alerta"), 16) + '</span>'
        f'<div><b>{_e(g["etiqueta"])} · {g["n"]} doc.</b><p>{_e(g.get("nota", ""))}'
        f'</p></div><span class="gm-grupo-v">{pesos(g.get("valor")) if g.get("valor") is not None else ""}</span></div>'
        for g in grupos)


# ------------------------------------------------------------------
# v6.16 · Antiguedad, comparativo y puente
# ------------------------------------------------------------------
COLOR_TRAMO = {"al_dia": "#4CC38A", "d30": "#A3C95C", "d60": "#E8C04A",
               "d90": "#F08A4B", "d180": "#F2736A", "mas": "#C9413A",
               "sin": "#8A8287"}


def html_antiguedad(tramos, nota=""):
    """Barra apilada por tramo de vencimiento + una fila por tramo con
    documentos, % del total y valor (el color nunca es la unica senal)."""
    filas = [t for t in tramos]
    total = sum(abs(t["valor"]) for t in filas)
    if not total:
        return '<div class="gm-graf-vacio">Sin documentos con saldo.</div>'
    pcs = porcentajes([t["valor"] for t in filas])
    barra = "".join(
        f'<span title="{_e(t["etiqueta"])}: {pesos(t["valor"])} '
        f'({texto_porcentaje(pc, t["valor"])})" style="flex:'
        f'{abs(t["valor"]) / total:.4f};background:{COLOR_TRAMO[t["tramo"]]}">'
        f'</span>' for t, pc in zip(filas, pcs) if t["valor"])
    lineas = "".join(
        f'<div class="gm-tramo{" cero" if not t["n"] else ""}">'
        f'<i style="background:{COLOR_TRAMO[t["tramo"]]}"></i>'
        f'<span>{_e(t["etiqueta"])}</span>'
        f'<small>{t["n"]} doc.</small>'
        f'<span class="gm-comp-pc">{texto_porcentaje(pc, t["valor"])}</span>'
        f'<b>{pesos(t["valor"])}</b></div>' for t, pc in zip(filas, pcs))
    vencido = sum(t["valor"] for t in filas if t["tramo"] not in
                  ("al_dia", "sin"))
    pc_v = texto_porcentaje(vencido / total * 100 if total else 0, vencido)
    return (f'<div class="gm-comp-barra">{barra}</div>{lineas}'
            f'<div class="gm-comp-tot"><span>Vencido{(" · " + _e(nota)) if nota else ""}'
            f'</span><b class="{"cero" if not vencido else ""}">{pesos(vencido)}'
            f' · {pc_v}</b></div>')


def html_comparativo(filas, nombre_a, nombre_b, color_a="#E0118F",
                     color_b="#8B95F5", pie_diferencia="Diferencia",
                     texto_diferencia=None, ok_si=None):
    """Dos barras por fila (serie A y B) en la misma escala, con el valor
    y la diferencia A - B escritos."""
    if not filas:
        return '<div class="gm-graf-vacio">Sin datos.</div>'
    tope = max(max(abs(a or 0), abs(b or 0)) for _, a, b in filas) or 1

    def barra(v, color):
        return (f'<div class="gm-cmp-b"><span class="gm-barra-pista">'
                f'<span class="gm-barra" style="background:{color};width:'
                f'{max(abs(v or 0) / tope * 100, 1.2 if v else 0):.1f}%">'
                f'</span></span><b>{pesos(v) if v is not None else "—"}</b></div>')
    cuerpo = "".join(
        f'<div class="gm-cmp-fila"><div class="gm-cmp-et"><span>{_e(e)}</span>'
        f'<small class="{"cero" if (ok_si(round((a or 0) - (b or 0), 2)) if ok_si else a is not None and b is not None and abs((a or 0) - (b or 0)) < .005) else ""}">'
        + (_e(texto_diferencia(round((a or 0) - (b or 0), 2))) if texto_diferencia
           else f'{_e(pie_diferencia)} {pesos(round((a or 0) - (b or 0), 2))}')
        + '</small></div>'
        f'<div class="gm-cmp-barras">{barra(a, color_a)}{barra(b, color_b)}'
        f'</div></div>' for e, a, b in filas)
    leyenda = (f'<div class="gm-cmp-ley"><span><i style="background:{color_a}">'
               f'</i>{_e(nombre_a)}</span><span><i style="background:{color_b}">'
               f'</i>{_e(nombre_b)}</span></div>')
    return f'<div class="gm-cmp">{leyenda}{cuerpo}</div>'


def html_puente(pasos, nota=""):
    """Puente (cascada) horizontal. pasos: [(etiqueta, valor, tipo)] con
    tipo "total" (saldo: se marca con una linea) o "ajuste" (barra que va
    del saldo acumulado anterior al nuevo). Escala comun a todas las filas;
    si no empieza en cero se dice en la nota."""
    if not pasos:
        return '<div class="gm-graf-vacio">Sin datos.</div>'
    filas, acum = [], 0.0
    for etiqueta, valor, tipo in pasos:
        if tipo == "total":
            acum = float(valor)
            filas.append((etiqueta, valor, tipo, acum, acum))
        else:
            ini = acum
            acum = round(acum + float(valor), 2)
            filas.append((etiqueta, valor, tipo, ini, acum))
    puntos = [x for f in filas for x in (f[3], f[4])]
    lo, hi = min(puntos), max(puntos)
    if lo > 0 and (hi - lo) < hi * 0.6:
        cero = False
    else:
        lo, hi, cero = min(lo, 0), max(hi, 0), True
    ancho = (hi - lo) or 1
    lo -= ancho * .03
    hi += ancho * .03
    ancho = hi - lo

    def x(v):
        return (v - lo) / ancho * 100

    cuerpo = []
    for etiqueta, valor, tipo, ini, fin in filas:
        if tipo == "total":
            marca = (f'<span class="gm-pte-total" style="left:{x(fin):.2f}%">'
                     f'</span>')
            clase = "total"
        else:
            a, b = sorted((x(ini), x(fin)))
            signo = "mas" if valor >= 0 else "menos"
            marca = (f'<span class="gm-pte-b {signo}" style="left:{a:.2f}%;'
                     f'width:{max(b - a, .6):.2f}%"></span>')
            clase = "ajuste"
        cuerpo.append(
            f'<div class="gm-pte-fila {clase}" title="{_e(etiqueta)}: '
            f'{pesos(valor)}"><span class="gm-pte-et">{_e(etiqueta)}</span>'
            f'<span class="gm-pte-pista">{marca}</span>'
            f'<b class="gm-pte-v">{("+" if tipo != "total" and valor > 0 else "") + pesos(valor)}</b></div>')
    pie = ("" if cero else "La escala no empieza en cero: se amplía el rango "
           "de los saldos para que se vean los ajustes. ") + (nota or "")
    return ('<div class="gm-pte">' + "".join(cuerpo) + '</div>'
            + (f'<div class="gm-pa-pie">{_e(pie)}</div>' if pie.strip() else ""))


def html_barras_valor(datos):
    """Barras horizontales de valores en pesos (valor absoluto en la barra;
    el valor con su signo escrito). Para top de terceros."""
    datos = [(e, float(v or 0)) for e, v in datos]
    if not datos:
        return '<div class="gm-graf-vacio">Sin datos.</div>'
    tope = max(abs(v) for _, v in datos) or 1
    pcs = porcentajes([v for _, v in datos])
    filas = "".join(
        f'<div class="gm-barra-fila" title="{_e(e)}: {pesos(v)} '
        f'({texto_porcentaje(pc, v)})"><span class="gm-barra-et">{_e(e)}</span>'
        f'<span class="gm-barra-pista"><span class="gm-barra" style="width:'
        f'{max(abs(v) / tope * 100, 1.5 if v else 0):.1f}%'
        f'{";background:#8A8287" if v < 0 else ""}"></span></span>'
        f'<span class="gm-barra-v">{pesos(v)} <small>{texto_porcentaje(pc, v)}'
        f'</small></span></div>' for (e, v), pc in zip(datos, pcs))
    return f'<div class="gm-barras">{filas}</div>'


# ------------------------------------------------------------------
# v6.17 · Columnas por hora, mapa de calor y linea de tiempo del dia
# ------------------------------------------------------------------
def html_columnas(serie, unidad="", marcar_max=True):
    """Columnas verticales (p. ej. 24 horas). serie: [(etiqueta, valor)].
    Etiqueta del eje cada 3 columnas; valor en el globo (<title>) y la
    columna mayor resaltada con su valor escrito."""
    if not serie or not any(v for _, v in serie):
        return '<div class="gm-graf-vacio">Sin actividad.</div>'
    tope = max(v for _, v in serie) or 1
    imax = max(range(len(serie)), key=lambda i: serie[i][1])
    cols = "".join(
        f'<div class="gm-col{" max" if marcar_max and i == imax else ""}" '
        f'title="{_e(e)}: {_num(v, unidad)}">'
        + (f'<em>{_num(v)}</em>' if marcar_max and i == imax else "")
        + f'<span style="height:{max(v / tope * 100, 2 if v else 0):.1f}%">'
        f'</span><small>{_e(e) if i % 3 == 0 else ""}</small></div>'
        for i, (e, v) in enumerate(serie))
    return f'<div class="gm-cols">{cols}</div>'


def html_mapa_calor(matriz, filas_et, cols_et):
    """Mapa de calor (filas x columnas) en escala de magenta; la cantidad
    va en el globo de cada celda y la escala se explica abajo."""
    tope = max((v for fila in matriz for v in fila), default=0)
    if not tope:
        return '<div class="gm-graf-vacio">Sin actividad.</div>'

    def celda(v):
        a = 0 if not v else .15 + .85 * v / tope
        return f'style="background:rgba(224,17,143,{a:.2f})"'
    cab = '<span></span>' + "".join(
        f'<small>{_e(c) if k % 3 == 0 else ""}</small>'
        for k, c in enumerate(cols_et))
    cuerpo = "".join(
        f'<b>{_e(et)}</b>' + "".join(
            f'<i {celda(v)} title="{_e(et)} {_e(cols_et[k])}: {_num(v)} '
            f'acciones"></i>' for k, v in enumerate(fila))
        for et, fila in zip(filas_et, matriz))
    escala = "".join(f'<i style="background:rgba(224,17,143,{a})"></i>'
                     for a in (.15, .36, .58, .79, 1))
    return (f'<div class="gm-calor" style="--gm-ncols:{len(cols_et)}">'
            f'{cab}{cuerpo}</div><div class="gm-calor-ley"><span>0</span>'
            f'<span class="gm-calor-esc">{escala}</span><span>{_num(tope)} '
            f'acciones / hora</span></div>')


def html_linea_tiempo(filas, desde_h=6, hasta_h=21):
    """Linea de tiempo de un dia. filas: [(nombre, [(ini_min, fin_min,
    "uso" | "abierta")])]. Se amplia el rango si hay actividad fuera."""
    if not filas:
        return '<div class="gm-graf-vacio">Nadie usó la plataforma ese día.</div>'
    todos = [t for _, ts in filas for t in ts]
    desde_h = min(desde_h, min(a for a, _, _ in todos) // 60)
    hasta_h = max(hasta_h, -(-max(b for _, b, _ in todos) // 60))
    ini, fin = desde_h * 60, hasta_h * 60
    largo = fin - ini

    def pos(m):
        return (m - ini) / largo * 100

    marcas = "".join(
        f'<small style="left:{pos(h * 60):.2f}%">{h:02d}:00</small>'
        for h in range(desde_h, hasta_h + 1, 2))
    rejilla = "".join(
        f'<u style="left:{pos(h * 60):.2f}%"></u>'
        for h in range(desde_h, hasta_h + 1, 2))
    cuerpo = "".join(
        f'<div class="gm-lt-fila"><span class="gm-lt-et">{_e(n)}</span>'
        f'<span class="gm-lt-pista">{rejilla}' + "".join(
            f'<span class="gm-lt-t {e}" style="left:{pos(a):.2f}%;width:'
            f'{max(pos(b) - pos(a), .4):.2f}%" title="{_e(n)}: '
            f'{a // 60:02d}:{a % 60:02d} – {b // 60:02d}:{b % 60:02d} · '
            f'{"en uso" if e == "uso" else "abierta sin uso"}"></span>'
            for a, b, e in ts) + '</span></div>' for n, ts in filas)
    return (f'<div class="gm-lt"><div class="gm-lt-fila gm-lt-cab"><span>'
            f'</span><span class="gm-lt-eje">{marcas}</span></div>{cuerpo}'
            f'</div><div class="gm-cmp-ley"><span><i style="background:'
            f'#E0118F"></i>En uso (hubo clics o cargas)</span><span><i '
            f'style="background:#5E585B"></i>Abierta sin uso</span></div>')
