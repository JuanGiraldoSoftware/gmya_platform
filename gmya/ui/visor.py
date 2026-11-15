"""Visor de documentos con resaltado (PDF y Excel/CSV), comun a los modulos.

Contrato:
  paginas_resaltadas(contenido, resaltar, es_libro, resolucion=None) -> imagenes de
      las paginas del PDF con los movimientos marcados.
  pdf_resaltado / excel_resaltado -> copia descargable del documento con
      las filas marcadas (el original nunca se modifica).
  html_visor_documentos(paneles, alto=760, apilado=False) -> html del visor
      lado a lado.
  numero_fila(m), numero_pagina(m) -> ubicacion de un movimiento.

Depende de: gmya.comun.numeros, gmya.comun.pdf, gmya.comun.grilla, gmya.ui.globos
"""

import base64
import datetime
import html
import io
import re
from collections import defaultdict
from decimal import Decimal

from gmya.comun.numeros import CENTAVO
from gmya.comun.pdf import agrupar_lineas, palabras_pagina
from gmya.comun.grilla import tabla_desde_archivo
from gmya.ui.globos import JS_GLOBOS


# ------------------------------------------------------------
# Visor de documentos: muestra el extracto y HELISA tal cual (PDF como
# imagen de la pagina, Excel/CSV como tabla) y resalta las partidas que
# no cuadran. Cada cotejo (las partidas del extracto y de HELISA que se
# compararon entre si) lleva su propio COLOR y NUMERO en los dos
# documentos, para saber que se cotejo con que. La partida que se esta
# revisando lleva ademas un recuadro magenta.
# ------------------------------------------------------------
RESOLUCION_VISOR = 110          # puntos por pulgada al dibujar la pagina
RESOLUCION_VISOR_COMPLETO = 150  # visor con zoom (nitido hasta ~250 %)
AMARILLO_VISOR = (255, 214, 0)
MAGENTA_VISOR = (224, 17, 143)


def numero_fila(movimiento):
    """'Fila 23' -> 23 (Excel / CSV)."""
    m = re.search(r"Fila\s+(\d+)", str(movimiento.get("ubicacion") or ""))
    return int(m.group(1)) if m else None


def numero_pagina(movimiento):
    if movimiento.get("pagina"):
        return int(movimiento["pagina"])
    m = re.search(r"P[áa]g\.?\s*(\d+)",
                  str(movimiento.get("ubicacion") or ""))
    return int(m.group(1)) if m else None


def _variantes_valor(valor):
    """Formas en que un valor puede aparecer escrito en el documento."""
    v = abs(Decimal(valor)).quantize(CENTAVO)
    entero = f"{int(v):,}"
    decimales = f"{v:.2f}".split(".")[1]
    return {
        f"{entero}.{decimales}",                              # 1,250,000.00
        f"{entero.replace(',', '.')},{decimales}",            # 1.250.000,00
        entero,                                               # 1,250,000
        entero.replace(",", "."),                             # 1.250.000
        f"{v:.2f}",                                           # 1250000.00
    }


def _lineas_con_caja(pagina):
    lineas = agrupar_lineas(palabras_pagina(pagina))
    for linea in lineas:
        palabras = linea["palabras"]
        linea["caja"] = (min(w["x0"] for w in palabras),
                         min(w["top"] for w in palabras),
                         max(w["x1"] for w in palabras),
                         max(w["bottom"] for w in palabras))
    return lineas


def _puntaje_linea(texto, movimiento, es_libro):
    claro = texto.replace("$", " ").replace("-", " ")
    puntos = 0
    if any(v in claro for v in _variantes_valor(movimiento["valor"])):
        puntos += 4
    fecha = movimiento["fecha"]
    if f"{fecha.day:02d}/{fecha.month:02d}" in texto or \
            f"{fecha.day:02d}/ " in texto or \
            texto.startswith(f"{fecha.day:02d}"):
        puntos += 1
    if es_libro:
        if re.search(r"(?<!\d)" + re.escape(str(movimiento["numero"]))
                     + r"(?!\d)", texto):
            puntos += 2
        if movimiento["tipo"] and movimiento["tipo"] in texto:
            puntos += 1
    else:
        palabras = [p for p in movimiento["descripcion"].split()
                    if len(p) > 3][:3]
        puntos += sum(1 for p in palabras if p in texto)
    return puntos


def ubicar_en_pagina(pagina, movimientos, es_libro):
    """Caja (x0, top, x1, bottom) de cada movimiento en la pagina PDF."""
    lineas = _lineas_con_caja(pagina)
    usadas, cajas = set(), {}
    for mov in movimientos:
        mejor, puntaje = None, 0
        for i, linea in enumerate(lineas):
            if i in usadas:
                continue
            p = _puntaje_linea(linea["texto"], mov, es_libro)
            if p > puntaje:
                mejor, puntaje = i, p
        if mejor is not None and puntaje >= 4:
            usadas.add(mejor)
            cajas[id(mov)] = lineas[mejor]["caja"]
    return cajas


# Colores de los cotejos (se repiten despues del ultimo; el numero no)
PALETA_COTEJOS = [
    (255, 214, 0), (0, 176, 240), (146, 208, 80), (255, 153, 51),
    (180, 140, 255), (255, 110, 160), (0, 200, 160), (120, 170, 255),
    (255, 120, 100), (200, 200, 0), (90, 220, 230), (230, 160, 220),
]
VERDE_CONCILIADA = (120, 200, 120)


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def _oscuro(rgb, factor=0.55):
    return tuple(int(c * factor) for c in rgb)


def _fuente(tamano):
    from PIL import ImageFont
    for nombre in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
                   "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:
        return ImageFont.load_default()


def _dibujar_marcas(imagen, marcas, escala_letra=1.0):
    """
    marcas: [(rect, color, etiqueta, actual)]. Pinta el fondo del color del
    cotejo, el borde y una etiqueta con el numero a la izquierda.
    """
    from PIL import Image, ImageDraw
    capa = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    for rect, color, etiqueta, actual in marcas:
        dibujo.rectangle(rect, fill=tuple(color) + (95,),
                         outline=(MAGENTA_VISOR + (255,)) if actual
                         else _oscuro(color) + (255,),
                         width=4 if actual else 2)
    imagen = Image.alpha_composite(imagen.convert("RGBA"), capa)
    dibujo = ImageDraw.Draw(imagen)
    fuente = _fuente(int(13 * escala_letra))
    for rect, color, etiqueta, actual in marcas:
        if not etiqueta:
            continue
        x0, top, x1, bottom = rect
        caja_texto = dibujo.textbbox((0, 0), etiqueta, font=fuente)
        ancho = caja_texto[2] - caja_texto[0] + 10
        alto = max(caja_texto[3] - caja_texto[1] + 6, bottom - top)
        bx0 = max(1, x0 - ancho - 3)
        by0 = (top + bottom) / 2 - alto / 2
        fondo = MAGENTA_VISOR if actual else _oscuro(color, 0.7)
        dibujo.rounded_rectangle((bx0, by0, bx0 + ancho, by0 + alto),
                                 radius=5, fill=fondo + (255,))
        dibujo.text((bx0 + ancho / 2, by0 + alto / 2), etiqueta,
                    fill=(255, 255, 255, 255), font=fuente, anchor="mm")
    return imagen.convert("RGB")


def _rect(caja, escala, x_inicio, y_inicio):
    x0, top, x1, bottom = caja
    return ((x0 - x_inicio - 4) * escala, (top - y_inicio - 3) * escala,
            (x1 - x_inicio + 4) * escala, (bottom - y_inicio + 3) * escala)


def imagen_pagina_resaltada(contenido, numero_pag, resaltar, actuales,
                            es_libro, resolucion=None, recorte=False,
                            con_zonas=False):
    """
    PNG de la pagina con cada partida de 'resaltar' en el color de su
    cotejo y las de 'actuales' (lo que se esta revisando) con recuadro
    magenta. Con recorte=True devuelve solo la franja de la pagina donde
    estan las partidas actuales (para verlas mas grandes).
    """
    import pdfplumber

    resolucion = resolucion or RESOLUCION_VISOR
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        total = len(pdf.pages)
        numero_pag = max(1, min(numero_pag or 1, total))
        pagina = pdf.pages[numero_pag - 1]
        lista = list(actuales) + [m for m in resaltar if m not in actuales]
        cajas = ubicar_en_pagina(pagina, lista, es_libro)
        imagen = pagina.to_image(resolution=resolucion).original
        escala = resolucion / 72
        x_inicio, y_inicio = pagina.bbox[0], pagina.bbox[1]

    ids_actuales = {id(m) for m in actuales}
    marcas, encontrada, vistos = [], False, set()
    for mov in lista:
        caja = cajas.get(id(mov))
        if not caja or id(mov) in vistos:
            continue
        vistos.add(id(mov))
        actual = id(mov) in ids_actuales
        encontrada = encontrada or actual
        marcas.append((_rect(caja, escala, x_inicio, y_inicio),
                       mov.get("_color", AMARILLO_VISOR),
                       mov.get("_etiqueta", ""), actual))
    imagen = _dibujar_marcas(imagen, marcas, resolucion / 110)
    actuales_rect = [m[0] for m in marcas if m[3]]
    arriba = 0
    if recorte and actuales_rect:
        margen = 70 * resolucion / 110
        arriba = int(max(0, min(r[1] for r in actuales_rect) - margen))
        abajo = min(imagen.height,
                    max(r[3] for r in actuales_rect) + margen)
        imagen = imagen.crop((0, arriba, imagen.width, int(abajo)))
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    if con_zonas:
        return (salida.getvalue(), numero_pag, total, encontrada,
                zonas_marcas(marcas, imagen.width, imagen.height, arriba))
    return salida.getvalue(), numero_pag, total, encontrada


def html_tabla_resaltada(contenido, filas_resaltar, filas_actuales,
                         contexto=12, marcas=None, zoom=100, tips=None,
                         tabla=None, solo=None):
    """
    Vista del Excel/CSV como hoja de calculo con numeros de fila. Cada fila
    que no cuadra lleva el color y el numero de su cotejo (columna
    'Cotejo'); la actual va con borde magenta.
    marcas: {fila: (color_rgb, etiqueta)}.
    """
    marcas = marcas or {}
    tips = tips or {}
    tabla = tabla if tabla is not None else tabla_desde_archivo(contenido)
    if not tabla:
        return "<p>Documento vacío.</p>", 0
    objetivo = min(filas_actuales) if filas_actuales else (
        min(filas_resaltar) if filas_resaltar else 1)
    if contexto is None:
        desde, hasta = 1, len(tabla)
    else:
        # Ventana que cubre TODAS las filas de la diferencia actual
        ultima = max(filas_actuales) if filas_actuales else objetivo
        desde = max(1, objetivo - contexto)
        hasta = min(len(tabla), ultima + contexto)
    ancho = max((len(tabla[n - 1]) for n in range(desde, hasta + 1)
                 if solo is None or n in solo), default=0) if tabla else 0
    ancho = max(ancho, 1)

    def celda(valor):
        if valor is None:
            return ""
        if isinstance(valor, (datetime.datetime, datetime.date)):
            return valor.strftime("%d/%m/%Y")
        if isinstance(valor, bool):
            return html.escape(str(valor))
        if isinstance(valor, float):
            return f"{valor:,.2f}"
        if isinstance(valor, int):
            return f"{valor:,}"
        return html.escape(str(valor))

    letras = [chr(65 + i) if i < 26 else f"C{i + 1}" for i in range(ancho)]
    partes = [f"<div class='gm-visor-xls' style='font-size:{zoom}%'>"
              "<table><thead><tr><th></th><th>Cotejo</th>"]
    partes += [f"<th>{l}</th>" for l in letras]
    partes.append("</tr></thead><tbody>")
    for numero in range(desde, hasta + 1):
        if solo is not None and numero not in solo:
            continue
        fila = tabla[numero - 1]
        color, etiqueta = marcas.get(numero, (None, ""))
        if color is None and numero in filas_resaltar:
            color = AMARILLO_VISOR
        clase = "actual" if numero in filas_actuales else ""
        estilo = (f" style='--fondo:{_hex(color)}40;--borde:"
                  f"{_hex(_oscuro(color))}'" if color else "")
        partes.append(f"<tr class='{clase} {'marcada' if color else ''}'"
                      f"{estilo}><th>{numero}</th>")
        if etiqueta:
            fondo = _hex(MAGENTA_VISOR) if numero in filas_actuales else \
                _hex(_oscuro(color, 0.7))
            tip = tips.get(etiqueta)
            globo = (f"<div class='gm-tip'>{tip}</div>" if tip else "")
            partes.append(f"<td class='cotejo{' gm-hot-td' if tip else ''}'>"
                          f"<span style='background:{fondo}'>"
                          f"{html.escape(etiqueta)}</span>{globo}</td>")
        else:
            partes.append("<td class='cotejo'></td>")
        for i in range(ancho):
            valor = fila[i] if i < len(fila) else None
            alinear = " class='num'" if isinstance(valor, (int, float)) \
                else ""
            partes.append(f"<td{alinear}>{celda(valor)}</td>")
        partes.append("</tr>")
    partes.append("</tbody></table></div>")
    return "".join(partes), len(tabla)


def paginas_resaltadas(contenido, resaltar, es_libro, resolucion=None):
    """
    Todas las paginas del PDF con TODAS las partidas marcadas con el color
    y el numero de su cotejo. Devuelve [(numero_pagina, png, marcadas)].
    """
    import pdfplumber

    resolucion = resolucion or RESOLUCION_VISOR
    escala = resolucion / 72
    por_pagina = defaultdict(list)
    for mov in resaltar:
        por_pagina[numero_pagina(mov) or 1].append(mov)

    salida = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for numero_pag, pagina in enumerate(pdf.pages, start=1):
            movimientos = por_pagina.get(numero_pag, [])
            cajas = ubicar_en_pagina(pagina, movimientos, es_libro) \
                if movimientos else {}
            imagen = pagina.to_image(resolution=resolucion).original
            x_inicio, y_inicio = pagina.bbox[0], pagina.bbox[1]
            marcas = [(_rect(cajas[id(m)], escala, x_inicio, y_inicio),
                       m.get("_color", AMARILLO_VISOR),
                       m.get("_etiqueta", ""), False)
                      for m in movimientos if id(m) in cajas]
            imagen = _dibujar_marcas(imagen, marcas, resolucion / 110)
            buffer = io.BytesIO()
            imagen.save(buffer, format="PNG")
            salida.append((numero_pag, buffer.getvalue(), len(marcas),
                           zonas_marcas(marcas, imagen.width,
                                        imagen.height)))
    return salida


def pdf_resaltado(contenido, resaltar, es_libro):
    """Copia del PDF (como imagenes) con los cotejos de colores."""
    from PIL import Image
    paginas = paginas_resaltadas(contenido, resaltar, es_libro,
                                 resolucion=150)
    imagenes = [Image.open(io.BytesIO(pagina[1])).convert("RGB")
                for pagina in paginas]
    salida = io.BytesIO()
    imagenes[0].save(salida, format="PDF", save_all=True,
                     append_images=imagenes[1:], resolution=150)
    return salida.getvalue()


def excel_resaltado(contenido, filas):
    """
    Copia del Excel/CSV con cada fila en el color de su cotejo y una
    columna 'Cotejo' con el numero. filas: [(fila, color_rgb, etiqueta)] o
    [fila]. Si el original es .xlsx se conserva tal cual.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill

    if contenido[:4] == b"PK\x03\x04":
        libro = load_workbook(io.BytesIO(contenido))
        hoja = libro.worksheets[0]
    else:
        libro = Workbook()
        hoja = libro.active
        for fila in tabla_desde_archivo(contenido):
            hoja.append([v for v in fila])
    ultima_columna = max(hoja.max_column, 1)
    columna_cotejo = ultima_columna + 1
    hoja.cell(1, columna_cotejo, "Cotejo").font = Font(bold=True)
    for item in filas:
        if isinstance(item, int):
            numero, color, etiqueta = item, AMARILLO_VISOR, ""
        else:
            numero, color, etiqueta = item
        claro = tuple(int(c + (255 - c) * 0.55) for c in color)
        relleno = PatternFill("solid", fgColor=_hex(claro)[1:])
        for c in range(1, ultima_columna + 1):
            hoja.cell(numero, c).fill = relleno
        celda = hoja.cell(numero, columna_cotejo, etiqueta)
        celda.fill = PatternFill("solid", fgColor=_hex(_oscuro(color, 0.7))
                                 [1:])
        celda.font = Font(bold=True, color="FFFFFF")
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


# ------------------------------------------------------------
# Explicacion al pasar el mouse (hover) sobre las partidas marcadas
# ------------------------------------------------------------

def zonas_marcas(marcas, ancho, alto, desplazamiento_y=0):
    """Rectangulos de las marcas como fracciones de la imagen final."""
    zonas = []
    for rect, _, etiqueta, actual in marcas:
        x0, top, x1, bottom = rect
        top, bottom = top - desplazamiento_y, bottom - desplazamiento_y
        if bottom < 0 or top > alto:
            continue
        zonas.append((max(0.0, x0 / ancho), max(0.0, top / alto),
                      min(1.0, x1 / ancho), min(1.0, bottom / alto),
                      etiqueta, actual))
    return zonas


# ------------------------------------------------------------
# Visor de documentos (v4.6): cada documento completo en su propio
# recuadro con desplazamiento independiente, boton "siguiente marca" por
# documento y zoom con Ctrl + rueda del mouse (o pellizco en el touchpad).
# Se dibuja como un componente HTML (iframe) para que la navegacion y el
# zoom ocurran en el navegador, sin recargar la pagina.
# ------------------------------------------------------------
def _imagen_ligera(png, calidad=82):
    """PNG -> JPEG en base64 (el visor carga mucho mas rapido)."""
    try:
        from PIL import Image
        imagen = Image.open(io.BytesIO(png)).convert("RGB")
        salida = io.BytesIO()
        imagen.save(salida, format="JPEG", quality=calidad, optimize=True)
        return "image/jpeg", base64.b64encode(salida.getvalue()).decode()
    except Exception:
        return "image/png", base64.b64encode(png).decode()


def contenido_pdf_visor(paginas, tips=None, solo_marcadas=False,
                        esperadas=None):
    """
    HTML de las paginas del PDF, una debajo de otra, con cada partida
    marcada como zona navegable (clase gm-marca) y su globo explicativo.
    paginas: [(numero, png, marcadas, zonas)] de paginas_resaltadas().
    """
    tips = tips or {}
    esperadas = esperadas or {}
    total = len(paginas)
    partes = []
    for numero_pag, png, marcadas, zonas in paginas:
        tiene = bool(zonas) or bool(esperadas.get(numero_pag))
        if solo_marcadas and not tiene:
            continue
        aviso = ""
        faltan = esperadas.get(numero_pag, 0) - len(zonas)
        if faltan > 0:
            aviso = (f" · {faltan} sin ubicar exactamente en la página")
        clase_titulo = "gv-pagina" + (" gm-marca" if faltan > 0 and not zonas
                                      else "")
        partes.append(f"<div class='{clase_titulo}'>Página {numero_pag} de "
                      f"{total}" + (f" · {len(zonas)} marcada(s)"
                                    if zonas else "") + f"{aviso}</div>")
        tipo, codigo = _imagen_ligera(png)
        capas = []
        for x0, y0, x1, y1, etiqueta, actual in sorted(
                zonas, key=lambda z: (z[1], z[0])):
            tip = tips.get(etiqueta)
            clases = "gm-marca" + (" gm-hot" if tip else "")
            clases += " gm-tip-arriba" if y0 > 0.62 else ""
            clases += " gm-tip-izq" if x0 > 0.5 else ""
            globo = f"<div class='gm-tip'>{tip}</div>" if tip else ""
            capas.append(
                f"<div class='{clases}' data-etq='{html.escape(etiqueta)}' "
                f"style='left:{x0 * 100:.3f}%;top:{y0 * 100:.3f}%;"
                f"width:{(x1 - x0) * 100:.3f}%;height:{(y1 - y0) * 100:.3f}%'>"
                f"{globo}</div>")
        partes.append(f"<div class='gm-lienzo gv-zoomable'>"
                      f"<img src='data:{tipo};base64,{codigo}'>"
                      f"{''.join(capas)}</div>")
    if not partes:
        partes.append("<p class='gv-vacio'>No hay páginas con partidas "
                      "marcadas.</p>")
    return "".join(partes)


def contenido_tabla_visor(tabla, marcas, tips=None, solo_marcadas=False):
    """HTML de la hoja completa (o solo las filas marcadas)."""
    if not tabla:
        return "<p class='gv-vacio'>Documento vacío.</p>"
    filas = set(marcas)
    html_tabla, _ = html_tabla_resaltada(
        None, filas, set(), contexto=None, marcas=marcas, zoom=100,
        tips=tips, tabla=tabla, solo=filas if solo_marcadas else None)
    return html_tabla.replace("class='gm-visor-xls'",
                              "class='gm-visor-xls gv-zoomable gv-tabla'", 1)


CSS_VISOR = """
* { box-sizing: border-box; }
body { margin: 0; font-family: Montserrat, "Segoe UI", Arial, sans-serif;
       color: #161415; background: transparent; }
.gv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.gv-grid.uno { grid-template-columns: 1fr; }
.gv-panel { display: flex; flex-direction: column; min-width: 0;
            border: 3px solid #272526; border-radius: 12px;
            background: #fff; overflow: hidden; }
.gv-cab { background: #272526; color: #fff; padding: 8px 10px;
          display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.gv-cod { background: #E0118F; color: #fff; font-weight: 900;
          font-size: 11px; padding: 2px 8px; border-radius: 999px;
          letter-spacing: .06em; }
.gv-titulo { font-weight: 800; font-size: 13px; flex: 1 1 140px;
             min-width: 0; overflow: hidden; text-overflow: ellipsis;
             white-space: nowrap; }
.gv-barra { display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
            padding: 6px 10px; background: #EEE9EC;
            border-bottom: 2px solid #272526; font-size: 12px; }
.gv-barra button { border: 2px solid #272526; background: #fff;
                   color: #161415; border-radius: 8px; font-weight: 800;
                   padding: 3px 10px; cursor: pointer; font-size: 12px; }
.gv-barra button.prim { background: #E0118F; border-color: #A30A67;
                        color: #fff; }
.gv-barra button:disabled { opacity: .45; cursor: default; }
.gv-cont { font-weight: 800; min-width: 92px; text-align: center; }
.gv-zoom { margin-left: auto; display: flex; align-items: center; gap: 4px; }
.gv-zoom span { min-width: 44px; text-align: center; font-weight: 800; }
.gv-aviso { background: #FFF4CC; color: #7F6000; font-size: 12px;
            padding: 6px 10px; border-bottom: 1px solid #E6D38A; }
.gv-cuerpo { overflow: auto; position: relative; background: #fff; }
.gv-pagina { font-size: 12px; font-weight: 800; color: #272526;
             padding: 8px 8px 4px; }
.gv-vacio { padding: 16px; color: #595959; font-size: 13px; }
.gm-lienzo { position: relative; width: 100%;
             border-bottom: 2px solid #CFC8CB; }
.gm-lienzo img { display: block; width: 100%; max-width: none; }
.gm-marca { position: absolute; border-radius: 3px; }
.gv-pagina.gm-marca { position: static; }
.gm-hot { cursor: help; }
.gm-hot:hover { outline: 3px solid #E0118F;
                background: rgba(224, 17, 143, .10); z-index: 40; }
.gv-foco { outline: 4px solid #E0118F !important;
           box-shadow: 0 0 0 6px rgba(224, 17, 143, .28); z-index: 30; }
tr.gv-foco td { border-top: 3px solid #E0118F !important;
                border-bottom: 3px solid #E0118F !important;
                font-weight: 800; }
tr.gv-foco th { background: #E0118F !important; color: #fff !important; }
.gm-tip { display: none; position: absolute; z-index: 60;
          top: calc(100% + 6px); left: 0; width: max-content;
          max-width: min(430px, 70vw); background: #272526;
          color: #fff !important; border-left: 5px solid #E0118F;
          border-radius: 8px; padding: .55rem .7rem; font-size: 12.5px;
          line-height: 1.38; font-weight: 500; white-space: normal;
          text-align: left; box-shadow: 0 8px 22px rgba(0,0,0,.35);
          pointer-events: none; }
.gm-tip b { color: #FF7CC8; }
.gm-tip i { color: #FFD24D; }
.gm-hot:hover .gm-tip { display: block; }
.gm-tip-arriba .gm-tip { top: auto; bottom: calc(100% + 6px); }
.gm-tip-izq .gm-tip { left: auto; right: 0; }
.gm-visor-xls { background: #fff; }
.gm-visor-xls table { border-collapse: collapse; font-size: .74em;
                      width: max-content; min-width: 100%; }
.gm-visor-xls th { background: #E7E3E5; color: #272526; font-weight: 800;
                   padding: .25rem .45rem; border: 1px solid #CFC8CB;
                   position: sticky; top: 0; z-index: 5; }
.gm-visor-xls tbody th { position: sticky; left: 0; top: auto; z-index: 4; }
.gm-visor-xls td { padding: .25rem .45rem; border: 1px solid #E4DEE1;
                   white-space: nowrap; max-width: 320px; overflow: hidden;
                   text-overflow: ellipsis; }
.gm-visor-xls td.num { text-align: right;
                       font-variant-numeric: tabular-nums; }
.gm-visor-xls tr.marcada td { background: var(--fondo); }
.gm-visor-xls tr.marcada th { box-shadow: inset 5px 0 0 var(--borde); }
.gm-visor-xls td.cotejo { text-align: center; }
.gm-visor-xls td.cotejo span { display: inline-block; min-width: 26px;
    padding: 1px 6px; border-radius: 6px; color: #fff; font-weight: 900; }
.gm-visor-xls td.gm-hot-td { position: relative; overflow: visible;
                             cursor: help; }
.gm-visor-xls td.gm-hot-td .gm-tip { left: calc(100% + 4px); top: -4px; }
.gm-visor-xls tr:hover td.gm-hot-td .gm-tip { display: block; }
.gm-visor-xls tr.marcada:hover td { outline: 1px solid #E0118F; }
.gv-pie { font-size: 11px; color: #595959; padding: 6px 2px 0; }
.gv-arriba { display: flex; align-items: center; gap: 10px;
            margin-bottom: 8px; }
.gv-arriba .gv-pista { font-size: 11.5px; color: #595959; flex: 1; }
.gv-ampliar { border: 2px solid #272526; background: #272526; color: #fff;
              border-radius: 9px; font-weight: 800; font-size: 12px;
              padding: 5px 12px; cursor: pointer; font-family: inherit; }
.gv-ampliar:hover { background: #E0118F; border-color: #A30A67; }
body.gv-expandido { padding: 12px 14px; background: #EEE9EC; }
body.gv-expandido .gv-cuerpo { height: calc(100vh - 150px) !important; }
body.gv-expandido .gv-pie { display: none; }
"""

JS_VISOR = """
(function () {
  // Copia intacta del visor (antes de cualquier zoom o marca) para el popup.
  var ORIGINAL = '<!doctype html>' + document.documentElement.outerHTML;
  var expandido = document.body.classList.contains('gv-expandido');
  var botonAmpliar = document.querySelector('.gv-ampliar');

  function cerrarPopup() {
    try {
      var capa = window.parent.document.getElementById('gmya-visor-popup');
      if (capa) { capa.remove(); }
    } catch (e) {}
    try { if (document.fullscreenElement) { document.exitFullscreen(); } }
    catch (e) {}
  }

  function abrirPopup() {
    var doc;
    try { doc = window.parent.document; doc.body; } catch (e) { doc = null; }
    if (!doc) {                       // sin acceso a la pagina: pantalla completa
      var raiz = document.documentElement;
      if (raiz.requestFullscreen) {
        document.body.classList.add('gv-expandido');
        raiz.requestFullscreen().catch(function () {
          document.body.classList.remove('gv-expandido'); });
        document.addEventListener('fullscreenchange', function () {
          if (!document.fullscreenElement) {
            document.body.classList.remove('gv-expandido'); }
        });
      }
      return;
    }
    var viejo = doc.getElementById('gmya-visor-popup');
    if (viejo) { viejo.remove(); }
    var capa = doc.createElement('div');
    capa.id = 'gmya-visor-popup';
    capa.style.cssText = 'position:fixed;inset:0;z-index:1000000;' +
      'background:rgba(22,20,21,.72);display:flex;align-items:center;' +
      'justify-content:center;';
    var caja = doc.createElement('div');
    caja.style.cssText = 'width:97vw;height:95vh;background:#EEE9EC;' +
      'border:3px solid #272526;border-radius:14px;overflow:hidden;' +
      'box-shadow:8px 8px 0 #E0118F;';
    var marco = doc.createElement('iframe');
    marco.style.cssText = 'width:100%;height:100%;border:0;display:block;';
    marco.setAttribute('title', 'Visor ampliado');
    marco.srcdoc = ORIGINAL.replace('<body>', '<body class="gv-expandido">');
    caja.appendChild(marco);
    capa.appendChild(caja);
    capa.addEventListener('click', function (e) {
      if (e.target === capa) { capa.remove(); } });
    doc.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { capa.remove();
        doc.removeEventListener('keydown', esc); } });
    doc.body.appendChild(capa);
  }

  if (botonAmpliar) {
    if (expandido) {
      botonAmpliar.textContent = '✕ Cerrar (Esc)';
      var pista = document.querySelector('.gv-pista');
      if (pista) { pista.textContent = 'Visor ampliado · cada documento ' +
        'se recorre por separado · Ctrl + rueda: zoom · Esc o ✕ para ' +
        'volver.'; }
      botonAmpliar.onclick = cerrarPopup;
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { cerrarPopup(); } });
    } else {
      botonAmpliar.onclick = abrirPopup;
    }
  }
})();
(function () {
  document.querySelectorAll('.gv-panel').forEach(function (panel) {
    var cuerpo = panel.querySelector('.gv-cuerpo');
    // Marcas seguidas con el mismo numero (p. ej. las lineas de un mismo
    // documento HELISA) forman una sola parada de "Siguiente".
    var marcas = [], previa = null;
    Array.prototype.slice.call(
      cuerpo.querySelectorAll('.gm-marca, tr.marcada')).forEach(function (el) {
        var span = el.querySelector && el.querySelector('td.cotejo span');
        var clave = el.getAttribute('data-etq') ||
          (span ? span.textContent : '') || '';
        if (clave && clave === previa && marcas.length) {
          marcas[marcas.length - 1].push(el);
        } else {
          marcas.push([el]);
        }
        previa = clave;
      });
    var cont = panel.querySelector('.gv-cont');
    var ant = panel.querySelector('.gv-ant');
    var sig = panel.querySelector('.gv-sig');
    var etiquetaZoom = panel.querySelector('.gv-zoom span');
    var idx = -1, zoom = 100;
    function contador() {
      cont.textContent = marcas.length
        ? (idx < 0 ? '0' : (idx + 1)) + ' de ' + marcas.length + ' marcas'
        : 'Sin marcas';
    }
    function ir(i) {
      if (!marcas.length) { return; }
      idx = (i + marcas.length) % marcas.length;
      marcas.forEach(function (g) {
        g.forEach(function (m) { m.classList.remove('gv-foco'); }); });
      marcas[idx].forEach(function (m) { m.classList.add('gv-foco'); });
      var el = marcas[idx][0];
      var r = el.getBoundingClientRect(), c = cuerpo.getBoundingClientRect();
      cuerpo.scrollTo({
        top: cuerpo.scrollTop + r.top - c.top - c.height * 0.3,
        left: el.tagName === 'TR' ? 0
          : Math.max(0, cuerpo.scrollLeft + r.left - c.left - 30),
        behavior: 'smooth'});
      contador();
    }
    if (ant) { ant.onclick = function () { ir(idx < 0 ? -1 : idx - 1); }; }
    if (sig) { sig.onclick = function () { ir(idx + 1); }; }
    if (!marcas.length) {
      if (ant) { ant.disabled = true; }
      if (sig) { sig.disabled = true; }
    }
    contador();

    function aplicar(nuevo, cx, cy) {
      nuevo = Math.max(50, Math.min(400, nuevo));
      if (Math.abs(nuevo - zoom) < 0.5) { return; }
      var fx = (cuerpo.scrollLeft + cx) / Math.max(1, cuerpo.scrollWidth);
      var fy = (cuerpo.scrollTop + cy) / Math.max(1, cuerpo.scrollHeight);
      zoom = nuevo;
      cuerpo.querySelectorAll('.gm-lienzo').forEach(function (l) {
        l.style.width = zoom + '%';
      });
      cuerpo.querySelectorAll('.gv-tabla').forEach(function (t) {
        t.style.fontSize = zoom + '%';
      });
      cuerpo.scrollLeft = fx * cuerpo.scrollWidth - cx;
      cuerpo.scrollTop = fy * cuerpo.scrollHeight - cy;
      etiquetaZoom.textContent = Math.round(zoom) + ' %';
    }
    cuerpo.addEventListener('wheel', function (e) {
      if (!e.ctrlKey && !e.metaKey) { return; }   // rueda sola = desplazar
      e.preventDefault();
      var c = cuerpo.getBoundingClientRect();
      aplicar(zoom * Math.exp(-e.deltaY * 0.0018),
              e.clientX - c.left, e.clientY - c.top);
    }, { passive: false });
    function centro(f) {
      aplicar(zoom * f, cuerpo.clientWidth / 2, cuerpo.clientHeight / 2);
    }
    panel.querySelector('.gv-mas').onclick = function () { centro(1.25); };
    panel.querySelector('.gv-menos').onclick = function () { centro(0.8); };
    panel.querySelector('.gv-cien').onclick = function () {
      centro(100 / zoom); };
  });
})();
"""


def html_visor_documentos(paneles, alto=760, apilado=False):
    """
    Pagina HTML completa del visor. paneles: [{"codigo", "titulo",
    "contenido" (html), "aviso" (opcional), "nota" (opcional)}].
    Cada documento tiene su propio desplazamiento, sus botones de marca
    anterior/siguiente y su zoom.
    """
    bloques = []
    for p in paneles:
        aviso = (f"<div class='gv-aviso'>{p['aviso']}</div>"
                 if p.get("aviso") else "")
        bloques.append(
            "<section class='gv-panel'>"
            f"<div class='gv-cab'><span class='gv-cod'>"
            f"{html.escape(p['codigo'])}</span><span class='gv-titulo' "
            f"title='{html.escape(p['titulo'])}'>"
            f"{html.escape(p['titulo'])}</span></div>"
            "<div class='gv-barra'>"
            "<button class='gv-ant' title='Marca anterior en este "
            "documento'>◀</button><span class='gv-cont'></span>"
            "<button class='gv-sig prim' title='Siguiente marca en este "
            "documento'>Siguiente ▶</button>"
            "<span class='gv-zoom' title='Zoom: Ctrl + rueda del mouse "
            "(o pellizca el touchpad) dentro del documento'>"
            "<button class='gv-menos'>−</button><span>100 %</span>"
            "<button class='gv-mas'>+</button>"
            "<button class='gv-cien' title='Volver a 100 %'>↺</button>"
            "</span></div>"
            f"{aviso}<div class='gv-cuerpo' style='height:{alto}px'>"
            f"{p['contenido']}</div></section>")
    clase = "gv-grid uno" if apilado or len(paneles) == 1 else "gv-grid"
    return ("<!doctype html><html lang='es' translate='no'><head>"
            "<meta charset='utf-8'><meta name='google' "
            "content='notranslate'>"
            f"<style>{CSS_VISOR}</style></head><body>"
            "<div class='gv-arriba'><span class='gv-pista'>Cada documento "
            "se recorre por separado. Ampliar abre el visor sobre toda la "
            "pantalla (Esc para cerrar).</span><button class='gv-ampliar' "
            "title='Ver el visor en una ventana sobre toda la pantalla'>"
            "⛶ Ampliar visor</button></div>"
            f"<div class='{clase}'>{''.join(bloques)}</div>"
            "<div class='gv-pie'>Rueda del mouse: desplazarse dentro del "
            "documento · Ctrl + rueda (o pellizco en el touchpad): zoom · "
            "Pasa el mouse sobre una marca para ver la explicación.</div>"
            f"<script>{JS_VISOR}</script><script>{JS_GLOBOS}</script>"
            "</body></html>")
