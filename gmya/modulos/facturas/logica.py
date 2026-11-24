"""Renombrar facturas (v6.22, sin Streamlit): cada archivo de factura queda
como «PROVEEDOR NÚMERO.pdf».

Contrato:
  leer_documento(nombre, contenido) -> datos crudos: {"tipo_doc",
      "candidatos" [(nit, dv, nombre)] en orden de aparicion, "numero",
      "fuente", "es_factura", "motivo"}. Lee PDF (texto), XML de la DIAN
      (Invoice / CreditNote / AttachedDocument) y .zip con esos archivos.
  nit_propio_probable(documentos) -> NIT que aparece en la mayoria de los
      documentos (la empresa de la carpeta) o "".
  resolver(doc, nit_propio, nombres_guardados) -> {"nit", "proveedor",
      "numero", "estado", "nota"}: el tercero es la contraparte (el emisor
      en las compras; el cliente si la factura la emitio la propia empresa).
  nombre_nuevo(proveedor, numero, extension, extra="") y unicos(nombres).
  anotacion_original(nombre) -> lo que va desde «codigo …» en el nombre
      original (clasificacion de la persona), para conservarlo al final.
  archivos_de_carpeta(ruta, recursivo=False) -> [(ruta, bytes)].
  aplicar(plan, modo, origen, destino) -> registro. modo "copiar" (a una
      carpeta destino) o "renombrar" (en la misma carpeta). Nunca escribe
      dentro de «001. EMPRESAS ACTIVAS USO DIARIO» (solo lectura).
  zip_renombrados(plan) -> bytes (archivos renombrados + REGISTRO.xlsx).
  nombres_guardados() / guardar_nombres(cambios): nombre a usar por NIT
      (facturas_proveedores.json en la carpeta GMYA Tools; si no hay, en
      este equipo).
Reglas: el numero se valida con el rango de la resolucion de facturacion
cuando el documento lo trae; el NIT con su digito de verificacion. Lo que
no se identifica queda con su nombre y se avisa (nada se inventa).
Depende de: gmya.comun.config_equipo, gmya.registro.logica
"""

import datetime
import io
import json
import re
import shutil
import unicodedata
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path

from gmya.comun.config_equipo import guardar_config, leer_config
from gmya.registro.logica import _es_carpeta_de_empresas, carpeta_gmya

EXTENSIONES = (".pdf", ".xml", ".zip")
ARCHIVO_NOMBRES = "facturas_proveedores.json"
SUFIJOS = re.compile(r"\b(S\.?\s?A\.?\s?S\.?|S\.?\s?A\.?|LTDA\.?|S\.?\s?C\.?\s?A\.?|"
                     r"E\.?\s?U\.?|S\.?\s?EN\s?C\.?|& CIA\.?|SAS|BIC)\b", re.I)
# Palabras de otra columna que se pegan al nombre en el texto del PDF.
CORTES = re.compile(r"\s+(FACTURA|CIUDAD\s*:|DIRECCI[OÓ]N|NIT\b|N\.I\.T|"
                    r"TEL[EÉ]FONO|TEL\.|FECHA|HORA|PA[IÍ]S\s*:|MONEDA|No\.|"
                    r"N[°º]|NRO|R[EÉ]GIMEN|EMAIL|CORREO|C[OÓ]DIGO)", re.I)
ETIQUETAS_NOMBRE = re.compile(
    r"^(?:Nombre\s*/\s*Raz[oó]n\s+Social|Nombre\s+o\s+Raz[oó]n\s+Social|"
    r"Raz[oó]n\s+Social|Nombre\s+Comercial|Nombre|Se[ñn]or(?:es)?\s*\(?\w*\)?|"
    r"Cliente|Adquiriente|Proveedor)\s*:\s*(.+)$", re.I)
RE_NIT = re.compile(
    r"(?:N\.?\s?I\.?\s?T\.?|Nit\s+del\s+Emisor|Nit/C\.?\s?C\.?|"
    r"NIT\s*/\s*CC)\s*[:.]?\s*:?\s*([0-9][0-9.]{5,13})(?:\s*-\s*|\s+)?(\d)?\b",
    re.I)


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def digito_verificacion(nit):
    pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    s = sum(int(d) * pesos[i] for i, d in enumerate(reversed(str(nit))))
    r = s % 11
    return r if r < 2 else 11 - r


def _sin_tildes(texto):
    return unicodedata.normalize("NFKD", str(texto or "")).encode(
        "ascii", "ignore").decode()


def limpiar_nombre(texto):
    t = re.sub(r"\s+", " ", str(texto or "")).strip(" ,:;-")
    m = CORTES.search(" " + t)
    if m and m.start() > 2:
        t = (" " + t)[:m.start()].strip(" ,:;-")
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", t)
    return re.sub(r"\s+", " ", t).strip(" ,").upper()


def anotacion_original(nombre_archivo):
    """Lo que la persona agrego al nombre desde «codigo …» (p. ej. «codigo
    100 200.000-300 400.000»): se conserva al final del nombre nuevo."""
    m = re.search(r"(c[oó]digo[\s_-]*\d.*)$", Path(nombre_archivo).stem, re.I)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1).replace("_", " ")).strip(" -").upper()


def _es_nombre(linea):
    t = linea.strip()
    if len(t) < 3 or len(re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", t)) < 3:
        return False
    if re.match(r"^(P[aá]gina|Representaci|Datos|Informaci|R[eé]gimen|"
                r"Persona|Direcci|Tel|Email|Correo|www|http|Autorizaci|"
                r"Resoluci|Fecha|Hora|CUFE|CUDE|ICA|GRANDES|AUTORRET|"
                r"AGENTE|NO SOMOS|SOMOS|RETENER|Nota|Venta|FACTURA)",
                t, re.I):
        return False
    return not re.match(r"^[\d\s.,:$-]+$", t)


# ------------------------------------------------------------
# Lectura
# ------------------------------------------------------------
def _texto_pdf(contenido, paginas=2):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        return "\n".join((p.extract_text() or "")
                         for p in pdf.pages[:paginas])


def _candidatos_texto(lineas):
    """[(nit, dv, nombre)] en el orden en que aparecen los NIT."""
    salida = []
    for k, linea in enumerate(lineas):
        for m in RE_NIT.finditer(linea):
            nit = re.sub(r"\D", "", m.group(1))
            if not 6 <= len(nit) <= 10:
                continue
            dv = m.group(2)
            nombre = ""
            # 1) etiqueta en la misma linea antes del NIT o en las 3 de antes
            for j in range(k, max(-1, k - 4), -1):
                texto = lineas[j][:m.start()] if j == k else lineas[j]
                e = ETIQUETAS_NOMBRE.match(texto.strip())
                if e and _es_nombre(e.group(1)):
                    nombre = limpiar_nombre(e.group(1))
                    break
            # 2) linea(s) de encabezado justo encima del NIT
            if not nombre:
                arriba = [lineas[j] for j in range(k - 1, max(-1, k - 4), -1)
                          if _es_nombre(lineas[j])]
                con_sufijo = [a for a in arriba
                              if SUFIJOS.search(limpiar_nombre(a))]
                elegido = con_sufijo[0] if con_sufijo else (
                    arriba[0] if arriba else "")
                nombre = limpiar_nombre(elegido)
            salida.append((nit, dv, nombre))
    return salida


def _rango(texto):
    m = re.search(r"rango\s*desde\s*:?\s*([A-Z0-9]*?[A-Z])?\s?(\d+)\s*hasta\s*"
                  r":?\s*([A-Z0-9]*?[A-Z])?\s?(\d+)", texto, re.I)
    if not m:
        return None
    return ((m.group(1) or "").upper(), int(m.group(2)), int(m.group(4)))


def _numero_texto(texto):
    rango = _rango(texto)
    if rango:
        prefijo, desde, hasta = rango
        patron = re.compile(rf"(?<![A-Z0-9]){re.escape(prefijo)}\s?-?\s?"
                            rf"(\d{{1,12}})(?!\d)", re.I) if prefijo else None
        if patron:
            hallados = [int(x) for x in patron.findall(texto)]
            dentro = [n for n in hallados if desde <= n <= hasta
                      and n not in (desde, hasta)]
            if dentro:
                return f"{prefijo}{Counter(dentro).most_common(1)[0][0]}", \
                    "rango de la resolución"
    patrones = [
        r"N[uú]mero\s+de\s+(?:Factura|documento|Nota)\s*:?\s*([A-Z0-9-]{3,})",
        r"FACTURA\s+ELECTR[OÓ]NICA\s+DE\s+VENTA\s*(?:No\.?|N[°º]\.?|Nro\.?)?"
        r"\s*:?\s*([A-Z]{0,6}\s?-?\d{3,}[A-Z0-9-]*)",
        r"NOTA\s+CR[EÉ]DITO\s*(?:ELECTR[OÓ]NICA)?\s*(?:No\.?|N[°º]\.?)\s*:?"
        r"\s*([A-Z0-9-]{3,})",
        r"(?:^|\s)N[°º]\.?\s*:?\s*([A-Z]{0,6}\d{4,}[A-Z0-9-]*)",
        r"(?:^|\s)No\.\s*([A-Z]{1,6}\s?\d{3,})",
        r"Factura\s*(?:No\.?|N[°º]|#)\s*:?\s*([A-Z]{0,6}\s?-?\d{3,})",
    ]
    for p in patrones:
        m = re.search(p, texto, re.I | re.M)
        if m:
            return re.sub(r"\s+", "", m.group(1)).strip("-").upper(), \
                "etiqueta del documento"
    return "", ""


def _tipo_documento(texto):
    cabeza = _sin_tildes(texto[:600]).upper()
    if "NOTA CREDITO" in cabeza:
        return "Nota crédito"
    if "NOTA DEBITO" in cabeza:
        return "Nota débito"
    if "DOCUMENTO SOPORTE" in cabeza:
        return "Documento soporte"
    if re.search(r"FACTURA|CUFE", _sin_tildes(texto).upper()):
        return "Factura"
    return ""


def _xml(contenido):
    """Invoice / CreditNote / DebitNote de la DIAN (o AttachedDocument que
    los trae dentro)."""
    import xml.etree.ElementTree as ET
    raiz = ET.fromstring(contenido)

    def local(e):
        return e.tag.rsplit("}", 1)[-1]
    if local(raiz) == "AttachedDocument":
        for e in raiz.iter():
            if local(e) == "Description" and e.text and "<" in e.text and \
                    re.search(r"<(\w+:)?(Invoice|CreditNote|DebitNote)\b",
                              e.text):
                return _xml(e.text.strip().encode("utf-8"))
    tipo = {"Invoice": "Factura", "CreditNote": "Nota crédito",
            "DebitNote": "Nota débito"}.get(local(raiz), "")
    numero = next((e.text for e in raiz if local(e) == "ID"), "") or ""

    def parte(nombre_parte):
        for e in raiz:
            if local(e) == nombre_parte:
                nit = nombre = ""
                for x in e.iter():
                    if local(x) == "CompanyID" and not nit:
                        nit = re.sub(r"\D", "", x.text or "")
                        dv = x.get("schemeID")
                    if local(x) in ("RegistrationName", "Name") and \
                            not nombre and x.text:
                        nombre = x.text
                return nit, nombre
        return "", ""
    emisor = parte("AccountingSupplierParty")
    cliente = parte("AccountingCustomerParty")
    cand = [(n, None, limpiar_nombre(nom)) for n, nom in (emisor, cliente)
            if n]
    return {"tipo_doc": tipo, "candidatos": cand,
            "numero": re.sub(r"\s+", "", numero).upper(),
            "origen_numero": "XML de la DIAN", "fuente": "XML",
            "es_factura": bool(tipo and numero)}


def leer_documento(nombre, contenido):
    ext = Path(nombre).suffix.lower()
    try:
        if ext == ".zip":
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                internos = sorted(z.namelist(), key=lambda n: (
                    not n.lower().endswith(".xml"), n))
                for n in internos:
                    if n.lower().endswith((".xml", ".pdf")):
                        d = leer_documento(n, z.read(n))
                        if d.get("es_factura"):
                            d["fuente"] = f"ZIP ({d['fuente']})"
                            return d
            return {"es_factura": False, "candidatos": [], "numero": "",
                    "tipo_doc": "", "fuente": "ZIP",
                    "motivo": "El ZIP no trae una factura reconocible."}
        if ext == ".xml":
            return _xml(contenido)
        texto = _texto_pdf(contenido)
    except Exception as error:
        return {"es_factura": False, "candidatos": [], "numero": "",
                "tipo_doc": "", "fuente": ext.upper().strip("."),
                "motivo": f"No se pudo leer ({type(error).__name__})."}
    lineas = [l for l in texto.split("\n") if l.strip()]
    if len(re.sub(r"\s", "", texto)) < 40:
        return {"es_factura": False, "candidatos": [], "numero": "",
                "tipo_doc": "", "fuente": "PDF",
                "motivo": "PDF sin texto (escaneado): no se puede leer."}
    numero, origen = _numero_texto(texto)
    tipo = _tipo_documento(texto)
    return {"tipo_doc": tipo, "candidatos": _candidatos_texto(lineas),
            "numero": numero, "origen_numero": origen, "fuente": "PDF",
            "es_factura": bool(tipo and numero)}


def nit_propio_probable(documentos):
    cuenta = Counter()
    for d in documentos:
        for nit in {c[0] for c in d.get("candidatos", [])}:
            cuenta[nit] += 1
    if not cuenta or len(documentos) < 2:
        return ""
    nit, n = cuenta.most_common(1)[0]
    return nit if n >= max(2, len(documentos) / 2) else ""


def resolver(doc, nit_propio="", guardados=None):
    guardados = guardados or {}
    salida = {"nit": "", "proveedor": "", "numero": doc.get("numero", ""),
              "tipo_doc": doc.get("tipo_doc", ""), "estado": "",
              "nota": doc.get("motivo", "")}
    otros = [c for c in doc.get("candidatos", []) if c[0] != nit_propio]
    if otros:
        nit, dv, nombre = otros[0]
        salida["nit"] = nit
        salida["proveedor"] = guardados.get(nit) or nombre
        if dv is not None and str(digito_verificacion(nit)) != str(dv):
            salida["nota"] = (f"El dígito de verificación del NIT {nit}-{dv} "
                              "no cuadra: confirmar el tercero.")
        if guardados.get(nit) and guardados[nit] != nombre:
            salida["nota"] = (salida["nota"] + " " if salida["nota"] else "") \
                + f"Nombre guardado para el NIT (en el documento: {nombre})."
    if not doc.get("es_factura"):
        salida["estado"] = "No es factura"
        salida["nota"] = salida["nota"] or ("No se encontró número de "
                                            "factura (¿extracto u otro "
                                            "documento?).")
    elif not salida["proveedor"] or not salida["numero"]:
        salida["estado"] = "Incompleto"
        salida["nota"] = salida["nota"] or "Falta el proveedor o el número."
    else:
        salida["estado"] = "Listo"
    return salida


# ------------------------------------------------------------
# Nombres
# ------------------------------------------------------------
def nombre_nuevo(proveedor, numero, extension, extra=""):
    base = f"{limpiar_nombre(proveedor)} {re.sub(r'[^A-Za-z0-9-]', '', str(numero or '')).upper()}"
    if extra:
        base += " " + extra
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", base)
    base = re.sub(r"\s+", " ", base).strip(" .")[:150]
    return base + extension.lower()


def unicos(nombres, existentes=()):
    usados = {n.lower() for n in existentes}
    salida = []
    for n in nombres:
        if not n:
            salida.append(n)
            continue
        base, ext = Path(n).stem, Path(n).suffix
        candidato, k = n, 2
        while candidato.lower() in usados:
            candidato = f"{base} ({k}){ext}"
            k += 1
        usados.add(candidato.lower())
        salida.append(candidato)
    return salida


def _ruta_nombres():
    try:
        carpeta = carpeta_gmya()
    except Exception:
        carpeta = ""
    if carpeta and not _es_carpeta_de_empresas(carpeta):
        return Path(carpeta) / ARCHIVO_NOMBRES
    return None


def nombres_guardados():
    ruta = _ruta_nombres()
    if ruta is not None:
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(leer_config().get("facturas_proveedores") or {})


def guardar_nombres(cambios):
    """cambios: {nit: nombre}. Combina con lo guardado (no borra lo de
    otros)."""
    datos = nombres_guardados()
    datos.update({str(k): v for k, v in cambios.items() if k and v})
    ruta = _ruta_nombres()
    if ruta is not None:
        try:
            ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            return "carpeta GMYA Tools (compartido)"
        except Exception:
            pass
    guardar_config(facturas_proveedores=datos)
    return "este equipo"


# ------------------------------------------------------------
# Carpeta y salida
# ------------------------------------------------------------
def archivos_de_carpeta(ruta, recursivo=False):
    base = Path(str(ruta).strip().strip('"'))
    if not base.is_dir():
        raise ValueError(f"No existe la carpeta «{ruta}».")
    patron = base.rglob("*") if recursivo else base.glob("*")
    return [(p, p.read_bytes()) for p in sorted(patron)
            if p.is_file() and p.suffix.lower() in EXTENSIONES]


def protegida(ruta):
    return bool(ruta) and _es_carpeta_de_empresas(str(ruta))


def _registro_excel(filas):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    libro = Workbook()
    h = libro.active
    h.title = "REGISTRO"
    h.append(["Archivo original", "Archivo nuevo", "Proveedor", "NIT",
              "Número", "Tipo", "Estado", "Nota"])
    for c in h[1]:
        c.font = Font(bold=True)
    for f in filas:
        h.append([f.get("original"), f.get("nuevo"), f.get("proveedor"),
                  f.get("nit"), f.get("numero"), f.get("tipo_doc"),
                  f.get("estado"), f.get("nota")])
    for col, ancho in zip("ABCDEFGH", (55, 55, 40, 14, 18, 14, 14, 60)):
        h.column_dimensions[col].width = ancho
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def aplicar(plan, modo, destino=None):
    """plan: [{"ruta": Path origen, "nuevo": nombre o "", ...}]. Devuelve el
    registro. Los que no tienen nombre nuevo no se tocan (al copiar se
    copian con su nombre)."""
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H%M")
    if modo == "renombrar":
        for f in plan:
            if protegida(f["ruta"]):
                raise PermissionError(
                    "La carpeta está dentro de «001. EMPRESAS ACTIVAS USO "
                    "DIARIO», que es solo lectura: copia las facturas "
                    "renombradas a otra carpeta o descárgalas en ZIP.")
    else:
        if not destino:
            raise ValueError("Falta la carpeta destino.")
        if protegida(destino):
            raise PermissionError(
                "No se puede escribir dentro de «001. EMPRESAS ACTIVAS USO "
                "DIARIO» (solo lectura): elige otra carpeta destino.")
        Path(destino).mkdir(parents=True, exist_ok=True)
    registro = []
    for f in plan:
        origen = Path(f["ruta"])
        nuevo = f.get("nuevo") or origen.name
        if modo == "renombrar":
            carpeta = origen.parent
            if nuevo == origen.name:
                registro.append(dict(f, original=origen.name, nuevo=nuevo,
                                     accion="sin cambio"))
                continue
            otros = {p.name for p in carpeta.iterdir() if p != origen}
            nuevo = unicos([nuevo], otros)[0]
            origen.rename(carpeta / nuevo)
            accion = "renombrado"
        else:
            carpeta = Path(destino)
            nuevo = unicos([nuevo], {p.name for p in carpeta.iterdir()})[0]
            shutil.copy2(origen, carpeta / nuevo)
            accion = "copiado"
        registro.append(dict(f, original=origen.name, nuevo=nuevo,
                             accion=accion))
    carpeta_reg = Path(destino) if modo != "renombrar" else \
        Path(plan[0]["ruta"]).parent if plan else None
    if carpeta_reg is not None:
        (carpeta_reg / f"REGISTRO RENOMBRADO FACTURAS {fecha}.xlsx") \
            .write_bytes(_registro_excel(registro))
    return registro


def zip_renombrados(plan):
    """plan: [{"original", "contenido", "nuevo", ...}]."""
    salida = io.BytesIO()
    nombres = unicos([f.get("nuevo") or f["original"] for f in plan])
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for f, n in zip(plan, nombres):
            z.writestr(n, f["contenido"])
        z.writestr("REGISTRO RENOMBRADO FACTURAS.xlsx", _registro_excel(
            [dict(f, nuevo=n) for f, n in zip(plan, nombres)]))
    return salida.getvalue()
