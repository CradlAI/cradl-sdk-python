import random
from datetime import datetime, timezone

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('email_config', [None, service.create_email_config()])
@pytest.mark.parametrize('error_config', [None, service.create_error_config()])
@pytest.mark.parametrize('completed_config', [None, service.create_completed_config()])
@pytest.mark.parametrize('metadata', [util.metadata(), None])
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(True))
def test_create_workflow(client: Client, email_config, error_config, completed_config, metadata, name_and_description):
    specification = {'definition': {}}
    response = client.create_workflow(
        specification,
        email_config=email_config,
        error_config=error_config,
        completed_config=completed_config,
        metadata=metadata,
        **name_and_description,
    )
    assert_workflow(response)


def test_list_workflows(client: Client):
    response = client.list_workflows()
    assert 'workflows' in response, 'Missing workflows in response'
    for workflow in response['workflows']:
        assert_workflow(workflow)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_workflows_with_pagination(client: Client, max_results, next_token):
    response = client.list_workflows(max_results=max_results, next_token=next_token)
    assert 'workflows' in response, 'Missing workflows in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_get_workflow(client: Client):
    workflow_id = service.create_workflow_id()
    response = client.get_workflow(workflow_id)
    assert_workflow(response)


@pytest.mark.parametrize('email_config', [None, service.create_email_config()])
@pytest.mark.parametrize('error_config', [None, service.create_error_config()])
@pytest.mark.parametrize('completed_config', [None, service.create_completed_config()])
@pytest.mark.parametrize('metadata', [util.metadata(), None])
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(True))
@pytest.mark.parametrize('status', [None, 'development', 'production'])
def test_update_workflow(
    client: Client,
    email_config,
    error_config,
    completed_config,
    metadata,
    name_and_description,
    status,
):
    optional_args = {'email_config': email_config, **name_and_description}
    response = client.update_workflow(
        service.create_workflow_id(),
        completed_config=completed_config,
        error_config=error_config,
        metadata=metadata,
        status=status,
        **optional_args,
    )
    assert_workflow(response)


@pytest.mark.parametrize(('from_start_time', 'to_start_time'), [
    (datetime(2022, 1, 1).astimezone(timezone.utc), datetime(2023, 1, 1).astimezone(timezone.utc)),
    (datetime(2022, 1, 1).astimezone(timezone.utc), None),
    (None, datetime(2023, 1, 1).astimezone(timezone.utc)),
    (datetime(2022, 1, 1).astimezone(timezone.utc).isoformat(), datetime(2023, 1, 1).astimezone(timezone.utc).isoformat()),
    (datetime(2022, 1, 1).astimezone(timezone.utc).isoformat(), None),
    (None, datetime(2023, 1, 1).astimezone(timezone.utc).isoformat()),
    (None, None),
])
@pytest.mark.parametrize('status', [
    ['succeeded'],
    ['failed'],
    'running',
    None,
])
def test_list_workflow_executions(client: Client, status, from_start_time, to_start_time):
    workflow_id = service.create_workflow_id()
    response = client.list_workflow_executions(
        workflow_id=workflow_id,
        status=status,
        from_start_time=from_start_time,
        to_start_time=to_start_time,
    )
    assert 'workflowId' in response, 'Missing workflowId in response'
    assert 'executions' in response, 'Missing executions in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_workflow_executions_with_pagination(client: Client, max_results, next_token):
    workflow_id = service.create_workflow_id()
    response = client.list_workflow_executions(workflow_id=workflow_id, max_results=max_results, next_token=next_token)
    assert 'workflowId' in response, 'Missing workflowId in response'
    assert 'executions' in response, 'Missing executions in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_execute_workflow(client: Client):
    workflow_id = service.create_workflow_id()
    response = client.execute_workflow(workflow_id, content={})
    assert_workflow_execution(response)


def test_delete_workflow_execution(client: Client):
    workflow_id = service.create_workflow_id()
    execution_id = service.create_workflow_execution_id()
    response = client.delete_workflow_execution(workflow_id, execution_id)
    assert_workflow_execution(response)


def test_delete_workflow(client: Client):
    workflow_id = service.create_workflow_id()
    response = client.delete_workflow(workflow_id)
    assert_workflow(response)


def test_get_workflow_execution(client: Client):
    response = client.get_workflow_execution(service.create_workflow_id(), service.create_workflow_execution_id())
    assert_workflow_execution(response)


@pytest.mark.parametrize('optional_args', [
    {'next_transition_id': service.create_transition_id()},
    {'status': 'completed'},
])
def test_update_workflow_execution(client: Client, optional_args):
    response = client.update_workflow_execution(
        service.create_workflow_id(),
        service.create_workflow_execution_id(),
        **optional_args,
    )
    assert_workflow_execution(response)


def assert_workflow(response):
    assert 'workflowId' in response, 'Missing workflowId in response'
    assert 'name' in response, 'Missing name in response'
    assert 'description' in response, 'Missing description in response'


def assert_workflow_execution(response):
    assert 'workflowId' in response, 'Missing workflowId in response'
    assert 'executionId' in response, 'Missing executionId in response'
    assert 'startTime' in response, 'Missing startTime in response'
    assert 'endTime' in response, 'Missing endTime in response'
    assert 'transitionExecutions' in response, 'Missing transitionExecutions in response'
