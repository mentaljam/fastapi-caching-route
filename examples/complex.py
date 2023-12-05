import anyio
from aiocache import SimpleMemoryCache
from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from fastapi_caching_route import CachingRoute, FastAPICache


app = FastAPI()
router = APIRouter(route_class=CachingRoute)
cache = FastAPICache(SimpleMemoryCache())
# Any non-empty string is considered a valid key
APIKeyDep = Depends(APIKeyHeader(name='X-Key'))


async def get_data() -> str:
    """Simulate data loading."""
    await anyio.sleep(1)
    return 'Hello, World!'


@router.get(
    path='/not-cached',
    dependencies=[APIKeyDep],
    response_class=PlainTextResponse,
)
async def not_cached() -> str:
    """Return not cached response."""
    return await get_data()


@cache(dependencies=[APIKeyDep])
@router.get(
    path='/cached',
    dependencies=[APIKeyDep],
    response_class=PlainTextResponse,
)
async def cached() -> str:
    """Return a cached response."""
    return await get_data()


@cache(dependencies=[APIKeyDep])
@router.get(
    path='/stream-cached',
    dependencies=[APIKeyDep],
)
async def stream_cached() -> StreamingResponse:
    """Stream a cached response."""
    data = await get_data()

    async def content():
        for chunk in data:
            yield chunk

    return StreamingResponse(
        content=content(),
        media_type='text/plain',
        headers={'Content-Length': str(len(data))},
    )


app.include_router(router)
cache.configure_app(app)
