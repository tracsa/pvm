Cacahuate
=========

.. image:: https://travis-ci.org/tracsa/cacahuate.svg?branch=master
   :target: https://travis-ci.org/tracsa/cacahuate
   :alt: Build Status

**The process virtual machine**

This project defines storage for an abstract _process_ in a company, and
implements a virtual machine that keeps track of the execution of instances of
the process.

Develop
-------

You will need the **redis** and **mongo** databases, and **rabbitmq** for this to work.

.. code-block:: bash

   git clone https://github.com/tracsa/cacahuate.git && cd cacahuate
   virtualenv -p /usr/bin/python3 .env
   echo "export CACAHUATE_SETTINGS=$(pwd)/settings_develop.py" >> .env/bin/activate
   echo "export FLASK_APP=cacahuate.http.wsgi" >> .env/bin/activate
   echo "export FLASK_DEBUG=1" >> .env/bin/activate
   touch settings_develop.py
   source .env/bin/activate
   pip install -r requirements.txt
   pytest

Installation
------------

.. code-block:: bash

   pip install cacahuate

Cacahuated
----------

This is the daemon in charge of moving pointers in the process, run with:

.. code-block:: bash

   cacahuated

The Cacahuate REST API
----------------------

In this same repository you will find a flask application that exposes a REST
api for controling Cacahuate.

**How to run**

.. code-block:: bash

   FLASK_APP=cacahuate.http.wsgi flask run

You can use any wsgi-compliant server, like gunicorn, to run this:

.. code-block:: bash

   gunicorn cacahuate.http.wsgi:app

TODO
----

* Cada campo de un formulario puede estar en uno de tres estados:
    - unfilled, valid, invalid
* la ejecución de un nodo depende de su condición
* ciudadanos de primera clase:
    - <node>
    - <subprocess>
    - <end>
* quitar símbolo de gato de los condicionales en todas partes
* probar input tipo aprobación
    - aprobar camina hacia enfrente
    - no aprobar sube al primer elemento inválido
    - información inválida nunca pasa validación de formulario
* considerar ids en nodos, no deberían ser necesarios
