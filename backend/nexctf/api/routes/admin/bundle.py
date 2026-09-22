import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from botocore.exceptions import ClientError
from fastapi import APIRouter, Form, UploadFile
from fastapi import Response as FastAPIResponse
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep, SessionDep, TokenScopesDep
from nexctf.bundle.errors import BundleFormatError
from nexctf.core import s3
from nexctf.exceptions import BundleFailedError, InsufficientScopeError
from nexctf.module import bundle
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.schema.bundle import (
    AdminBundleApply,
    AdminBundleApplyResult,
    AdminBundleManifestRead,
    AdminBundlePlanRead,
)

bundle_router = APIRouter(prefix="/bundle", tags=["Bundle"])

_READ_SCOPES = ("read:admin.challenge",)
_WRITE_SCOPES = (
    "write:admin.challenge",
    "write:admin.content",
    "write:admin.user",
    "write:admin.config",
)


def _require_scopes(granted: frozenset[str] | None, *required: str) -> None:
    """Assert scopes a token needs beyond the router's group. No-op for sessions."""
    if granted is None:
        return
    for scope in required:
        if scope not in granted:
            raise InsufficientScopeError(scope)


def _require_challenge_read(granted: frozenset[str] | None) -> None:
    """An export or plan embeds every solution, so it needs the challenge read."""
    _require_scopes(granted, *_READ_SCOPES)


def _fail(exc: Exception) -> BundleFailedError:
    return BundleFailedError(detail=str(exc))


@bundle_router.get("/export")
async def export_bundle(
    granted: TokenScopesDep,
    session: SessionDep,
    redis: RedisDep,
    include_files: bool = True,
    include_secrets: bool = False,
) -> FastAPIResponse:
    """Build a content archive and hand it straight back as a download."""
    _require_challenge_read(granted)
    if include_secrets:
        _require_scopes(granted, "read:admin.config")
    try:
        data = await bundle.export(
            session, include_files=include_files, include_secrets=include_secrets
        )
    except (bundle.BundleError, BundleFormatError) as exc:
        raise _fail(exc)

    filename = bundle.filename_for(datetime.now(UTC))
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type="bundle.exported",
        actor_id=actor_id,
        ip=ip,
        target_type="bundle",
        target_label=filename,
        meta={"include_files": include_files, "include_secrets": include_secrets},
    )
    return FastAPIResponse(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bundle_router.post("/import/plan")
async def plan_import(
    granted: TokenScopesDep,
    session: SessionDep,
    upload: UploadFile,
    prune: Annotated[bool, Form()] = False,
) -> Response[AdminBundlePlanRead]:
    """Stage an uploaded archive and return what importing it would do."""
    _require_challenge_read(granted)
    data = await upload.read()
    try:
        incoming, blobs = await asyncio.to_thread(bundle.parse_archive, data)
        plan = await bundle.plan_import(session, incoming, blobs=blobs, prune=prune)
    except (bundle.BundleError, BundleFormatError) as exc:
        raise _fail(exc)

    import_key = f"{bundle.IMPORT_PREFIX}{uuid4()}.zip"
    await s3.upload(import_key, data, "application/zip")

    return Response(
        data=AdminBundlePlanRead(
            import_key=import_key,
            prune=prune,
            manifest=AdminBundleManifestRead(
                format_version=incoming.manifest.format_version,
                nexctf_version=incoming.manifest.nexctf_version,
                exported_at=incoming.manifest.exported_at,
                challenge_types=incoming.manifest.requires.challenge_types,
                solve_types=incoming.manifest.requires.solve_types,
                plugins=incoming.manifest.requires.plugins,
            ),
            counts=plan.counts(),
            entries=plan.entries,
        )
    )


@bundle_router.post("/import/apply")
async def apply_import(
    granted: TokenScopesDep,
    session: SessionDep,
    redis: RedisDep,
    body: AdminBundleApply,
) -> Response[AdminBundleApplyResult]:
    """Apply a reviewed plan, re-deriving it from the staged archive first."""
    _require_scopes(granted, *_READ_SCOPES, *_WRITE_SCOPES)
    try:
        key = bundle.validate_import_key(body.import_key)
    except bundle.BundleError as exc:
        raise _fail(exc)

    try:
        data = await s3.download(key)
    except ClientError:
        raise BundleFailedError(
            detail="The staged archive has expired; upload it again."
        )

    try:
        incoming, blobs = await asyncio.to_thread(bundle.parse_archive, data)
        applied = await bundle.apply_import(
            session, redis, incoming, blobs, prune=body.prune
        )
    except (bundle.BundleError, BundleFormatError) as exc:
        raise _fail(exc)

    await s3.delete(key)
    return Response(
        data=AdminBundleApplyResult(counts=applied.counts(), entries=applied.entries)
    )
