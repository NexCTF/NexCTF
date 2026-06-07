import hashlib
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model.oauth_server import OAuthServerClient
from nexctf.schema.oauth_server import (
    AdminOAuthClientCreate,
    AdminOAuthClientCreated,
    AdminOAuthClientCreateFull,
    AdminOAuthClientRead,
    AdminOAuthClientUpdate,
)

oauth_client_router = APIRouter(prefix="/oauth-client", tags=["Oauth Client"])


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@oauth_client_router.get("")
async def list_oauth_clients(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.OAuthServerClientCrud.paginate_params())],
) -> PaginatedResponse[AdminOAuthClientRead]:
    return await crud.OAuthServerClientCrud.paginate(
        session=session,
        **params,
        schema=AdminOAuthClientRead,
    )


@oauth_client_router.post("")
async def create_oauth_client(
    session: SessionDep,
    obj: AdminOAuthClientCreate,
) -> Response[AdminOAuthClientCreated]:
    raw_secret = secrets.token_urlsafe(32)
    full = AdminOAuthClientCreateFull(
        **obj.model_dump(),
        client_id="nexctf_" + secrets.token_urlsafe(16),
        client_secret_hash=_hash(raw_secret),
    )
    client = await crud.OAuthServerClientCrud.create(session=session, obj=full)
    return Response(
        data=AdminOAuthClientCreated(
            **AdminOAuthClientRead.model_validate(client).model_dump(),
            client_secret=raw_secret,
        )
    )


@oauth_client_router.get("/{uuid}")
async def get_client(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminOAuthClientRead]:
    return await crud.OAuthServerClientCrud.get(
        session=session,
        filters=[OAuthServerClient.id == uuid],
        schema=AdminOAuthClientRead,
    )


@oauth_client_router.put("/{uuid}")
async def update_client(
    session: SessionDep,
    obj: AdminOAuthClientUpdate,
    uuid: UUID,
) -> Response[AdminOAuthClientRead]:
    return await crud.OAuthServerClientCrud.update(
        session=session,
        filters=[OAuthServerClient.id == uuid],
        obj=obj,
        schema=AdminOAuthClientRead,
    )


@oauth_client_router.delete("/{uuid}")
async def delete_client(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.OAuthServerClientCrud.delete(
        session=session,
        filters=[OAuthServerClient.id == uuid],
        return_response=True,
    )
