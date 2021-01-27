API Http
========

A continuación se describen los diferentes endpoints HTTP de cacahuate.

``[GET] /``

Existe con el único propósito de mostrar un mensaje al pedir la raíz de la API.

Autenticación
-------------

``[POST] /v1/auth/signin/<AuthProvider:backend>``

Inicia sesión.

``[GET] /v1/auth/whoami``

Provee información sobre el token dado.

``[GET] /v1/user/_identifier/<user_identifier>/info``

Provee información sobre el usuario indicado.

Procesos
--------

``[GET] /v1/process``

Lista procesos disponibles.

``[GET] /v1/process/<id>/statistics``

Muestra estadísticas del proceso dado.

``[GET] /v1/process/<name>``

Muestra información sobre el proceso dado.

``[GET] /v1/process/<name>.xml``

Muestra información sobre la versión específica del proceso.

``[GET] /v1/process/statistics``

Muestra estadísticas sobre todos los procesos.

Ejecuciones
-----------

``[GET] /v1/execution``

Lista todas las ejecuciones en curso.

``[POST] /v1/execution``

Inicia la ejecución de un proceso.

``[DELETE] /v1/execution/<id>``

Fuerza una ejecución a terminar.

``[GET] /v1/execution/<id>``

Obtén el estado de una ejecución en curso.

``[PATCH] /v1/execution/<id>``

Cambia el estado de una ejecución en curso.

``[PUT] /v1/execution/<id>/user``

Añade un usuario como candidato para resolver un puntero activo.

``[GET] /v1/execution/<id>/summary``

Resumen de una ejecución en curso.

Punteros
--------

``[GET] /v1/pointer``

Listado de punteros.

``[POST] /v1/pointer``

Resuelve un nodo y mueve la ejecución al siguiente.

``[GET] /v1/pointer/<id>``

Estado de un puntero.

Algunas otras cosas
-------------------

``[GET] /v1/inbox``

None.

``[GET] /v1/log``

None.

``[GET] /v1/log/<id>``

None.

``[GET] /v1/activity``

None.

``[GET] /v1/task``

None.

``[GET] /v1/task/<id>``

None.
