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


def test_delete_agent_with_its_resources(client: Client, sent):
    agent_id = service.create_agent_id()
    client.delete_agent(agent_id, delete_resources=True)
    client.delete_agent(agent_id)
    assert sent == [
        ('DELETE', f'/agents/{agent_id}', None, {'deleteResources': 'true'}),
        ('DELETE', f'/agents/{agent_id}', None, None),
    ]


def test_update_agent_environments(client: Client, sent):
    agent_id = service.create_agent_id()
    environments = [{'name': 'Production', 'variables': [{'name': 'API_URL', 'value': 'https://example.com'}]}]
    client.update_agent(agent_id, environments=environments, draft_environment_id='env-0123456789ab')
    assert sent == [('PATCH', f'/agents/{agent_id}', {
        'environments': environments,
        'draftEnvironmentId': 'env-0123456789ab',
    }, None)]


def test_get_agent_graph(client: Client):
    graph = client.get_agent_graph(service.create_agent_id())
    assert 'nodes' in graph, 'Missing nodes in graph'
    assert 'edges' in graph, 'Missing edges in graph'


def test_update_agent_graph(client: Client):
    graph = client.update_agent_graph(service.create_agent_id(), layout={service.create_hook_id(): {'x': 0, 'y': 225}})
    assert 'nodes' in graph, 'Missing nodes in graph'


@pytest.mark.parametrize('resource_id, path', [
    ('cradl:agent:abc', '/agents/cradl:agent:abc'),
    ('cradl:agent:abc:3', '/agents/cradl:agent:abc:3'),
    ('cradl:agent:abc:@prod', '/agents/cradl:agent:abc:@prod'),
    ('cradl:agent:abc:$latest', '/agents/cradl:agent:abc:$latest'),
    ('cradl:organization:cradl/cradl:agent:abc', '/agents/cradl:organization:cradl%2Fcradl:agent:abc'),
])
def test_an_id_is_one_path_segment(client: Client, sent, resource_id, path):
    client.get_agent(resource_id)
    assert sent[0][1] == path
