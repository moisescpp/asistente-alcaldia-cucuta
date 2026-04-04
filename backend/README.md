# Backend

Base del backend para el asistente de tramites estrella de rentas e impuestos.

## Estructura

- `app/main.py`: punto de entrada de FastAPI.
- `app/api/routes.py`: rutas base de la API.
- `app/core/config.py`: configuracion de entorno.
- `tests/`: pruebas iniciales.
- `requirements.txt`: dependencias iniciales.

## Arranque esperado

1. Crear un entorno virtual local en `backend/.venv`.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Ejecutar el servidor con `uvicorn app.main:app --reload`.

## Objetivo de Iteracion 1

Dejar listo el entorno base del backend para que en la siguiente iteracion podamos:

- modelar tramites estrella,
- conectar PostgreSQL,
- y exponer los primeros endpoints del asistente.
