import random
import pytest
from cradl.client import Client

from . import service


def assert_agent(agent):
    assert 'agentId' in agent, 'Missing agentId in agent'
    assert 'resourceIds' in agent, 'Missing resourceIds in agent'


def test_create_agent(client: Client):
    agent = client.create_agent(
        name='Test Agent',
        description='A test agent',
        resource_ids=[
            service.create_action_id(),
            service.create_hook_id(),
            service.create_validation_id(),
            service.create_model_id(),
        ]
        ,
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
    agent = client.update_agent(agent_id, name='Updated Agent', resource_ids=[service.create_action_id()])
    assert_agent(agent)


def test_delete_agent(client: Client):
    agent_id = service.create_agent_id()
    agent = client.delete_agent(agent_id)
    assert_agent(agent)
