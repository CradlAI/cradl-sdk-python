import random
import pytest
from cradl.client import Client

from . import service


def assert_agent(agent):
    assert 'agentId' in agent, 'Missing agentId in agent'
    assert 'resourceIds' in agent, 'Missing resourceIds in agent'


def test_create_agent(client: Client):
    agent = client.create_agent(name='Test Agent', description='A test agent')
    assert_agent(agent)


def test_create_agent_with_resource_ids_is_deprecated(client: Client):
    with pytest.warns(DeprecationWarning, match='agent_id'):
        agent = client.create_agent(
            name='Test Agent',
            description='A test agent',
            resource_ids=[
                service.create_action_id(),
                service.create_hook_id(),
                service.create_validation_id(),
                service.create_model_id(),
            ],
        )
    assert_agent(agent)


def test_list_agents(client: Client):
    response = client.list_agents()
    assert 'agents' in response, 'Missing agents in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for agent in response['agents']:
        assert_agent(agent)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_agents_with_pagination(client: Client, max_results, next_token):
    response = client.list_agents(max_results=max_results, next_token=next_token)
    assert 'agents' in response, 'Missing agents in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for agent in response['agents']:
        assert_agent(agent)


def test_get_agent(client: Client):
    agent_id = service.create_agent_id()
    agent = client.get_agent(agent_id)
    assert_agent(agent)


def test_update_agent(client: Client):
    agent_id = service.create_agent_id()
    agent = client.update_agent(agent_id, name='Updated Agent')
    assert_agent(agent)


def test_update_agent_with_resource_ids_is_deprecated(client: Client):
    agent_id = service.create_agent_id()
    with pytest.warns(DeprecationWarning, match='agent_id'):
        agent = client.update_agent(agent_id, name='Updated Agent', resource_ids=[service.create_action_id()])
    assert_agent(agent)


@pytest.mark.parametrize('create, args', [
    ('create_action', {'function_id': service.create_function_id()}),
    ('create_hook', {'trigger': 'Document is Created'}),
    ('create_model', {'field_config': {}}),
    ('create_validation', {}),
])
def test_a_resource_is_created_for_an_agent(client: Client, monkeypatch, create, args):
    """Sent as agentId, which the mock API's specification validates; without agent_id, a standalone resource"""
    sent = []
    make_request = client._make_request

    def recorded(requests_fn, path, body=None, **kwargs):
        sent.append(body)
        return make_request(requests_fn, path, body=body, **kwargs)
    monkeypatch.setattr(client, '_make_request', recorded)
    agent_id = service.create_agent_id()

    getattr(client, create)(**args, agent_id=agent_id)
    getattr(client, create)(**args)

    assert sent[0]['agentId'] == agent_id
    assert 'agentId' not in sent[1]


def test_delete_agent(client: Client):
    agent_id = service.create_agent_id()
    agent = client.delete_agent(agent_id)
    assert_agent(agent)
