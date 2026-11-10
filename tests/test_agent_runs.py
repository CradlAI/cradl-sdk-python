import random
from datetime import datetime, timezone

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


def test_create_agent_run_from_a_trigger(client: Client):
    run = client.create_agent_run(service.create_agent_id(), trigger_id=service.create_action_id())
    assert_agent_run(run)


def test_create_agent_run_of_an_alias(client: Client, sent):
    agent_id = service.create_agent_id()
    client.create_agent_run(f'{agent_id}:@prod')
    assert sent == [('POST', f'/agents/{agent_id}:@prod/runs', {}, None)]


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


@pytest.mark.parametrize('filters', [
    {'status': 'error'},
    {'sort': 'createdTime:asc'},
    {'created_time_after': '2026-01-01T00:00:00+00:00', 'created_time_before': datetime.now(timezone.utc)},
    {'updated_time_after': datetime(2026, 1, 1, tzinfo=timezone.utc)},
])
def test_list_agent_runs_with_filters(client: Client, filters):
    response = client.list_agent_runs(service.create_agent_id(), **filters)
    assert 'runs' in response, 'Missing runs in response'


def test_list_agent_runs_with_several_statuses_and_sort_keys(client: Client, sent):
    """Sent as repeated query parameters, which the mock API's specification declares as single strings"""
    agent_id = service.create_agent_id()
    statuses, sort = ['ready-for-review', 'review-in-progress'], ['status', 'updatedTime:desc']
    client.list_agent_runs(agent_id, status=statuses, sort=sort)
    assert sent[0][3] == {'status': statuses, 'sort': sort}


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
