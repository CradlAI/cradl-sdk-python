"""
The mock API's specification has no response schemas for versions and aliases yet ({"type": "object"}), so it checks
the requests, and the paths and bodies are checked as they're sent
"""
import random

import pytest
from cradl.client import Client

from . import service

RESOURCES = [
    ('agent', service.create_agent_id),
    ('model', service.create_model_id),
    ('function', service.create_function_id),
]


@pytest.mark.parametrize('singular, create_id', RESOURCES)
def test_create_version(client: Client, singular, create_id):
    assert isinstance(getattr(client, f'create_{singular}_version')(create_id()), dict)


@pytest.mark.parametrize('singular, create_id', RESOURCES)
@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_versions(client: Client, singular, create_id, max_results, next_token):
    response = getattr(client, f'list_{singular}_versions')(create_id(), max_results=max_results, next_token=next_token)
    assert isinstance(response, dict)


@pytest.mark.parametrize('singular, create_id', RESOURCES)
def test_aliases(client: Client, singular, create_id):
    resource_id = create_id()
    assert isinstance(getattr(client, f'set_{singular}_alias')(resource_id, 'prod', resource_version=3), dict)
    assert isinstance(getattr(client, f'get_{singular}_alias')(resource_id, 'prod'), dict)
    assert isinstance(getattr(client, f'list_{singular}_aliases')(resource_id), dict)
    assert isinstance(getattr(client, f'delete_{singular}_alias')(resource_id, 'prod'), dict)


def test_an_agent_alias_has_an_environment(client: Client, sent):
    """Recorded: the mock API's specification types environmentId as an object"""
    agent_id = service.create_agent_id()
    client.set_agent_alias(agent_id, 'prod', resource_version=2, environment_id='env-0123456789ab')
    assert sent == [
        ('PUT', f'/agents/{agent_id}/aliases/prod', {'resourceVersion': 2, 'environmentId': 'env-0123456789ab'}, None),
    ]


@pytest.mark.parametrize('singular, collection, create_id', [
    ('agent', 'agents', service.create_agent_id),
    ('model', 'models', service.create_model_id),
    ('function', 'functions', service.create_function_id),
])
def test_version_and_alias_paths(client: Client, sent, singular, collection, create_id):
    resource_id = create_id()
    getattr(client, f'create_{singular}_version')(resource_id)
    getattr(client, f'set_{singular}_alias')(resource_id, 'prod', resource_version=3)
    assert sent == [
        ('POST', f'/{collection}/{resource_id}/versions', {}, None),
        ('PUT', f'/{collection}/{resource_id}/aliases/prod', {'resourceVersion': 3}, None),
    ]


def test_an_agent_alias_environment_is_cleared_with_none(client: Client, sent):
    agent_id = service.create_agent_id()
    client.set_agent_alias(agent_id, 'prod', resource_version=2, environment_id=None)
    client.set_agent_alias(agent_id, 'prod', resource_version=2)
    assert [body for _, _, body, _ in sent] == [
        {'resourceVersion': 2, 'environmentId': None},
        {'resourceVersion': 2},
    ]
