Almacenamiento persistente (MongoDB)
====================================

A continuación se desrciben los documentos (tablas en mongodb) utilizados por cacahuate.

Clases utilitarias
------------------

Ayudan a definir objetos comunmente usados en el modelo de información del almacenamieto persistente.

SortedMap
^^^^^^^^^

.. code-block:: python

   obj1 = {'key': "llave1"}
   obj2 = {'key': "llave2"}

   SortedMap([obj1, obj2], key='key').to_json() == {
      "_type": ":sorted_map",
      "item_order": ["llave1", "llave2"],
      "items": {
         "llave1": obj1,
         "llave2": obj2,
      }
   }

Map
^^^

.. code-block:: python

   obj1 = {'key': "llave1"}
   obj2 = {'key': "llave2"}

   Map([obj1, obj2], key='key').to_json() == {
      "_type": ":map",
      "items": {
         "llave1": obj1,
         "llave2": obj2,
      }
   }

Ejecuciones (Colección)
-----------------------

Cada registro en esta colección corresponde a una ejecución iniciada en el sistema y tiene la siguiente estructura:

.. code-block:: python

   {
      "_id": "5bb2cb576e6c8e52e72b60cb",
      "_type": "execution",
      "id": "6bc19964c5e311e88609f8597182d24b",
      "state": SortedMap(nodes, key='id'),  # Véase Nodos
   }

Nodos (Objeto)
^^^^^^^^^^^^^^

Representa un elemento del archivo xml

.. code-block:: python

   {
      "_type": "node",
      "actors": Map(actores, key='identifier'),  # Véase Actores
      "comment": "Comentario del nodo",
      "description": "Descripción del nodo",
      "id": "node_id",
      "milestone": false,
      "name": "Nombre humano del nodo",
      "state": "unfilled",
      "type": "validation",
   }

Actores (Objeto)
^^^^^^^^^^^^^^^^

Representa a un usuario o bot que intervino en el proceso

.. code-block:: python

   {
      "_type": "actor",
      "forms": forms,  # lista de formularios, véase Formularios
      "state": "valid",
      "user": {
         "_type": "user",
         "identifier": "__system__",
         "fullname": "System"
      }
   }

Formularios (Objeto)
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   {
      '_type': 'form',
      'state': 'valid',
      'ref': 'form_id',
      'inputs': SortedMap(inputs, key='name').to_json(),  # Véase Campos
   }

Campos (Objeto)
^^^^^^^^^^^^^^^

.. code-block:: python

   {
      '_type': 'field',
      'state': 'valid',
      'value': 'yes',
      'name': 'data',
   }

Punteros (Colección)
--------------------

.. code-block:: python

   {
      'id': pointer_id,
      'started_at': datetime,
      'finished_at': datetime or None,
      'execution': execution.to_json(),
      'node': {
         'id': node_id,
         'name': node_human_name,
         'description': description,
         'type': type(self).__name__.lower(),
      },
      'actors': Map([actors], key='identifier').to_json(),
      'process_id': execution.process_name,
      'notified_users': notified_users or [],
   }
