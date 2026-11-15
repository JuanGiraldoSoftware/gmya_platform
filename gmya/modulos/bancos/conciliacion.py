"""Emparejamiento extracto <-> HELISA (sin Streamlit).

Contrato:
  conciliar(extracto, libro, ventana_dias, tolerancia, banco) -> marca cada
      movimiento: conciliado / diferencia / agrupado / sin_libro y cada
      registro HELISA: conciliado / sin_extracto.
  analizar(extracto, libro, ventana_dias=15, ...) -> totales, validaciones
      y avisos.
  leer_extracto / leer_libro -> lectura automatica PDF o Excel.

Depende de: gmya.comun.numeros, gmya.comun.grilla, gmya.modulos.bancos.lectura
"""

import datetime
import io
import re
from collections import OrderedDict, defaultdict
from decimal import Decimal
from itertools import combinations

from gmya.comun.numeros import CENTAVO, CERO, formato_cop
from gmya.comun.grilla import tabla_desde_archivo
from gmya.modulos.bancos.lectura import (
    CATEGORIAS_BANCARIAS, CATEGORIAS_ESPECIFICAS, clasificar_concepto,
    construir_categorias,
    _contiene, crear_fecha, detectar_banco, detectar_cuenta, detectar_periodo,
    detectar_tipo_cuenta, elegir_seccion_libro, es_cargo_bancario,
    es_libro_helisa, es_registro_bancario_libro, ETIQUETA_MES,
    leer_extracto_pdf, leer_libro_helisa, leer_resumen_saldos, _mes_abreviado,
    MESES_COMPLETOS, procesar_lineas_libro, RE_HELISA_PERIODO,
    texto_comparable, ultimo_dia_mes,
)


# ------------------------------------------------------------
# Conciliacion (emparejamiento extracto <-> libro)
# ------------------------------------------------------------
def _subconjunto_exacto(valores, objetivo, minimo=2, orden=None,
                        maximo=22):
    """
    Indices de un subconjunto de 'valores' que suma EXACTAMENTE 'objetivo'
    (al centavo), con al menos 'minimo' elementos, o None. Usa los 'maximo'
    candidatos mas cercanos segun 'orden' (dias de diferencia) y busca por
    mitades (meet in the middle) para que sea rapido.
    """
    if not valores or len(valores) < minimo:
        return None
    pos = list(range(len(valores)))
    if orden is not None:
        pos.sort(key=lambda k: orden[k])
    pos = pos[:maximo]
    centavos = [int((valores[k] * 100).to_integral_value()) for k in pos]
    meta = int((objetivo * 100).to_integral_value())
    mitad = len(pos) // 2
    a, b = centavos[:mitad], centavos[mitad:]

    def sumas(lista):
        salida = {}
        for mascara in range(1 << len(lista)):
            total = 0
            for k in range(len(lista)):
                if mascara >> k & 1:
                    total += lista[k]
            previo = salida.get(total)
            if previo is None or bin(mascara).count("1") > \
                    bin(previo).count("1"):
                salida[total] = mascara
        return salida
    sa, sb = sumas(a), sumas(b)
    mejor = None
    for total, mb in sb.items():
        ma = sa.get(meta - total)
        if ma is None:
            continue
        n = bin(ma).count("1") + bin(mb).count("1")
        if n >= minimo and (mejor is None or n > mejor[0]):
            mejor = (n, ma, mb)
    if not mejor:
        return None
    _, ma, mb = mejor
    elegidos = [pos[k] for k in range(len(a)) if ma >> k & 1] + \
        [pos[mitad + k] for k in range(len(b)) if mb >> k & 1]
    return elegidos


def conciliar(extracto, libro_movs, ventana_dias, tolerancia_redondeo,
              nombre_banco):
    """
    Marca cada movimiento del extracto con su estado frente a HELISA:
      conciliado  -> mismo valor, fechas cercanas
      diferencia  -> misma partida pero con valor distinto
      agrupado    -> gastos bancarios registrados en un solo asiento (NB)
                     o movimientos agrupados n a m (v6.5, exactos)
      sin_libro   -> no se encuentra en HELISA
    y cada registro de HELISA: conciliado / sin_extracto.
    """
    ventana = datetime.timedelta(days=ventana_dias)

    for mov in extracto:
        mov.update(estado="sin_libro", pareja=[], nota="")
    for mov in libro_movs:
        mov.update(estado="sin_extracto", pareja=[])

    libres_e = set(range(len(extracto)))
    libres_l = set(range(len(libro_movs)))

    def emparejar(i, j, estado, nota=""):
        extracto[i].update(estado=estado, nota=nota)
        extracto[i]["pareja"] = [j]
        libro_movs[j].update(estado="conciliado")
        libro_movs[j]["pareja"] = [i]
        libres_e.discard(i)
        libres_l.discard(j)

    # 1) Mismo valor exacto y fechas dentro de la ventana.
    grupos = defaultdict(lambda: ([], []))
    for i in libres_e:
        grupos[extracto[i]["valor"]][0].append(i)
    for j in libres_l:
        grupos[libro_movs[j]["valor"]][1].append(j)

    for _, (es, ls) in grupos.items():
        candidatos = sorted(
            (abs((extracto[i]["fecha"] - libro_movs[j]["fecha"]).days), i, j)
            for i in es for j in ls
            if abs(extracto[i]["fecha"] - libro_movs[j]["fecha"]) <= ventana)
        for _, i, j in candidatos:
            if i in libres_e and j in libres_l:
                emparejar(i, j, "conciliado")

    # 2) Gastos bancarios registrados en conjunto (nota bancaria).
    for signo in (-1, 1):
        ext = [i for i in sorted(libres_e)
               if (extracto[i]["valor"] < 0) == (signo < 0)
               and (es_cargo_bancario(extracto[i]["categoria"])
                    or extracto[i]["categoria"] == "rendimientos")]
        lib = [j for j in sorted(libres_l)
               if (libro_movs[j]["valor"] < 0) == (signo < 0)
               and es_registro_bancario_libro(libro_movs[j], nombre_banco)]
        if not ext or not lib:
            continue

        suma_l = sum((libro_movs[j]["valor"] for j in lib), CERO)

        # Se busca el subconjunto de categorias del extracto cuya suma
        # coincide con lo que HELISA registro.
        categorias = sorted({extracto[i]["categoria"] for i in ext})
        elegido = None
        for tamano in range(len(categorias), 0, -1):
            for combinacion in combinations(categorias, tamano):
                suma_e = sum((extracto[i]["valor"] for i in ext
                              if extracto[i]["categoria"] in combinacion),
                             CERO)
                # v6.4: exacto al centavo (antes +-0,05).
                if suma_e == suma_l:
                    elegido = combinacion
                    break
            if elegido:
                break

        if elegido:
            seleccion = [i for i in ext
                         if extracto[i]["categoria"] in elegido]
            nota = ("Registrado en conjunto: "
                    + ", ".join(f"{libro_movs[j]['tipo']} "
                                f"{libro_movs[j]['numero']}" for j in lib))
            estado = "agrupado"
        else:
            seleccion = ext
            suma_e = sum((extracto[i]["valor"] for i in ext), CERO)
            nota = ("Registrado en conjunto con diferencia: extracto "
                    f"{formato_cop(abs(suma_e))} vs HELISA "
                    f"{formato_cop(abs(suma_l))}")
            estado = "agrupado_diferencia"

        for i in seleccion:
            extracto[i].update(estado=estado, nota=nota, pareja=list(lib))
            libres_e.discard(i)
        for j in lib:
            libro_movs[j].update(estado="conciliado", pareja=list(seleccion))
            libres_l.discard(j)

    # 2b) v6.5: movimientos AGRUPADOS (n a m), exactos al centavo:
    #   - un comprobante de HELISA con varias lineas (p. ej. PE 1164 de la
    #     nomina) = varios movimientos del extracto, o
    #   - un movimiento del extracto = varios registros de HELISA.
    # Quedan conciliados con el estado "agrupado" y una nota que lo explica.
    def marcar_grupo(idx_e, idx_l):
        total = sum((extracto[i]["valor"] for i in idx_e), CERO)
        docs = sorted({f"{libro_movs[j]['tipo']} {libro_movs[j]['numero']}"
                       for j in idx_l})
        fechas = sorted({extracto[i]["fecha"] for i in idx_e})
        nota = (f"MOVIMIENTO AGRUPADO: {len(idx_e)} movimiento"
                f"{'' if len(idx_e) == 1 else 's'} del extracto ("
                + ", ".join(f"{f:%d/%m}" for f in fechas) + ") = "
                f"{len(idx_l)} registro{'' if len(idx_l) == 1 else 's'} de "
                f"HELISA ({', '.join(docs)}) por {formato_cop(abs(total))}")
        for i in idx_e:
            extracto[i].update(estado="agrupado", nota=nota,
                               pareja=list(idx_l), grupo_nm=True)
            libres_e.discard(i)
        for j in idx_l:
            libro_movs[j].update(estado="conciliado", pareja=list(idx_e),
                                 agrupado=True, nota=nota)
            libres_l.discard(j)

    for signo in (-1, 1):
        # A. Comprobante de HELISA = varios movimientos del extracto.
        por_doc = defaultdict(list)
        for j in sorted(libres_l):
            if (libro_movs[j]["valor"] < 0) == (signo < 0):
                l = libro_movs[j]
                por_doc[(l["tipo"], l["numero"], l["fecha"])].append(j)
        for (_, _, fecha), idx_l in sorted(por_doc.items(),
                                           key=lambda x: -len(x[1])):
            if any(j not in libres_l for j in idx_l):
                continue
            objetivo = sum((libro_movs[j]["valor"] for j in idx_l), CERO)
            cands = [i for i in libres_e
                     if (extracto[i]["valor"] < 0) == (signo < 0)
                     and abs(extracto[i]["fecha"] - fecha) <= ventana]
            elegidos = _subconjunto_exacto(
                [extracto[i]["valor"] for i in cands], objetivo,
                minimo=1 if len(idx_l) > 1 else 2,
                orden=[abs((extracto[i]["fecha"] - fecha).days)
                       for i in cands])
            if elegidos:
                marcar_grupo([cands[k] for k in elegidos], idx_l)
        # B. Un movimiento del extracto = varios registros de HELISA.
        for i in sorted(libres_e):
            e = extracto[i]
            if (e["valor"] < 0) != (signo < 0) or i not in libres_e:
                continue
            cands = [j for j in libres_l
                     if (libro_movs[j]["valor"] < 0) == (signo < 0)
                     and abs(libro_movs[j]["fecha"] - e["fecha"]) <= ventana]
            elegidos = _subconjunto_exacto(
                [libro_movs[j]["valor"] for j in cands], e["valor"],
                minimo=2, orden=[abs((libro_movs[j]["fecha"]
                                      - e["fecha"]).days) for j in cands])
            if elegidos:
                marcar_grupo([i], [cands[k] for k in elegidos])

    # 3) Mismo concepto con valor distinto: redondeo o error de registro.
    def candidatos_diferencia(maximo_dif, solo_especificas):
        lista = []
        for i in libres_e:
            e = extracto[i]
            if solo_especificas and e["categoria"] not in \
                    CATEGORIAS_ESPECIFICAS:
                continue
            for j in libres_l:
                l = libro_movs[j]
                if (e["valor"] < 0) != (l["valor"] < 0):
                    continue
                if abs(e["fecha"] - l["fecha"]) > ventana:
                    continue
                if solo_especificas and l["categoria"] != e["categoria"]:
                    continue
                dif = abs(abs(e["valor"]) - abs(l["valor"]))
                if maximo_dif is None or dif <= maximo_dif:
                    lista.append((dif, abs((e["fecha"] - l["fecha"]).days),
                                  i, j))
        return sorted(lista)

    for _, _, i, j in candidatos_diferencia(tolerancia_redondeo, False):
        if i in libres_e and j in libres_l:
            emparejar(i, j, "diferencia")
    # v6.7: por categoria especifica con CUALQUIER diferencia solo se
    # empareja cuando no hay duda: es la unica partida posible de cada lado
    # (antes se emparejaba la mas cercana y podia juntar dos pagos
    # distintos, p. ej. 19 M con 9 M, ocultando que uno no estaba).
    lista = candidatos_diferencia(None, True)
    por_e, por_l = defaultdict(set), defaultdict(set)
    for _, _, i, j in lista:
        por_e[i].add(j)
        por_l[j].add(i)
    for _, _, i, j in lista:
        if i in libres_e and j in libres_l and por_e[i] == {j} \
                and por_l[j] == {i}:
            emparejar(i, j, "diferencia",
                      "Única partida posible de la misma categoría y signo "
                      "en la ventana de días, con valor distinto: verificar "
                      "que sea la misma.")

    # v6.9.2: misma fecha, cualquier categoria (no gastos ni intereses del
    # banco): si de cada lado es la UNICA partida libre del mismo signo ese
    # dia y la diferencia es menor que la partida mas pequena, se empareja
    # como VALOR DIFERENTE para que se vea la diferencia (p. ej. Bold abona
    # la venta neta de comision, IVA y retenciones). Nunca como conciliada.
    def propia_del_banco(m):
        cat = str(m.get("categoria") or "")
        return cat in CATEGORIAS_BANCARIAS or "rendim" in cat or \
            "interes" in cat

    mismo_dia = []
    for i in libres_e:
        e = extracto[i]
        if propia_del_banco(e):
            continue
        for j in libres_l:
            l = libro_movs[j]
            if (e["valor"] < 0) != (l["valor"] < 0) or \
                    e["fecha"] != l["fecha"] or propia_del_banco(l):
                continue
            mismo_dia.append((i, j))
    por_e, por_l = defaultdict(set), defaultdict(set)
    for i, j in mismo_dia:
        por_e[i].add(j)
        por_l[j].add(i)
    for i, j in mismo_dia:
        if not (i in libres_e and j in libres_l and por_e[i] == {j}
                and por_l[j] == {i}):
            continue
        ve, vl = abs(extracto[i]["valor"]), abs(libro_movs[j]["valor"])
        dif = abs(ve - vl)
        if not dif or dif >= min(ve, vl):
            continue
        nota = (f"Única partida del mismo día y signo en los dos lados, con "
                f"valor distinto (diferencia {formato_cop(dif)}): verificar que sea "
                "la misma.")
        texto = texto_comparable(extracto[i].get("descripcion", ""))
        if any(p in texto for p in ("bold", "datafono", "wompi", "payu",
                                     "mercado pago", "pasarela")) and \
                ve < vl:
            nota += (" La pasarela de pagos abona la venta neta: la "
                     "diferencia suele ser comisión, IVA y retenciones "
                     "descontadas; registrarlas según el soporte de la "
                     "liquidación.")
        emparejar(i, j, "diferencia", nota)

    for i in libres_e:
        extracto[i]["estado"] = "sin_libro"

    return extracto, libro_movs


# ------------------------------------------------------------
# Analisis completo
# ------------------------------------------------------------

def sumar(movs, condicion=lambda m: True):
    return sum((m["valor"] for m in movs if condicion(m)), CERO)


def validar(extracto, libro, seccion, resultado_conciliacion, avisos):
    """Lista (control, esperado, obtenido, estado, nota)."""
    filas = []
    res = extracto["resumen"]
    movs = extracto["movimientos"]

    def estado(ok):
        return "OK" if ok else "REVISAR"

    def igual(a, b, tolerancia=CERO):     # v6.4: exacto (antes 0,02)
        return a is not None and b is not None and abs(a - b) <= tolerancia

    ingresos = sumar(movs, lambda m: m["valor"] > 0)
    egresos = -sumar(movs, lambda m: m["valor"] < 0)

    if res.get("saldo_inicial") is not None and \
            res.get("saldo_final") is not None:
        calculado = res["saldo_inicial"] + sumar(movs)
        filas.append((
            "Extracto: saldo inicial + movimientos leídos = saldo final",
            res["saldo_final"], calculado,
            estado(igual(calculado, res["saldo_final"])),
            "Confirma que se leyeron todas las filas del extracto"))

    if extracto["saldo_corrido"]:
        filas.append((
            "Extracto: filas cuyo saldo corrido no cuadra con el valor",
            0, extracto["inconsistentes"],
            estado(extracto["inconsistentes"] == 0),
            "Cada fila debe cumplir saldo anterior + valor = saldo"))

    extras = {k: res.get(k, CERO) for k in ("iva", "gmf", "intereses")}

    if res.get("creditos") is not None:
        directo = igual(ingresos, res["creditos"])
        ampliado = igual(ingresos, res["creditos"] + abs(
            extras.get("intereses", CERO)))
        filas.append((
            "Extracto: créditos leídos vs. total abonos del resumen",
            res["creditos"], ingresos, estado(directo or ampliado),
            "Algunos bancos informan IVA, 4x1000 e intereses aparte"))

    if res.get("debitos") is not None:
        directo = igual(egresos, res["debitos"])
        ampliado = igual(egresos, res["debitos"] + abs(extras["iva"])
                         + abs(extras["gmf"]))
        filas.append((
            "Extracto: débitos leídos vs. total cargos del resumen",
            res["debitos"], egresos, estado(directo or ampliado),
            "Algunos bancos informan IVA, 4x1000 e intereses aparte"))

    lib_movs = seccion["movimientos"]
    if seccion["saldo_inicial"] is not None:
        calculado = seccion["saldo_inicial"] + sumar(lib_movs)
        filas.append((
            "HELISA: saldo inicial + movimientos = saldo final",
            seccion["saldo_final"], calculado,
            estado(igual(calculado, seccion["saldo_final"])),
            "Confirma que se leyeron todas las filas de HELISA"))

    filas.append((
        "HELISA: filas cuyo saldo corrido no cuadra",
        0, seccion["inconsistentes"],
        estado(seccion["inconsistentes"] == 0), ""))

    p_ext, p_lib = extracto["periodo"], libro["periodo"]
    if p_lib:
        solapan = p_ext[0] <= p_lib[1] and p_lib[0] <= p_ext[1]
        mismo = (p_ext[0] == p_lib[0] and p_ext[1] == p_lib[1])
        filas.append((
            "Periodo de HELISA vs. periodo del extracto",
            f"{p_ext[0]:%d/%m/%Y} – {p_ext[1]:%d/%m/%Y}",
            f"{p_lib[0]:%d/%m/%Y} – {p_lib[1]:%d/%m/%Y}",
            estado(mismo),
            "Los periodos no se cruzan: probablemente es el mes equivocado"
            if not solapan else
            ("Los periodos se cruzan parcialmente" if not mismo else "")))

    filas.append((
        "Cuenta de HELISA vs. cuenta del extracto",
        extracto["cuenta"] or "no identificada",
        seccion["cuenta"] or "no identificada",
        estado(not any("cuenta" in a.lower() for a in avisos)), ""))

    filas.append((
        "Conciliación de saldos: diferencia no explicada",
        0, resultado_conciliacion["no_explicada"],
        estado(resultado_conciliacion["no_explicada"] == CERO),
        "Saldo extracto + partidas conciliatorias = saldo HELISA"))

    return filas


def analizar(extracto, libro, ventana_dias=15,
             tolerancia_redondeo=CERO, palabras_extra=None,
             seccion=None, avisos_previos=None):
    avisos = list(avisos_previos or [])
    if seccion is None:
        seccion, aviso = elegir_seccion_libro(libro, extracto["cuenta"])
        if aviso:
            avisos.append(aviso)

    categorias = construir_categorias(palabras_extra)

    ext = [dict(m) for m in extracto["movimientos"]]
    for mov in ext:
        mov["categoria"], mov["categoria_nombre"] = clasificar_concepto(
            mov["descripcion"], mov["valor"], categorias)

    lib = [dict(m) for m in seccion["movimientos"]]
    for mov in lib:
        mov["categoria"], mov["categoria_nombre"] = clasificar_concepto(
            f"{mov['tercero']}", mov["valor"], categorias)

    conciliar(ext, lib, ventana_dias, tolerancia_redondeo,
              extracto["banco"])

    # Identidad de conciliacion:
    # libro_final = extracto_final + (libro_ini - ext_ini)
    #               + (libro conciliado - extracto conciliado)
    #               + libro sin extracto - extracto sin libro
    res = extracto["resumen"]
    saldo_ini_ext = res.get("saldo_inicial") or CERO
    saldo_fin_ext = res.get("saldo_final")
    if saldo_fin_ext is None:
        saldo_fin_ext = saldo_ini_ext + sumar(ext)
    saldo_ini_lib = seccion["saldo_inicial"] or CERO
    saldo_fin_lib = seccion["saldo_final"] or CERO

    ext_conciliado = sumar(ext, lambda m: m["estado"] != "sin_libro")
    lib_conciliado = sumar(lib, lambda m: m["estado"] == "conciliado")
    lib_sin_ext = sumar(lib, lambda m: m["estado"] == "sin_extracto")
    ext_sin_lib = sumar(ext, lambda m: m["estado"] == "sin_libro")
    diferencia_saldo_inicial = saldo_ini_lib - saldo_ini_ext
    diferencia_valores = lib_conciliado - ext_conciliado

    calculado = (saldo_fin_ext + diferencia_saldo_inicial
                 + diferencia_valores + lib_sin_ext - ext_sin_lib)
    conc = {
        "saldo_ini_ext": saldo_ini_ext, "saldo_fin_ext": saldo_fin_ext,
        "saldo_ini_lib": saldo_ini_lib, "saldo_fin_lib": saldo_fin_lib,
        "ext_sin_lib": ext_sin_lib, "lib_sin_ext": lib_sin_ext,
        "diferencia_valores": diferencia_valores,
        "diferencia_saldo_inicial": diferencia_saldo_inicial,
        "calculado": calculado,
        "no_explicada": (saldo_fin_lib - calculado).quantize(CENTAVO),
    }

    validaciones = validar(extracto, libro, seccion, conc, avisos)

    return {
        "extracto": extracto, "libro": libro, "seccion": seccion,
        "movs": ext, "libro_movs": lib, "conc": conc,
        "validaciones": validaciones, "avisos": avisos,
        "parametros": {"ventana_dias": ventana_dias,
                       "tolerancia_redondeo": tolerancia_redondeo},
    }


# ------------------------------------------------------------
# Libro Excel de salida
# ------------------------------------------------------------

def agrupar_gastos_bancarios(movs):
    """Agrupa los cargos bancarios por concepto para la hoja de gastos."""
    grupos = OrderedDict()

    for mov in movs:
        if not es_cargo_bancario(mov["categoria"]):
            continue

        if mov["categoria"] == "gmf":
            clave = "GMF / 4x1000"
        elif mov["categoria"] == "iva_bancario":
            clave = "IVA de servicios bancarios"
        else:
            base = re.sub(r"[\d\-/:]+", " ", mov["descripcion"])
            clave = re.sub(r"\s+", " ", base).strip(" .") \
                or "Comisión bancaria"
            clave = next((k for k in grupos if k.lower() == clave.lower()),
                         clave)
        if mov["valor"] > 0:
            clave = "Reintegro: " + clave

        grupos.setdefault(clave, {"categoria": mov["categoria"],
                                  "movs": []})["movs"].append(mov)

    resultado = []
    for concepto, datos in grupos.items():
        movs_g = datos["movs"]
        valores = {abs(m["valor"]) for m in movs_g}
        pendientes = [m for m in movs_g if m["estado"] == "sin_libro"]
        resultado.append({
            "concepto": concepto,
            "categoria": datos["categoria"],
            "cantidad": len(movs_g),
            "unitario": next(iter(valores)) if len(valores) == 1 else None,
            "total": sum((abs(m["valor"]) for m in movs_g), CERO),
            "pendientes": pendientes,
            "total_pendiente": sum((abs(m["valor"]) for m in pendientes),
                                   CERO),
            "movs": movs_g,
            "credito": movs_g[0]["valor"] > 0,
        })
    return resultado


def frase_resultado(mov):
    estado = mov["estado"]
    if estado == "conciliado":
        return "Contabilizado"
    if estado == "diferencia":
        return "DIFERENCIA DE VALOR"
    if estado in ("agrupado", "agrupado_diferencia"):
        return ("Contabilizado en conjunto" if estado == "agrupado"
                else "DIFERENCIA en registro conjunto")
    return "PENDIENTE: no se identifica en HELISA"


# ------------------------------------------------------------
# Lectura de extractos y libros en EXCEL / CSV
# ------------------------------------------------------------
# Ademas del PDF, el extracto bancario y HELISA se
# pueden cargar como Excel (.xlsx, .xls, XML 2003) o CSV. La lectura se
# hace por ENCABEZADOS de columna (no por posiciones fijas) para servir a
# cualquier banco.

ENCABEZADOS_EXTRACTO = {
    "fecha": ["fecha", "fecha movimiento", "fecha transaccion",
              "fecha de transaccion", "fecha operacion", "fecha valor",
              "fecha de operacion", "fecha mov", "date"],
    "descripcion": ["descripcion", "concepto", "detalle", "transaccion",
                    "movimiento", "glosa", "descripcion movimiento",
                    "descripcion motivo", "motivo",
                    "clase de movimiento", "narrativa", "nombre"],
    "referencia": ["referencia", "documento", "doc", "numero documento",
                   "comprobante", "ref", "referencia 1", "nro documento",
                   "no documento"],
    "oficina": ["oficina", "sucursal", "canal", "oficina/canal"],
    "debito": ["debito", "debitos", "cargo", "cargos", "retiro", "retiros",
               "egreso", "egresos", "salida", "salidas", "valor debito",
               "debe"],
    "credito": ["credito", "creditos", "abono", "abonos", "deposito",
                "depositos", "consignacion", "consignaciones", "ingreso",
                "ingresos", "entrada", "entradas", "valor credito", "haber"],
    "valor": ["valor", "monto", "importe", "valor transaccion",
              "valor movimiento", "valor total"],
    "saldo": ["saldo", "saldo disponible", "saldo total", "nuevo saldo",
              "saldo final"],
    "naturaleza": ["naturaleza", "tipo", "d/c", "tipo movimiento",
                   "debito/credito", "signo", "transaccion",
                   "tipo de transaccion"],
}

ENCABEZADOS_LIBRO = {
    "fecha": ["fecha"],
    "tipo": ["tipo", "tipo documento", "tipo doc", "comprobante", "doc",
             "clase"],
    "numero": ["numero", "no", "nro", "numero documento", "consecutivo",
               "num"],
    "documento": ["documento", "comprobante numero", "soporte"],
    "tercero": ["tercero", "nombre", "beneficiario", "nombre tercero",
                "detalle", "concepto", "descripcion", "nombre del tercero"],
    "debito": ["debito", "debitos", "debe", "valor debito"],
    "credito": ["credito", "creditos", "haber", "valor credito"],
    "saldo": ["saldo", "saldo final", "nuevo saldo"],
}


def _celda_texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float):
        return f"{valor:.2f}"
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor.strftime("%d/%m/%Y")
    return str(valor).strip()


def fecha_celda(valor, anio_defecto=None):
    """Fecha desde una celda de Excel/CSV (fecha, serial o texto)."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if isinstance(valor, (int, float)) and 20000 < float(valor) < 80000:
        return datetime.date(1899, 12, 30) + datetime.timedelta(
            days=int(valor))
    texto = str(valor).strip()
    texto = re.sub(r"\s+", " ", texto)
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", texto)
    if m:
        return crear_fecha(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"^(\d{1,2})[/\-. ]\s*(\d{1,2})[/\-. ]\s*(\d{2,4})\b", texto)
    if m:
        anio = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return crear_fecha(anio, int(m[2]), int(m[1]))
    m = re.match(r"^(\d{1,2})[/\-. ]\s*([A-Za-zñÑ]{3,10})\.?[/\-. ]\s*"
                 r"(\d{2,4})\b", texto)
    if m:
        mes = _mes_abreviado(m[2]) or MESES_COMPLETOS.get(
            texto_comparable(m[2]))
        anio = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return crear_fecha(anio, mes, int(m[1])) if mes else None
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})$", texto)
    if m and anio_defecto:
        return crear_fecha(anio_defecto, int(m[2]), int(m[1]))
    return None


def monto_celda(valor):
    """Decimal desde numero o texto ($ 1.234.567,89 / 1,234.56- / (500))."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(round(float(valor), 2))).quantize(CENTAVO)
    texto = str(valor).strip()
    if not re.search(r"\d", texto):
        return None
    negativo = (texto.startswith("(") and texto.endswith(")")) or \
        bool(re.match(r"^\s*-|.*-\s*$|^\$\s*-", texto))
    cuerpo = re.sub(r"[^\d.,]", "", texto)
    if not cuerpo or re.search(r"[A-Za-z]{2,}", texto):
        return None
    if "," in cuerpo and "." in cuerpo:
        decimal = "," if cuerpo.rfind(",") > cuerpo.rfind(".") else "."
    elif "," in cuerpo:
        decimal = "," if (cuerpo.count(",") == 1 and
                          re.search(r",\d{1,2}$", cuerpo)) else None
    elif "." in cuerpo:
        decimal = "." if (cuerpo.count(".") == 1 and
                          re.search(r"\.\d{1,2}$", cuerpo)) else None
    else:
        decimal = None
    if decimal:
        miles = "," if decimal == "." else "."
        cuerpo = cuerpo.replace(miles, "").replace(decimal, ".")
    else:
        cuerpo = cuerpo.replace(",", "").replace(".", "")
    try:
        numero_valor = Decimal(cuerpo).quantize(CENTAVO)
    except Exception:
        return None
    return -numero_valor if negativo else numero_valor


def _ubicar_encabezados(tabla, sinonimos, obligatorias, maximo=60):
    """Busca la fila de encabezados. Devuelve (indice_fila, {campo: col})."""
    for indice, fila in enumerate(tabla[:maximo]):
        textos = [texto_comparable(_celda_texto(v)).strip(" :.")
                  for v in fila]
        columnas = {}
        # Primero los nombres exactos ("Valor Total" antes que "Valor
        # Cheque"), luego los que empiezan por un sinonimo.
        for exacto in (True, False):
            for campo, nombres in sinonimos.items():
                if campo in columnas:
                    continue
                for col, texto in enumerate(textos):
                    if not texto or col in columnas.values():
                        continue
                    if texto in nombres or (not exacto and any(
                            texto.startswith(n + " ") for n in nombres
                            if len(n) > 3)):
                        columnas[campo] = col
                        break
        if all(any(c in columnas for c in grupo) for grupo in obligatorias):
            return indice, columnas
    return None, {}


def _texto_tabla(filas):
    return "\n".join(" ".join(_celda_texto(v) for v in fila if
                              _celda_texto(v)) for fila in filas)


def leer_extracto_excel(contenido, anio_defecto=None):
    anio_defecto = anio_defecto or datetime.date.today().year
    try:
        tabla = tabla_desde_archivo(contenido)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("No se pudo abrir el extracto en Excel/CSV. "
                         "Verifica que no tenga contraseña.") from error

    fila_cab, columnas = _ubicar_encabezados(
        tabla, ENCABEZADOS_EXTRACTO,
        [("fecha",), ("valor", "debito", "credito")])
    if fila_cab is None:
        raise ValueError(
            "No se encontró la fila de encabezados del extracto (se busca "
            "una columna FECHA y una de VALOR o DÉBITO/CRÉDITO).")

    texto_encabezado = _texto_tabla(tabla[:fila_cab])
    periodo = detectar_periodo(texto_encabezado)
    anio = periodo[1].year if periodo else anio_defecto

    def celda(fila, campo):
        col = columnas.get(campo)
        return fila[col] if col is not None and col < len(fila) else None

    filas = []
    pie = []
    for indice in range(fila_cab + 1, len(tabla)):
        fila = tabla[indice]
        fecha = fecha_celda(celda(fila, "fecha"), anio)
        if not fecha:
            if any(_celda_texto(v) for v in fila):
                pie.append(fila)
            continue
        debito = monto_celda(celda(fila, "debito"))
        credito = monto_celda(celda(fila, "credito"))
        valor = monto_celda(celda(fila, "valor"))
        saldo = monto_celda(celda(fila, "saldo"))
        if debito is None and credito is None and valor is None:
            continue
        if debito is not None or credito is not None:
            valor = abs(credito or CERO) - abs(debito or CERO)
        else:
            naturaleza = texto_comparable(_celda_texto(
                celda(fila, "naturaleza")))
            # "D", "Débito", "Cargo", "Nota Débito" (portal Davivienda)...
            if (naturaleza.startswith(("d", "cargo", "retiro", "egreso"))
                    or re.search(r"\b(debito|cargo|retiro)\b", naturaleza)) \
                    and valor > 0:
                valor = -valor
        if valor == 0:
            continue
        descripcion = " ".join(x for x in [
            _celda_texto(celda(fila, "descripcion")),
            _celda_texto(celda(fila, "referencia"))] if x) \
            or "(sin descripción)"
        filas.append({"fecha": fecha, "valor": valor, "saldo": saldo,
                      "descripcion": re.sub(r"\s+", " ", descripcion),
                      "fila": indice + 1})

    if not filas:
        raise ValueError("No se encontraron movimientos en el extracto "
                         "(filas con fecha y valor).")

    # Algunos bancos listan del mas reciente al mas antiguo.
    if filas[0]["fecha"] > filas[-1]["fecha"]:
        filas.reverse()

    con_saldo = sum(1 for f in filas if f["saldo"] is not None)
    saldo_corrido = con_saldo >= max(1, int(len(filas) * 0.6))
    inconsistentes = 0

    # Con un solo campo VALOR sin signo, el signo sale del saldo corrido.
    if saldo_corrido and "valor" in columnas and not (
            "debito" in columnas or "credito" in columnas) and \
            all(f["valor"] > 0 for f in filas):
        anterior = None
        for f in filas:
            if f["saldo"] is None:
                continue
            if anterior is not None:
                if abs((f["saldo"] - anterior) + f["valor"]) <= CENTAVO:
                    f["valor"] = -f["valor"]
            anterior = f["saldo"]

    resumen = leer_resumen_saldos(
        texto_encabezado + "\n" + _texto_tabla(pie), ".")
    if saldo_corrido:
        primera = next(f for f in filas if f["saldo"] is not None)
        resumen.setdefault("saldo_inicial", primera["saldo"]
                           - primera["valor"])
        ultima = next(f for f in reversed(filas) if f["saldo"] is not None)
        resumen.setdefault("saldo_final", ultima["saldo"])
        anterior = resumen.get("saldo_inicial")
        for f in filas:
            if f["saldo"] is None:
                continue
            if anterior is not None and abs(anterior + f["valor"]
                                            - f["saldo"]) > CENTAVO:
                inconsistentes += 1
            anterior = f["saldo"]
    for clave in ("creditos", "debitos"):
        if resumen.get(clave) is not None:
            resumen[clave] = abs(resumen[clave])

    if not periodo:
        inicio = min(f["fecha"] for f in filas)
        fin = max(f["fecha"] for f in filas)
        periodo = (inicio.replace(day=1),
                   fin.replace(day=ultimo_dia_mes(fin.year, fin.month)))

    movimientos = [{
        "fecha": f["fecha"],
        "descripcion": f["descripcion"],
        "valor": f["valor"].quantize(CENTAVO),
        "saldo": f["saldo"],
        "pagina": None,
        "ubicacion": f"Fila {f['fila']}",
    } for f in filas]

    texto_total = _texto_tabla(tabla)
    banco = detectar_banco(texto_total)
    encabezado = " ".join(texto_comparable(_celda_texto(v))
                          for v in tabla[fila_cab])
    if (not banco or "no reconocido" in str(banco).lower()) and \
            "descripcion motivo" in encabezado and "fecha de sistema" in \
            encabezado:
        banco = "Davivienda"          # exportacion del portal Davivienda
    return {
        "banco": banco,
        "tipo_cuenta": detectar_tipo_cuenta(texto_total),
        "cuenta": detectar_cuenta(texto_encabezado) or
        detectar_cuenta(texto_total),
        "periodo": periodo,
        "resumen": resumen,
        "movimientos": movimientos,
        "saldo_corrido": saldo_corrido,
        "inconsistentes": inconsistentes,
        "decimal": ".",
        "formato": "Excel",
    }


def leer_libro_excel(contenido):
    """
    HELISA exportado a Excel. Primero se intenta
    por encabezados (FECHA / DEBITOS / CREDITOS / SALDO); si no, cada fila
    se convierte en texto y se interpreta igual que el PDF.
    """
    try:
        tabla = tabla_desde_archivo(contenido)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("No se pudo abrir el archivo de HELISA en Excel. "
                         "Verifica que no tenga contraseña.") from error

    texto_inicio = _texto_tabla(tabla[:40])
    empresa = next((_celda_texto(v) for fila in tabla[:3] for v in fila
                    if _celda_texto(v)), "")
    nit = re.search(r"nit:?\s*([\d.,\- ]+\d)", texto_inicio, re.IGNORECASE)
    periodo = None
    m = RE_HELISA_PERIODO.search(texto_inicio)
    if m:
        mes1, mes2 = _mes_abreviado(m[2]), _mes_abreviado(m[5])
        if mes1 and mes2:
            periodo = (crear_fecha(int(m[3]), mes1, int(m[1])),
                       crear_fecha(int(m[6]), mes2, int(m[4])))
    else:
        m = re.search(r"desde\s+(\S+)\s+(?:a|hasta)\s+(\S+)", texto_inicio,
                      re.IGNORECASE)
        if m:
            a, b = fecha_celda(m[1]), fecha_celda(m[2])
            if a and b:
                periodo = (a, b)

    fila_cab, columnas = _ubicar_encabezados(
        tabla, ENCABEZADOS_LIBRO, [("fecha",), ("debito",), ("credito",)])

    secciones, actual = [], None
    anio = periodo[1].year if periodo else datetime.date.today().year

    def celda(fila, campo):
        col = columnas.get(campo)
        return fila[col] if col is not None and col < len(fila) else None

    if fila_cab is not None:
        for indice in range(fila_cab + 1, len(tabla)):
            fila = tabla[indice]
            texto = " ".join(_celda_texto(v) for v in fila if
                             _celda_texto(v))
            if re.search(r"saldo\s+inicial", texto, re.IGNORECASE):
                etiqueta = re.split(r"saldo\s+inicial", texto,
                                    flags=re.IGNORECASE)[0].strip()
                numeros = [monto_celda(v) for v in fila
                           if monto_celda(v) is not None
                           and not fecha_celda(v)]
                digitos = re.findall(r"\d[\d\-]{4,}\d", etiqueta)
                clave = re.sub(r"\D", "", digitos[-1]) if digitos \
                    else etiqueta
                existente = next((s for s in secciones
                                  if s["clave"] == clave), None)
                if existente:
                    actual = existente
                else:
                    actual = {"clave": clave, "etiqueta": etiqueta,
                              "cuenta": clave if digitos else "",
                              "saldo_inicial": numeros[-1] if numeros
                              else None,
                              "fecha_saldo_inicial": None,
                              "movimientos": []}
                    secciones.append(actual)
                continue

            fecha = fecha_celda(celda(fila, "fecha"), anio)
            debito = monto_celda(celda(fila, "debito"))
            credito = monto_celda(celda(fila, "credito"))
            if not fecha or (not debito and not credito):
                continue
            tipo = _celda_texto(celda(fila, "tipo"))
            numero_doc = _celda_texto(celda(fila, "numero"))
            documento = _celda_texto(celda(fila, "documento"))
            if documento and not (tipo and numero_doc):
                partes = re.match(r"^\s*([A-Za-z]{1,5})[\s\-]*(.*)$",
                                  documento)
                if partes:
                    tipo = tipo or partes[1].upper()
                    numero_doc = numero_doc or partes[2].strip()
                else:
                    numero_doc = numero_doc or documento
            numero_doc = re.sub(r"\.0+$", "", numero_doc)
            if actual is None:
                actual = {"clave": "", "etiqueta": "", "cuenta": "",
                          "saldo_inicial": None, "fecha_saldo_inicial": None,
                          "movimientos": []}
                secciones.append(actual)
            debito = abs(debito or CERO)
            credito = abs(credito or CERO)
            saldo = monto_celda(celda(fila, "saldo"))
            actual["movimientos"].append({
                "fecha": fecha,
                "tipo": tipo or "DOC",
                "numero": numero_doc.lstrip("0") or "0",
                "tercero": re.sub(r"\s+", " ", _celda_texto(
                    celda(fila, "tercero"))),
                "debito": debito,
                "credito": credito,
                "valor": (debito - credito).quantize(CENTAVO),
                "saldo": saldo,
                "pagina": None,
                "ubicacion": f"Fila {indice + 1}",
            })

    secciones = [s for s in secciones if s["movimientos"]]
    if not secciones:
        # Respaldo: cada fila como linea de texto, igual que el PDF.
        lineas, ubicaciones = [], []
        for indice, fila in enumerate(tabla):
            partes = []
            for v in fila:
                if isinstance(v, float):
                    partes.append(f"{v:,.2f}")
                elif isinstance(v, (datetime.datetime, datetime.date)):
                    partes.append(f"{v.day:02d}/"
                                  f"{ETIQUETA_MES[v.month - 1].capitalize()}"
                                  f"/{v.year}")
                elif _celda_texto(v):
                    partes.append(_celda_texto(v))
            lineas.append(" ".join(partes))
            ubicaciones.append(f"Fila {indice + 1}")
        libro = procesar_lineas_libro(lineas, ubicaciones, None, "Excel")
        return libro

    for seccion in secciones:
        movs = seccion["movimientos"]
        if seccion["saldo_inicial"] is None:
            primero = next((m for m in movs if m["saldo"] is not None), None)
            if primero:
                seccion["saldo_inicial"] = primero["saldo"] - primero["valor"]
        neto = sum((m["valor"] for m in movs), CERO)
        ultimo = next((m["saldo"] for m in reversed(movs)
                       if m["saldo"] is not None), None)
        seccion["saldo_final"] = ultimo if ultimo is not None else (
            (seccion["saldo_inicial"] or CERO) + neto)
        previo = seccion["saldo_inicial"]
        seccion["inconsistentes"] = 0
        for mov in movs:
            if mov["saldo"] is None:
                mov["saldo"] = (previo or CERO) + mov["valor"]
            elif previo is not None and abs(
                    previo + mov["valor"] - mov["saldo"]) > CERO:
                seccion["inconsistentes"] += 1
            previo = mov["saldo"]

    if not periodo:
        fechas = [m["fecha"] for s in secciones for m in s["movimientos"]]
        periodo = (min(fechas).replace(day=1),
                   max(fechas).replace(day=ultimo_dia_mes(
                       max(fechas).year, max(fechas).month)))

    return {
        "empresa": empresa,
        "nit": nit.group(1).strip() if nit else "",
        "periodo": periodo,
        "secciones": secciones,
        "formato": "Excel",
    }


def es_pdf(contenido):
    return contenido[:5] == b"%PDF-" or contenido[:1024].find(b"%PDF") >= 0


def leer_extracto(contenido, anio_defecto=None):
    if es_pdf(contenido):
        return leer_extracto_pdf(contenido, anio_defecto)
    return leer_extracto_excel(contenido, anio_defecto)


def leer_libro(contenido):
    if es_pdf(contenido):
        return leer_libro_helisa(contenido)
    return leer_libro_excel(contenido)


def detectar_tipo_documento(contenido):
    """'libro' (HELISA), 'extracto' o 'desconocido'. PDF, Excel o CSV."""
    try:
        if es_pdf(contenido):
            import pdfplumber
            with pdfplumber.open(io.BytesIO(contenido)) as pdf:
                texto = (pdf.pages[0].extract_text(x_tolerance=1.5) or "")
        else:
            texto = _texto_tabla(tabla_desde_archivo(contenido)[:40])
    except Exception:
        return "desconocido"
    return "libro" if es_libro_helisa(texto) else "extracto"


# Compatibilidad con la version anterior
detectar_tipo_pdf = detectar_tipo_documento


# ------------------------------------------------------------
# Conciliacion bancaria flexible: varios extractos contra uno o varios
# HELISA (varias cuentas). Nunca se bloquea por documentos
# "raros": se concilia lo que se pueda y se avisa lo que no cuadra.
# ------------------------------------------------------------
UMBRAL_PAREJA_SEGURA = 50       # puntaje desde el que la pareja es clara


UMBRAL_PAREJA_DUDOSA = 25       # por debajo: "parecen cuentas distintas"


def etiqueta_cuenta(extracto, seccion):
    tipo = (extracto or {}).get("tipo_cuenta") or ""
    numero = (extracto or {}).get("cuenta") or (seccion or {}).get(
        "cuenta") or (seccion or {}).get("etiqueta") or "sin número"
    return f"{tipo} {numero}".strip()


def avisos_totales(resultado):
    """Avisos generales + los de cada cuenta, sin repetir."""
    vistos, salida = set(), []
    for aviso in resultado["avisos"] + [
            a for c in resultado["cuentas"] for a in c["analisis"]["avisos"]]:
        if aviso not in vistos:
            vistos.add(aviso)
            salida.append(aviso)
    return salida


# ------------------------------------------------------------
# Gastos bancarios por categoria y subcategoria (soporte de notas)
# ------------------------------------------------------------
SUBCATEGORIAS_COMISION = [
    ("Cuota manejo tarjeta débito", ["manejo tarj", "c manejo",
                                     "cuota de manejo", "cuota manejo"]),
    ("Cuota plan canal negocios", ["cuota plan", "plan canal"]),
    ("Comisión pago nómina", ["pago de nomina", "pago nomina"]),
    ("Comisión pago proveedores", ["pago a proveedores", "pago de prov",
                                   "pago proveedores"]),
    ("Pago a otros bancos", ["otros bancos", "otro banco"]),
    ("Chequera", ["chequera"]),
    ("Transferencias", ["transf", "ach"]),
    ("Intereses cobrados por el banco", ["interes", "sobregiro"]),
]


def categoria_gasto(mov):
    """(categoria, subcategoria) del soporte de gastos bancarios o None."""
    claro = texto_comparable(mov.get("descripcion", ""))
    cat = mov.get("categoria")
    if cat == "gmf":
        return "GMF 4x1000", "GMF"
    if cat == "iva_bancario":
        if _contiene(claro, "cuota plan") or _contiene(claro, "plan canal"):
            return "IVA sobre comisión", "IVA cuota plan"
        if "automatic" in claro:
            return "IVA sobre comisión", "IVA pagos automáticos"
        return "IVA sobre comisión", "IVA comisiones"
    if cat == "rendimientos" and mov["valor"] > 0:
        return "Intereses ganados", ("Intereses de ahorros" if "ahorro"
                                     in claro else "Rendimientos")
    if cat == "comision":
        for nombre, palabras in SUBCATEGORIAS_COMISION:
            if any(_contiene(claro, p) for p in palabras):
                return "Comisión", nombre
        return "Comisión", "Otras comisiones"
    if cat == "impuestos" and any(_contiene(claro, p) for p in
                                  ("retefuente", "retencion")) \
            and mov["valor"] < 0 and "banc" in claro:
        return "Retención en la fuente", "Retención sobre rendimientos"
    return None


def contabilizado_en_libro(mov, lib):
    estado = mov["estado"]
    docs = ", ".join(f"{lib[j]['tipo']} {lib[j]['numero']}"
                     for j in mov.get("pareja", []))
    if estado == "conciliado":
        return f"Sí ({docs})"
    if estado == "agrupado":
        return (f"Sí, agrupado ({docs})" if mov.get("grupo_nm")
                else f"Sí, en nota agrupada ({docs})")
    if estado == "agrupado_diferencia":
        return f"En nota agrupada con diferencia ({docs})"
    if estado == "diferencia":
        return f"Con valor diferente ({docs})"
    return "No"
