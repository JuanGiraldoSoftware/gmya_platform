"""Automatizacion Odoo para EMPRESA A: factura + relacion de afiliados SURA ->
Excel de importacion de asiento en Odoo (sin Streamlit).

Contrato:
  leer_factura_sura(contenido) / leer_relacion_sura(contenido)
  lineas_odoo_sura(factura, relacion, partidas, periodo_texto="") -> lineas del asiento
      (cuentas 5/7 + 01 salud / 02 vida segun centro de costo; 136595
      descuento 50 % del beneficiario al empleado; IVA 24080206; ajuste
      53959501 debito / 429581 credito con analitica 004).
  generar_excel_odoo_sura(factura, relacion, filas) -> libro con hojas
      "Importar Odoo" y "Control".
  maestro_odoo / guardar_maestro_odoo / leer_relacion_cuentas(contenido)
      -> relacion de cuentas y centros de costo (dato privado, v6.23).
  coberturas_odoo / guardar_coberturas_odoo -> beneficiarios al 100 %
      (excepciones de contrato) en odoo_coberturas.json de la carpeta
      GMYA Tools.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.config_equipo, gmya.registro.logica,
gmya.registro.privados
"""

import datetime
import io
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

from gmya.comun.texto import comparable, _solo_digitos
from gmya.comun.numeros import formato_cop
from gmya.comun.config_equipo import guardar_config, leer_config
from gmya.registro.logica import carpeta_gmya, _es_carpeta_de_empresas
from gmya.registro.privados import guardar_privado, leer_privado


# ============================================================
# AUTOMATIZACIONES ODOO: SEGUROS SURA (EMPRESA A)
# ============================================================
# Arma el Excel de importacion de facturas de proveedor de Odoo a partir de
# la FACTURA electronica de Seguros de Vida Suramericana y su RELACION de
# asegurados (PDF). Dos productos:
#   - Salud colectivo (ramo 091): relacion por afiliado con sus
#     beneficiarios; prima del periodo + IVA 5 %.
#   - Vida de grupo (ramo 083): recibo de cobro con la relacion de
#     asegurados; sin IVA.
# Reglas (confirmadas con facturas reales importadas en Odoo):
#   - Una linea por asegurado con su prima del periodo (sin IVA).
#   - Cuenta: la columna "Cuenta" (5 o 7) de la relacion de cuentas y
#     centros de costo de la empresa + el producto: 5105 54 01 / 7305 54 01
#     salud colectivo, 5105 54 02 / 7305 54 02 vida de grupo.
#   - Analitica: el centro de costo del empleado en 3 digitos
#     ({"227": 100.0}). Los beneficiarios usan los del afiliado.
#   - Beneficiarios: la empresa asume el 50 %; el otro 50 % es descuento al
#     empleado: cuenta 136595 con el empleado como tercero. Excepcion:
#     beneficiarios cubiertos al 100 % por contrato (coberturas_odoo).
#   - IVA (salud): una linea a 24080206 por el IVA de la factura.
#   - Diferencia factura vs relacion (aproximacion de SURA): debito
#     53959501 o credito 429581 (precio negativo), analitica 004.
# Solo lee los PDF cargados; no escribe en ninguna carpeta.
SURA_CONTACTO = "SEGUROS DE VIDA SURAMERICANA S.A."
SURA_NIT = "890903790"
ODOO_DIARIO_COMPRAS = "Compras"
CUENTA_DESCUENTO_EMPLEADO = 136595
CUENTA_IVA_SURA = 24080206
CUENTA_AJUSTE_DEBITO = 53959501
CUENTA_AJUSTE_CREDITO = 429581
ANALITICA_AJUSTE = "004"
PORCENTAJE_EMPRESA_BENEFICIARIO = 50.0
# Cuenta 5 o 7 de la relacion de la empresa -> raiz de la cuenta Odoo.
RAIZ_CUENTA_ODOO = {5: "510554", 7: "730554"}
PRODUCTOS_SURA = OrderedDict([
    ("salud", {"nombre": "Salud colectivo", "sufijo": "01",
               "etiqueta": "SALUD COLECTIVO", "ramo": "091"}),
    ("vida", {"nombre": "Vida de grupo", "sufijo": "02",
              "etiqueta": "SEGURO VIDA GRUPO", "ramo": "083"}),
])

# Relacion de cuentas y centros de costo de cada empresa: dato privado del
# cliente (empleados), fuera del codigo. Se importa desde el modulo (Excel
# de la empresa) y se guarda en ARCHIVO_MAESTRO_ODOO (carpeta GMYA Tools).
ARCHIVO_MAESTRO_ODOO = "odoo_maestro"

EMPRESAS_ODOO = OrderedDict([
    ("EMPRESA A", {
        "nombre": "EMPRESA A S.A.S.",
        "corto": "EMPRESA A",
        "nit": "900000001",
        # Afiliado -> beneficiarios cubiertos al 100 % por terminos de su
        # contrato (los demas: 50 % empresa y 50 % descuento al empleado).
        # Dato privado: se ajusta desde el modulo y se guarda en
        # ARCHIVO_COBERTURAS_ODOO (carpeta GMYA Tools).
        "beneficiarios_100": {},
    }),
])

# Coberturas al 100 % ajustadas desde el modulo: archivo compartido en la
# carpeta "GMYA Tools" (todos los equipos ven lo mismo); si no hay carpeta,
# se guardan en la configuracion de este equipo.
ARCHIVO_COBERTURAS_ODOO = "odoo_coberturas.json"


def _ruta_coberturas_odoo():
    try:
        carpeta = carpeta_gmya()
    except Exception:
        carpeta = ""
    if carpeta and not _es_carpeta_de_empresas(carpeta):
        return Path(carpeta) / ARCHIVO_COBERTURAS_ODOO
    return None


def coberturas_odoo(clave):
    """{id afiliado: {id beneficiario: nombre}} cubiertos al 100 %."""
    guardadas = None
    ruta = _ruta_coberturas_odoo()
    if ruta is not None:
        try:
            guardadas = json.loads(ruta.read_text(encoding="utf-8")) \
                .get(clave)
        except Exception:
            guardadas = None
    if guardadas is None:
        guardadas = (leer_config().get("odoo_coberturas") or {}).get(clave)
    if guardadas is None:
        guardadas = EMPRESAS_ODOO[clave].get("beneficiarios_100", {})
    return {str(a): {str(b): n for b, n in (v or {}).items()}
            for a, v in guardadas.items() if v}


def _combinar_coberturas(actual, base, nuevas):
    """v6.7: aplica solo LOS CAMBIOS de esta persona (nuevas - base) sobre
    lo que hay hoy guardado (actual), para no borrar lo que otra persona
    guardo mientras tanto."""
    def pares(d):
        return {(str(a), str(b)): n for a, v in (d or {}).items()
                for b, n in (v or {}).items()}
    p_act, p_base, p_new = pares(actual), pares(base), pares(nuevas)
    resultado = dict(p_act)
    for k in set(p_base) - set(p_new):        # quitados por esta persona
        resultado.pop(k, None)
    for k in set(p_new) - set(p_base):        # agregados por esta persona
        resultado[k] = p_new[k]
    salida = {}
    for (a, b), n in resultado.items():
        salida.setdefault(a, {})[b] = n
    return salida, p_act != p_base


def guardar_coberturas_odoo(clave, coberturas, base=None):
    """Guarda las coberturas al 100 %. Devuelve donde quedaron. Con 'base'
    (lo que habia cuando la persona empezo a editar) solo se aplican sus
    cambios sobre lo guardado hoy (v6.7: dos personas a la vez no se
    borran)."""
    if base is not None:
        coberturas, combinado = _combinar_coberturas(
            coberturas_odoo(clave), base, coberturas)
    else:
        combinado = False
    limpias = {str(a): {str(b): n for b, n in v.items()}
               for a, v in coberturas.items() if v}
    ruta = _ruta_coberturas_odoo()
    if ruta is not None:
        try:
            datos = {}
            if ruta.exists():
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            datos[clave] = limpias
            ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            return "carpeta GMYA Tools (compartido)" + (
                "; se combinó con cambios que otra persona guardó mientras "
                "editabas" if combinado else "")
        except Exception:
            pass
    todas = leer_config().get("odoo_coberturas") or {}
    todas[clave] = limpias
    guardar_config(odoo_coberturas=todas)
    return "este equipo"


MESES_SURA = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP",
              "OCT", "NOV", "DIC"]
MESES_SURA_EN = {"JAN": 1, "APR": 4, "AUG": 8, "DEC": 12}


def maestro_odoo(clave):
    """[(identificacion, nombre, cc, nombre centro, cuenta 5/7)] guardados
    de la empresa (dato privado, fuera del codigo)."""
    datos = leer_privado(ARCHIVO_MAESTRO_ODOO, {}) or {}
    filas = []
    for f in datos.get(clave) or []:
        try:
            filas.append((str(f[0]).strip(), str(f[1]).strip(),
                          str(f[2]).strip(), str(f[3]).strip(), int(f[4])))
        except (IndexError, TypeError, ValueError):
            continue
    return filas


def guardar_maestro_odoo(clave, filas):
    datos = leer_privado(ARCHIVO_MAESTRO_ODOO, {}) or {}
    datos[clave] = [list(f) for f in filas]
    return guardar_privado(ARCHIVO_MAESTRO_ODOO, datos)


_COLS_MAESTRO = {
    "id": ("IDENTIFICACION", "CEDULA", "DOCUMENTO", "NUMERO DE ID", "ID"),
    "nombre": ("NOMBRE",),
    "nombre_cc": ("NOMBRE CENTRO", "NOMBRE CC", "NOMBRE DEL CENTRO",
                  "DESCRIPCION CENTRO", "AREA"),
    "cc": ("CENTRO DE COSTO", "CENTRO COSTO", "CODIGO CENTRO", "COD CC",
           "CC"),
    "cuenta": ("CUENTA",),
}


def leer_relacion_cuentas(contenido, nombre_archivo=""):
    """Excel/CSV de la relacion de cuentas y centros de costo de la empresa
    -> (filas [(id, nombre, cc, nombre centro, cuenta)], avisos). Busca la
    fila de encabezados; la cuenta debe ser 5 o 7 (o empezar por 5/7)."""
    from gmya.comun.grilla import tabla_desde_archivo
    tabla = [list(f) for f in tabla_desde_archivo(contenido)]
    for i, fila in enumerate(tabla[:30]):
        textos = [comparable(str(v or "")) for v in fila]
        cols = {}
        for campo, claves in _COLS_MAESTRO.items():
            for j, t in enumerate(textos):
                if j in cols.values() or not t:
                    continue
                if any(t == k or t.startswith(k + " ") for k in claves) and \
                        not (campo == "nombre" and "CENTRO" in t) and \
                        not (campo == "cc" and t.startswith("NOMBRE")):
                    cols[campo] = j
                    break
        if {"id", "nombre", "cc", "cuenta"} <= set(cols):
            break
    else:
        raise ValueError("No se encontraron los encabezados (identificación, "
                         "nombre, centro de costo y cuenta).")
    filas, avisos = [], []
    for fila in tabla[i + 1:]:
        def val(c):
            j = cols.get(c)
            return "" if j is None or j >= len(fila) or fila[j] is None \
                else str(fila[j]).strip()
        ident = re.sub(r"\.0$", "", val("id")).replace(".", "").strip()
        if not ident or not re.fullmatch(r"[0-9A-Za-z-]+", ident):
            continue
        cuenta = re.sub(r"\.0$", "", val("cuenta"))[:1]
        if cuenta not in ("5", "7"):
            avisos.append(f"{ident}: la cuenta «{val('cuenta')}» no es 5 ni "
                          "7; no se importa.")
            continue
        cc = re.sub(r"\.0$", "", val("cc"))
        cc = cc.zfill(4) if cc.isdigit() else cc
        filas.append((ident, val("nombre"), cc, val("nombre_cc"),
                      int(cuenta)))
    if not filas:
        raise ValueError("La relación no tiene empleados con cuenta 5 o 7.")
    return filas, avisos


def maestro_empresa_odoo(clave):
    """{identificacion: {nombre, cc, nombre_cc, cuenta}} de la empresa."""
    return {str(i).strip(): {"nombre": n, "cc": str(cc).strip(),
                             "nombre_cc": ncc, "cuenta": int(c)}
            for i, n, cc, ncc, c in maestro_odoo(clave)}


def analitica_cc(cc):
    """'0227' -> '227'; '0001' -> '001' (como en Odoo)."""
    d = _solo_digitos(cc)
    return d[-3:].zfill(3) if d else ""


def cuenta_odoo(cuenta_5_7, producto):
    raiz = RAIZ_CUENTA_ODOO.get(int(cuenta_5_7)) if cuenta_5_7 else None
    return int(raiz + PRODUCTOS_SURA[producto]["sufijo"]) if raiz else None


def _monto_sura(texto):
    """'$ 1,234,567' / '$12,345' (factura y vida) o '$123.456' /
    '$12.345,6' (relacion de salud) -> float."""
    t = str(texto or "").replace("$", "").replace("COP", "").strip()
    t = t.replace(" ", "")
    if not t:
        return 0.0
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):          # 1.234,5
            t = t.replace(".", "").replace(",", ".")
        else:                                    # 1,234.5
            t = t.replace(",", "")
    elif "," in t:
        partes = t.split(",")
        # ',9' / ',55' decimales; ',549' miles.
        t = t.replace(",", "") if len(partes[-1]) == 3 else \
            t.replace(",", ".")
    elif "." in t:
        partes = t.split(".")
        t = t.replace(".", "") if len(partes[-1]) == 3 else t
    try:
        return float(t)
    except ValueError:
        return 0.0


def _fecha_sura(texto):
    """'2026-10-23', '15-OCT-2026', '17-MAY-01' -> date."""
    t = str(texto or "").strip().upper()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)),
                             int(m.group(3)))
    m = re.match(r"(\d{1,2})-([A-Z]{3})-(\d{2,4})$", t)
    if m:
        mes = (MESES_SURA.index(m.group(2)) + 1 if m.group(2) in MESES_SURA
               else MESES_SURA_EN.get(m.group(2)))
        anio = int(m.group(3))
        if anio < 100:
            anio += 2000 if anio <= 50 else 1900
        if mes:
            return datetime.date(anio, mes, int(m.group(1)))
    return None


def fecha_txt_sura(fecha):
    """date -> '15-OCT-2026' (como en las etiquetas)."""
    return f"{fecha.day:02d}-{MESES_SURA[fecha.month - 1]}-{fecha.year}"


def periodo_por_defecto_sura(fecha, dia=15):
    """Ciclo de cobro (del dia 15 al 15) que contiene la fecha."""
    if not fecha:
        return None
    if fecha.day >= dia:
        inicio = fecha.replace(day=dia)
    else:
        mes = fecha.month - 1 or 12
        inicio = datetime.date(fecha.year - (fecha.month == 1), mes, dia)
    mes = inicio.month % 12 + 1
    fin = datetime.date(inicio.year + (inicio.month == 12), mes, dia)
    return inicio, fin


def texto_periodo_sura(periodo):
    if not periodo or not periodo[0] or not periodo[1]:
        return ""
    return f"{fecha_txt_sura(periodo[0])} a {fecha_txt_sura(periodo[1])}"


def _paginas_pdf_sura(contenido):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        textos = []
        for pagina in pdf.pages:
            t = pagina.extract_text() or ""
            t = re.sub(r"(\(cid:\d+\))+", "", t)
            textos.append(t)
    return textos


def _siguiente_linea(lineas, patron):
    for i, linea in enumerate(lineas):
        if re.search(patron, linea, re.I):
            for siguiente in lineas[i + 1:]:
                if siguiente.strip():
                    return siguiente.strip()
    return ""


def leer_factura_sura(contenido):
    """Factura electronica de venta de SURA (PDF de una pagina)."""
    texto = "\n".join(_paginas_pdf_sura(contenido))
    lineas = [l for l in texto.split("\n") if l.strip()]
    if "SURAMERICANA" not in texto.upper() or \
            not re.search(r"Factura Electr.nica de venta", texto, re.I):
        raise ValueError("No parece una factura electrónica de Seguros de "
                         "Vida Suramericana.")

    def buscar(patron, grupo=1):
        m = re.search(patron, texto, re.I)
        return m.group(grupo).strip() if m else ""

    numero = buscar(r"Factura Electr.nica de venta\s+(\d+)")
    fecha_linea = _siguiente_linea(lineas, r"^Fecha factura")
    fecha = _fecha_sura(fecha_linea.split()[0]) if fecha_linea else None
    plano = re.sub(r"\s+", " ", texto.upper())
    if "SALUD" in plano and "COLECTIVO" in plano:
        producto = "salud"
    elif "VIDA DE GRUPO" in plano or "VIDA GRUPO" in plano:
        producto = "vida"
    else:
        producto = None
    subtotal = _monto_sura(buscar(r"Subtotal\s+(\$\s*[\d.,]+)"))
    iva = _monto_sura(buscar(r"\bIVA\s+(\$\s*[\d.,]+)"))
    total = _monto_sura(buscar(r"Total a pagar\s+(\$\s*[\d.,]+)"))
    tasa = buscar(r"%\s*([\d.]+)\s+\$")
    nit_cliente = ""
    for i, linea in enumerate(lineas):
        if linea.upper().startswith("NOMBRES") and "NIT" in linea.upper():
            for siguiente in lineas[i + 1:i + 5]:
                m = re.search(r"\b(\d{9,10})\b", siguiente)
                if m:
                    nit_cliente = m.group(1)
                    break
            break
    return {
        "numero": numero, "fecha": fecha, "producto": producto,
        "poliza": buscar(r"P.liza\s+(\d+)"),
        "recibo": buscar(r"Recibo de Cobro\s+(\d+)"),
        "proveedor_nit": _solo_digitos(buscar(r"NIT\s+([\d.\-]+)"))[:9],
        "nit_cliente": nit_cliente, "subtotal": subtotal, "iva": iva,
        "total": total or round(subtotal + iva, 2),
        "tasa_iva": float(tasa) if tasa else (5.0 if iva else 0.0),
    }


_PARENTESCOS_SURA = ("AFILIADO(A)", "AFILIADO", "CONYUGE", "CÓNYUGE",
                     "HIJO(A)", "PROGENITOR(A)", "PADRE", "MADRE",
                     "HERMANO(A)", "OTRO(A)", "OTRO")
_TIPOS_ID_SURA = ("CEDULA DE EXTRANJERIA", "CEDULA", "CÉDULA", "PASAPORTE",
                  "TARJETA DE IDENTIDAD", "REGISTRO CIVIL",
                  "PERMISO POR PROTECCION TEMPORAL",
                  "PERMISO POR PROTECCION TEMPORL",
                  "PERMISO ESPECIAL DE PERMANENCIA", "PERMISO", "NIT")


def es_afiliado_sura(parentesco):
    return comparable(parentesco).startswith("AFILIADO")


def _leer_relacion_salud(paginas):
    lineas = [l.strip() for p in paginas for l in p.split("\n")]
    texto = "\n".join(lineas)
    cab = _siguiente_linea(lineas, r"^Fecha\s+P.liza\s+Forma de pago")
    partes = cab.split()
    relacion = {
        "producto": "salud", "asegurados": [], "avisos": [],
        "fecha": _fecha_sura(partes[0]) if partes else None,
        "poliza": partes[1] if len(partes) > 1 else "",
        "recibo": partes[-1] if len(partes) > 3 else "",
        "periodo": None,
        "nit_tomador": "",
    }
    m_nit = re.search(r"NIT\s+(\d{9,10})", texto)
    if m_nit:
        relacion["nit_tomador"] = m_nit.group(1)
    patron_par = "|".join(re.escape(p) for p in _PARENTESCOS_SURA)
    re_aseg = re.compile(
        rf"^(\d{{4,15}})\s+(\d{{1,2}})\s*(.*?)\s*({patron_par})\s+([FM])\s+"
        r"(\d{4}-\d{2}-\d{2})\s+(\d{1,3})$")
    re_montos = re.compile(r"(\$[\d.,]+)\s+(\$[\d.,]+)\s+(\$[\d.,]+)\s+"
                           r"(\$[\d.,]+)\s*$")
    afiliado = None
    pendiente = None
    for i, linea in enumerate(lineas):
        if linea.startswith("Nombre del afiliado"):
            j = i + 1
            while j < len(lineas) and not lineas[j]:
                j += 1
            fila = lineas[j] if j < len(lineas) else ""
            m = re.match(r"^(.*?)\s+(\d{4,15})\s+(\d+)$", fila)
            if not m:
                relacion["avisos"].append(f"No se entendió el afiliado: "
                                          f"«{fila}».")
                continue
            nombre_tipo = m.group(1)
            tipo = next((t for t in _TIPOS_ID_SURA
                         if comparable(nombre_tipo).endswith(" " + t)), "")
            nombre = nombre_tipo[:len(nombre_tipo) - len(tipo)].strip() \
                if tipo else " ".join(nombre_tipo.split()[:-1])
            afiliado = {"id": m.group(2), "nombre": " ".join(nombre.split()),
                        "tipo_id": tipo, "plan": m.group(3)}
            continue
        m = re_aseg.match(linea)
        if m and afiliado:
            nombre = m.group(3).strip()
            if not nombre:
                antes = lineas[i - 1] if i > 0 else ""
                despues = lineas[i + 1] if i + 1 < len(lineas) else ""
                nombre = " ".join(x for x in (
                    "" if antes.startswith("asegurado") else antes,
                    "" if despues.startswith("Ingreso") else despues) if x)
            pendiente = {
                "id": m.group(1), "id_texto": m.group(1),
                "consecutivo": int(m.group(2)),
                "nombre": " ".join(nombre.split()),
                "parentesco": m.group(4), "sexo": m.group(5),
                "nacimiento": m.group(6),
                "afiliado_id": afiliado["id"],
                "afiliado_nombre": afiliado["nombre"],
                "prima": None,
            }
            relacion["asegurados"].append(pendiente)
            continue
        if pendiente is not None and pendiente["prima"] is None and \
                "$" in linea:
            m = re_montos.search(linea)
            if m:
                pendiente.update(
                    prima=_monto_sura(m.group(1)),
                    descuento=_monto_sura(m.group(2)),
                    iva=_monto_sura(m.group(3)),
                    total=_monto_sura(m.group(4)))
    m = re.search(r"Valor total del seguro\s+(\$[\d.,]+)\s+(\$[\d.,]+)\s+"
                  r"(\$[\d.,]+)\s+(\$[\d.,]+)", texto)
    if m:
        relacion["total_prima"] = _monto_sura(m.group(1))
        relacion["total_descuento"] = _monto_sura(m.group(2))
        relacion["total_iva"] = _monto_sura(m.group(3))
        relacion["total"] = _monto_sura(m.group(4))
    sin_valor = [a["nombre"] for a in relacion["asegurados"]
                 if a["prima"] is None]
    if sin_valor:
        relacion["avisos"].append("Sin prima leída: " + ", ".join(sin_valor))
        for a in relacion["asegurados"]:
            if a["prima"] is None:
                a.update(prima=0.0, descuento=0.0, iva=0.0, total=0.0)
    return relacion


def _leer_relacion_vida(contenido, paginas):
    """Recibo de cobro de vida de grupo: la tabla de asegurados parte las
    identificaciones en dos renglones, por eso se lee por columnas."""
    import pdfplumber
    texto = "\n".join(paginas)
    lineas = [l.strip() for l in texto.split("\n")]
    relacion = {"producto": "vida", "asegurados": [], "avisos": []}
    pol = _siguiente_linea(lineas, r"^N.mero de la p.liza")
    relacion["poliza"] = pol.split()[0] if pol else ""
    rec = _siguiente_linea(lineas, r"^N.mero de recibo")
    partes = rec.split()
    relacion["recibo"] = partes[0] if partes else ""
    fechas = [f for f in (_fecha_sura(p) for p in partes) if f]
    relacion["periodo"] = (fechas[0], fechas[1]) if len(fechas) >= 2 \
        else None
    gen = _siguiente_linea(lineas, r"^Fecha de generaci.n")
    relacion["fecha"] = _fecha_sura(gen.split()[0]) if gen else None
    montos = re.findall(r"\$[\d.,]+", gen)
    if montos:
        relacion["total_prima"] = _monto_sura(montos[0])
        relacion["total_iva"] = _monto_sura(montos[1]) \
            if len(montos) > 1 else 0.0
        relacion["total"] = _monto_sura(montos[-1])
    m = re.search(r"\b(\d{9,10})\b", _siguiente_linea(
        lineas, r"Tipo de identificaci.n\s+N.mero de identificaci.n"))
    relacion["nit_tomador"] = m.group(1) if m else ""

    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words(keep_blank_chars=False)
            cab = [w for w in palabras if w["text"] == "Subgrupo"]
            if not cab:
                continue
            y_cab = cab[0]["top"]
            enc = [w for w in palabras if abs(w["top"] - y_cab) < 12]

            def x_de(texto, despues=0.0):
                xs = [w["x0"] for w in enc if w["text"] == texto
                      and w["x0"] > despues]
                return min(xs) if xs else None

            x_sub = cab[0]["x0"]
            x_afi = x_de("Id", x_sub)
            x_ase = x_de("Id", (x_afi or x_sub) + 5) or \
                x_de("asegurado", (x_afi or x_sub) + 20)
            x_nom = x_de("Nombre")
            x_par = x_de("Parentesco")
            x_fec = x_de("nacimiento") or x_de("Fecha", x_par or 0)
            x_val = x_de("vida", x_fec or 0)
            x_pri = x_de("seguro", x_val or 0)
            if None in (x_afi, x_ase, x_nom, x_par, x_fec, x_val, x_pri):
                relacion["avisos"].append("No se reconocieron las columnas "
                                          "de la relación de asegurados.")
                continue
            columnas = [("rgo", 0), ("sub", x_sub - 2), ("afi", x_afi - 2),
                        ("ase", x_ase - 2), ("nom", x_nom - 2),
                        ("par", x_par - 2), ("fec", x_fec - 2),
                        ("val", x_val - 2), ("pri", x_pri - 2)]

            def columna(w):
                nombre = "rgo"
                for c, x in columnas:
                    if w["x0"] >= x:
                        nombre = c
                return nombre

            fin = min([w["top"] for w in palabras if w["text"] == "Página"
                       and w["top"] > y_cab] or [pagina.height])
            cuerpo = [w for w in palabras if y_cab + 8 < w["top"] < fin]
            inicios = sorted(w["top"] for w in cuerpo
                             if columna(w) == "sub"
                             and re.fullmatch(r"\d{5,}", w["text"]))
            for k, y0 in enumerate(inicios):
                y1 = inicios[k + 1] if k + 1 < len(inicios) else y0 + 18
                y1 = min(y1, y0 + 18)
                bloque = sorted((w for w in cuerpo
                                 if y0 - 1.5 <= w["top"] < y1 - 1.5),
                                key=lambda w: (round(w["top"]), w["x0"]))
                col = defaultdict(list)
                for w in bloque:
                    if w["text"] != "COP":
                        col[columna(w)].append(w["text"])
                id_ase = "".join(col["ase"])
                id_afi = "".join(col["afi"])
                m = re.match(r"^([A-Z]+)?(\d+)$", id_ase)
                prefijo = (m.group(1) or "") if m else ""
                digitos = m.group(2) if m else _solo_digitos(id_ase)
                valores = [_monto_sura(t) for t in col["pri"]
                           if t.startswith("$")]
                relacion["asegurados"].append({
                    "id": digitos,
                    "id_texto": (digitos if prefijo in ("", "C")
                                 else prefijo + digitos),
                    "consecutivo": None,
                    "nombre": " ".join(col["nom"]),
                    "parentesco": " ".join(col["par"]) or "AFILIADO",
                    "nacimiento": " ".join(col["fec"]),
                    "afiliado_id": _solo_digitos(id_afi) or digitos,
                    "afiliado_nombre": " ".join(col["nom"]),
                    "prima": valores[0] if valores else 0.0,
                    "descuento": 0.0, "iva": 0.0,
                    "total": valores[0] if valores else 0.0,
                })
    # Nombre del afiliado de los beneficiarios (si los hubiera).
    nombres = {a["id"]: a["nombre"] for a in relacion["asegurados"]
               if es_afiliado_sura(a["parentesco"])}
    for a in relacion["asegurados"]:
        a["afiliado_nombre"] = nombres.get(a["afiliado_id"],
                                           a["afiliado_nombre"])
    return relacion


def leer_relacion_sura(contenido):
    """Relacion de asegurados de SURA (salud colectivo o vida de grupo)."""
    paginas = _paginas_pdf_sura(contenido)
    texto = "\n".join(paginas).upper()
    if "RECIBO DE COBRO VIDA GRUPO" in texto or \
            ("RELACIÓN DE ASEGURADOS" in texto and "SUBGRUPO" in texto):
        relacion = _leer_relacion_vida(contenido, paginas)
    elif "NOMBRE DEL AFILIADO" in texto and "PRIMA DEL" in texto:
        relacion = _leer_relacion_salud(paginas)
    else:
        raise ValueError("No parece una relación de asegurados de SURA "
                         "(salud colectivo o vida de grupo).")
    if not relacion["asegurados"]:
        raise ValueError("No se encontraron asegurados en la relación.")
    relacion["suma_prima"] = round(sum(a["prima"]
                                       for a in relacion["asegurados"]), 2)
    relacion["suma_iva"] = round(sum(a.get("iva") or 0
                                     for a in relacion["asegurados"]), 2)
    return relacion


def partidas_sura(factura, relacion, clave_empresa="EMPRESA A",
                  coberturas=None):
    """
    Una partida por asegurado con lo que se propone (editable en la
    revision): cuenta 5/7, centro de costo y % que asume la empresa.
    """
    maestro = maestro_empresa_odoo(clave_empresa)
    if coberturas is None:
        coberturas = EMPRESAS_ODOO[clave_empresa].get("beneficiarios_100", {})
    cubiertos = {str(k): {str(b) for b in v} for k, v in coberturas.items()}
    partidas = []
    for orden, a in enumerate(relacion["asegurados"]):
        titular = maestro.get(a["afiliado_id"]) or maestro.get(a["id"])
        afiliado = es_afiliado_sura(a["parentesco"])
        if afiliado:
            pct, motivo = 100.0, "Afiliado: lo asume la empresa"
        elif a["id"] in cubiertos.get(a["afiliado_id"], set()):
            pct, motivo = 100.0, ("Beneficiario cubierto al 100 % (término "
                                  "del contrato)")
        else:
            pct, motivo = PORCENTAJE_EMPRESA_BENEFICIARIO, \
                "Beneficiario: 50 % empresa y 50 % descuento al empleado"
        partidas.append({
            "orden": orden, "id": a["id"], "id_texto": a["id_texto"],
            "nombre": a["nombre"], "parentesco": a["parentesco"],
            "afiliado_id": a["afiliado_id"],
            "afiliado_nombre": a["afiliado_nombre"],
            "tercero": (titular["nombre"] if titular
                        else a["afiliado_nombre"]),
            "prima": a["prima"],
            "cuenta_5_7": titular["cuenta"] if titular else None,
            "cc": titular["cc"] if titular else "",
            "en_maestro": bool(titular),
            "pct_empresa": pct, "motivo": motivo,
        })
    return partidas


def validar_sura(factura, relacion, partidas, clave_empresa="EMPRESA A"):
    """Avisos (texto, grave) antes de generar."""
    avisos = []
    empresa = EMPRESAS_ODOO[clave_empresa]
    if factura.get("producto") and relacion.get("producto") and \
            factura["producto"] != relacion["producto"]:
        avisos.append((f"La factura es de "
                       f"{PRODUCTOS_SURA[factura['producto']]['nombre']} y "
                       f"la relación de "
                       f"{PRODUCTOS_SURA[relacion['producto']]['nombre']}.",
                       True))
    if factura.get("poliza") and relacion.get("poliza") and \
            factura["poliza"] != relacion["poliza"]:
        avisos.append((f"Póliza distinta: factura {factura['poliza']}, "
                       f"relación {relacion['poliza']}.", True))
    if factura.get("recibo") and relacion.get("recibo") and \
            factura["recibo"] != relacion["recibo"]:
        avisos.append((f"N° de recibo distinto: factura {factura['recibo']}"
                       f", relación {relacion['recibo']}.", True))
    for nit, de in ((factura.get("nit_cliente"), "la factura"),
                    (relacion.get("nit_tomador"), "la relación")):
        if nit and _solo_digitos(nit)[:9] != empresa["nit"][:9]:
            avisos.append((f"El NIT del cliente en {de} ({nit}) no es el de "
                           f"{empresa['corto']} ({empresa['nit']}).", True))
    diferencia = round(factura["subtotal"] - relacion["suma_prima"], 2)
    if abs(diferencia) >= 0.01:
        cuenta = (CUENTA_AJUSTE_DEBITO if diferencia > 0
                  else CUENTA_AJUSTE_CREDITO)
        avisos.append((f"La relación suma {formato_cop(relacion['suma_prima'])}"
                       f" y la factura {formato_cop(factura['subtotal'])}: "
                       f"la diferencia ({formato_cop(diferencia)}) va como "
                       f"ajuste por aproximación a la cuenta {cuenta}.",
                       abs(diferencia) > 1000))
    sin = [p for p in partidas if not p["en_maestro"]]
    for p in sin:
        avisos.append((f"{p['afiliado_nombre']} (ID {p['afiliado_id']}) no "
                       "está en la relación de cuentas y centros de costo: "
                       "asígnale cuenta y centro de costo en la revisión.",
                       not (p["cuenta_5_7"] and p["cc"])))
    for a in relacion.get("avisos", []):
        avisos.append((a, True))
    return avisos


def _division_empresa(prima, pct):
    empresa = round(prima * float(pct) / 100.0, 2)
    return empresa, round(prima - empresa, 2)


def lineas_odoo_sura(factura, relacion, partidas, periodo_texto=""):
    """Filas del archivo de importacion (sin el encabezado de columnas)."""
    producto = relacion.get("producto") or factura.get("producto")
    datos = PRODUCTOS_SURA[producto]
    poliza = factura.get("poliza") or relacion.get("poliza")
    sufijo_periodo = f" - {periodo_texto}" if periodo_texto else ""

    def etiqueta(p):
        partes = [f"{datos['etiqueta']} POL {poliza}", p["nombre"],
                  f"ID {p['id_texto']}"]
        if producto == "salud":
            partes.append("AFILIADO" if es_afiliado_sura(p["parentesco"])
                          else f"{p['parentesco']} DE {p['afiliado_nombre']}")
        elif not es_afiliado_sura(p["parentesco"]):
            partes.append(f"{p['parentesco']} DE {p['afiliado_nombre']}")
        return " - ".join(partes) + sufijo_periodo

    filas = []
    # Familias: lineas de la empresa y luego el descuento al empleado.
    grupos = OrderedDict()
    for p in sorted(partidas, key=lambda x: x["orden"]):
        grupos.setdefault(p["afiliado_id"], []).append(p)
    for familia in grupos.values():
        descuentos = []
        for p in familia:
            empresa_valor, empleado_valor = _division_empresa(
                p["prima"], p["pct_empresa"])
            analitica = analitica_cc(p["cc"])
            distribucion = json.dumps({analitica: 100.0}) if analitica else ""
            filas.append({
                "tipo": "asegurado", "etiqueta": etiqueta(p),
                "cuenta": cuenta_odoo(p["cuenta_5_7"], producto),
                "tercero": "", "analitica": distribucion,
                "precio": empresa_valor, "partida": p})
            if empleado_valor:
                descuentos.append({
                    "tipo": "descuento", "etiqueta": etiqueta(p),
                    "cuenta": CUENTA_DESCUENTO_EMPLEADO,
                    "tercero": p["tercero"], "analitica": distribucion,
                    "precio": empleado_valor, "partida": p})
        filas.extend(descuentos)
    diferencia = round(factura["subtotal"] - relacion["suma_prima"], 2)
    if abs(diferencia) >= 0.01:
        filas.append({
            "tipo": "ajuste",
            "etiqueta": (f"AJUSTE POR APROXIMACION SURA (diferencia factura "
                         f"vs relacion) - POL {poliza}"),
            "cuenta": (CUENTA_AJUSTE_DEBITO if diferencia > 0
                       else CUENTA_AJUSTE_CREDITO),
            "tercero": "", "analitica": json.dumps(
                {ANALITICA_AJUSTE: 100.0}),
            "precio": diferencia})
    if factura.get("iva"):
        tasa = factura.get("tasa_iva") or 5
        tasa_txt = f"{tasa:g}"
        filas.append({
            "tipo": "iva",
            "etiqueta": (f"{datos['etiqueta']} POL {poliza} - IVA COMPRAS DE "
                         f"SERVICIOS TARIFA {tasa_txt}%"),
            "cuenta": CUENTA_IVA_SURA, "tercero": "", "analitica": "",
            "precio": factura["iva"]})
    return filas


def nombre_archivo_odoo_sura(factura):
    return f"SEGUROS DE VIDA SURA FACT.{factura['numero']} IMP ODOO.xlsx"


def generar_excel_odoo_sura(factura, relacion, filas):
    """Libro con las hojas 'Importar Odoo' y 'Control' (como los que se
    importaron)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    hoja = wb.active
    hoja.title = "Importar Odoo"
    columnas = ["Fecha de la factura",
                "Nombre del contacto a mostrar en la factura", "Referencia",
                "Diario", "Líneas de factura/Etiqueta",
                "Líneas de factura/Cuenta", "Líneas de factura/Tercero",
                "Líneas de factura/Distribución analítica",
                "Líneas de factura/Cantidad",
                "Líneas de factura/Precio unitario",
                "Líneas de factura/Impuestos"]
    hoja.append(columnas)
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="2B6BF3")
    fecha = factura.get("fecha") or relacion.get("fecha")
    for i, f in enumerate(filas):
        cabecera = ([fecha.isoformat() if fecha else "", SURA_CONTACTO,
                     str(factura["numero"]), ODOO_DIARIO_COMPRAS]
                    if i == 0 else [None] * 4)
        hoja.append(cabecera + [f["etiqueta"], f["cuenta"],
                                f["tercero"] or None,
                                f["analitica"] or None, 1, f["precio"],
                                None])
        hoja.cell(hoja.max_row, 10).number_format = "#,##0.00"
    for letra, ancho in zip("ABCDEFGHIJK",
                            [16, 38, 16, 10, 100, 16, 34, 18, 10, 16, 14]):
        hoja.column_dimensions[letra].width = ancho
    hoja.freeze_panes = "A2"

    ultima = hoja.max_row
    filas_aseg = [i + 2 for i, f in enumerate(filas)
                  if f["tipo"] in ("asegurado", "descuento")]
    fila_ajuste = next((i + 2 for i, f in enumerate(filas)
                        if f["tipo"] == "ajuste"), None)
    fila_iva = next((i + 2 for i, f in enumerate(filas)
                     if f["tipo"] == "iva"), None)
    r_aseg = (f"'Importar Odoo'!J{min(filas_aseg)}:J{max(filas_aseg)}"
              if filas_aseg else None)
    control = wb.create_sheet("Control")
    n_aseg = len(relacion["asegurados"])
    n_desc = sum(1 for f in filas if f["tipo"] == "descuento")
    producto = PRODUCTOS_SURA[relacion["producto"]]["nombre"]
    datos = [
        ("Producto", f"{producto} · póliza {factura.get('poliza')}"),
        ("Suma relación (primas)", f"=SUM({r_aseg})" if r_aseg else 0),
        ("Ajuste por aproximación",
         f"='Importar Odoo'!J{fila_ajuste}" if fila_ajuste else 0),
        ("Subtotal líneas", "=B2+B3"),
        ("Subtotal factura SURA", factura["subtotal"]),
        ("Diferencia subtotal", "=B4-B5"),
        ("IVA (línea)", f"='Importar Odoo'!J{fila_iva}" if fila_iva else 0),
        ("IVA factura SURA", factura["iva"]),
        ("Total líneas",
         f"=SUMPRODUCT('Importar Odoo'!I2:I{ultima},"
         f"'Importar Odoo'!J2:J{ultima})"),
        ("Total factura SURA", factura["total"]),
        ("Diferencia total", "=B9-B10"),
        ("N° asegurados", n_aseg),
        ("Líneas de descuento al empleado (136595)", n_desc),
        ("Nota", "Precio unitario = prima del periodo de la relación (sin "
                 "IVA). Beneficiarios: 50 % empresa y 50 % descuento al "
                 "empleado (136595), salvo las excepciones. La diferencia "
                 "factura vs. relación es aproximación de SURA."),
    ]
    for etiqueta_c, valor in datos:
        control.append([etiqueta_c, valor])
    for r in range(2, 12):
        control.cell(r, 2).number_format = "#,##0.00"
    control.column_dimensions["A"].width = 40
    control.column_dimensions["B"].width = 24
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def resumen_lineas_sura(filas):
    total = round(sum(f["precio"] for f in filas), 2)
    por_cuenta = defaultdict(float)
    for f in filas:
        por_cuenta[f["cuenta"]] += f["precio"]
    return {"total": total,
            "por_cuenta": {k: round(v, 2) for k, v in por_cuenta.items()},
            "descuento_empleado": round(sum(
                f["precio"] for f in filas if f["tipo"] == "descuento"), 2)}
