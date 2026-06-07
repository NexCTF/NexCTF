import nexctf.crud as crud
from fastapi import APIRouter
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import SessionDep
from nexctf.model.page import CustomPage
from nexctf.schema.page import PublicPageDetail, PublicPageRead

page_router = APIRouter(prefix="/page", tags=["Page"])


@page_router.get("")
async def list_published_pages(
    session: SessionDep,
) -> Response[list[PublicPageRead]]:
    """Return a list of all published pages (slug, title, nav_placement)."""
    pages = await crud.PageCrud.get_multi(
        session, filters=[CustomPage.is_published.is_(True)]
    )
    return Response(data=[PublicPageRead.model_validate(p) for p in pages])


@page_router.get("/{slug}")
async def get_published_page(
    session: SessionDep, slug: str
) -> Response[PublicPageDetail]:
    """Return a single published page by slug."""
    return await crud.PageCrud.get(
        session,
        filters=[CustomPage.slug == slug, CustomPage.is_published.is_(True)],
        schema=PublicPageDetail,
    )
