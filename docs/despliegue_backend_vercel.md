# Despliegue del backend en Vercel

## Objetivo

Publicar el backend FastAPI en Vercel para conectarlo con el frontend ya desplegado.

## Punto de entrada

Vercel reconoce aplicaciones FastAPI cuando encuentra una instancia `app` en rutas como `app/index.py`.

En este proyecto:

- [backend/app/main.py](../backend/app/main.py) conserva la aplicacion FastAPI real.
- [backend/app/index.py](../backend/app/index.py) es solo un adaptador para Vercel.

El adaptador contiene:

```python
from app.main import app
```

Asi evitamos duplicar logica y mantenemos un solo backend real.

## Configuracion de Vercel

El archivo [vercel.json](../vercel.json) enruta las peticiones al backend:

```json
{
  "builds": [
    {
      "src": "backend/app/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "backend/app/index.py"
    }
  ]
}
```

## Variables de entorno

Configura estas variables en el proyecto backend de Vercel:

```env
APP_ENV=production
APP_NAME=Asistente Institucional de Tramites
APP_VERSION=0.1.0
API_PREFIX=/api
FRONTEND_URL=https://TU-FRONTEND.vercel.app
FRONTEND_URLS=https://TU-FRONTEND.vercel.app
OPENAI_API_KEY=TU_API_KEY
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
RESPONSE_MODEL=gpt-5-nano
RESPONSE_MAX_OUTPUT_TOKENS=450
RESPONSE_REASONING_EFFORT=minimal
RESPONSE_TEXT_VERBOSITY=low
ADMIN_ACCESS_PIN=TU_PIN_ADMIN
ADMIN_SESSION_SECRET=TU_SECRETO_JWT_LARGO
ADMIN_SESSION_TTL_MINUTES=5
DATABASE_URL=TU_DATABASE_URL
EMBEDDING_DIMENSIONS=1536
```

En produccion no uses los valores por defecto de desarrollo. Si `APP_ENV=production` y el backend detecta el PIN `246810`, el secreto `cucuta-admin-session-secret` o un secreto demasiado corto, el acceso administrativo queda bloqueado hasta configurar credenciales seguras.

## Base de datos

Vercel no reemplaza la base de datos. El backend necesita una PostgreSQL externa y accesible por internet.

Recomendacion:

- usar una base PostgreSQL que soporte `pgvector`;
- copiar su URL en `DATABASE_URL`;
- si la URL viene como `postgres://...` o `postgresql://...`, el backend ya la normaliza para SQLAlchemy con `psycopg`.

## Despues del deploy

1. Probar:

```text
https://TU-BACKEND.vercel.app/api/health
```

2. Actualizar el frontend en Vercel:

```env
VITE_API_URL=https://TU-BACKEND.vercel.app/api
```

3. Redeployar el frontend.

4. Probar desde la interfaz:

- `Quiero informacion sobre impuesto predial`
- `impuestos`
- `necesito saber sobre lo de la luz`

## Advertencia tecnica

Vercel ejecuta el backend como funcion serverless. Para pruebas con usuarios y validacion universitaria puede funcionar bien, pero si luego necesitas ejecuciones largas, procesos persistentes o mayor control de base de datos, conviene volver a una plataforma de backend tradicional.

## Referencia oficial

- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
