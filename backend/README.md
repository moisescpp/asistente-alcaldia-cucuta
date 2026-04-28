# Backend

Backend del asistente de tramites estrella de rentas e impuestos, actualmente enfocado en el cierre de la **Iteracion 4**.

## Estructura

- `app/main.py`: punto de entrada de FastAPI.
- `app/api/routes.py`: rutas base de la API.
- `app/core/config.py`: configuracion de entorno.
- `tests/`: pruebas automatizadas del flujo administrativo, calidad semantica y consulta.
- `requirements.txt`: dependencias del backend.

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
  - `pytest -q` -> `61 passed, 1 skipped`
  - `scripts\backfill_embeddings.py`
  - `scripts\validate_rag_queries.py` -> bateria superada
  - `scripts\audit_tramite_quality.py` -> catalogo auditado

## Capacidades activas al cierre de Iteracion 4

- sesion administrativa privada con PIN y expiracion visible;
- restauracion del borrador admin tras expiracion o recarga;
- validacion semantica de tramites antes de crear o editar;
- recuperacion semantica y textual para la consulta ciudadana;
- registro de actividad del asistente con origen, estado y resultados;
- estadisticas de preguntas para ayudar a mejorar el catalogo.

## Nota de catalogo actual

La auditoria actual del catalogo deja un hallazgo fuera de foco:

- `ID 1158 - Duplicado de la licencia de tránsito de un vehículo automotor`

No falla semanticamente, pero no muestra contexto claro de rentas e impuestos. Hoy se conserva solo como tramite de prueba y no como un bloqueo funcional del cierre.
