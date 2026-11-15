"""Conciliacion "flexible": cualquier documento bancario y una o varias
cuentas a la vez.

Contrato:
  generar_conciliacion(archivo_extracto, archivo_libro, ventana_dias=15,
      tolerancia_redondeo=0, palabras_extra=None) -> resultado; acepta
      PDF, Excel (.xlsx/.xls/XML) o CSV.
  generar_conciliacion_multiple(documentos, ...) -> empareja cada extracto
      con su cuenta en HELISA (emparejar_cuentas) y concilia cada par.

Depende de: gmya.modulos.bancos.lectura, gmya.modulos.bancos.conciliacion, gmya.modulos.bancos.sugerencias, gmya.modulos.bancos.excel
"""

import datetime
import re
from collections import Counter
from decimal import Decimal

from gmya.modulos.bancos.lectura import (
    descripcion_periodo, detectar_banco, detectar_cuenta, detectar_tipo_cuenta,
)
from gmya.modulos.bancos.conciliacion import (
    analizar, detectar_tipo_documento, etiqueta_cuenta, leer_extracto,
    leer_libro, UMBRAL_PAREJA_DUDOSA, UMBRAL_PAREJA_SEGURA,
)
from gmya.modulos.bancos.sugerencias import generar_sugerencias
from gmya.modulos.bancos.excel import construir_excel_bancos


# ------------------------------------------------------------
# Punto de entrada (una pareja de archivos; compatibilidad)
# ------------------------------------------------------------
def generar_conciliacion(archivo_extracto, archivo_libro, ventana_dias=15,
                         tolerancia_redondeo=Decimal("0"),
                         palabras_extra=None):
    """Acepta extracto y HELISA en PDF, Excel (.xlsx/.xls/XML) o CSV."""
    resultado = generar_conciliacion_multiple(
        [("extracto", archivo_extracto)], [("libro", archivo_libro)],
        ventana_dias, tolerancia_redondeo, palabras_extra)
    principal = resultado["cuentas"][0]
    return {"archivo": resultado["archivo"],
            "nombre_archivo": resultado["nombre_archivo"],
            "analisis": principal["analisis"],
            "documentos": principal["documentos"],
            "multiple": resultado}


UMBRAL_COINCIDENCIA = 0.30      # menos del 30 % de partidas cruzadas


def _extracto_vacio(periodo=None):
    hoy = datetime.date.today()
    return {
        "banco": "Sin extracto", "tipo_cuenta": "", "cuenta": "",
        "periodo": periodo or (hoy.replace(day=1), hoy),
        "resumen": {}, "movimientos": [], "saldo_corrido": False,
        "inconsistentes": 0, "decimal": ".", "formato": "—",
        "vacio": True,
    }


def _libro_vacio():
    return {"empresa": "", "nit": "", "periodo": None, "secciones": [],
            "formato": "—", "vacio": True}


def _seccion_vacia():
    return {"clave": "", "etiqueta": "(sin HELISA)", "cuenta": "",
            "saldo_inicial": None, "saldo_final": None, "movimientos": [],
            "inconsistentes": 0, "vacia": True}


def leer_documento_bancario(nombre, contenido, cargado_como, anio=None):
    """
    v6.5: el archivo se lee SIEMPRE como lo que es el cuadro donde se cargo
    (extracto o HELISA); nunca se cambia de lado. Si el contenido parece
    del otro tipo solo se avisa ('detectado'). Nunca lanza error: si no se
    puede leer devuelve tipo 'desconocido' con el motivo.
    """
    detectado = detectar_tipo_documento(contenido)
    orden = [cargado_como]
    errores = []
    for tipo in orden:
        try:
            if tipo == "libro":
                dato = leer_libro(contenido)
            else:
                dato = leer_extracto(contenido, anio_defecto=anio)
                if not dato["movimientos"]:
                    raise ValueError("no tiene movimientos")
                # Exportaciones del portal sin encabezado: el banco, el tipo
                # y el numero de cuenta se toman del nombre del archivo.
                if not dato.get("tipo_cuenta"):
                    dato["tipo_cuenta"] = detectar_tipo_cuenta(nombre)
                if not dato.get("cuenta"):
                    dato["cuenta"] = detectar_cuenta(nombre)
                if not dato.get("banco") or "no reconocido" in str(
                        dato.get("banco")).lower():
                    dato["banco"] = detectar_banco(nombre) or dato.get("banco")
            return {"nombre": nombre, "cargado_como": cargado_como,
                    "tipo": tipo, "dato": dato, "contenido": contenido,
                    "errores": errores, "detectado": detectado}
        except Exception as error:          # se informa, no se bloquea
            errores.append(f"como {tipo}: {error}")
    return {"nombre": nombre, "cargado_como": cargado_como,
            "tipo": "desconocido", "dato": None, "contenido": contenido,
            "errores": errores, "detectado": detectado}


def _digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def _parecido_cuenta(a, b):
    """0..1: que tan parecidos son dos numeros de cuenta."""
    import difflib
    a, b = _digitos(a), _digitos(b)
    if not a or not b:
        return None
    if len(min(a, b, key=len)) >= 6 and (a.endswith(b) or b.endswith(a)):
        return 1.0
    # Bancolombia imprime 778-00002022 en el extracto y HELISA 7780002022:
    # se comparan sin ceros y por los ultimos digitos.
    if a.lstrip("0").replace("0", "") == b.lstrip("0").replace("0", "") \
            and a[-4:] == b[-4:]:
        return 0.95
    razon = difflib.SequenceMatcher(None, a, b).ratio()
    if a[-4:] == b[-4:]:
        razon = max(razon, 0.8)
    return razon


def puntaje_pareja(extracto, seccion):
    """
    Que tan probable es que el extracto y la cuenta de HELISA sean la
    misma cuenta. Devuelve (puntaje, motivos).
    """
    puntos, motivos = 0.0, []
    parecido = _parecido_cuenta(extracto.get("cuenta"), seccion.get("cuenta"))
    if parecido is not None:
        if parecido >= 0.95:
            puntos += 50
            motivos.append("número de cuenta coincide")
        elif parecido >= 0.8:
            puntos += 35
            motivos.append("número de cuenta parecido (mismos últimos "
                           "dígitos)")
        else:
            puntos -= 10
            motivos.append("número de cuenta distinto")

    def igual(a, b):
        return a is not None and b is not None and \
            Decimal(a) == Decimal(b)

    res = extracto.get("resumen") or {}
    if igual(res.get("saldo_inicial"), seccion.get("saldo_inicial")):
        puntos += 20
        motivos.append("mismo saldo inicial")
    if igual(res.get("saldo_final"), seccion.get("saldo_final")):
        puntos += 20
        motivos.append("mismo saldo final")

    valores_e = [abs(m["valor"]) for m in extracto.get("movimientos", [])]
    valores_l = Counter(abs(m["valor"]) for m in seccion.get(
        "movimientos", []))
    if valores_e and valores_l:
        comunes = sum(1 for v in set(valores_e) if v in valores_l)
        fraccion = comunes / max(1, min(len(set(valores_e)),
                                        len(valores_l)))
        puntos += 30 * fraccion
        motivos.append(f"{comunes} valores en común")
    return round(puntos, 1), motivos


def emparejar_cuentas(extractos, secciones):
    """
    Empareja extractos con cuentas de HELISA (mayor puntaje primero).
    Devuelve [(i_extracto | None, j_seccion | None, puntaje, motivos)].
    """
    candidatos = []
    for i, e in enumerate(extractos):
        for j, s in enumerate(secciones):
            puntos, motivos = puntaje_pareja(e, s)
            candidatos.append((puntos, i, j, motivos))
    candidatos.sort(key=lambda c: -c[0])
    usados_e, usados_s, parejas = set(), set(), []
    for puntos, i, j, motivos in candidatos:
        if i in usados_e or j in usados_s:
            continue
        usados_e.add(i)
        usados_s.add(j)
        parejas.append((i, j, puntos, motivos))
    for i in range(len(extractos)):
        if i not in usados_e:
            parejas.append((i, None, None, []))
    for j, s in enumerate(secciones):
        if j not in usados_s and (s["movimientos"]
                                  or s.get("saldo_inicial") is not None):
            parejas.append((None, j, None, []))
    return parejas


def excel_basico_bancos(resultado):
    """Libro minimo de respaldo (v6.5): una hoja de saldos por cuenta y la
    conciliacion linea a linea. Solo usa datos ya calculados."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    hoja = wb.active
    hoja.title = "Resumen"
    negrita = Font(bold=True)
    hoja.append(["CONCILIACIÓN BANCARIA (versión básica)"])
    hoja["A1"].font = Font(bold=True, size=13)
    hoja.append(["Cuenta", "Saldo inicial extracto", "Saldo final extracto",
                 "Saldo inicial HELISA", "Saldo final HELISA",
                 "Diferencia no explicada"])
    for celda in hoja[2]:
        celda.font = negrita
    for c in resultado["cuentas"]:
        conc = c["analisis"]["conc"]
        hoja.append([c["etiqueta"]] + [
            float(conc.get(k) or 0) for k in (
                "saldo_ini_ext", "saldo_fin_ext", "saldo_ini_lib",
                "saldo_fin_lib", "no_explicada")])
    for aviso in resultado.get("avisos") or []:
        hoja.append([f"Aviso: {aviso}"])
    linea = wb.create_sheet("Conciliación")
    linea.append(["Cuenta", "Lado", "Estado", "Fecha", "Descripción / "
                  "comprobante", "Valor"])
    for celda in linea[1]:
        celda.font = negrita
    for c in resultado["cuentas"]:
        a = c["analisis"]
        for m in a["movs"]:
            linea.append([c["etiqueta"], "Extracto", m.get("estado"),
                          m.get("fecha"), m.get("descripcion"),
                          float(m.get("valor") or 0)])
        for m in a["libro_movs"]:
            linea.append([c["etiqueta"], "HELISA", m.get("estado"),
                          m.get("fecha"),
                          f"{m.get('tipo', '')} {m.get('numero', '')} "
                          f"{m.get('tercero', '')}".strip(),
                          float(m.get("valor") or 0)])
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def generar_conciliacion_multiple(archivos_extracto, archivos_libro,
                                  ventana_dias=15,
                                  tolerancia_redondeo=Decimal("0"),
                                  palabras_extra=None):
    """
    archivos_extracto / archivos_libro: listas de (nombre, bytes).
    Concilia cada extracto contra la cuenta de HELISA que le corresponde.
    Solo lanza error si ningun archivo se puede leer.
    """
    avisos = []
    cargas = [(n, c, "extracto") for n, c in archivos_extracto] + \
        [(n, c, "libro") for n, c in archivos_libro]
    if not cargas:
        raise ValueError("No se cargó ningún documento.")

    # 1. Libros primero (dan el año para los extractos sin año).
    leidos = []
    anio = None
    for nombre, contenido, ranura in sorted(
            cargas, key=lambda x: x[2] != "libro"):
        doc = leer_documento_bancario(nombre, contenido, ranura, anio)
        if doc["tipo"] == "libro" and doc["dato"]["periodo"] and not anio:
            anio = doc["dato"]["periodo"][1].year
        leidos.append(doc)

    for doc in leidos:
        ranura = ("extracto bancario" if doc["cargado_como"] == "extracto"
                  else "HELISA")
        otro = doc.get("detectado") not in (None, "desconocido",
                                            doc["cargado_como"])
        parece = ("un informe de HELISA" if doc.get("detectado") == "libro"
                  else "un extracto bancario")
        if doc["tipo"] == "desconocido":
            avisos.append(
                f"No se pudo leer «{doc['nombre']}» como {ranura} (el cuadro "
                f"donde se cargó): "
                f"{'; '.join(re.sub(r'^como \w+: ', '', e).rstrip('.') for e in doc['errores'])}."
                + (f" Su contenido parece {parece}: si es así, cárgalo en el "
                   "otro cuadro." if otro else "")
                + " Se dejó por fuera.")
        elif otro:
            avisos.append(
                f"«{doc['nombre']}» se cargó como {ranura} y se usó así, "
                f"pero su contenido parece {parece}. Revisa que esté en el "
                "cuadro correcto.")

    docs_ext = [d for d in leidos if d["tipo"] == "extracto"]
    docs_lib = [d for d in leidos if d["tipo"] == "libro"]
    if not docs_ext and not docs_lib:
        raise ValueError(
            "Ninguno de los archivos se pudo leer como extracto bancario o "
            "HELISA. Verifica que sean PDF con texto o Excel/CSV.")
    if not docs_ext:
        avisos.append(
            "No se identificó ningún extracto bancario: HELISA se "
            "concilia contra un extracto vacío (todo queda como NO ESTÁ EN "
            "EL EXTRACTO). Revisa que hayas cargado los extractos.")
    if not docs_lib:
        avisos.append(
            "No se identificó ningún HELISA: los extractos se "
            "concilian contra HELISA sin movimientos (todo queda como NO ESTÁ EN "
            "HELISA). Revisa que hayas cargado el informe de bancos de HELISA.")

    # 2. Cuentas de HELISA (un archivo de HELISA puede traer varias cuentas).
    secciones = []
    for doc in docs_lib:
        for s in doc["dato"]["secciones"]:
            secciones.append((doc, s))
    extractos = [d["dato"] for d in docs_ext]
    parejas = emparejar_cuentas(extractos, [s for _, s in secciones])

    # 3. Conciliacion por cuenta.
    cuentas = []
    for i, j, puntos, motivos in parejas:
        doc_e = docs_ext[i] if i is not None else None
        doc_l, seccion = secciones[j] if j is not None else (None, None)
        extracto = doc_e["dato"] if doc_e else _extracto_vacio(
            doc_l["dato"]["periodo"] if doc_l else None)
        libro = doc_l["dato"] if doc_l else _libro_vacio()
        seccion = seccion or _seccion_vacia()
        etiqueta = etiqueta_cuenta(doc_e and extracto, seccion)
        propios = []
        if doc_e and doc_l:
            if puntos < UMBRAL_PAREJA_DUDOSA:
                propios.append(
                    f"El extracto «{doc_e['nombre']}» (cuenta "
                    f"{extracto['cuenta'] or 'sin número'}) y la cuenta de "
                    f"HELISA {seccion['etiqueta'] or seccion['cuenta']} "
                    "parecen de cuentas distintas (no coinciden número, "
                    "saldos ni valores). Se conciliaron igual: revisa que "
                    "sean los documentos correctos.")
            elif puntos < UMBRAL_PAREJA_SEGURA:
                detalle = ", ".join(motivos) or "sin datos comunes"
                cuenta_libro = seccion["etiqueta"] or seccion["cuenta"]
                propios.append(
                    f"La cuenta de HELISA {cuenta_libro} se asoció al "
                    f"extracto «{doc_e['nombre']}» con coincidencia parcial "
                    f"({detalle}). Confirma que sean la misma cuenta.")
        elif doc_e:
            if docs_lib:
                propios.append(
                    f"No se encontró en HELISA una cuenta para el "
                    f"extracto «{doc_e['nombre']}» (cuenta "
                    f"{extracto['cuenta'] or 'sin número'}); se concilia "
                    "contra HELISA sin movimientos.")
        elif doc_l:
            if docs_ext:
                propios.append(
                    f"La cuenta de HELISA {seccion['etiqueta']} no tiene "
                    "extracto cargado; sus registros quedan como NO ESTÁ EN "
                    "EL EXTRACTO.")

        analisis = analizar(
            extracto, libro, ventana_dias=ventana_dias,
            tolerancia_redondeo=Decimal(tolerancia_redondeo),
            palabras_extra=palabras_extra, seccion=seccion,
            avisos_previos=propios)
        analisis["sugerencias"] = generar_sugerencias(analisis)

        movs, lib = analisis["movs"], analisis["libro_movs"]
        if movs and lib:
            cruzadas = sum(1 for m in movs
                           if m["estado"] in ("conciliado", "agrupado"))
            fraccion = cruzadas / len(movs)
            if fraccion < UMBRAL_COINCIDENCIA:
                analisis["avisos"].append(
                    f"Cuenta {etiqueta}: solo {cruzadas} de {len(movs)} "
                    f"movimientos del extracto ({fraccion:.0%}) cruzan "
                    "exactamente con HELISA. Parecen documentos que no corresponden "
                    "(otra cuenta u otro mes).")
        p_e, p_l = extracto["periodo"], libro.get("periodo")
        if doc_e and p_l and not (p_e[0] <= p_l[1] and p_l[0] <= p_e[1]):
            analisis["avisos"].append(
                f"Cuenta {etiqueta}: el periodo del extracto "
                f"({p_e[0]:%d/%m/%Y}–{p_e[1]:%d/%m/%Y}) no se cruza con el "
                f"de HELISA ({p_l[0]:%d/%m/%Y}–{p_l[1]:%d/%m/%Y}).")

        base, n_rep = etiqueta, 2
        while any(c["etiqueta"] == etiqueta for c in cuentas):
            etiqueta, n_rep = f"{base} ({n_rep})", n_rep + 1
        cuentas.append({
            "etiqueta": etiqueta,
            "analisis": analisis,
            "documentos": {
                "extracto": doc_e["contenido"] if doc_e else None,
                "libro": doc_l["contenido"] if doc_l else None,
            },
            "archivo_extracto": doc_e["nombre"] if doc_e else "",
            "archivo_libro": doc_l["nombre"] if doc_l else "",
            "puntaje": puntos,
            "motivos": motivos,
        })

    resultado = {"cuentas": cuentas, "avisos": avisos, "leidos": [
        {"nombre": d["nombre"], "cargado_como": d["cargado_como"],
         "tipo": d["tipo"], "errores": d["errores"]} for d in leidos]}
    # v6.5: el Excel se genera SIEMPRE. Si el libro completo falla por un
    # caso no previsto, se entrega uno basico (saldos + linea a linea) y se
    # avisa; nunca se queda la conciliacion sin documento.
    try:
        resultado["archivo"] = construir_excel_bancos(resultado)
    except Exception as error:
        resultado["archivo"] = excel_basico_bancos(resultado)
        avisos.append(
            "El Excel completo no se pudo armar "
            f"({type(error).__name__}: {error}); se generó una versión "
            "básica con los saldos y la conciliación línea a línea. Avisa al "
            "administrador para revisar el caso.")
    periodos = [c["analisis"]["extracto"]["periodo"] for c in cuentas]
    inicio = min(p[0] for p in periodos)
    fin = max(p[1] for p in periodos)
    _, rango, _ = descripcion_periodo(inicio, fin)
    sufijo = rango.replace("/", "_").replace("–", "-").upper()
    resultado["nombre_archivo"] = (
        f"Conciliacion_{sufijo}.xlsx" if len(cuentas) == 1 else
        f"Conciliacion_{len(cuentas)}_cuentas_{sufijo}.xlsx")
    return resultado
