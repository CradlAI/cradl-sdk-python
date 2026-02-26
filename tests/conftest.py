import json
import string
from base64 import b64encode
from os import urandom
from random import choice, randint

import pytest
from cradl import Client
from requests_mock import Mocker


@pytest.fixture(scope='session')
def token():
    header = b64encode(json.dumps({
        'alg': 'RS256',
        'kid': 'ff:ff:ff:ff:ff:ff:ff:ff:ff:ff:ff:ff:ff:ff:ff:ff',
        'typ': 'JWT'
    }).encode()).decode()

    claims = b64encode(json.dumps({
        'external_app_client_id': 'cradl:app-client:00000000000000000000000000000000',
        'external_organization_id': 'cradl:organization:00000000000000000000000000000000',
        'scope': 'actions: read actions:write',
    }).encode()).decode()

    signature = ''.join(choice(string.ascii_uppercase) for _ in range(randint(50, 50)))  # invalid
    return {
        'access_token': '.'.join([header, claims, signature]),
        'expires_in': 123456789,
    }


@pytest.fixture(scope='session', autouse=True)
def mock_access_token_endpoint(token):
    with Mocker(real_http=True) as m:
        m.post('/token', json=token)
        yield


@pytest.fixture(scope='module')
def client():
    client = Client()
    return client


@pytest.fixture(scope='module')
def static_client():
    client = Client()
    original_make_request = client._make_request
    client._make_request = lambda *args, **kwargs: original_make_request(
        *args, **{
            **kwargs,
            'extra_headers': {
                **kwargs.get('extra_headers', {}),
                'Prefer': 'dynamic=false',
            }
        }
    )
    client._make_fileserver_request = lambda *args, **kwargs: b''
    return client


@pytest.fixture
def mime_type():
    return 'image/jpeg'


@pytest.fixture(scope='function')
def content():
    """
    Yields a random JPEG bytestring with a length 2E4
    """
    yield b'\xFF\xD8\xFF\xEE' + urandom(int(2E4))


@pytest.fixture(scope='session')
def pdf_content():
    yield 'HTTP/1.0 200 OK%PDF-1.4 %½¾¼µ %%EOF'.encode()
