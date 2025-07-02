import json
import uuid
from base64 import b64encode
from pathlib import Path

import requests_mock
import pytest
from cradl.response import InvalidCredentialsException, LimitExceededException, TooManyRequestsException
from cradl.content import parse_content

from . import service


@pytest.fixture(scope='module')
def client_with_access_token(client):
    _ = client.credentials.access_token
    return client


@pytest.mark.parametrize('error_code,error_content,error_name', [
    (429, json.dumps({'message': 'Limit Exceeded'}).encode(), LimitExceededException),
    (429, json.dumps({'message': 'Too Many Requests'}).encode(), TooManyRequestsException),
    (403, json.dumps({'message': 'Forbidden'}).encode(), InvalidCredentialsException),
])
def test_invalid_credentials(
    error_code,
    error_content,
    error_name,
    content,
    client_with_access_token,
):

    client = client_with_access_token
    consent_id = service.create_consent_id()
    document_id = service.create_document_id()
    model_id = service.create_model_id()

    with requests_mock.Mocker() as m:
        m.post('/'.join([client.credentials.api_endpoint, 'documents']), status_code=error_code, content=error_content)
        m.post('/'.join([client.credentials.api_endpoint, 'predictions']), status_code=error_code, content=error_content)
        m.delete('/'.join([client.credentials.api_endpoint, 'documents']), status_code=error_code, content=error_content)

        with pytest.raises(error_name):
            client.create_document(content, consent_id=consent_id)

        with pytest.raises(error_name):
            client.create_prediction(document_id, model_id)

        with pytest.raises(error_name):
            client.delete_documents(consent_id=consent_id)


@pytest.mark.parametrize('content', [
    service.document_path(),
    service.document_path(),
    open(service.document_path(), 'rb'),
    open(service.document_path(), 'r'),
    open(service.document_path()),
    service.document_path().open(),
    service.document_path().open('rb'),
    service.document_path().open('r'),
    service.document_path().read_bytes(),
    service.document_path().read_text().encode(),
    b64encode(service.document_path().read_bytes()),
    bytearray(service.document_path().read_bytes()),
])
def test_parse_content(content):
    expected_result = b64encode(service.document_path().read_bytes()).decode(), None
    result = parse_content(content)
    assert result == expected_result


@pytest.mark.parametrize(('content', 'error'), [
    (Path(uuid.uuid4().hex), FileNotFoundError),
    (uuid.uuid4().hex, FileNotFoundError),
    (service.document_path().read_bytes().decode(), OSError),
    (service.document_path().read_text()[0:30], FileNotFoundError),
    (b64encode(service.document_path().read_bytes()).decode()[0:30], FileNotFoundError),
    (1, TypeError),
    (0.1, TypeError),
])
def test_parse_erroneous_content(content, error):
    with pytest.raises(error):
        parse_content(content)
