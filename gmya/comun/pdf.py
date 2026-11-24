"""Lectura basica de PDF con pdfplumber (sin Streamlit).

Contrato:
  palabras_pagina(pagina) -> palabras con coordenadas de una pagina.
  agrupar_lineas(palabras) -> lineas (listas de palabras) ordenadas de
                              arriba abajo, agrupadas por altura.

Depende de: (solo biblioteca estandar / terceros)
"""



# ------------------------------------------------------------
# Lectura de palabras y lineas del PDF
# ------------------------------------------------------------
def agrupar_lineas(palabras, tolerancia=2.5):
    lineas = []

    for palabra in sorted(palabras, key=lambda w: (w["top"], w["x0"])):
        if lineas and abs(palabra["top"] - lineas[-1]["top"]) <= tolerancia:
            lineas[-1]["palabras"].append(palabra)
        else:
            lineas.append({"top": palabra["top"], "palabras": [palabra]})

    for linea in lineas:
        linea["palabras"].sort(key=lambda w: w["x0"])
        unidas = []
        for palabra in linea["palabras"]:
            if unidas and unidas[-1]["text"] in ("$", "$-", "-$"):
                previa = unidas.pop()
                palabra = {
                    **palabra,
                    "text": previa["text"] + palabra["text"],
                    "x0": previa["x0"],
                }
            unidas.append(palabra)
        linea["palabras"] = unidas
        linea["texto"] = " ".join(w["text"] for w in unidas)

    return lineas


def palabras_pagina(pagina):
    palabras = pagina.extract_words(
        x_tolerance=1.5, keep_blank_chars=False, extra_attrs=["upright"]
    )
    # El texto vertical (sellos, marcas de agua) no es parte de la tabla.
    return [w for w in palabras if w.get("upright", True)]
