# Evidencia de rendimiento local

**Corte:** 30 de abril de 2026

Este reporte registra la linea base local de tiempos de respuesta del asistente usando consultas representativas sobre el catalogo vigente.

## Configuracion de la prueba

- Casos evaluados: `6`
- Corridas por caso: `3`
- Meta local de promedio: `<= 1.50 s`
- Meta local de maximo: `<= 2.50 s`

## Resultados por caso

### Quiero informacion sobre impuesto predial
- Promedio: `8.1901 s`
- Minimo: `5.9446 s`
- Maximo: `10.8425 s`

### cambios en industria y comercio
- Promedio: `5.8446 s`
- Minimo: `5.7295 s`
- Maximo: `5.9266 s`

### Papeles para hacer un concierto en Cucuta
- Promedio: `6.9862 s`
- Minimo: `5.3431 s`
- Maximo: `8.9735 s`

### impuestos
- Promedio: `1.3938 s`
- Minimo: `1.2773 s`
- Maximo: `1.4708 s`

### paz y salbo
- Promedio: `7.4284 s`
- Minimo: `6.1432 s`
- Maximo: `9.4167 s`

### informacion de impuetos
- Promedio: `1.3998 s`
- Minimo: `1.3538 s`
- Maximo: `1.4439 s`

## Resumen general

- Tiempo promedio global: `5.2072 s`
- Mediana global: `5.9022 s`
- Percentil 95 aproximado: `9.4167 s`
- Maximo global: `10.8425 s`

## Lectura tecnica

- Promedio dentro de objetivo local: `no`
- Maximo dentro de objetivo local: `no`

## Interpretacion

Esta evidencia muestra que la validacion funcional del sistema es buena, pero la meta de rendimiento local planteada para esta linea base no se cumple todavia en consultas que disparan recuperacion mas profunda y generacion de respuesta completa.

En otras palabras:

- el requisito funcional de responder correctamente esta bien encaminado;
- el requisito no funcional de rendimiento **todavia necesita ajuste o una redefinicion de umbral realista** segun el entorno de ejecucion;
- esta medicion sirve como soporte tecnico para justificar una iteracion posterior de optimizacion o una contextualizacion honesta del rendimiento en ambiente universitario.
