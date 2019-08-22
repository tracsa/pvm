Extendiendo el lenguaje XML de cacahuate
========================================

Todas las cosas de las que cacahuate es capaz tienen una representación en el
formato XML que se utiliza para definir procesos. Para definir nuevas acciones
que no estén comprendidas en el esquema actual es necesario crear nuevos nodos,
subnodos o propiedades en los ya existentes.

Validación de procesos en XML
-----------------------------

Los archivos XML de procesos son validados usando
`Relax NG <https://relaxng.org/>`_, así que es necesario modificar el esquema
contenido en el archivo ``cacahuate/xml/process-spec.rng`` si se pretenden usar
nuevas características como nodos o atributos no definidos previamente.

Para validar un archivo XML de proceso puedes el programa ``xmlllint`` incluído
generalmente en el paquete ``libxml2`` como sigue:

.. code-block:: bash

   xmllint --noout --relaxng cacahuate/xml/process-spec.rng tu_proceso.xml

Si no estás segur@ de dónde se encuentra el archivo ``.rng`` puedes usar el
programa ``rng_path`` incluído con cacahuate para encontrarlo:

.. code-block:: bash

   $ rng_path
   /home/juan/src/cacahuate/cacahuate/xml/process-spec.rng

Una alternativa a ``xmllint`` es `Jing <https://github.com/relaxng/jing-trang>`_,
un software hecho en java que ofrece mejores mensajes de error en general.

Adicional a eso y dado que existen limitaciones en el lenguaje **RNG** se usa
un sistema de validación interno que verifica algunas condiciones anómalas
comunes. Para correr estas validaciones contra un xml usa el comando
`xml_validate` como sigue:

.. code-block:: bash

   xml_validate tu_proceso,xml
