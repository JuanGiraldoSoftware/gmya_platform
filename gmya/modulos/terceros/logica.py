"""Creacion de terceros (v6.20, sin Streamlit): que clientes de Alegra o
Medifony hay que crear en HELISA y en que formato.

Contrato:
  leer_helisa_clientes(contenido) -> {"por_id", "por_id_sin_ceros",
      "por_nombre", "ciudades", "nombres", "apellidos", "n"}. Listado de
      clientes de HELISA tal como se descarga (.xls).
  leer_origenes(archivos) -> {"registros", "sistemas", "completo",
      "avisos", "leidos"}. archivos: [(nombre, bytes)]. Reconoce solo:
      contactos de Alegra (.zip con los CSV, cada CSV suelto aunque no traiga
      titulos, o el Excel), y el "Reporte Facturacion Total" de Medifony.
  leer_consulta_cedulas(contenido) -> {cedula: {...}} (export de "Consulta
      Cedulas": Cedula, apellidos, nombres, Estado Consulta).
  cruzar(helisa, origenes, consulta=None, config=None) -> resultado con:
      crear (terceros nuevos, uno por documento, en el formato a subir),
      por_consultar (cedulas sin verificar), revisar, no_se_suben (NIT y
      sin clase), datos_distintos (ya en HELISA con otra clase o nombre),
      helisa_no_en_origen (solo si el origen es la lista completa de
      contactos), encontrados_normalizando (Excel no los encuentra por
      ceros o caracteres invisibles), repetidos (mismo documento con
      nombres distintos en el origen), resumen.
  dividir_nombre(nombre, nombres, apellidos) -> (n1, n2, a1, a2, dudoso).
  excel_terceros(resultado) / nombre_archivo(resultado, fecha).
Reglas (proceso confirmado con la firma, nov-2026):
  - Se compara por documento normalizado: sin espacios, puntos, guiones ni
    caracteres invisibles; despues sin ceros a la izquierda.
  - Repetidos en el origen: queda uno (el mas completo); si los nombres no
    coinciden se avisa.
  - Cedulas de ciudadania: se verifican en "Consulta Cedulas"; con el
    resultado se toman nombres y apellidos oficiales. Sin resultado: se
    sube marcado y se avisa (puede ser otro tipo de documento).
  - NIT (empresas, y personas registradas con NIT): no se suben salvo que
    se pida; la lista de HELISA es de clientes y suelen ser proveedores.
  - Nada se inventa: ciudad solo si su codigo esta en HELISA; nombres de
    Medifony se dividen con los nombres y apellidos que ya tiene HELISA y
    los dudosos se avisan.
Depende de: gmya.comun.grilla
"""

import csv
import datetime
import io
import re
import unicodedata
import zipfile
from collections import Counter, OrderedDict

from gmya.comun.grilla import tabla_desde_archivo

# Columnas del archivo a subir a HELISA (formato de la firma: "TRABAJADO A
# SUBIR A HELISA", tal cual).
COLUMNAS_SUBIR = [
    "CARTERA", "PRIMER NOMBRE", "Segundo nombre", "Primer apellido",
    "Segundo apellido", "NOMBRE", "Identificación", "CLASE DE ",
    "Tipo de persona", "Responsabilidad Tributaria", "Departamento",
    "Municipio", "CUIDAD", "Dirección", "Teléfono 1", "Correo", "NATURALEZA",
    "REGIMEN", "RESPONSABLE",
]

# Tipo de documento del origen -> clase de HELISA. Deducido de los terceros
# que ya estan creados en HELISA: C cedulas, R registros civiles, T tarjetas,
# P pasaportes, X cedulas de extranjeria, D documento extranjero, O nacido
# vivo y PPT, A NIT y NUIP.
CLASES_HELISA = OrderedDict([
    ("CC", "C"), ("CEDULA DE CIUDADANIA", "C"),
    ("RC", "R"), ("REGISTRO CIVIL", "R"),
    ("TI", "T"), ("TARJETA DE IDENTIDAD", "T"),
    ("PA", "P"), ("PASAPORTE", "P"),
    ("CE", "X"), ("CEDULA DE EXTRANJERIA", "X"),
    ("TE", "E"), ("TARJETA DE EXTRANJERIA", "E"),
    ("DE", "D"), ("DOCUMENTO DE IDENTIFICACION EXTRANJERO", "D"),
    ("NV", "O"), ("CERTIFICADO DE NACIDO VIVO", "O"),
    ("PPT", "O"), ("PERMISO DE PROTECCION TEMPORAL", "O"),
    ("PEP", "O"), ("PERMISO ESPECIAL DE PERMANENCIA", "O"),
    ("MS", "O"), ("AS", "O"), ("SC", "O"), ("CD", "O"),
    ("NUIP", "A"),
    ("NIT", "A"), ("NUMERO DE IDENTIFICACION TRIBUTARIA", "A"),
    ("NIT DE OTRO PAIS", "A"),
])
NOMBRE_CLASE = {"C": "Cédula de ciudadanía", "R": "Registro civil",
                "T": "Tarjeta de identidad", "P": "Pasaporte",
                "X": "Cédula de extranjería", "E": "Tarjeta de extranjería",
                "D": "Documento extranjero", "O": "Otro", "A": "NIT"}
# Clases equivalentes (persona natural con NIT = su cedula).
EQUIVALENTES = {frozenset("CA")}

CONFIG_TERCEROS = {
    "cartera": "CLIENTES", "naturaleza": "0", "regimen": "49",
    "responsable": "49", "tipo_persona": "Persona natural",
    "resp_tributaria": "No responsable del IVA", "incluir_nit": False,
    "clases": dict(CLASES_HELISA),
}

ALEGRA_ENCABEZADO = [
    "Nombre", "Segundo nombre", "Primer apellido", "Segundo apellido",
    "Identificación", "Tipo de identificación", "Dígito de verificación",
    "Tipo de persona", "Responsabilidad Tributaria", "Departamento",
    "Municipio", "Dirección", "Código Postal", "País", "Teléfono 1",
    "Teléfono 2", "Fax", "Celular", "Correo", "Correo electrónico 2",
    "Estado del contacto", "Cuenta por cobrar", "Cuenta por pagar",
    "Término de pago", "Lista de precios", "Vendedor",
]
PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "SAN", "SANTA", "Y", "DA",
              "DI", "VAN", "VON", "MC", "MAC"}


# ------------------------------------------------------------
# Normalizacion
# ------------------------------------------------------------
def _txt(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    return "" if texto.lower() in ("none", "null", "nan", "#n/a") else texto


def clave_texto(texto):
    t = unicodedata.normalize("NFKD", _txt(texto)).encode(
        "ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", t)).strip()


def normalizar_id(valor):
    """Documento comparable: solo letras y digitos en mayuscula (quita
    espacios, tabulaciones, puntos, guiones y caracteres invisibles)."""
    return re.sub(r"[^0-9A-Z]", "", _txt(valor).upper())


def sin_ceros(identificacion):
    return identificacion.lstrip("0") or identificacion


def tiene_invisibles(valor):
    return bool(re.search(r"[^\x20-\x7E]", str(valor or "")))


def _celda(fila, col):
    return fila[col] if col is not None and col < len(fila) else None


def _columnas(fila, nombres):
    claves = [clave_texto(v) for v in fila]
    salida = {}
    for campo, opciones in nombres.items():
        for op in opciones:
            if clave_texto(op) in claves:
                salida[campo] = claves.index(clave_texto(op))
                break
    return salida


def _cabecera(tabla, obligatorias, maximo=30):
    for k, fila in enumerate(tabla[:maximo]):
        claves = {clave_texto(v) for v in fila}
        if all(clave_texto(o) in claves for o in obligatorias):
            return k
    return None


def _tokens(texto):
    return [t for t in clave_texto(texto).split() if t]


def mismo_nombre(a, b):
    """Parecido de nombres tolerante a recortes (HELISA corta a ~28 letras),
    orden y segundos nombres: comparte al menos 2 palabras (o todas si una
    tiene menos)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return True
    comunes = sum(1 for t in ta if len(t) >= 2 and any(
        u.startswith(t) or t.startswith(u) for u in tb if len(u) >= 2))
    return comunes >= min(2, len(ta), len(tb))


def clave_nombre(texto):
    return " ".join(sorted(t for t in _tokens(texto)
                           if t not in PARTICULAS))


# ------------------------------------------------------------
# HELISA
# ------------------------------------------------------------
def leer_helisa_clientes(contenido):
    tabla = tabla_desde_archivo(contenido)
    cab = _cabecera(tabla, ["Identidad", "Clase", "Nombre"])
    if cab is None:
        raise ValueError("No se encontró el listado de clientes de HELISA "
                         "(columnas Identidad, Clase y Nombre).")
    col = _columnas(tabla[cab], {
        "codigo": ["Código"], "id": ["Identidad"], "clase": ["Clase"],
        "nombre": ["Nombre"], "ciudad": ["Ciudad"],
        "nombre_ciudad": ["Nombre de la ciudad"],
        "a1": ["Primer apellido"], "a2": ["Segundo apellido"],
        "n1": ["Primer nombre"], "n2": ["Segundo nombre"]})
    por_id, por_cero, por_nombre = {}, {}, {}
    ciudades, nombres, apellidos = {}, Counter(), Counter()
    for fila in tabla[cab + 1:]:
        ident = normalizar_id(_celda(fila, col["id"]))
        if not ident:
            continue
        t = {"id": ident, "codigo": _txt(_celda(fila, col.get("codigo"))),
             "clase": _txt(_celda(fila, col["clase"])).upper(),
             "nombre": _txt(_celda(fila, col["nombre"]))}
        por_id.setdefault(ident, t)
        por_cero.setdefault(sin_ceros(ident), t)
        k = clave_nombre(t["nombre"])
        if k:
            por_nombre.setdefault(k, []).append(t)
        codigo = _txt(_celda(fila, col.get("ciudad")))
        nombre_ciudad = clave_texto(_celda(fila, col.get("nombre_ciudad")))
        if codigo and nombre_ciudad:
            ciudades.setdefault(nombre_ciudad, Counter())[codigo] += 1
        for c in ("n1", "n2"):
            for tk in _tokens(_celda(fila, col.get(c))):
                nombres[tk] += 1
        for c in ("a1", "a2"):
            for tk in _tokens(_celda(fila, col.get(c))):
                apellidos[tk] += 1
    return {"por_id": por_id, "por_id_sin_ceros": por_cero,
            "por_nombre": por_nombre,
            "ciudades": {k: v.most_common(1)[0][0]
                         for k, v in ciudades.items()},
            "nombres": nombres, "apellidos": apellidos, "n": len(por_id)}


# ------------------------------------------------------------
# Origenes: Alegra y Medifony
# ------------------------------------------------------------
def _registro(**campos):
    base = {"sistema": "", "tipo": "", "ident_raw": "", "nombre": "",
            "n1": "", "n2": "", "a1": "", "a2": "", "direccion": "",
            "municipio": "", "departamento": "", "telefono": "",
            "correo": "", "tipo_persona": "", "resp_tributaria": "",
            "referencia": "", "archivo": ""}
    base.update({k: _txt(v) for k, v in campos.items()})
    base["id"] = normalizar_id(base["ident_raw"])
    base["invisibles"] = tiene_invisibles(campos.get("ident_raw"))
    return base


def _primero(*valores):
    return next((_txt(v) for v in valores if _txt(v) and _txt(v) != "0"), "")


def _alegra(tabla, nombre_archivo, encabezado=None):
    cab = _cabecera(tabla, ["Identificación", "Tipo de identificación"])
    if cab is not None:
        encabezado = [_txt(v) for v in tabla[cab]]
        filas = tabla[cab + 1:]
    elif encabezado:
        filas = tabla
    else:
        return None, None
    idx = {clave_texto(c): k for k, c in enumerate(encabezado)}

    def v(fila, nombre):
        return _celda(fila, idx.get(clave_texto(nombre)))
    regs = []
    for k, fila in enumerate(filas):
        if not any(_txt(x) for x in fila):
            continue
        regs.append(_registro(
            sistema="Alegra", tipo=v(fila, "Tipo de identificación"),
            ident_raw=v(fila, "Identificación"),
            n1=v(fila, "Nombre"), n2=v(fila, "Segundo nombre"),
            a1=v(fila, "Primer apellido"), a2=v(fila, "Segundo apellido"),
            direccion=v(fila, "Dirección"), municipio=v(fila, "Municipio"),
            departamento=v(fila, "Departamento"),
            telefono=_primero(v(fila, "Teléfono 1"), v(fila, "Celular"),
                              v(fila, "Teléfono 2")),
            correo=v(fila, "Correo"), tipo_persona=v(fila, "Tipo de persona"),
            resp_tributaria=v(fila, "Responsabilidad Tributaria"),
            referencia=f"fila {k + (cab or 0) + 2}", archivo=nombre_archivo))
        r = regs[-1]
        r["nombre"] = " ".join(x for x in (r["n1"], r["n2"], r["a1"],
                                           r["a2"]) if x)
    return regs, encabezado


def _medifony(tabla, nombre_archivo):
    cab = _cabecera(tabla, ["Cliente Doc.", "Nombre"])
    if cab is None:
        return None
    col = _columnas(tabla[cab], {
        "doc": ["Cliente Doc."], "nombre": ["Nombre"],
        "factura": ["# Facturar"], "t1": ["Teléfono 1"], "t2": ["Teléfono 2"],
        "m1": ["Movil 1"], "m2": ["Movil 2"], "correo": ["Correo Electrónico"],
        "direccion": ["Dirección"], "municipio": ["Municipio"]})
    regs = []
    for fila in tabla[cab + 1:]:
        doc = _txt(_celda(fila, col["doc"]))
        if not doc:
            continue
        m = re.match(r"^\s*([A-Za-z]{1,4})[\s.:-]+(.+)$", doc)
        tipo, numero = (m.group(1), m.group(2)) if m else ("", doc)
        if tipo.upper() == "NIT":     # NIT con digito de verificacion
            numero = re.sub(r"-\s*\d\s*$", "", numero)
        regs.append(_registro(
            sistema="Medifony", tipo=tipo.upper(), ident_raw=numero,
            nombre=_celda(fila, col["nombre"]),
            direccion=_celda(fila, col.get("direccion")),
            municipio=_celda(fila, col.get("municipio")),
            telefono=_primero(*(_celda(fila, col.get(c))
                                for c in ("m1", "t1", "m2", "t2"))),
            correo=_celda(fila, col.get("correo")),
            referencia=_txt(_celda(fila, col.get("factura"))),
            archivo=nombre_archivo))
    return regs


def leer_origenes(archivos):
    """archivos: [(nombre, bytes)]. Nunca se detiene por un archivo: lo que
    no se reconoce se avisa."""
    registros, sistemas, avisos, leidos = [], Counter(), [], []
    piezas = []
    for nombre, contenido in archivos:
        if contenido[:4] == b"PK\x03\x04" and \
                nombre.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                for interno in sorted(z.namelist()):
                    if interno.lower().endswith((".csv", ".xlsx", ".xls")):
                        piezas.append((f"{nombre} › {interno}",
                                       z.read(interno)))
        else:
            piezas.append((nombre, contenido))
    # Las partes del CSV de Alegra despues de la primera no traen titulos.
    piezas.sort(key=lambda p: p[0])
    encabezado = None
    sueltas = []
    for nombre, contenido in piezas:
        try:
            tabla = tabla_desde_archivo(contenido)
        except Exception as error:
            avisos.append(f"«{nombre}»: no se pudo abrir ({error}).")
            continue
        regs = _medifony(tabla, nombre)
        if regs is not None:
            registros += regs
            sistemas["Medifony"] += len(regs)
            leidos.append((nombre, "Medifony", len(regs)))
            continue
        regs, enc = _alegra(tabla, nombre, encabezado)
        if regs is not None:
            encabezado = enc
            registros += regs
            sistemas["Alegra"] += len(regs)
            leidos.append((nombre, "Alegra", len(regs)))
            continue
        sueltas.append((nombre, tabla))
    for nombre, tabla in sueltas:
        ancho = max((len(f) for f in tabla), default=0)
        if ancho == len(ALEGRA_ENCABEZADO):
            regs, _ = _alegra(tabla, nombre, encabezado or ALEGRA_ENCABEZADO)
            registros += regs
            sistemas["Alegra"] += len(regs)
            leidos.append((nombre, "Alegra", len(regs)))
            avisos.append(f"«{nombre}» no trae títulos: se leyó con las "
                          "columnas de la exportación de contactos de Alegra.")
        else:
            avisos.append(f"«{nombre}» no se reconoció como contactos de "
                          "Alegra ni como reporte de facturación de Medifony: "
                          "se dejó por fuera.")
    return {"registros": registros, "sistemas": dict(sistemas),
            "completo": "Alegra" in sistemas, "avisos": avisos,
            "leidos": leidos}


def leer_consulta_cedulas(contenido):
    tabla = tabla_desde_archivo(contenido)
    cab = _cabecera(tabla, ["Cédula", "Estado Consulta"])
    if cab is None:
        raise ValueError("No es el resultado de la Consulta de Cédulas "
                         "(columnas Cédula y Estado Consulta).")
    col = _columnas(tabla[cab], {
        "cedula": ["Cédula"], "a1": ["Primer Apellido"],
        "a2": ["Segundo Apellido"], "n1": ["Primer Nombre"],
        "n2": ["Otros Nombres"], "completo": ["Nombre Completo"],
        "estado": ["Estado Consulta"], "obs": ["Observaciones"]})
    salida = {}
    for fila in tabla[cab + 1:]:
        ced = normalizar_id(_celda(fila, col["cedula"]))
        if not ced:
            continue
        datos = {c: _txt(_celda(fila, col.get(c))) for c in col}
        for c in ("a1", "a2", "n1", "n2", "completo"):
            if datos.get(c) in ("—", "-"):
                datos[c] = ""
        datos["exitoso"] = clave_texto(datos.get("estado")).startswith(
            "EXITOS")
        salida[ced] = datos
    return salida


# ------------------------------------------------------------
# Nombres
# ------------------------------------------------------------
def _agrupar_particulas(palabras):
    salida, pendiente = [], []
    for p in palabras:
        if clave_texto(p) in PARTICULAS:
            pendiente.append(p)
            continue
        salida.append(" ".join(pendiente + [p]))
        pendiente = []
    if pendiente:
        if salida:
            salida[-1] += " " + " ".join(pendiente)
        else:
            salida = [" ".join(pendiente)]
    return salida


def dividir_nombre(nombre, nombres=None, apellidos=None):
    """(n1, n2, a1, a2, dudoso). Orden colombiano: nombres y luego
    apellidos. Con 3 palabras la del medio es nombre o apellido segun como
    aparece en los terceros de HELISA; si no hay datos claros, dudoso."""
    nombres, apellidos = nombres or Counter(), apellidos or Counter()
    t = _agrupar_particulas(_txt(nombre).upper().split())
    # Apellidos repetidos ("ANA PEREZ GOMEZ PEREZ GOMEZ").
    for largo in (2, 1):
        if len(t) >= 1 + 2 * largo and t[-largo:] == t[-2 * largo:-largo]:
            t = t[:-largo]
            break

    def es_nombre(palabra):
        u = clave_texto(palabra).split()
        u = u[-1] if u else ""
        n, a = nombres[u], apellidos[u]
        # Palabra que HELISA nunca ha visto como nombre: apellido (asi lo
        # hace la firma). Dudosa solo si se usa de las dos formas.
        return n > a, n > 0 and a > 0 and max(n, a) < 3 * min(n, a)
    if not t:
        return "", "", "", "", True
    if len(t) == 1:
        return t[0], "", "", "", True
    if len(t) == 2:
        return t[0], "", t[1], "", False
    if len(t) == 3:
        nom, duda = es_nombre(t[1])
        return ((t[0], t[1], t[2], "", duda) if nom
                else (t[0], "", t[1], t[2], duda))
    if len(t) == 4:
        return t[0], t[1], t[2], t[3], False
    k = 1
    while k < len(t) - 2 and es_nombre(t[k])[0]:
        k += 1
    return t[0], " ".join(t[1:k]), t[k], " ".join(t[k + 1:]), True


def _partir_apellidos(a1, a2):
    if a2 or not a1:
        return a1, a2
    partes = _agrupar_particulas(a1.split())
    if len(partes) >= 2:
        return partes[0], " ".join(partes[1:])
    return a1, a2


# ------------------------------------------------------------
# Cruce
# ------------------------------------------------------------
def _clase(tipo, config):
    return config["clases"].get(clave_texto(tipo), "")


def _completitud(r):
    return sum(1 for c in ("direccion", "municipio", "telefono", "correo",
                           "n1", "a1") if r.get(c))


def cruzar(helisa, origenes, consulta=None, config=None):
    config = dict(CONFIG_TERCEROS, **(config or {}))
    consulta = consulta or {}
    revisar, no_suben, distintos, normalizando = [], [], [], []
    repetidos = []
    vistos_ids = set()

    def aviso(tipo, r, detalle):
        revisar.append({"tipo": tipo, "id": r.get("id", ""),
                        "nombre": r.get("nombre", ""),
                        "origen": r.get("sistema", ""), "detalle": detalle})

    # 1. Agrupar por documento (repetidos en el origen).
    grupos = OrderedDict()
    for r in origenes["registros"]:
        if r["id"]:
            grupos.setdefault(r["id"], []).append(r)
    en_origen = len(grupos)
    nuevos = []
    for ident, regs in grupos.items():
        r = max(regs, key=_completitud)
        repetido = len(regs) > 1 and any(
            not mismo_nombre(regs[0]["nombre"], x["nombre"])
            for x in regs[1:])
        if repetido:
            repetidos.append({
                "id": ident, "origen": r["sistema"], "n": len(regs),
                "nombres": " / ".join(sorted({x["nombre"] for x in regs})),
                "en_helisa": ident in helisa["por_id"]})
        h = helisa["por_id"].get(ident)
        via = ""
        if h is None:
            h = helisa["por_id_sin_ceros"].get(sin_ceros(ident))
            via = "ceros" if h else ""
        if h is not None:
            vistos_ids.add(h["id"])
            if via or r["invisibles"]:
                normalizando.append({
                    "id": ident, "raw": r["ident_raw"], "nombre": r["nombre"],
                    "origen": r["sistema"], "helisa": h["id"],
                    "motivo": "ceros a la izquierda" if via else
                    "caracteres invisibles en el documento"})
            clase_o = _clase(r["tipo"], config)
            par = frozenset((clase_o, h["clase"]))
            cambios = []
            if clase_o and h["clase"] and clase_o != h["clase"] and \
                    par not in EQUIVALENTES:
                cambios.append(f"Clase: HELISA {h['clase']} "
                               f"({NOMBRE_CLASE.get(h['clase'], '?')}), "
                               f"{r['sistema']} {r['tipo']}")
            if not mismo_nombre(r["nombre"], h["nombre"]):
                cambios.append("Nombre distinto")
            if cambios:
                distintos.append({"id": ident, "clase_helisa": h["clase"],
                                  "nombre_helisa": h["nombre"],
                                  "tipo_origen": r["tipo"],
                                  "nombre_origen": r["nombre"],
                                  "origen": r["sistema"],
                                  "que": "; ".join(cambios)})
            continue
        if repetido:
            aviso("Mismo documento, nombres distintos", r,
                  f"{repetidos[-1]['n']} registros en {r['sistema']} con "
                  f"este documento y nombres distintos: "
                  f"{repetidos[-1]['nombres']}. Confirmar a quién pertenece "
                  "antes de crearlo.")
        nuevos.append(r)

    # 2. Terceros nuevos en el formato a subir.
    crear, por_consultar = [], []
    nombres_nuevos = {}
    for r in nuevos:
        clase = _clase(r["tipo"], config)
        notas, estado = [], "lista"
        if r["invisibles"]:
            notas.append("El documento trae caracteres invisibles en "
                         f"{r['sistema']} (se quitaron).")
        if not clase:
            no_suben.append(dict(r, motivo=f"Tipo de documento «{r['tipo']}» "
                                 "sin clase de HELISA: asígnala en los "
                                 "parámetros."))
            continue
        if clase == "A" and not config["incluir_nit"]:
            no_suben.append(dict(r, motivo="NIT: la lista de HELISA es de "
                                 "clientes; confirmar si es cliente (crear) o "
                                 "proveedor (revisar en proveedores)."))
            continue
        # Nombres
        dudoso = False
        if r["sistema"] == "Alegra" and (r["n1"] or r["a1"]):
            n1, n2 = r["n1"].strip(), r["n2"].strip()
            a1, a2 = _partir_apellidos(r["a1"].strip(), r["a2"].strip())
            if not n2 and len(n1.split()) == 2:
                n1, n2 = n1.split()
        else:
            n1, n2, a1, a2, dudoso = dividir_nombre(
                r["nombre"], helisa["nombres"], helisa["apellidos"])
            # Documentos extranjeros con 3 palabras: suelen ser 2 nombres y
            # 1 apellido; no se puede saber, se confirma.
            if clase in ("P", "X", "D", "E") and len(_agrupar_particulas(
                    r["nombre"].split())) == 3:
                dudoso = True
        verificado = None
        if clase == "C":
            c = consulta.get(r["id"])
            if c is None:
                estado = "cc_sin_verificar"
                por_consultar.append(r["id"])
            elif c["exitoso"] and (c.get("n1") or c.get("a1")):
                verificado = c
                n1, a1, a2 = c.get("n1", ""), c.get("a1", ""), c.get("a2", "")
                partes = c.get("n2", "").split()
                n2 = " ".join(partes)
                dudoso = False
                oficial = " ".join(x for x in (n1, n2, a1, a2) if x)
                if not mismo_nombre(oficial, r["nombre"]):
                    aviso("Nombre distinto al de la Registraduría", r,
                          f"{r['sistema']}: {r['nombre']} · consulta: "
                          f"{oficial}. Verificar que la cédula sea de esta "
                          "persona.")
            else:
                estado = "cc_sin_resultado"
                aviso("Cédula sin resultado en la consulta", r,
                      "La consulta no encontró la cédula: puede ser otro tipo "
                      "de documento (registro civil, tarjeta) o un número mal "
                      "digitado.")
        if dudoso:
            aviso("Nombre dividido por la plataforma", r,
                  f"Se tomó: nombres «{' '.join(x for x in (n1, n2) if x)}», "
                  f"apellidos «{' '.join(x for x in (a1, a2) if x)}». "
                  "Confirmar.")
        nombre_completo = " ".join(x for x in (n1, n2, a1, a2) if x).upper()
        municipio = r["municipio"]
        ciudad = helisa["ciudades"].get(clave_texto(municipio), "") \
            if municipio else ""
        if municipio and not ciudad:
            notas.append(f"Municipio «{municipio}» sin código de ciudad en "
                         "HELISA: completar CUIDAD.")
        fila = OrderedDict([
            ("CARTERA", config["cartera"]), ("PRIMER NOMBRE", n1.upper()),
            ("Segundo nombre", n2.upper()), ("Primer apellido", a1.upper()),
            ("Segundo apellido", a2.upper()), ("NOMBRE", nombre_completo),
            ("Identificación", r["id"]), ("CLASE DE ", clase),
            ("Tipo de persona", r["tipo_persona"] or config["tipo_persona"]),
            ("Responsabilidad Tributaria",
             r["resp_tributaria"] or config["resp_tributaria"]),
            ("Departamento", r["departamento"]), ("Municipio", municipio),
            ("CUIDAD", ciudad), ("Dirección", r["direccion"]),
            ("Teléfono 1", r["telefono"]), ("Correo", r["correo"]),
            ("NATURALEZA", config["naturaleza"]),
            ("REGIMEN", config["regimen"]),
            ("RESPONSABLE", config["responsable"]),
        ])
        for n in notas:
            aviso("Dato por completar" if "completar" in n
                  else "Documento corregido", r, n)
        crear.append({"fila": fila, "estado": estado, "origen": r,
                      "verificado": verificado, "notas": notas})
        nombres_nuevos.setdefault(clave_nombre(nombre_completo), []).append(
            r)
        # Posible ya creado con otra identificacion.
        for h in helisa["por_nombre"].get(clave_nombre(nombre_completo), []):
            if h["id"] != r["id"]:
                aviso("Posible ya creado con otro documento", r,
                      f"En HELISA hay un tercero con el mismo nombre y "
                      f"documento {h['id']} (clase {h['clase']}): confirmar "
                      "antes de crear.")
                break
    for regs in nombres_nuevos.values():
        if len({x["id"] for x in regs}) > 1:
            for x in regs:
                aviso("Mismo nombre, documentos distintos", x,
                      "Documentos " + ", ".join(sorted({y["id"] for y in
                                                       regs}))
                      + ": puede ser un número mal digitado. Crear solo el "
                      "correcto.")
    crear.sort(key=lambda c: (c["fila"]["CLASE DE "], c["fila"][
        "Identificación"]))

    helisa_no = []
    if origenes.get("completo"):
        helisa_no = [h for i, h in helisa["por_id"].items()
                     if i not in vistos_ids]
    resumen = OrderedDict([
        ("En el origen (documentos únicos)", en_origen),
        ("Ya están en HELISA", en_origen - len(nuevos)),
        ("A crear en HELISA", len(crear)),
        ("Cédulas por consultar", len(por_consultar)),
        ("Para revisar", len(revisar)),
        ("No se suben (NIT o sin clase)", len(no_suben)),
        ("Ya en HELISA con datos distintos", len(distintos)),
        ("Documentos repetidos con nombres distintos en el origen",
         len(repetidos)),
    ])
    if origenes.get("completo"):
        resumen["En HELISA y no en Alegra"] = len(helisa_no)
    return {"crear": crear, "por_consultar": sorted(set(por_consultar)),
            "revisar": revisar, "no_se_suben": no_suben,
            "datos_distintos": distintos, "helisa_no_en_origen": helisa_no,
            "encontrados_normalizando": normalizando, "resumen": resumen,
            "repetidos": repetidos,
            "sistemas": origenes.get("sistemas", {}),
            "completo": origenes.get("completo", False),
            "con_consulta": bool(consulta)}


# ------------------------------------------------------------
# Excel
# ------------------------------------------------------------
COLOR_SIN_VERIFICAR = "FFFFFF99"
COLOR_SIN_RESULTADO = "FFFFCC99"


def nombre_archivo(resultado, fecha=None):
    fecha = fecha or datetime.date.today()
    origen = " Y ".join(sorted(resultado.get("sistemas", {}))).upper() \
        or "ORIGEN"
    return f"TERCEROS A CREAR EN HELISA {origen} {fecha:%d-%m-%Y}.xlsx"


def excel_terceros(resultado):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    negrita = Font(bold=True)

    def relleno(color):
        return PatternFill("solid", fgColor=color)

    def hoja_tabla(libro, titulo, cab, filas, anchos=None):
        h = libro.create_sheet(titulo[:31])
        h.append(cab)
        for c in h[1]:
            c.font = negrita
            c.fill = relleno("FFD9D9D9")
        for f in filas:
            h.append(list(f))
        for i, c in enumerate(cab, start=1):
            ancho = (anchos or {}).get(i) or min(45, max(
                len(str(c)), *(len(str(f[i - 1] or "")) for f in filas))
                + 2 if filas else len(str(c)) + 2)
            h.column_dimensions[get_column_letter(i)].width = ancho
        h.freeze_panes = "A2"
        if filas:
            h.auto_filter.ref = f"A1:{get_column_letter(len(cab))}" \
                f"{len(filas) + 1}"
        return h

    libro = Workbook()
    libro.remove(libro.active)
    # 1. Archivo a subir (formato de la firma).
    filas = [list(c["fila"].values()) for c in resultado["crear"]]
    h = hoja_tabla(libro, "A SUBIR A HELISA", COLUMNAS_SUBIR, filas)
    for k, c in enumerate(resultado["crear"], start=2):
        color = {"cc_sin_verificar": COLOR_SIN_VERIFICAR,
                 "cc_sin_resultado": COLOR_SIN_RESULTADO}.get(c["estado"])
        if color:
            for celda in h[k]:
                celda.fill = relleno(color)
        h.cell(k, 7).number_format = "@"
    # 2. Cedulas para la consulta (una columna, como la Hoja4 de la firma).
    h = libro.create_sheet("CEDULAS POR CONSULTAR")
    for ced in resultado["por_consultar"]:
        h.append([ced])
        h.cell(h.max_row, 1).number_format = "@"
    h.column_dimensions["A"].width = 16
    # 3. Revisar.
    hoja_tabla(libro, "REVISAR", ["Qué", "Identificación", "Nombre",
                                  "Origen", "Detalle"],
               [(r["tipo"], r["id"], r["nombre"], r["origen"], r["detalle"])
                for r in resultado["revisar"]], {5: 100})
    # 4. No se suben.
    hoja_tabla(libro, "NO SE SUBEN", ["Identificación", "Tipo en origen",
                                      "Nombre", "Origen", "Referencia",
                                      "Motivo"],
               [(r["id"], r["tipo"], r["nombre"], r["sistema"],
                 r["referencia"], r["motivo"])
                for r in resultado["no_se_suben"]], {6: 90})
    # 5. Ya en HELISA con datos distintos.
    hoja_tabla(libro, "YA EN HELISA DATOS DISTINTOS",
               ["Identificación", "Clase HELISA", "Nombre HELISA",
                "Origen", "Tipo en origen", "Nombre en origen", "Qué cambia"],
               [(d["id"], d["clase_helisa"], d["nombre_helisa"], d["origen"],
                 d["tipo_origen"], d["nombre_origen"], d["que"])
                for d in resultado["datos_distintos"]], {7: 60})
    # 6. Encontrados solo al normalizar (el BUSCARV de Excel no los ve).
    hoja_tabla(libro, "YA CREADOS (BUSCARV NO LOS VE)",
               ["Documento en origen", "Documento en HELISA", "Nombre",
                "Origen", "Motivo"],
               [(n["raw"], n["helisa"], n["nombre"], n["origen"], n["motivo"])
                for n in resultado["encontrados_normalizando"]])
    # 6b. Repetidos en el origen (calidad de datos de Alegra / Medifony).
    hoja_tabla(libro, "REPETIDOS EN ORIGEN",
               ["Identificación", "Origen", "Registros", "Nombres",
                "Ya en HELISA"],
               [(r["id"], r["origen"], r["n"], r["nombres"],
                 "Sí" if r["en_helisa"] else "No")
                for r in resultado["repetidos"]], {4: 80})
    # 7. Viceversa.
    if resultado["completo"]:
        hoja_tabla(libro, "EN HELISA Y NO EN ALEGRA",
                   ["Código HELISA", "Identidad", "Clase", "Nombre"],
                   [(h_["codigo"], h_["id"], h_["clase"], h_["nombre"])
                    for h_ in resultado["helisa_no_en_origen"]])
    # 8. Detalle de origen de cada tercero a crear.
    hoja_tabla(libro, "DETALLE", [
        "Identificación", "Origen", "Archivo", "Referencia",
        "Tipo en origen", "Documento tal como viene", "Nombre en origen",
        "Estado", "Notas"],
        [(c["fila"]["Identificación"], c["origen"]["sistema"],
          c["origen"]["archivo"], c["origen"]["referencia"],
          c["origen"]["tipo"], c["origen"]["ident_raw"],
          c["origen"]["nombre"],
          {"lista": "Lista", "cc_sin_verificar": "Cédula sin verificar",
           "cc_sin_resultado": "Cédula sin resultado en la consulta"}[
              c["estado"]], " ".join(c["notas"]))
         for c in resultado["crear"]], {3: 40, 9: 60})
    # 9. Resumen.
    h = libro.create_sheet("RESUMEN")
    h.append(["TERCEROS A CREAR EN HELISA"])
    h["A1"].font = Font(bold=True, size=12)
    h.append(["Origen", ", ".join(f"{k} ({v} registros)" for k, v in
                                  resultado["sistemas"].items())])
    h.append([])
    for k, v in resultado["resumen"].items():
        h.append([k, v])
    h.append([])
    h.append(["Colores en A SUBIR A HELISA"])
    h.cell(h.max_row, 1).font = negrita
    for color, texto in ((COLOR_SIN_VERIFICAR, "Cédula sin verificar: pasar "
                          "por la Consulta de Cédulas y cargar el resultado"),
                         (COLOR_SIN_RESULTADO, "Cédula sin resultado en la "
                          "consulta: revisar el tipo de documento")):
        h.append(["", texto])
        h.cell(h.max_row, 1).fill = relleno(color)
    h.column_dimensions["A"].width = 38
    h.column_dimensions["B"].width = 90
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
