# Asistente Alcaldia Cucuta

Asistente inteligente orientado a tramites estrella del sector de rentas e impuestos de la Alcaldia de San Jose de Cucuta. El proyecto se desarrolla con XP y actualmente se encuentra en la **Iteracion 4**, enfocada en mejorar claridad, precision de respuesta, observabilidad administrativa y experiencia de uso sobre la base RAG ya funcional.

## Estado actual

La base tecnica principal ya esta lista. Actualmente el sistema incluye:

- backend en FastAPI con CRUD administrativo de tramites;
- frontend en React para consulta ciudadana y gestion administrativa;
- base de datos PostgreSQL con soporte vectorial mediante `pgvector`;
- embeddings reales almacenados en `embedding_vector`;
- recuperacion semantica con distancia de coseno;
- integracion RAG para orientar al ciudadano con contexto institucional;
- validacion automatica del backend y bateria funcional de consultas reales.

## Modulos

- `frontend/`: aplicacion React para ciudadania y panel interno.
- `backend/`: API en FastAPI, logica semantica, RAG y acceso a PostgreSQL.

## Alcance vigente de la Iteracion 4

La Iteracion 4 no busca rehacer la arquitectura base, sino **pulir la experiencia sobre el flujo existente**. El foco actual se concentra en:

- hacer mas clara la respuesta ciudadana;
- mejorar el manejo de consultas ambiguas;
- registrar y observar mejor la actividad del asistente;
- facilitar el seguimiento administrativo de preguntas reales;
- mantener consistencia entre panel administrativo, base de datos y respuesta final.

## Avances ya consolidados en Iteracion 4

### Vista ciudadana

- respuestas mas claras y mejor redactadas;
- tolerancia a errores tipograficos frecuentes;
- sugerencias guiadas para reformular consultas;
- desambiguacion con opciones cercanas cuando la pregunta es demasiado general;
- preguntas rapidas para arrancar la experiencia con menos friccion;
- mejoras de accesibilidad como `main`, salto al contenido y foco visible.

### Panel interno

- registro persistente de consultas realizadas;
- panel de actividad del asistente;
- agrupacion por fecha y filtros por estado;
- deteccion de patrones problematicos;
- buscador y filtro por dependencia en el inventario de tramites;
- acceso menos expuesto al admin desde la interfaz principal.

## Mejoras laterales ya hechas pero no nucleares para Iteracion 4

Estas mejoras existen en el proyecto, pero **no se consideran el centro de la iteracion**:

- mediciones locales con Lighthouse o Unlighthouse;
- modo claro y modo oscuro;
- ajustes cosmeticos de encabezado o branding.

## Funcionalidades disponibles

### Consulta ciudadana

- consulta de tramites por lenguaje natural;
- recuperacion semantica de tramites de rentas e impuestos;
- respuesta estructurada con tramite principal, datos registrados y sugerencias;
- manejo de consultas ambiguas y consultas fuera de alcance;
- uso de sugerencias y opciones cercanas para precisar una pregunta.

### Panel interno

- crear tramites;
- editar tramites;
- desactivar tramites;
- revisar consultas recientes del asistente;
- analizar preguntas ambiguas, positivas y sin coincidencia;
- reflejar automaticamente los cambios en la consulta del asistente.

## Endpoints principales

- `GET /api/health`
- `GET /api/tramites`
- `GET /api/tramites/{id}`
- `POST /api/admin/tramites`
- `PUT /api/admin/tramites/{id}`
- `DELETE /api/admin/tramites/{id}`
- `GET /api/admin/consultas`
- `POST /api/consulta`

## Ejecucion local

### Backend

```powershell
cd C:\asistente-alcaldia-cucuta\backend
.venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

### Frontend

```powershell
cd C:\asistente-alcaldia-cucuta\frontend
npm run dev
```

## Validacion

### Pruebas automatizadas

```powershell
cd C:\asistente-alcaldia-cucuta\backend
.venv\Scripts\activate
pytest -q
```

### Bateria funcional RAG

```powershell
cd C:\asistente-alcaldia-cucuta\backend
.venv\Scripts\activate
python scripts\validate_rag_queries.py
```

## Objetivo tecnico inmediato

Cerrar la Iteracion 4 con una validacion funcional clara del flujo completo, asegurando:

- precision en la recuperacion del tramite principal;
- control de consultas ambiguas con guias utiles;
- observabilidad real de las preguntas ciudadanas;
- consistencia entre panel interno, base de datos y respuesta final;
- y una experiencia ciudadana mas clara sin perder honestidad sobre datos faltantes.
