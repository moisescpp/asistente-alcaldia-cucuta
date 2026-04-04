from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db_session
from app.models import Tramite
from app.schemas.consulta import ConsultaRequest, ConsultaResponse
from app.schemas.tramite import TramiteCreate, TramiteRead, TramiteUpdate
from app.services import process_consulta


router = APIRouter()
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("/", tags=["meta"])
def read_root() -> dict[str, str]:
    return {
        "message": "Backend base del asistente de tramites estrella",
        "environment": settings.app_env,
    }


@router.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/tramites", response_model=list[TramiteRead], tags=["tramites"])
def list_tramites(db: DbSession) -> list[TramiteRead]:
    try:
        query = select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.nombre)
        tramites = db.scalars(query).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    return [TramiteRead.model_validate(tramite) for tramite in tramites]


@router.get(
    "/tramites/{tramite_id}",
    response_model=TramiteRead,
    tags=["tramites"],
)
def get_tramite_detail(tramite_id: int, db: DbSession) -> TramiteRead:
    try:
        tramite = db.get(Tramite, tramite_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    if tramite is None or not tramite.activo:
        raise HTTPException(status_code=404, detail="Tramite no encontrado.")

    return TramiteRead.model_validate(tramite)


@router.post(
    "/admin/tramites",
    response_model=TramiteRead,
    status_code=201,
    tags=["admin-tramites"],
)
def create_tramite(payload: TramiteCreate, db: DbSession) -> TramiteRead:
    tramite = Tramite(**payload.model_dump())

    try:
        db.add(tramite)
        db.commit()
        db.refresh(tramite)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible crear el tramite.",
        ) from exc

    return TramiteRead.model_validate(tramite)


@router.put(
    "/admin/tramites/{tramite_id}",
    response_model=TramiteRead,
    tags=["admin-tramites"],
)
def update_tramite(
    tramite_id: int,
    payload: TramiteUpdate,
    db: DbSession,
) -> TramiteRead:
    try:
        tramite = db.get(Tramite, tramite_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    if tramite is None:
        raise HTTPException(status_code=404, detail="Tramite no encontrado.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tramite, field, value)

    try:
        db.add(tramite)
        db.commit()
        db.refresh(tramite)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible actualizar el tramite.",
        ) from exc

    return TramiteRead.model_validate(tramite)


@router.delete(
    "/admin/tramites/{tramite_id}",
    response_model=TramiteRead,
    tags=["admin-tramites"],
)
def delete_tramite(tramite_id: int, db: DbSession) -> TramiteRead:
    try:
        tramite = db.get(Tramite, tramite_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    if tramite is None:
        raise HTTPException(status_code=404, detail="Tramite no encontrado.")

    tramite.activo = False

    try:
        db.add(tramite)
        db.commit()
        db.refresh(tramite)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible desactivar el tramite.",
        ) from exc

    return TramiteRead.model_validate(tramite)


@router.post(
    "/consulta",
    response_model=ConsultaResponse,
    tags=["consulta"],
)
def consulta_tramites(payload: ConsultaRequest, db: DbSession) -> ConsultaResponse:
    try:
        query = select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.nombre)
        tramites = db.scalars(query).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    return process_consulta(payload.pregunta, tramites)
