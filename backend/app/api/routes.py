import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal, get_db_session
from app.models import Tramite
from app.schemas.admin_session import (
    AdminSessionRead,
    AdminSessionRequest,
    AdminSessionStatus,
)
from app.schemas.consulta_log import ConsultaLogRead
from app.schemas.consulta import ConsultaRequest, ConsultaResponse
from app.schemas.tramite import TramiteCreate, TramiteRead, TramiteUpdate
from app.services import (
    assess_tramite_quality,
    activate_admin_session,
    create_admin_session_token,
    AdminSessionClaims,
    ensure_admin_session_is_active,
    get_admin_session_remaining_seconds,
    has_insecure_admin_config,
    is_tramite_in_catalog_scope,
    list_recent_consulta_logs,
    log_consulta_result,
    process_consulta,
    require_admin_session,
    update_tramite_embedding,
    validate_tramite_payload,
    verify_admin_pin,
)


router = APIRouter()
DbSession = Annotated[Session, Depends(get_db_session)]


def require_active_admin_session(
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> AdminSessionClaims:
    claims = require_admin_session(authorization)
    ensure_admin_session_is_active(db, claims)
    return claims


AdminSession = Annotated[AdminSessionClaims, Depends(require_active_admin_session)]

def _sync_tramite_embedding(tramite_id: int) -> None:
    try:
        snapshot_db = SessionLocal()
    except SQLAlchemyError:
        return

    try:
        snapshot = snapshot_db.get(Tramite, tramite_id)
        if snapshot is None:
            return

        update_tramite_embedding(snapshot_db, snapshot)
    except Exception:
        snapshot_db.rollback()
        # Si el embedding no puede actualizarse en este momento, el tramite sigue
        # disponible y la consulta puede apoyarse en el respaldo textual.
    finally:
        snapshot_db.close()


def _reload_tramite_snapshot(tramite_id: int) -> Tramite | None:
    try:
        snapshot_db = SessionLocal()
    except SQLAlchemyError:
        return None

    try:
        snapshot = snapshot_db.get(Tramite, tramite_id)
        if snapshot is not None:
            snapshot_db.expunge(snapshot)
        return snapshot
    except SQLAlchemyError:
        return None
    finally:
        snapshot_db.close()


def _serialize_tramite_snapshot(tramite_id: int) -> TramiteRead:
    snapshot = _reload_tramite_snapshot(tramite_id)
    if snapshot is None:
        raise HTTPException(
            status_code=503,
            detail="No fue posible recargar el tramite despues de guardarlo.",
        )

    return _serialize_tramite(snapshot)


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
            "semantic_scope_status": quality.scope_status,
            "semantic_recommended_action": quality.recommended_action,
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


@router.post(
    "/admin/session",
    response_model=AdminSessionRead,
    tags=["admin-auth"],
)
def create_admin_session(payload: AdminSessionRequest, db: DbSession) -> AdminSessionRead:
    if has_insecure_admin_config():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "El acceso administrativo no esta habilitado porque faltan "
                "credenciales seguras de produccion."
            ),
        )

    if not verify_admin_pin(payload.pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El PIN administrativo no es valido.",
        )

    access_token, expires_in_seconds, expires_at, session_id = create_admin_session_token()
    activate_admin_session(db, session_id)
    return AdminSessionRead(
        access_token=access_token,
        expires_in_seconds=expires_in_seconds,
        expires_at=expires_at,
    )


@router.get(
    "/admin/session",
    response_model=AdminSessionStatus,
    tags=["admin-auth"],
)
def read_admin_session(claims: AdminSession) -> AdminSessionStatus:
    return AdminSessionStatus(
        authenticated=True,
        expires_in_seconds=get_admin_session_remaining_seconds(claims),
        expires_at=claims.exp,
    )


@router.get("/tramites", response_model=list[TramiteRead], tags=["tramites"])
def list_tramites(db: DbSession) -> list[TramiteRead]:
    try:
        query = select(Tramite).where(Tramite.activo.is_(True)).order_by(Tramite.nombre)
        tramites = [
            tramite
            for tramite in db.scalars(query).all()
            if is_tramite_in_catalog_scope(tramite)
        ]
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

    if tramite is None or not tramite.activo or not is_tramite_in_catalog_scope(tramite):
        raise HTTPException(status_code=404, detail="Tramite no encontrado.")

    return _serialize_tramite(tramite)


@router.post(
    "/admin/tramites",
    response_model=TramiteRead,
    status_code=201,
    tags=["admin-tramites"],
)
def create_tramite(
    payload: TramiteCreate,
    db: DbSession,
    _: AdminSession,
) -> TramiteRead:
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

        _sync_tramite_embedding(tramite_id)

        return _serialize_tramite_snapshot(tramite_id)

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

    tramite_id = tramite.id
    _sync_tramite_embedding(tramite_id)

    return _serialize_tramite_snapshot(tramite_id)


@router.get(
    "/admin/tramites/desactivados",
    response_model=list[TramiteRead],
    tags=["admin-tramites"],
)
def list_inactive_tramites(
    db: DbSession,
    _: AdminSession,
) -> list[TramiteRead]:
    try:
        query = select(Tramite).where(Tramite.activo.is_(False)).order_by(Tramite.nombre)
        tramites = [
            tramite
            for tramite in db.scalars(query).all()
            if is_tramite_in_catalog_scope(tramite)
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar los tramites desactivados.",
        ) from exc

    return [_serialize_tramite(tramite) for tramite in tramites]


@router.put(
    "/admin/tramites/{tramite_id}",
    response_model=TramiteRead,
    tags=["admin-tramites"],
)
def update_tramite(
    tramite_id: int,
    payload: TramiteUpdate,
    db: DbSession,
    _: AdminSession,
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
        "dirigido_a": payload.dirigido_a if payload.dirigido_a is not None else tramite.dirigido_a,
        "pasos": payload.pasos if payload.pasos is not None else tramite.pasos,
        "tiempo_estimado": payload.tiempo_estimado if payload.tiempo_estimado is not None else tramite.tiempo_estimado,
        "medio_seguimiento": payload.medio_seguimiento if payload.medio_seguimiento is not None else tramite.medio_seguimiento,
        "normatividad": payload.normatividad if payload.normatividad is not None else tramite.normatividad,
        "costo": payload.costo if payload.costo is not None else tramite.costo,
        "horario": payload.horario if payload.horario is not None else tramite.horario,
        "dependencia": payload.dependencia if payload.dependencia is not None else tramite.dependencia,
        "fuente_url": payload.fuente_url if payload.fuente_url is not None else tramite.fuente_url,
        "enlace_click_aqui": (
            payload.enlace_click_aqui
            if payload.enlace_click_aqui is not None
            else tramite.enlace_click_aqui
        ),
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

    _sync_tramite_embedding(tramite_id)

    return _serialize_tramite_snapshot(tramite_id)


@router.delete(
    "/admin/tramites/{tramite_id}",
    response_model=TramiteRead,
    tags=["admin-tramites"],
)
def delete_tramite(
    tramite_id: int,
    db: DbSession,
    _: AdminSession,
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


@router.delete(
    "/admin/tramites/{tramite_id}/permanente",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin-tramites"],
)
def permanently_delete_inactive_tramite(
    tramite_id: int,
    db: DbSession,
    _: AdminSession,
) -> None:
    try:
        tramite = db.get(Tramite, tramite_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    if tramite is None:
        raise HTTPException(status_code=404, detail="Tramite no encontrado.")

    if tramite.activo:
        raise HTTPException(
            status_code=409,
            detail="Primero desactiva el trámite antes de eliminarlo definitivamente.",
        )

    try:
        db.delete(tramite)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible eliminar definitivamente el trámite.",
        ) from exc


@router.post(
    "/admin/tramites/{tramite_id}/reactivar",
    response_model=TramiteRead,
    tags=["admin-tramites"],
)
def reactivate_tramite(
    tramite_id: int,
    db: DbSession,
    _: AdminSession,
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

    tramite.activo = True

    try:
        db.add(tramite)
        db.commit()
        db.refresh(tramite)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No fue posible reactivar el tramite.",
        ) from exc

    _sync_tramite_embedding(tramite_id)

    return _serialize_tramite_snapshot(tramite_id)


@router.get(
    "/admin/consultas",
    response_model=list[ConsultaLogRead],
    tags=["admin-consultas"],
)
def list_consulta_logs(
    db: DbSession,
    _: AdminSession,
) -> list[ConsultaLogRead]:
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
        tramites = [
            tramite
            for tramite in db.scalars(query).all()
            if is_tramite_in_catalog_scope(tramite)
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos.",
        ) from exc

    started_at = time.perf_counter()
    response = process_consulta(db, payload.pregunta, tramites)
    response_time_ms = int((time.perf_counter() - started_at) * 1000)

    if not getattr(request.app.state, "disable_consulta_logging", False):
        try:
            log_consulta_result(
                db,
                pregunta=payload.pregunta,
                response=response,
                response_time_ms=response_time_ms,
            )
        except SQLAlchemyError:
            db.rollback()

    return response
