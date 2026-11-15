"""Globos de ayuda flotantes (JS_GLOBOS) y bloqueo de la traduccion automatica
del navegador.

Contrato:
  _bloquear_traduccion() -> inyecta un componente invisible (height=0) que
      marca la pagina como lang="es" translate="no" y posiciona los globos
      "?" para que nunca queden cortados por los bordes de la pantalla.
      app.py lo llama en cada ejecucion.

Depende de: (solo biblioteca estandar / terceros)
"""

import json


# ------------------------------------------------------------
# Globos flotantes (v5.9): las ayudas (?) y las explicaciones del visor
# se muestran en UNA capa fija sobre toda la pagina (no dentro de su
# contenedor), ubicada para que quepa en la pantalla: debajo o encima del
# elemento segun el espacio, pegada al borde izquierdo o derecho y sin
# salirse de los margenes. Asi no la cortan los paneles con desplazamiento,
# las columnas, la barra lateral ni el borde de la ventana, y queda por
# encima de cualquier otro elemento. Si el script no corre, queda el globo
# por CSS de siempre.
# ------------------------------------------------------------
JS_GLOBOS = r"""
(function (doc) {
  if (!doc || doc.getElementById('gm-flot')) { return; }
  var win = doc.defaultView || window;
  var estilo = doc.createElement('style');
  estilo.id = 'gm-flot-estilo';
  estilo.textContent = [
    'html.gm-globos-js .gm-ayuda .gm-ayuda-texto,',
    'html.gm-globos-js .gm-emp-off .gm-ayuda-texto,',
    'html.gm-globos-js .gm-tip { display: none !important; }',
    '#gm-flot { position: fixed; left: 0; top: 0; display: none;',
    '  z-index: 2147483000; pointer-events: none; box-sizing: border-box;',
    '  overflow: hidden; white-space: normal; text-align: left;',
    '  text-transform: none; letter-spacing: 0; word-wrap: break-word;',
    '  font-family: Montserrat, "Segoe UI", Arial, sans-serif; }',
    '#gm-flot.ayuda { background: #161415; color: #fff;',
    '  border: 2px solid #E0118F; border-radius: 12px;',
    '  padding: .85rem 1rem; font-size: 12.8px; font-weight: 500;',
    '  line-height: 1.55; box-shadow: 5px 5px 0 #E0118F; }',
    '#gm-flot.ayuda b { color: #FF8AD0; }',
    '#gm-flot.tip { background: #272526; color: #fff;',
    '  border-left: 5px solid #E0118F; border-radius: 8px;',
    '  padding: .55rem .7rem; font-size: 12.5px; font-weight: 500;',
    '  line-height: 1.38; box-shadow: 0 8px 22px rgba(0,0,0,.35); }',
    '#gm-flot.tip b { color: #FF7CC8; } #gm-flot.tip i { color: #FFD24D; }'
  ].join('\n');
  (doc.head || doc.documentElement).appendChild(estilo);
  var flot = doc.createElement('div');
  flot.id = 'gm-flot';
  flot.setAttribute('role', 'tooltip');
  doc.body.appendChild(flot);
  doc.documentElement.classList.add('gm-globos-js');

  var MARGEN = 8, SEPARACION = 8, actual = null;

  // Elemento que dispara el globo y su contenido.
  function origen(el) {
    if (!el || !el.closest) { return null; }
    var a = el.closest('.gm-ayuda, .gm-emp-off');
    if (a) {
      var t = a.querySelector('.gm-ayuda-texto');
      return t ? {ancla: a, refe: a, tipo: 'ayuda', html: t.innerHTML} : null;
    }
    var h = el.closest('.gm-hot');
    if (h) {
      var t2 = h.querySelector('.gm-tip');
      return t2 ? {ancla: h, refe: h, tipo: 'tip', html: t2.innerHTML} : null;
    }
    var fila = el.closest('tr');
    if (fila) {
      var celda = fila.querySelector('td.gm-hot-td');
      var t3 = celda && celda.querySelector('.gm-tip');
      return t3 ? {ancla: fila, refe: celda, tipo: 'tip',
                   html: t3.innerHTML} : null;
    }
    return null;
  }

  function ubicar(o) {
    var vw = doc.documentElement.clientWidth || win.innerWidth;
    var vh = doc.documentElement.clientHeight || win.innerHeight;
    var r = o.refe.getBoundingClientRect();
    var ancho = o.tipo === 'ayuda' ? 380 : 430;
    flot.className = o.tipo;
    flot.innerHTML = o.html;
    flot.style.visibility = 'hidden';
    flot.style.display = 'block';
    flot.style.left = '0px'; flot.style.top = '0px';
    flot.style.maxHeight = (vh - 2 * MARGEN) + 'px';
    if (o.tipo === 'ayuda') {
      flot.style.width = Math.min(ancho, vw - 2 * MARGEN) + 'px';
      flot.style.maxWidth = '';
    } else {
      flot.style.width = 'max-content';
      flot.style.maxWidth = Math.min(ancho, vw - 2 * MARGEN) + 'px';
    }
    var w = flot.offsetWidth, h = flot.offsetHeight;
    // Vertical: debajo si cabe; si no, encima; si no, donde haya mas
    // espacio, sin salirse de la pantalla.
    var abajo = vh - r.bottom - SEPARACION - MARGEN;
    var arriba = r.top - SEPARACION - MARGEN;
    var top;
    if (h <= abajo) { top = r.bottom + SEPARACION; }
    else if (h <= arriba) { top = r.top - SEPARACION - h; }
    else { top = abajo >= arriba ? vh - MARGEN - h : MARGEN; }
    top = Math.max(MARGEN, Math.min(top, vh - MARGEN - h));
    // Horizontal: si el elemento esta en la mitad derecha, el globo crece
    // hacia la izquierda (alineado a su borde derecho); si no, a la derecha.
    var left = (r.left + r.width / 2 > vw / 2) ? r.right - w : r.left;
    left = Math.max(MARGEN, Math.min(left, vw - MARGEN - w));
    flot.style.left = Math.round(left) + 'px';
    flot.style.top = Math.round(top) + 'px';
    flot.style.visibility = 'visible';
  }

  function mostrar(o) { actual = o; ubicar(o); }
  function ocultar() { actual = null; flot.style.display = 'none'; }

  doc.addEventListener('mouseover', function (e) {
    var o = origen(e.target);
    if (!o) { if (actual) { ocultar(); } return; }
    if (actual && actual.ancla === o.ancla) { return; }
    mostrar(o);
  }, true);
  doc.addEventListener('mouseout', function (e) {
    if (!actual) { return; }
    var hacia = e.relatedTarget;
    if (!hacia || !actual.ancla.contains(hacia)) { ocultar(); }
  }, true);
  doc.addEventListener('focusin', function (e) {
    var o = origen(e.target);
    if (o) { mostrar(o); }
  }, true);
  doc.addEventListener('focusout', ocultar, true);
  // Al desplazar o cambiar el tamano se reubica (o se oculta si el
  // elemento ya no esta en pantalla o desaparecio).
  function reubicar() {
    if (!actual) { return; }
    if (!doc.body.contains(actual.ancla)) { ocultar(); return; }
    var r = actual.refe.getBoundingClientRect();
    var vh = doc.documentElement.clientHeight || win.innerHeight;
    if (r.bottom < 0 || r.top > vh) { ocultar(); return; }
    ubicar(actual);
  }
  win.addEventListener('scroll', reubicar, true);
  win.addEventListener('resize', reubicar);
  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { ocultar(); } });
})(document);
"""


def _bloquear_traduccion():
    """
    Evita el error del navegador "NotFoundError: removeChild ... no es un
    hijo de este nodo". Lo causa el traductor automatico de Chrome/Edge (o
    extensiones que reescriben la pagina): cambian los textos por debajo de
    Streamlit y al actualizar la pantalla los nodos ya no coinciden. Se marca
    la pagina como "no traducir" desde un componente invisible.
    """
    try:
        import streamlit.components.v1 as componentes
        componentes.html(
            """
            <script>
            (function () {
              try {
                var doc = window.parent.document;
                doc.documentElement.setAttribute("translate", "no");
                doc.documentElement.setAttribute("lang", "es");
                doc.documentElement.classList.add("notranslate");
                if (doc.body) { doc.body.classList.add("notranslate"); }
                if (!doc.querySelector('meta[name="google"]')) {
                  var meta = doc.createElement("meta");
                  meta.name = "google";
                  meta.content = "notranslate";
                  doc.head.appendChild(meta);
                }
              } catch (e) {}
              // Globos flotantes: el codigo se inserta como <script> en la
              // pagina principal (corre alli, aunque este componente se
              // vuelva a crear en cada recarga) y se instala una sola vez.
              try {
                var d = window.parent.document;
                if (!d.getElementById("gm-flot-script")) {
                  var s = d.createElement("script");
                  s.id = "gm-flot-script";
                  s.textContent = JS_GLOBOS_AQUI;
                  d.head.appendChild(s);
                }
              } catch (e) {}
            })();
            </script>
            """.replace("JS_GLOBOS_AQUI", json.dumps(JS_GLOBOS)),
            height=0,
        )
    except Exception:
        pass
