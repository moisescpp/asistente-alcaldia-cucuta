# Backend

Base del backend para el asistente de tramites estrella de rentas e impuestos.

## Estructura

- `app/main.py`: punto de entrada de FastAPI.
- `app/api/routes.py`: rutas base de la API.
- `app/core/config.py`: configuracion de entorno.
- `tests/`: pruebas iniciales.
- `requirements.txt`: dependencias iniciales.

## Arranque esperado

1. Usar el entorno virtual local **vigente** en `backend/.venv`.
2. Si necesitas recrearlo y `python` en PATH no apunta a un interprete usable, utiliza:

   ```powershell
   & 'C:\Users\perez\AppData\Local\Python\bin\python.exe' -m venv .venv
   ```

3. Instalar dependencias con `pip install -r requirements.txt`.
4. Ejecutar el servidor con `uvicorn app.main:app --reload`.

## Entorno validado

- entorno estandar actual: `backend/.venv`
- version validada hoy en esta maquina: `Python 3.14.3`
- validacion ejecutada:
  - `pytest -q` -> `53 passed, 1 skipped`
  - `scripts\backfill_embeddings.py`
  - `scripts\validate_rag_queries.py` -> bateria superada

## Objetivo de Iteracion 1

Dejar listo el entorno base del backend para que en la siguiente iteracion podamos:

- modelar tramites estrella,
- conectar PostgreSQL,
- y exponer los primeros endpoints del asistente.
