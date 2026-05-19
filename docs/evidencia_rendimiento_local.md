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

---

# Evidencia de optimizacion - Iteracion 6

**Corte:** 19 de mayo de 2026

Durante la Iteracion 6 se aplicaron dos ajustes de rendimiento:

- Se dejo la introduccion RAG generada por OpenAI como opcional mediante `ENABLE_RAG_INTRO=false`, porque la interfaz ciudadana ya muestra la ficha estructurada del tramite.
- Se agrego una ruta rapida textual para evitar llamadas a embeddings cuando la consulta ya tiene una coincidencia textual confiable o cuando una consulta general puede resolverse con candidatos textuales suficientes.

## Configuracion de la prueba

- Script utilizado: `backend/scripts/report_performance_baseline.py`
- Casos evaluados: `6`
- Corridas por caso: `3`
- Meta local de promedio: `<= 1.50 s`
- Meta local de maximo: `<= 2.50 s`

## Resultados por caso

### Quiero informacion sobre impuesto predial
- Promedio: `0.0489 s`
- Minimo: `0.0466 s`
- Maximo: `0.0511 s`

### cambios en industria y comercio
- Promedio: `0.0765 s`
- Minimo: `0.0520 s`
- Maximo: `0.0906 s`

### Papeles para hacer un concierto en Cucuta
- Promedio: `0.0926 s`
- Minimo: `0.0846 s`
- Maximo: `0.1034 s`

### impuestos
- Promedio: `0.0419 s`
- Minimo: `0.0369 s`
- Maximo: `0.0489 s`

### paz y salbo
- Promedio: `0.0446 s`
- Minimo: `0.0411 s`
- Maximo: `0.0507 s`

### informacion de impuetos
- Promedio: `0.0684 s`
- Minimo: `0.0571 s`
- Maximo: `0.0747 s`

## Resumen general

- Tiempo promedio global: `0.0622 s`
- Mediana global: `0.0515 s`
- Percentil 95 aproximado: `0.0906 s`
- Maximo global: `0.1034 s`
- Promedio dentro de objetivo local: `si`
- Maximo dentro de objetivo local: `si`

## Validacion tecnica ejecutada

- `pytest tests/test_tramites_api.py tests/test_consulta_api.py -q`: `72 passed`
- `npm run lint`: exitoso
- `npm run build`: exitoso

## Interpretacion

La optimizacion redujo el tiempo promedio local de `5.2072 s` en la linea base inicial a `0.0622 s` en la medicion de Iteracion 6. Esto fortalece el requisito no funcional de rendimiento y deja evidencia concreta para la validacion del sistema.
