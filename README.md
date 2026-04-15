# Asistente Alcaldia Cucuta

Asistente inteligente orientado a tramites estrella del sector de rentas e impuestos de la Alcaldia de San Jose de Cucuta. El proyecto se desarrolla con XP y actualmente cuenta con una base funcional de consulta ciudadana, panel administrativo y un flujo RAG inicial para recuperar informacion institucional y responder con mayor precision.

## Estado actual

El proyecto ya supera la fase de base tecnica inicial y se encuentra en una etapa avanzada de la Iteracion 3. Actualmente incluye:

- backend en FastAPI con CRUD administrativo de tramites;
- frontend en React para consulta ciudadana y gestion administrativa;
- base de datos PostgreSQL con soporte vectorial mediante `pgvector`;
- embeddings reales almacenados en `embedding_vector`;
- recuperacion semantica con distancia de coseno;
- integracion RAG para generar orientaciones breves con contexto institucional;
- validacion automatica del backend y bateria funcional de consultas reales.

## Modulos

- `frontend/`: aplicacion React para ciudadanos y panel administrativo.
- `backend/`: API en FastAPI, logica de recuperacion semantica, RAG y acceso a PostgreSQL.

## Funcionalidades disponibles

### Vista ciudadana

- consulta de tramites por lenguaje natural;
- recuperacion semantica de tramites de rentas e impuestos;
- respuesta estructurada con tramite principal, datos registrados y sugerencias;
- manejo de consultas ambiguas y consultas fuera de alcance.

### Panel administrativo

- crear tramites;
- editar tramites;
- desactivar tramites;
- reflejar automaticamente los cambios en la consulta del asistente.

## Endpoints principales

- `GET /api/health`
- `GET /api/tramites`
- `GET /api/tramites/{id}`
- `POST /api/admin/tramites`
- `PUT /api/admin/tramites/{id}`
- `DELETE /api/admin/tramites/{id}`
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

Cerrar la Iteracion 3 con una validacion robusta del modulo RAG, asegurando:

- precision en la recuperacion del tramite principal;
- control de consultas ambiguas;
- manejo honesto de datos incompletos;
- y consistencia entre panel administrativo, base de datos y respuesta final del asistente.
