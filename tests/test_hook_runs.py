import random
import pytest
from cradl.client import Client

from . import service

def assert_hook_run(run):
    assert 'runId' in run, 'Missing runId in hook run'
    assert 'hookId' in run, 'Missing hookId in hook run'

def test_create_hook_run(client: Client):
    hook_id = 'las:hook:dummyid'
    run = client.create_action_run(hook_id, input={'foo': 'bar'})
    assert_hook_run(run)

def test_list_hook_runs(client: Client):
    hook_id = 'las:hook:dummyid'
    response = client.list_hook_runs(hook_id)
    assert 'runs' in response or 'hookRuns' in response, 'Missing runs in response'
    # Accept both keys for robustness

@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_hook_runs_with_pagination(client: Client, max_results, next_token):
    hook_id = 'las:hook:dummyid'
    response = client.list_hook_runs(hook_id, max_results=max_results, next_token=next_token)
    assert 'runs' in response or 'hookRuns' in response, 'Missing runs in response'

def test_get_hook_run(client: Client):
    hook_id = 'las:hook:dummyid'
    run_id = 'dummy_run_id'
    run = client.get_hook_run(hook_id, run_id)
    assert_hook_run(run)

def test_update_hook_run(client: Client):
    hook_id = 'las:hook:dummyid'
    run_id = 'dummy_run_id'
    run = client.update_hook_run(hook_id, run_id, status='completed')
    assert_hook_run(run)

