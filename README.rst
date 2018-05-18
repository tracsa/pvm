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

* añadir endpoint /v1/pointer y usar consultas
* hacer obsoleto el validate_user
* cambiar api de LoginProvider y HierarchyProvider, no deben guardar usuarios
* auth backends no deben crear usuarios, solo devolver objetos calificados
* quitar refs de tres niveles en params de auth filter, guardar un estado optimizado

* date input solo debe recibir yyyy-mm-dd

* hacer validación intensiva de xml:
  - dependencias existen arriba en el xml
  - id de nodos son únicos
* guardar en un store privado por hash los xml al iniciar proceso, obsoleta el sistema de versiones (borrar toda referencia a la versión)
