import random
import pytest
from cradl.client import Client

from . import service

def assert_action_run(run):
    assert 'runId' in run, 'Missing runId in action run'
    assert 'actionId' in run, 'Missing actionId in action run'

def test_create_action_run(client: Client):
    action_id = 'las:action:dummyid'
    run = client.create_action_run(action_id, input={'foo': 'bar'})
    assert_action_run(run)

def test_list_action_runs(client: Client):
    action_id = 'las:action:dummyid'
    response = client.list_action_runs(action_id)
    assert 'runs' in response or 'actionRuns' in response, 'Missing runs in response'

@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_action_runs_with_pagination(client: Client, max_results, next_token):
    action_id = 'las:action:dummyid'
    response = client.list_action_runs(action_id, max_results=max_results, next_token=next_token)
    assert 'runs' in response or 'actionRuns' in response, 'Missing runs in response'

def test_get_action_run(client: Client):
    action_id = 'las:action:dummyid'
    run_id = 'dummy_run_id'
    run = client.get_action_run(action_id, run_id)
    assert_action_run(run)

def test_update_action_run(client: Client):
    action_id = 'las:action:dummyid'
    run_id = 'dummy_run_id'
    run = client.update_action_run(action_id, run_id, status='completed')
    assert_action_run(run)

