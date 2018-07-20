Instalación
===========

Requisitos
----------

Sistema:

* systemd
* python 3.6 o mayor
* un servidor wsgi como `gunicorn <http://gunicorn.org/>`_

Software:

* `Base de datos redis <https://redis.io/>`_
* `Servidor de mensajería rabbitmq <https://www.rabbitmq.com/>`_
* `Base de datos mongodb <https://www.mongodb.com/>`_

Instalación del módulo
----------------------

Cacahuate puede ser instalado facilmente usando ``pip``::

   $ pip install cacahuate

Cofiguración de systemd
-----------------------

Como Cacahuate está conformado por dos componentes necesitarás sendas unidades de ``systemd``, una para el demonio que mueve los punteros y otra para la api HTTP. A continuación un ejemplo del archivo `cacahuated.service`::

   [Unit]
   Description=Cacahuate daemon
   After=network.target rabbitmq-server.service

   [Service]
   WorkingDirectory=/home/me/cacahuate
   ExecStart=/home/me/cacahuate/.venv/bin/cacahuated
   Environment=CACAHUATE_SETTINGS=/home/me/cacahuate/settings_production.py
   Restart=always

   [Install]
   WantedBy=default.target

Y un ejemplo del archivo `cacahuate-http.service`::

   [Unit]
   Description=the gunicorn process for cacahuate
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/home/me/cacahuate
   ExecStart=/home/me/cacahuate/.venv/bin/gunicorn cacahuate.http.wsgi:app
   ExecReload=/bin/kill -s HUP $MAINPID
   ExecStop=/bin/kill -s TERM $MAINPID
   Restart=always

   [Install]
   WantedBy=multi-user.target
