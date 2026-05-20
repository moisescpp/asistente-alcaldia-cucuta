# Guia de consultas ciudadanas - Iteracion final

Esta guia resume formas reales en que un ciudadano podria preguntar por cada tramite. Sirve como apoyo para pruebas manuales, validacion con usuarios y documentacion del sistema.

| Tramite | Como podria preguntar un ciudadano | Errores o expresiones comunes consideradas |
|---|---|---|
| Impuesto predial unificado | "Quiero saber lo de la casa", "necesito pagar el predial", "donde veo el impuesto de mi predio" | "impuetso predial", "lo de la casa", "recibo predial", "ficha catastral" |
| Generacion de Paz y Salvo | "Necesito sacar paz y salvo", "quiero saber si estoy al dia", "necesito un certificado de impuestos" | "paz y salbo", "paz salvo", "certificado de deuda" |
| Registro de contribuyentes del impuesto de industria y comercio | "Voy a abrir un negocio", "como registro mi negocio", "necesito inscribir industria y comercio" | "registro ica", "matricula de negocio", "registrar comercio" |
| Modificacion en el Registro de Contribuyentes - Industria y Comercio | "Quiero cambiar los datos del negocio", "cambie de direccion", "necesito actualizar industria y comercio" | "modificar registro", "actualizar datos", "cambio de actividad" |
| Cancelacion del registro de contribuyentes | "Quiero cerrar mi negocio", "ya no tengo negocio", "necesito cancelar industria y comercio" | "cese de actividades", "retirar industria y comercio", "cerrar registro" |
| Devolucion y/o compensacion de pagos en exceso y pagos de lo no debido | "Me cobraron de mas", "pague por error", "quiero que me devuelvan la plata" | "devolver plata", "pague de mas", "saldo a favor", "reembolso" |
| Impuesto sobre el servicio de alumbrado publico | "Necesito saber lo de la luz", "impuesto de alumbrado", "servicio de la luz publica" | "lo de la luz", "recibo de luz", "iluminacion publica" |
| Impuesto sobre Espectaculos Publicos | "Voy a hacer un concierto", "tengo un evento con boletas", "quiero hacer una fiesta con entrada" | "evento publico", "boletas", "boleteria", "orquesta", "show" |
| Actualizacion de Informacion SISBEN | "Necesito actualizar el SISBEN", "cambie de direccion", "quiero cambiar datos del SISBEN" | "sisben", "cambio de domicilio", "encuesta sisben" |
| Duplicado de la licencia de transito de un vehiculo automotor | "Se me perdio la tarjeta del carro", "necesito duplicado de licencia de transito", "perdi los papeles del carro" | "tarjeta de propiedad", "licencia de transito", "papeles del carro" |

## Recomendacion para pruebas manuales

Para validar el sistema con ciudadanos, se recomienda tomar 2 o 3 preguntas por tramite:

- una pregunta formal;
- una pregunta escrita como la haria una persona en lenguaje cotidiano;
- una pregunta con error ortografico o expresion incompleta.

El resultado esperado es que el asistente encuentre el tramite correcto cuando la intencion sea clara, y que solicite precision cuando la pregunta pueda referirse a varios tramites.
