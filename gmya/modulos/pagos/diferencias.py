"""Datos del panel de revision de la programacion de pagos / cuentas por
cobrar (v6.14, sin Streamlit). Reemplaza al visor como vista principal.
Modelo: gmya/ui/visual.py (panel de diferencias, modo "revision").

Contrato:
  panel_revision_pagos(partidas, ordenar, titulo, lado="Programación")
      -> [concepto] (uno) con revision=True:
    total_a = total incluido en la programacion actual, total_b = 0.
    composicion (suma EXACTA total_a): "Sin novedad" (explicada) y una
      fila por motivo a confirmar (pendiente), segun el PRIMER motivo de
      cada partida.
    partidas: solo las INCLUIDAS que tienen algo que confirmar (lista
      'revisar' de las reglas de cada empresa), las mismas que marcaba el
      visor. grupos: lo que sale de la programacion (no se paga).
Regla confidencial: no se clasifica ni se resalta nada por venir solo de
la programacion anterior; las partidas de ese origen no traen 'revisar' y
quedan dentro de "Sin novedad" con las demas.
Depende de: gmya.comun.numeros
"""

from gmya.comun.numeros import formato_cop

# (palabra del motivo, causa corta). El primero que coincide gana.
CAUSAS = [
    ("proyección", "Proyección (factura aún no llega)"),
    ("nuevo", "Nueva: completar datos"),
    ("fecha de pago que ya pasó", "¿Ya se pagó?"),
    ("anterior a la programación", "No estaba en la anterior"),
    ("abonos", "Tiene abonos"),
    ("negativo", "Valor negativo"),
    ("observación anterior", "Observación por resolver"),
    ("fecha incompleta", "Fecha incompleta"),
    ("mayor que el valor", "Saldo mayor al inicial"),
    ("vencida", "Vencida hace más de 90 días"),
]


def _f(v):
    return round(float(v or 0), 2)


def _valor(p):
    return _f(p["pagar"] if p.get("pagar") is not None else p.get("saldo"))


def causa_revision(textos):
    t = " ".join(textos).lower()
    for palabra, causa in CAUSAS:
        if palabra in t:
            return causa
    return "Confirmar"


def panel_revision_pagos(partidas, ordenar, titulo, lado="Programación"):
    orden = ordenar(partidas) if ordenar else list(partidas)
    incluidas = [p for p in orden if p.get("incluir")]
    salen = [p for p in orden if not p.get("incluir")]
    revisar = [p for p in incluidas if p.get("revisar")]
    sin_nov = [p for p in incluidas if not p.get("revisar")]
    total = _f(sum(_valor(p) for p in incluidas))

    comp = []
    if sin_nov:
        comp.append({"etiqueta": "Sin novedad (se programan tal cual)",
                     "valor": _f(sum(_valor(p) for p in sin_nov)),
                     "tipo": "explicada", "n": len(sin_nov)})
    por_causa = {}
    for p in revisar:
        por_causa.setdefault(causa_revision(p["revisar"]), []).append(p)
    for causa, ps in por_causa.items():
        comp.append({"etiqueta": causa, "valor": _f(sum(_valor(p) for p in ps)),
                     "tipo": "pendiente", "n": len(ps)})

    filas = []
    for p in revisar:
        quien = p.get("proveedor") or p.get("grupo") or p.get("tercero") or ""
        doc = " ".join(str(x) for x in (p.get("tipo"), p.get("numero"))
                       if x).strip()
        sub = " · ".join(x for x in (
            doc, str(p.get("concepto") or "")[:60],
            f"vence {p['vence']:%d/%m/%Y}" if p.get("vence") else "") if x)
        filas.append({
            "id": p.get("id") or quien, "titulo": quien or doc or "Partida",
            "sub": sub, "causa": causa_revision(p["revisar"]), "tipo": "otro",
            "revision": True, "lado_a": "A pagar",
            "a": _valor(p), "b": None, "nota": " ".join(p["revisar"]),
            "detalle": [("Documento", doc or "—", ""),
                        ("Saldo", _f(p.get("saldo")), ""),
                        ("A pagar", _valor(p), "")]
            + ([("Observación", p["obs"], "")] if p.get("obs") else [])})

    grupos = []
    if salen:
        grupos.append({"etiqueta": "Salen de la programación", "n": len(salen),
                       "valor": _f(sum(_f(p.get("saldo")) for p in salen)),
                       "tipo": "explicada",
                       "nota": "Pagadas, sin saldo o desmarcadas: no se "
                               "incluyen. Se pueden volver a incluir en la "
                               "tabla de revisión."})
    return [{
        "clave": titulo, "nombre": "", "revision": True,
        "sub": f"{len(incluidas)} partidas incluidas · {len(revisar)} por "
               "confirmar",
        "lado_a": lado, "lado_b": "",
        "total_a": total, "total_b": 0.0,
        "dona": [("Sin novedad", len(sin_nov), "ok"),
                 ("Por confirmar", len(revisar), "alerta"),
                 ("Salen", len(salen), "neutro")],
        "centro": str(len(incluidas)), "centro_sub": "incluidas",
        "datos": [("Total incluido", formato_cop(total)),
                  ("Por confirmar", formato_cop(sum(_valor(p)
                                                    for p in revisar))),
                  ("Partidas por confirmar", str(len(revisar))),
                  ("Salen", str(len(salen)))],
        "composicion": comp, "partidas": filas, "grupos": grupos,
    }]


# ------------------------------------------------------------
# v6.16 · Graficos de la programacion (antiguedad y concentracion)
# ------------------------------------------------------------
def datos_graficos(partidas, fecha):
    """Solo partidas INCLUIDAS, agregadas (ninguna fila se marca ni se
    distingue por su origen):
      antiguedad: tramos de vencimiento a la fecha de la programacion.
      terceros: [(tercero, valor)] top 10 + "Otros".
      concentracion: (k, n) k terceros suman el 80 % del total.
    """
    from gmya.comun.estadistica import antiguedad, concentracion, top_n
    inc = [p for p in partidas if p.get("incluir")]
    tramos = antiguedad(inc, fecha, _valor, lambda p: p.get("vence"))
    por = {}
    for p in inc:
        t = p.get("proveedor") or p.get("tercero") or p.get("grupo") or \
            "(sin tercero)"
        por[t] = por.get(t, 0) + _valor(p)
    return {"antiguedad": tramos,
            "terceros": top_n(por.items(), 10),
            "concentracion": concentracion(por.values())}
