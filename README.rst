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

You will need the **redis** and **mongo** databases, and **rabbitmq** for this
to work. I recommend using `pipenv` or `virtualenv` in your python projetcs ;)

* clone the repo
* install the requirements listed in `requirements.txt`
* run the tests (`pytest`)

you can control your cacahuate installation using this three environment
variables: `CACAHUATE_SETTINGS`, `FLASK_APP`, `FLASK_DEBUG`.

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

The docs
--------

Docs are built using `sphinx <http://www.sphinx-doc.org/en/master/>`_ and published in
https://tracsa.github.io/cacahuate/index.html. To build a local copy of the docs
navigate to the `docs/` directory and run:

.. code-block:: bash

   make html

For more options just run `make` by itself.

Release
-------

```bash
./release.sh cacahuate/version.txt [major|minor|patch]
```
