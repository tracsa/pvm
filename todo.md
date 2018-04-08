# Colores

* api de status de una parte del proceso que muestra status, label, nombre humano del valor del status

## primera iteración

* test de que responder un formulario con un campo que es status guarda status en mongo
* test de que responder un formulario con un campo que viaja al pasado establece status del pasado
    - probar también con más de un elemento en la historia
* test de que iniciar un proceso con status guarda valores iniciales
    - a menos que el formulario tenga el campo status

* no hay colores, se guarda todo el estado
* regresar restaura el estado
* regresar dispara búsqueda de padres de punteros para saber quienes sobreviven y quienes no
* botar los refs, mandar siempre si el formulario admite múltiples respuestas y validar al recibir información
* buscar todos los lugares donde se usan refs para pensar cómo sustituirlos
* las decisiones solo pueden depender de los formularios, esto permite simplificar la gramática de las condiciones

# Multiauth

* cada respuesta de usuario elimina la relación entre el usuario y el puntero
* validar que un usuario sin relación con el puntero no pueda responder
* handler no elimina ni avanza puntero hasta que esté satisfecho el número de respondientes
* último en responder elimina puntero y encola petición
* notificar usuarios no crea punteros a menos que haya un formulario
* terminar un nodo elimina todas las relaciones entre puntero y usuario (que podrían ser muchas)

# Otros

* handler debe poder cargar hierarchy externos
* mecanismo de suspensión de procesos en caso de falla crítica para no matar otros procesos
