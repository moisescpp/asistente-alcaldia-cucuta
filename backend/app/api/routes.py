from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db_session
from app.models import Tramite
from app.schemas.consulta_log import ConsultaLogRead
from app.schemas.consulta import ConsultaRequest, ConsultaResponse
from app.schemas.tramite import TramiteCreate, TramiteRead, TramiteUpdate
from app.services import (
    assess_tramite_quality,
    list_recent_consulta_logs,
    log_consulta_result,
    process_consulta,
    update_tramite_embedding,
    validate_tramite_payload,
)


router = APIRouter()
DbSession = Annotated[Session, Depends(get_db_session)]


def _sync_tramite_embedding(db: Session, tramite: Tramite) -> None:
    try:
        update_tramite_embedding(db, tramite)
    except Exception:
        db.rollback()
        # Si el embedding no puede actualizarse en este momento, el tramite sigue
        # disponible y la consulta puede apoyarse en el respaldo textual.
        pass


def _reload_tramite_snapshot(db: Session, tramite_id: int) -> Tramite | None:
    try:
        return db.get(Tramite, tramite_id)
    except SQLAlchemyError:
        return None


def _find_tramite_by_name_or_slug(
    db: Session,
    *,
    nombre: str,
    slug: str,
    exclude_id: int | None = None,
) -> Tramite | None:
    query = select(Tramite).where(
        or_(Tramite.nombre == nombre, Tramite.slug == slug),
    )

    if exclude_id is not None:
        query = query.where(Tramite.id != exclude_id)

    return db.scalars(query).first()


def _serialize_tramite(tramite: Tramite) -> TramiteRead:
    quality = assess_tramite_quality(tramite)
    payload = TramiteRead.model_validate(tramite).model_dump()
    payload.update(
        {
            "semantic_quality_score": quality.score,
            "semantic_quality_level": quality.level,
            "semantic_quality_alerts": quality.alerts,
        }
    )
    return TramiteRead.model_validate(payload)


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

    return [_serialize_tramite(tramite) for tramite in tramites]


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

    return _serialize_tramite(tramite)


@router.post(
    "/admin/tramites",
    response_model=TramiteRead,
    status_code=201,
    tags=["admin-tramites"],
)
def create_tramite(payload: TramiteCreate, db: DbSession) -> TramiteRead:
    blocking_issues = validate_tramite_payload(payload.model_dump())
    if blocking_issues:
        raise HTTPException(status_code=422, detail=" ".join(blocking_issues))

    existing_tramite = _find_tramite_by_name_or_slug(
        db,
        nombre=payload.nombre,
        slug=payload.slug,
    )

    if existing_tramite is not None:
        tramite_id = existing_tramite.id
        if existing_tramite.activo:
            duplicated_field = (
                "nombre" if existing_tramite.nombre == payload.nombre else "slug"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe un tramite activo con ese {duplicated_field}.",
            )

        for field, value in payload.model_dump().items():
            setattr(existing_tramite, field, value)
        existing_tramite.activo = True

        try:
            db.add(existing_tramite)
            db.commit()
            db.refresh(existing_tramite)
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="No fue posible reactivar el tramite existente.",
            ) from exc

        _sync_tramite_embedding(db, existing_tramite)

        return _serialize_tramite(
            _reload_tramite_snapshot(db, tramite_id) or existing_tramite
        )

    tramite = Tramite(**payload.model_dump())

    try:
        db.add(tramite)
        db.commit()
        db.refresh(tramite)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ya existe un tramite con el mismo nombre o slug.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible crear el tramite.",
        ) from exc

    _sync_tramite_embedding(db, tramite)

    return _serialize_tramite(
        _reload_tramite_snapshot(db, tramite.id) or tramite
    )


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

    tramite_id = tramite.id
    draft_payload = {
        "nombre": payload.nombre or tramite.nombre,
        "slug": payload.slug or tramite.slug,
        "descripcion": payload.descripcion if payload.descripcion is not None else tramite.descripcion,
        "requisitos": payload.requisitos if payload.requisitos is not None else tramite.requisitos,
        "costo": payload.costo if payload.costo is not None else tramite.costo,
        "horario": payload.horario if payload.horario is not None else tramite.horario,
        "dependencia": payload.dependencia if payload.dependencia is not None else tramite.dependencia,
        "fuente_url": payload.fuente_url if payload.fuente_url is not None else tramite.fuente_url,
        "embedding_vector": tramite.embedding_vector,
    }
    blocking_issues = validate_tramite_payload(draft_payload)
    if blocking_issues:
        raise HTTPException(status_code=422, detail=" ".join(blocking_issues))

    existing_tramite = _find_tramite_by_name_or_slug(
        db,
        nombre=payload.nombre or tramite.nombre,
        slug=payload.slug or tramite.slug,
        exclude_id=tramite.id,
    )

    if existing_tramite is not None:
        duplicated_field = (
            "nombre"
            if (payload.nombre and existing_tramite.nombre == payload.nombre)
            else "slug"
        )
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe otro tramite con ese {duplicated_field}.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tramite, field, value)

    try:
        db.add(tramite)
        db.commit()
        db.refresh(tramite)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ya existe otro tramite con el mismo nombre o slug.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible actualizar el tramite.",
        ) from exc

    _sync_tramite_embedding(db, tramite)

    return _serialize_tramite(
        _reload_tramite_snapshot(db, tramite_id) or tramite
    )


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

    return _serialize_tramite(tramite)


@router.get(
    "/admin/consultas",
    response_model=list[ConsultaLogRead],
    tags=["admin-consultas"],
)
def list_consulta_logs(db: DbSession) -> list[ConsultaLogRead]:
    logs = list_recent_consulta_logs(db)
    return [ConsultaLogRead.model_validate(log) for log in logs]


@router.post(
    "/consulta",
    response_model=ConsultaResponse,
    tags=["consulta"],
)
def consulta_tramites(
    payload: ConsultaRequest,
    request: Request,
    db: DbSession,
) -> ConsultaResponse:
    try:
        query = select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.nombre)
        tramites = db.scalars(query).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    response = process_consulta(db, payload.pregunta, tramites)

    if not getattr(request.app.state, "disable_consulta_logging", False):
        try:
            log_consulta_result(
                db,
                pregunta=payload.pregunta,
                response=response,
            )
        except SQLAlchemyError:
            db.rollback()

    return response
