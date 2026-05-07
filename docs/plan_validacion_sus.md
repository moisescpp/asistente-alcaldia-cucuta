# Plan de validacion SUS

**Corte:** 30 de abril de 2026

**Actualizacion:** 6 de mayo de 2026

Este documento deja preparada la aplicacion de la escala SUS para cerrar el requisito no funcional de usabilidad con ciudadanos de la region.

## Objetivo

Evaluar la usabilidad percibida del asistente de tramites por parte de ciudadanos cucuteños, verificando si la interfaz conversacional y el flujo de consulta permiten comprender y usar el sistema con facilidad.

## Muestra sugerida

- Entre `5` y `10` ciudadanos
- Preferiblemente con perfiles variados:
  - estudiantes
  - comerciantes
  - trabajadores independientes
  - personas con experiencia digital basica

## Escenarios de prueba sugeridos

Cada participante debe intentar al menos tres tareas:

1. Consultar un tramite especifico  
   Ejemplo: `Quiero informacion sobre impuesto predial`

2. Resolver una consulta ambigua  
   Ejemplo: `impuestos`

3. Revisar una sugerencia del sistema  
   Ejemplo: elegir una ruta propuesta cuando no hay coincidencia directa

## Escala SUS

Cada afirmacion debe puntuarse de `1` a `5`, donde:

- `1`: totalmente en desacuerdo
- `2`: en desacuerdo
- `3`: neutral
- `4`: de acuerdo
- `5`: totalmente de acuerdo

### Preguntas SUS

1. Me gustaria usar este sistema con frecuencia.  
2. Encontre el sistema innecesariamente complejo.  
3. El sistema me parecio facil de usar.  
4. Creo que necesitaria ayuda tecnica para poder usar este sistema.  
5. Las funciones del sistema estaban bien integradas.  
6. Encontre demasiadas inconsistencias en el sistema.  
7. Creo que la mayoria de las personas aprenderian a usar este sistema rapidamente.  
8. El sistema me parecio engorroso de usar.  
9. Me senti seguro usando el sistema.  
10. Necesite aprender muchas cosas antes de poder usar el sistema.

## Formato de captura sugerido

La recoleccion de respuestas se realizara de forma externa al sistema, preferiblemente con un formulario de Google Forms. Eso ayuda a que la experiencia del ciudadano dentro de la aplicacion siga limpia, institucional y centrada en consultar tramites.

### Estructura recomendada del formulario

1. Datos basicos del participante
- nombre o iniciales
- perfil general: estudiante, comerciante, ciudadano, funcionario, otro
- fecha de prueba

2. Escenario de uso
- pregunta o consulta que intento realizar
- logro encontrar una respuesta util: si / no / parcialmente
- tipo de caso probado: coincidencia clara / consulta ambigua / sin coincidencia

3. Escala SUS
- usar las 10 preguntas SUS con respuestas de `1` a `5`

4. Preguntas complementarias de evaluacion
- que tan clara fue la respuesta del asistente
- que tan rapido sintio el sistema
- que tan ordenada y formal se vio la interfaz
- que fue lo mas util del sistema
- que fue lo que mas le confundio
- que mejoraria o que sugerencia dejaria

| Participante | Tarea 1 | Tarea 2 | Tarea 3 | SUS total | Observaciones |
|---|---:|---:|---:|---:|---|
| P1 |  |  |  |  |  |
| P2 |  |  |  |  |  |
| P3 |  |  |  |  |  |
| P4 |  |  |  |  |  |
| P5 |  |  |  |  |  |

## Criterio de aceptacion sugerido

- Meta minima: `SUS > 68`
- Meta deseable: `SUS >= 75`

## Evidencia a recopilar

- fecha de aplicacion
- numero de participantes
- perfil general de los ciudadanos
- respuestas SUS
- dificultades reportadas
- sugerencias de mejora

## Cierre esperado

Cuando se aplique esta validacion, el proyecto podra afirmar formalmente que no solo funciona tecnicamente, sino que tambien fue evaluado desde la experiencia real del ciudadano.
