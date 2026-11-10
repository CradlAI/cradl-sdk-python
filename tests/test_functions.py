import random

import pytest
from cradl.client import Client

from . import service


def assert_function(function):
    assert 'functionId' in function, 'Missing functionId in function'
    assert 'runtime' in function, 'Missing runtime in function'


def test_create_function(client: Client):
    function = client.create_function('python', name='Test function', description='A test function')
    assert_function(function)


def test_create_function_with_code(static_client: Client):
    function = static_client.create_function('python', content=b'def main(event):\n    return event\n')
    assert_function(function)


def test_a_function_whose_code_upload_fails_is_deleted(client: Client, monkeypatch):
    deleted: list[str] = []

    def fail(*args, **kwargs):
        raise RuntimeError('upload failed')
    monkeypatch.setattr(client, '_make_fileserver_request', fail)
    monkeypatch.setattr(client, 'delete_function', deleted.append)

    with pytest.raises(RuntimeError, match='upload failed'):
        client.create_function('python', content=b'def main(event):\n    return event\n')
    assert len(deleted) == 1


def test_list_functions(client: Client):
    response = client.list_functions()
    assert 'functions' in response, 'Missing functions in response'
    for function in response['functions']:
        assert_function(function)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_functions_with_pagination(client: Client, max_results, next_token):
    response = client.list_functions(
        max_results=max_results, next_token=next_token, sort_by='createdTime', order='descending',
    )
    assert 'functions' in response, 'Missing functions in response'


def test_list_functions_by_id(client: Client):
    response = client.list_functions(function_id=service.create_function_id())
    assert 'functions' in response, 'Missing functions in response'


@pytest.mark.parametrize('list_resources, key', [
    ('list_actions', 'actionId'),
    ('list_functions', 'functionId'),
    ('list_hooks', 'hookId'),
    ('list_models', 'modelId'),
    ('list_validations', 'validationId'),
    ('list_documents', 'documentId'),
])
def test_list_resources_by_ids(client: Client, sent, list_resources, key):
    """Sent as a repeated query parameter, which the mock API's specification declares as a single string"""
    ids = ['cradl:resource:a', 'cradl:resource:b']
    getattr(client, list_resources)(**{key.replace('Id', '_id'): ids})
    assert sent[0][3] == {key: ids}


def test_get_function(client: Client):
    function = client.get_function(service.create_function_id())
    assert_function(function)


def test_get_function_with_code(static_client: Client):
    function = static_client.get_function(service.create_function_id(), get_content=True)
    assert_function(function)
    assert function['content'] == ''


def test_update_function(client: Client):
    function = client.update_function(service.create_function_id(), name='Updated function')
    assert_function(function)


def test_update_function_code_only(static_client: Client):
    function = static_client.update_function(service.create_function_id(), content=b'def main(event):\n    return {}\n')
    assert_function(function)


def test_delete_function(client: Client):
    function = client.delete_function(service.create_function_id())
    assert_function(function)
