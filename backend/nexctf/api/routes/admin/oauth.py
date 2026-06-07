from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model import OAuthProvider
from nexctf.schema.oauth import (
    AdminOAuthProviderCreate,
    AdminOAuthProviderRead,
    AdminOAuthProviderUpdate,
)

oauth_router = APIRouter(prefix="/oauth-provider", tags=["OAuthProvider"])


@oauth_router.get("")
async def get_oauth_providers(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.OAuthProviderCrud.paginate_params())],
) -> PaginatedResponse[AdminOAuthProviderRead]:
    return await crud.OAuthProviderCrud.paginate(
        session=session,
        **params,
        schema=AdminOAuthProviderRead,
    )


@oauth_router.post("")
async def create_oauth_provider(
    session: SessionDep,
    obj: AdminOAuthProviderCreate,
) -> Response[AdminOAuthProviderRead]:
    return await crud.OAuthProviderCrud.create(
        session=session, obj=obj, schema=AdminOAuthProviderRead
    )


@oauth_router.get("/{uuid}")
async def get_oauth_provider(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminOAuthProviderRead]:
    return await crud.OAuthProviderCrud.get(
        session=session,
        filters=[OAuthProvider.id == uuid],
        schema=AdminOAuthProviderRead,
    )


@oauth_router.put("/{uuid}")
async def update_oauth_provider(
    session: SessionDep,
    uuid: UUID,
    obj: AdminOAuthProviderUpdate,
) -> Response[AdminOAuthProviderRead]:
    return await crud.OAuthProviderCrud.update(
        session=session,
        filters=[OAuthProvider.id == uuid],
        obj=obj,
        schema=AdminOAuthProviderRead,
    )


@oauth_router.delete("/{uuid}")
async def delete_oauth_provider(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.OAuthProviderCrud.delete(
        session=session,
        filters=[OAuthProvider.id == uuid],
        return_response=True,
    )
