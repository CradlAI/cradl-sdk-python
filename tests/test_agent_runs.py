import random
import pytest
from cradl.client import Client

from . import service

def assert_agent_run(run):
    assert 'runId' in run, 'Missing runId in agent run'
    assert 'agentId' in run, 'Missing agentId in agent run'

def test_create_agent_run(client: Client):
    agent_id = service.create_agent_id()
    run = client.create_agent_run(agent_id, variables={'foo': 'bar'})
    assert_agent_run(run)

def test_list_agent_runs(client: Client):
    agent_id = service.create_agent_id()
    response = client.list_agent_runs(agent_id)
    assert 'runs' in response, 'Missing runs in response'

@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_agent_runs_with_pagination(client: Client, max_results, next_token):
    agent_id = service.create_agent_id()
    response = client.list_agent_runs(agent_id, max_results=max_results, next_token=next_token)
    assert 'runs' in response, 'Missing runs in response'

def test_get_agent_run(client: Client):
    agent_id = service.create_agent_id()
    run_id = service.create_agent_run_id()
    run = client.get_agent_run(agent_id, run_id)
    assert_agent_run(run)

def test_update_agent_run(client: Client):
    agent_id = service.create_agent_id()
    run_id = service.create_agent_run_id()
    run = client.update_agent_run(agent_id, run_id, status='archived')
    assert_agent_run(run)
