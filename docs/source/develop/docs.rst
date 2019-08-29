Escribiendo documentación
=========================

La documentación está hecha en `Sphinx <http://www.sphinx-doc.org/en/master/usage/quickstart.html>`_, para extenderla basta añadir los contenidos en la carpeta ``docs/source`` y para construirla correr el comando ``make html`` dentro de la carpeta ``docs``.

Los contenidos son generados dentro de ``docs/build/html``, carpeta que puede ser servida para su visualización local con ``python -m http.server`` (estando obviamente dentro).

Otras opciones de construcción incluyen reemplazar ``html`` por ``pdf`` como argumento del comando ``make``.
