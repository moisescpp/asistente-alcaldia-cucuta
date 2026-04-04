import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import Tramite
from app.services import update_tramite_embedding


def main() -> None:
    with SessionLocal() as db:
        tramites = db.scalars(
            select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.id)
        ).all()

        if not tramites:
            print("No hay tramites activos para procesar.")
            return

        updated = 0
        for tramite in tramites:
            update_tramite_embedding(db, tramite)
            updated += 1
            print(f"Embedding actualizado para tramite {tramite.id}: {tramite.nombre}")

        print(f"Proceso completado. Embeddings actualizados: {updated}")


if __name__ == "__main__":
    main()
