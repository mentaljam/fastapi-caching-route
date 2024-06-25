from collections.abc import Callable

import pytest
from aiocache import SimpleMemoryCache
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi_caching_route.main import (
    CacheInitializationError,
    CachingRoute,
    FastAPICache,
    RouteClassError,
)
from starlette.testclient import TestClient

from examples import invalidate
from examples.complex import app, cache


def simple_client_factory(
    *,
    ns_root: str | None = None,
    ns_method: str | None = None,
    configure: bool = True,
    route_class: type[APIRoute] = CachingRoute,
) -> TestClient:
    router = APIRouter(route_class=route_class)
    cache = FastAPICache(SimpleMemoryCache(namespace=ns_root))

    @cache(namespace=ns_method)
    @router.get('/')
    def cached() -> str:
        """Return cached response."""
        return 'Hello, World!'

    app_ = FastAPI()
    app_.include_router(router)
    if configure:
        cache.configure_app(app_)

    return TestClient(app_)


@pytest.fixture(name='anonymous_client')
def anonymous_client_fixture() -> TestClient:
    return TestClient(app)


@pytest.fixture(name='client')
def client_fixture() -> TestClient:
    return TestClient(app, headers={'X-Key': 'secret'})


def test_unconfigured() -> None:
    client = simple_client_factory(configure=False)
    with pytest.raises(CacheInitializationError):
        client.get('/')


def test_configure_twice() -> None:
    with pytest.raises(CacheInitializationError):
        cache.configure_app(app)


def test_bad_route_class() -> None:
    with pytest.raises(RouteClassError):
        simple_client_factory(route_class=APIRoute)


@pytest.mark.parametrize(
    'ns_kwargs',
    [{'ns_root': 'root'}, {'ns_method': 'method'}, {'ns_root': 'root', 'ns_method': 'method'}],
    ids=['root', 'method', 'root and method'],
)
def test_namespace(ns_kwargs: dict) -> None:
    client = simple_client_factory(**ns_kwargs)
    client.get('/')


def test_non_authorized(anonymous_client: TestClient) -> None:
    res = anonymous_client.get('/cached')
    assert res.status_code == 403


@pytest.mark.parametrize('url', ['/cached', '/stream-cached'])
def test_cached(client: TestClient, url: str) -> None:
    res = client.get(url)
    assert res.status_code == 200
    assert res.headers['x-cache'] == 'MISS'

    res = client.get(url)
    assert res.status_code == 200
    assert res.headers['x-cache'] == 'HIT'


def _test_valid_etag(client: TestClient, etag: str) -> None:
    res = client.get('/cached', headers={'if-none-match': etag})
    content_len = int(res.headers['content-length'])
    assert res.status_code == 304
    assert len(res.content) == content_len == 0


def _test_invalid_etag(client: TestClient, _etag: str) -> None:
    res = client.get('/cached', headers={'if-none-match': '"invalid"'})
    assert res.status_code == 200
    assert res.headers['x-cache'] == 'HIT'
    assert len(res.content) > 0


def _test_valid_etag_with_w(client: TestClient, etag: str) -> None:
    res = client.get('/cached', headers={'if-none-match': 'W/' + etag})
    content_len = int(res.headers['content-length'])
    assert res.status_code == 304
    assert len(res.content) == content_len == 0


@pytest.mark.parametrize(
    'tester',
    [_test_valid_etag, _test_invalid_etag, _test_valid_etag_with_w],
    ids=['valid', 'invalid', 'valid with W/'],
)
def test_etag(client: TestClient, tester: Callable) -> None:
    res = client.get('/cached')
    etag = res.headers['etag']
    assert res.status_code == 200
    assert etag
    tester(client, etag)


def test_query(client: TestClient) -> None:
    res = client.get('/query', params={'a': 'a'})
    assert res.headers['x-cache'] == 'MISS'
    data = res.json()
    assert isinstance(data, dict)
    assert data['a'] == 'a'
    assert data['b'] == 'b'

    res = client.get('/query', params={'b': 'b', 'a': 'a'})
    assert res.headers['x-cache'] == 'HIT'
    data = res.json()
    assert isinstance(data, dict)
    assert data['a'] == 'a'
    assert data['b'] == 'b'


def test_invalidation() -> None:
    client = TestClient(invalidate.app)
    user_id = client.post('/users', json={'name': 'Sasa'}).json()['id']
    user_url = f'/users/{user_id}'
    res = client.get(user_url)
    assert res.headers['x-cache'] == 'MISS'
    res = client.get(user_url)
    assert res.headers['x-cache'] == 'HIT'
    client.patch(user_url, json={'name': 'Sasha'})
    res = client.get(user_url)
    assert res.headers['x-cache'] == 'MISS'


@pytest.mark.parametrize(
    ('url', 'status_code'),
    [('/not-cached', 200), ('/404', 404)],
    ids=['not cached', 'not found'],
)
def test_other(client: TestClient, url: str, status_code: int) -> None:
    res = client.get(url)
    assert res.status_code == status_code
    assert 'x-cache' not in res.headers
