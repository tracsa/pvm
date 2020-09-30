Escribiendo XMLs
================

Detalles sobre la estructura y el significado de los archivos XML

Nodo request
------------

.. code-block:: xml

   <request id="request_node" method="GET">
      <url>http://localhost/</url>
      <headers>
         <header name="content-type">application/json</header>
      </headers>
      <body></body>
      <captures type="json">
         <capture id="capture1">
            <value path="name" name="name" label="Nombre" type="text"></value>
         </capture>

         <capture id="capture2" multiple="multiple" path="params.items.*">
            <value path="age" name="latitude" label="Latitud" type="float" />
         </capture>
      </captures>
   </request>

Captures
^^^^^^^^

La etiqueta captures dentro de un nodo ``<request>`` permite capturar información del cuerpo de la respuesta cuando este está en formato JSON.

Debe tener como descencientes etiquetas ``<capture>``, cada una de las cuales generará uno o más formularios análogos a los de un nodo ``<action>`` de interacción con el usuario. El ``id`` de cada ``capture`` es el id del formulario a generar.

Los descendientes de la etiqueta ``<capture>`` son etiquetas ``<value>`` que se comportan como inputs en un nodo ``<action>``. El atributo ``path`` de una etiqueta ``<value>`` establece la ruta `jsonpath <https://jsonpath.com/>`_ para llegar al valor a capturar, que deberá ser un valor escalar (cadena, entero, flotante, booleano).

Atributo path de <capture>
""""""""""""""""""""""""""

Hay dos posibles significados del atributo ``path`` de un ``<capture>``. El primero es que los ``path`` de todos sus ``<value>`` serán relativos al elemento señalado por ``path`` del ``<capture>``. En el siguiente ejemplo se usa esto para evitar escribir las rutas absolutas en cada ``<value>``.

.. code-block:: json

   {
     "type": "FeatureCollection",
     "features": [
       {
         "type": "Feature",
         "properties": {
           "name": "Foo",
           "address": "Rébsamen 40"
         },
         "geometry": {
           "type": "Point",
           "coordinates": [
             -89.60174560546875,
             20.97426314957793
           ]
         }
       }
     ]
   }

.. code-block:: xml

   <captures type="json">
      <capture id="info" path="features.0.properties">
         <value path="name" name="name" label="Nombre" type="text"></value>
         <value path="address" name="address" label="Dirección" type="text"></value>
      </capture>
   </captures>

El segundo es explica a continuación.

Capturas múltiples
""""""""""""""""""

Es posible capturar un formulario múltiples veces estableciendo el atributo ``multiple="multiple"`` y usando el atributo ``path`` de la etiqueta ``<capture>``. Esta ruta en formato `jsonpath <https://jsonpath.com/>`_ debe ser capaz de encontrar una lista de elementos. En este caso el atributo ``path`` de los ``<value>`` descendientes tendrá como raíz cada elemento de la lista.

Por ejemplo para el siguiente JSON:

.. code-block:: json

   {
      "id": 231,
      "attrs": {
         "name": "Xochitl"
      },
      "jobs": [
         {
            "role": "Manager"
         },
         {
            "role": "Developer"
         }
      ]
   }

se pueden capturar los roles de María en un formulario múltiple como sigue:

.. code-block:: xml

   <captures type="json">
      <capture id="basicinfo">
         <value path="attrs.name" name="name" label="Nombre" type="text"></value>
      </capture>

      <capture id="role" multiple="multiple" path="jobs">
         <value path="role" name="role" label="Rol" type="text" />
      </capture>
   </captures>

Interpolación de variables
--------------------------

Existen varios puntos en la definición de un XML donde se puede usar interpolación de variables escribiendo los valores como si fueran templates de `jinja <https://palletsprojects.com/p/jinja/>`_.

Específicamente los lugares son los siguientes:

* la URL y el cuerpo de un nodo `request`.
* el nombre y la descripción de cualquier nodo
* el nombre y la descripción de un proceso

Los valores que se pueden usar en estos lugares son todos aquellos que hayan aparecido antes en el proceso, por ejemplo inputs de formularios de nodos previos. Para esta interpolación se utiliza un diccionario como este:

.. code-block:: json

   {
      "formulario1": {
         "input1": "valor1",
         "input2": "valor2"
      },
      "formulario2": {
         "input3": "valor3"
      }
   }

De manera que para usar uno de estos valores en la interpolación lo puedes encontrar como notación de objeto:

.. code-block:: xml

   <name>Name {{ formulario1.input1 }}</name>

Formularios múltiples durante la interpolación
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Debido a que cacahuate soporta formularios múltiples estos también pueden ser usados durante la interpolación. Por defecto si ``formulario1`` tiene múltiples respuestas al hacer:

.. code-block:: xml

   <name>Name {{ formulario1.input1 }}</name>

se utilizará la última respuesta del formulario, sin embargo es posible iterar todas las respuestas usando la función ``.all()`` del objeto :py:class:`cacahuate.jsontypes.MultiFormDict` como sigue:

.. code-block:: jinja

   {% for ans in formulario1.all() %}
      {{ ans.input1 }}
   {% endfor %}

También es posible iterar los distintos valores de una llave en específico usando ``.getlist(key)`` como se detalla a continuación:

.. code-block:: jinja

   {% for ans in formulario1.getlist('input1') %}
      {{ ans }}
   {% endfor %}

Este último ejemplo y el que le precede producen el mismo resultado. Para mayor información consultar la documentación de la clase.


Valores siempre presentes
^^^^^^^^^^^^^^^^^^^^^^^^^

Por conveniencia se añade además información sobre la ejecución actual a este contexto y variables de entorno que se pueden configurar al iniciar los servicios de cacahuate. Los datos agregados tienen la estructura siguiente:

.. code-block:: json

   {
      "_execution": {
         "id": "nf384d34",
         "name": "Nombre del proceso",
         "process_name": "archivo.2019-10-30.xml",
         "description": "Descripción del proceso",
         "started_at": "2019-10-30T21:57:51.927624+00:00"
      },
      "_env": {
         "FOO": "var"
      }
   }

Y los puedes usar como:

.. code-block:: jinja

   {{ _execution.name }} {{ _env.FOO }}

Por defecto la llave ``_env`` está vacía, pero puedes establecer valores para la misma en tu archivo de configuraciones, usando la variable ``PROCESS_ENV``:

.. code-block:: python

   # settings.py

   PROCESS_ENV = {
      'FOO': 'var',
   }
