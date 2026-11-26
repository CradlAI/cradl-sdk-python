"""
The mock API's specification doesn't have the restore endpoints yet, so the requests are recorded instead of sent, and
their paths, bodies and query parameters are checked
"""
from uuid import uuid4

import pytest
from cradl.client import Client

from . import service

RESOURCES = [
    ('agent', 'agents', service.create_agent_id),
    ('model', 'models', service.create_model_id),
    ('function', 'functions', service.create_function_id),
]


def create_restore_id():
    return f'cradl:restore:{uuid4().hex}'


@pytest.mark.parametrize('singular, collection, create_id', RESOURCES)
@pytest.mark.parametrize('qualifier', ['3', '@prod', '$latest'])
def test_create_restore(client: Client, sent, singular, collection, create_id, qualifier):
    resource_id = create_id()
    getattr(client, f'create_{singular}_restore')(resource_id, source_id=f'{resource_id}:{qualifier}')
    assert sent == [
        ('POST', f'/{collection}/{resource_id}/restores', {'sourceId': f'{resource_id}:{qualifier}'}, None),
    ]


@pytest.mark.parametrize('singular, collection, create_id', RESOURCES)
def test_a_dry_run_restore_sends_dry_run(client: Client, sent, singular, collection, create_id):
    resource_id = create_id()
    create_restore = getattr(client, f'create_{singular}_restore')
    create_restore(resource_id, source_id=f'{resource_id}:@prod', dry_run=True)
    create_restore(resource_id, source_id=f'{resource_id}:@prod', dry_run=False)
    assert [body for _, _, body, _ in sent] == [
        {'sourceId': f'{resource_id}:@prod', 'dryRun': True},
        {'sourceId': f'{resource_id}:@prod'},
    ]


@pytest.mark.parametrize('singular, collection, create_id', RESOURCES)
@pytest.mark.parametrize('max_results, next_token, params', [
    (None, None, {}),
    (10, None, {'maxResults': 10}),
    (10, 'foo', {'maxResults': 10, 'nextToken': 'foo'}),
])
def test_list_restores(client: Client, sent, singular, collection, create_id, max_results, next_token, params):
    resource_id = create_id()
    getattr(client, f'list_{singular}_restores')(resource_id, max_results=max_results, next_token=next_token)
    assert sent == [('GET', f'/{collection}/{resource_id}/restores', None, params)]


@pytest.mark.parametrize('singular, collection, create_id', RESOURCES)
def test_get_restore(client: Client, sent, singular, collection, create_id):
    resource_id = create_id()
    restore_id = create_restore_id()
    getattr(client, f'get_{singular}_restore')(resource_id, restore_id)
    assert sent == [('GET', f'/{collection}/{resource_id}/restores/{restore_id}', None, None)]


def test_restore_paths_quote_an_id_naming_its_organization(client: Client, sent):
    function_id = 'cradl:organization:cradl/cradl:function:abc'
    restore_id = create_restore_id()
    client.create_function_restore(function_id, source_id=f'{function_id}:3')
    client.list_function_restores(function_id)
    client.get_function_restore(function_id, restore_id)
    quoted = '/functions/cradl:organization:cradl%2Fcradl:function:abc/restores'
    assert [path for _, path, _, _ in sent] == [quoted, quoted, f'{quoted}/{restore_id}']
