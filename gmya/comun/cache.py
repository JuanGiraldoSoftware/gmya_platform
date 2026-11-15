"""Decoradores de cache de Streamlit que degradan a "sin cache" cuando
Streamlit no esta disponible (pruebas).

Contrato:
  @_cache          st.cache_data (8 entradas)   resultados por contenido.
  @_cache_datos    st.cache_data (1 h, 4)       lecturas pesadas de disco.
  @_cache_recurso  st.cache_resource            objetos unicos (indices,
                                                hilos de escritura).
  _huella(*partes) -> sha1 hex de bytes/textos, para saber si cambio algo.
  @memo_copia(n)   memoria propia (sin Streamlit) de las ultimas n lecturas
                   por contenido; devuelve SIEMPRE una copia, asi quien la
                   modifique no altera la guardada (v6.6: un PDF de HELISA
                   ya no se lee dos veces, al cargarlo y al conciliar).

Depende de: (solo biblioteca estandar / terceros)
"""

import streamlit as st


def _cache(funcion):
    decorador = getattr(st, "cache_data", None)
    return decorador(show_spinner=False, max_entries=8)(funcion) \
        if decorador else funcion


def _cache_recurso(funcion):
    decorador = getattr(st, "cache_resource", None)
    return decorador(show_spinner=False)(funcion) if decorador else funcion


def _cache_datos(funcion):
    decorador = getattr(st, "cache_data", None)
    return decorador(show_spinner=False, ttl=3600, max_entries=4)(funcion) \
        if decorador else funcion


def _huella(*partes):
    import hashlib
    h = hashlib.sha1()
    for p in partes:
        h.update(p if isinstance(p, bytes) else str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def memo_copia(maximo=6):
    import copy
    import hashlib
    from collections import OrderedDict
    from functools import wraps

    def decorador(funcion):
        guardados = OrderedDict()

        @wraps(funcion)
        def envoltura(contenido, *args, **kwargs):
            if not isinstance(contenido, (bytes, bytearray)):
                return funcion(contenido, *args, **kwargs)
            llave = (hashlib.sha1(contenido).hexdigest(), args,
                     tuple(sorted(kwargs.items())))
            if llave in guardados:
                guardados.move_to_end(llave)
                return copy.deepcopy(guardados[llave])
            valor = funcion(contenido, *args, **kwargs)
            guardados[llave] = copy.deepcopy(valor)
            while len(guardados) > maximo:
                guardados.popitem(last=False)
            return valor
        envoltura.limpiar = guardados.clear
        return envoltura
    return decorador
