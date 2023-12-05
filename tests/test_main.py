from collections.abc import Callable

import pytest
from examples.complex import app
from starlette.testclient import TestClient


@pytest.fixture(name='anonymous_client')
def anonymous_client_fixture() -> TestClient:
    return TestClient(app)


@pytest.fixture(name='client')
def client_fixture() -> TestClient:
    return TestClient(app, headers={'X-Key': 'secret'})


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


@pytest.mark.parametrize('tester', [_test_valid_etag, _test_invalid_etag], ids=['valid', 'invalid'])
def test_etag(client: TestClient, tester: Callable) -> None:
    res = client.get('/cached')
    etag = res.headers['etag']
    assert res.status_code == 200
    assert etag
    tester(client, etag)
