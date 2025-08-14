import random
import pytest
from cradl.client import Client
from . import service, util

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(('metadata', 'image'), [
    (util.metadata(), True),
    (None, False),
])
def test_create_document(
    monkeypatch,
    static_client: Client,
    content,
    image,
    metadata,
    pdf_content,
):
    consent_id = service.create_consent_id()
    post_documents_response = static_client.create_document(
        content if image else pdf_content,
        consent_id=consent_id,
        metadata=metadata,
    )

    assert 'documentId' in post_documents_response, 'Missing documentId in response'
    assert 'consentId' in post_documents_response, 'Missing consentId in response'
    assert 'contentType' in post_documents_response, 'Missing contentType in response'


@pytest.mark.parametrize('consent_id,dataset_id', [
    (None, None),
    (None, service.create_dataset_id()),
    (service.create_consent_id(), None),
    ([service.create_consent_id()], [service.create_dataset_id()]),
])
@pytest.mark.parametrize('sort_by,order', [
    ('createdTime', 'ascending'),
    ('createdTime', 'descending'),
])
def test_list_documents(static_client: Client, consent_id, dataset_id, sort_by, order):
    response = static_client.list_documents(
        consent_id=consent_id,
        dataset_id=dataset_id,
        sort_by=sort_by,
        order=order,
    )
    assert 'documents' in response, 'Missing documents in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_documents_with_pagination(static_client: Client, max_results, next_token):
    response = static_client.list_documents(max_results=max_results, next_token=next_token)
    assert 'documents' in response, 'Missing documents in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


@pytest.mark.parametrize('width', [None, 100])
@pytest.mark.parametrize('height', [None, 100])
@pytest.mark.parametrize('page', [None, 1])
@pytest.mark.parametrize('rotation', [None, 90])
@pytest.mark.parametrize('density', [None, 100])
@pytest.mark.parametrize('quality', [None, 'low'])
def test_get_document(static_client: Client, width, height, page, rotation, density, quality):
    document_id = service.create_document_id()
    response = static_client.get_document(
        document_id=document_id,
        width=width,
        height=height,
        page=page,
        rotation=rotation,
        density=density,
        quality=quality,
    )
    assert 'documentId' in response, 'Missing documentId in response'
    assert 'consentId' in response, 'Missing consentId in response'
    assert 'contentType' in response, 'Missing contentType in response'
    assert 'groundTruth' in response, 'Missing groundTruth in response'


@pytest.mark.parametrize('metadata', [util.metadata(), None])
def test_update_document(static_client: Client, metadata):
    document_id = service.create_document_id()
    ground_truth = [
        {'label': 'total_amount', 'value': '54.50'},
        {'label': 'purchase_date', 'value': '2007-07-30'},
        {'label': 'secure_agreement', 'value': True},
    ]

    post_document_id_response = static_client.update_document(
        document_id,
        ground_truth=ground_truth,
        dataset_id=service.create_dataset_id(),
        metadata=metadata,
    )

    assert 'groundTruth' in post_document_id_response, 'Missing groundTruth in response'
    assert 'documentId' in post_document_id_response, 'Missing documentId in response'
    assert 'consentId' in post_document_id_response, 'Missing consentId in response'


@pytest.mark.parametrize('consent_id,dataset_id', [
    (None, None),
    (None, service.create_dataset_id()),
    (service.create_consent_id(), None),
    ([service.create_consent_id()], [service.create_dataset_id()]),
])
def test_delete_documents(static_client: Client, consent_id, dataset_id):
    delete_documents_response = static_client.delete_documents(consent_id=consent_id, dataset_id=dataset_id)

    assert 'documents' in delete_documents_response, 'Missing documents in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_delete_documents_with_pagination(static_client: Client, max_results, next_token):
    response = static_client.delete_documents(max_results=max_results, next_token=next_token)
    assert 'documents' in response, 'Missing documents in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
