"""GMYA Tools · paquete de la plataforma de automatizacion contable de
Giraldo Mosquera y Asociados SAS.

Estructura (las capas solo importan de capas anteriores, nunca al reves):
  config        constantes de marca, version y recursos (iconos, logos)
  comun/        utilidades puras sin interfaz (texto, numeros, fechas,
                lectura de grillas Excel/XLS/PDF, cache, config del equipo)
  ui/           piezas visuales reutilizables (estilos, componentes, globos
                de ayuda, visor de documentos)
  registro/     usuario del equipo y registro de uso (sin datos de clientes)
  modulos/<m>/  un paquete por modulo del menu: logica (sin Streamlit) e
                interfaz (pantalla Streamlit)
El punto de entrada es app.py (raiz del proyecto)."""
