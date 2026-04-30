# Evidencia de cobertura del catalogo

**Corte:** 30 de abril de 2026

Este reporte deja constancia del estado real del catalogo que alimenta al asistente y del nivel de cobertura operativa que ya existe dentro del sistema.

## Resumen general

- Total de tramites reales evaluados: `16`
- Tramites activos en el catalogo ciudadano: `9`
- Tramites desactivados en el panel admin: `7`

## Calidad semantica del catalogo activo

- Fuertes: `9`
- Estables: `0`
- En riesgo: `0`
- Criticos: `0`

## Foco institucional del catalogo activo

- En foco tributario: `8`
- Fuera de foco: `1`
- Sin contexto suficiente: `0`

## Cobertura operativa ya disponible

- El asistente consulta tramites activos desde la base institucional.
- El panel admin permite crear, editar, desactivar y reactivar tramites.
- Los tramites desactivados se conservan en una vista administrativa separada.
- Cada tramite expone evaluacion semantica para detectar fichas debiles antes de que afecten la experiencia ciudadana.

## Muestra de tramites activos cubiertos

- ID `1302`: Actualización de Información SISBÉN
- ID `4`: Devolucion y/o compensacion de pagos en exceso y pagos de lo no debido
- ID `1158`: Duplicado de la licencia de tránsito de un vehículo automotor
- ID `988`: Generación de Paz y Salvo
- ID `1`: Impuesto predial unificado
- ID `886`: Impuesto sobre Espectáculos Públicos
- ID `248`: Impuesto sobre el servicio de alumbrado público
- ID `847`: Modificación en el Registro de Contribuyentes – Industria y Comercio
- ID `2`: Registro de contribuyentes del impuesto de industria y comercio

## Muestra de tramites desactivados

- ID `3`: Facilidades de pago para los deudores de obligaciones tributarias
- ID `90`: Impuesto vehicular
- ID `199`: Licencia de conducir
- ID `5`: Sisben
- ID `1627`: Tester 28 abril - Ajuste frase tramite para
- ID `1626`: Tester 28 abril - Correccion de datos del impuesto predial
- ID `1748`: Tramite para hacer hamburguesas

## Lectura tecnica

La cobertura actual ya es suficiente para demostrar que el sistema no depende de un catalogo vacio o de ejemplos aislados. El asistente esta respondiendo sobre un conjunto real de tramites activos, y el panel administrativo ya conserva tanto los tramites vigentes como los desactivados para su mantenimiento posterior.

Tambien queda visible que el catalogo contiene algunos registros de prueba o fuera de foco. Eso no invalida la cobertura; mas bien deja evidencia de que el sistema ya cuenta con mecanismos de control para detectarlos, desactivarlos y separarlos del flujo ciudadano principal.
