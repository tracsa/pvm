Sistema de templates
--------------------

Cacahuate tiene por defecto un template para resumen de proceso llamado ``summary.html`` ubicado en una carpeta interna de templates (``cacahuate/templates/summary.html``). Para modificarlo puedes establecer la configuración ``TEMPLATE_PATH`` hacia una carpeta donde quieras guardar tus templates:

.. code-block:: python

   # settings.py
   TEMPLATE_PATH = '/opt/myinstance/templates'

En dicha carpeta puedes guardar un archivo ``summary.html`` usando la sintaxis y poder de `Jinja <https://jinja.palletsprojects.com/en/2.11.x/>`_. Por conveniencia podrías querer tener un template de resumen para cada tipo de proceso, para esto basta con crear una carpeta con el nombre del proceso y si esta tiene un archivo ``summary.html`` será usado como template:

``/opt/myinstance/templates/my-process/summary.html``

Este mecanismo se puede refinar aun más dando la posibilidad de crear un template específico para una versión de cierto proceso:

``/opt/myinstance/templates/my-process/2020-09-30/summary.html``

Siendo este el último nivel de especificidad.

Reutilización de bloques
........................

Puede ser que tus diseños de template de más de un proceso compartarn un bloque, o incluso que quieras reciclar un layout. Por esta razón el sistema de resolución de templates realiza un proceso escalonado que concluye con la carpeta de templates de cacahuate. Si consultas la página de resumen de un template y suponiendo que tu variable ``TEMPLATE_PATH`` tiene el valor ``/opt/myinstance/templates`` las siguientes rutas estarán disponibles en el ``PATH`` de Jinja:

.. code-block:: text

   /opt/myinstance/templates/my-process/2020-09-30/
   /opt/myinstance/templates/my-process/
   /opt/myinstance/templates/
   /path/to/cacahuate/templates

Y serán accedidas exactamente en ese orden. De manera que puedes tener bloques o layouts accessibles para todos los templates en ``/opt/myinstance/templates`` y algunos overrides en la carpeta específica de un proceso o de una versión de un proceso.

Variables
.........

En los templates de resumen estarán disponibles las mismas variables que se detallan `aquí <../xml>`_. Además los valores de fecha (de momento solamente ``started_at``) son un objeto ``datetime.datetime`` de python al que puedes dar formato usando un `filtro personalizado <https://jinja.palletsprojects.com/en/2.11.x/api/#custom-filters>`_ de jinja o el filtro incluído ``datetimeformat``.

Filtros
.......

Además de los `filtros básicos de jinja <https://jinja.palletsprojects.com/en/2.11.x/templates/#list-of-builtin-filters>`_ cacahuate incluye el filtro ``datetimeformat`` que por defecto formatea una fecha en formato ISO. También acepta un argumento ``format`` para cambiar su comportamiento:

.. code-block:: jinja

   ISO: {{ _execution.started_at | datetimeformat }}
   es_MX: {{ _execution.started_at | datetimeformat(format='%d/%m/%Y %H:%M') }}

Puedes añadir tus propios filtros de jinja usando la configuración ``JINJA_FILTERS``:

.. code-block:: python

   # settings.py

   def ismybirthday(value):
       if value.month == 5 and value.day == 10:
           return 'Today is my birthday!'
       return 'Is not my birthday'

    JINJA_FILTERS = {
        'ismybirthday': ismybirthday,
    }

y los puedes usar en tus templates:

.. code-block:: jinja

   {{ _execution.started_at | ismybirthday }}
