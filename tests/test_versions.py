import pytest
from cradl.client import Client

from . import service

RESOURCES = [
    ('agent', 'agents', service.create_agent_id),
    ('model', 'models', service.create_model_id),
    ('function', 'functions', service.create_function_id),
]


@pytest.mark.parametrize('singular, collection, create_id', RESOURCES)
def test_versions(client: Client, sent, singular, collection, create_id):
    resource_id = create_id()
    getattr(client, f'create_{singular}_version')(resource_id)
    getattr(client, f'list_{singular}_versions')(resource_id)
    getattr(client, f'list_{singular}_versions')(resource_id, max_results=10, next_token='foo')
    assert sent == [
        ('POST', f'/{collection}/{resource_id}/versions', {}, None),
        ('GET', f'/{collection}/{resource_id}/versions', None, {}),
        ('GET', f'/{collection}/{resource_id}/versions', None, {'maxResults': 10, 'nextToken': 'foo'}),
    ]


@pytest.mark.parametrize('singular, collection, create_id', RESOURCES)
def test_aliases(client: Client, sent, singular, collection, create_id):
    resource_id = create_id()
    getattr(client, f'set_{singular}_alias')(resource_id, 'prod', resource_version=3)
    getattr(client, f'get_{singular}_alias')(resource_id, 'prod')
    getattr(client, f'list_{singular}_aliases')(resource_id)
    getattr(client, f'delete_{singular}_alias')(resource_id, 'prod')
    assert sent == [
        ('PUT', f'/{collection}/{resource_id}/aliases/prod', {'resourceVersion': 3}, None),
        ('GET', f'/{collection}/{resource_id}/aliases/prod', None, None),
        ('GET', f'/{collection}/{resource_id}/aliases', None, None),
        ('DELETE', f'/{collection}/{resource_id}/aliases/prod', None, None),
    ]


def test_an_agent_alias_has_an_environment(client: Client, sent):
    agent_id = service.create_agent_id()
    client.set_agent_alias(agent_id, 'prod', resource_version=2, environment_id='env-0123456789ab')
    assert sent == [
        ('PUT', f'/agents/{agent_id}/aliases/prod', {'resourceVersion': 2, 'environmentId': 'env-0123456789ab'}, None),
    ]
