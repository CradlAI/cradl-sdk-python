import logging
import random
from datetime import datetime, timezone
from unittest.mock import patch, ANY

import cradl
import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('transition_type,parameters', [
    ('docker', {'imageUrl': 'python3.8'}),
    ('manual', None),
    ('manual', {'assets': {'jsRemoteComponent': service.create_asset_id()}}),
])
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_transition(client: Client, transition_type, parameters, name_and_description):
    response = client.create_transition(
        transition_type,
        parameters=parameters,
        **name_and_description,
    )
    logging.info(response)
    assert_transition(response)


def test_get_transition(client: Client):
    response = client.get_transition(service.create_transition_id())
    logging.info(response)
    assert_transition(response)


def test_delete_transition(client: Client):
    response = client.delete_transition(service.create_transition_id())
    logging.info(response)
    assert_transition(response)


@pytest.mark.parametrize('transition_type', [['docker'], ['manual'], 'docker', 'manual', None])
def test_list_transitions(client: Client, transition_type):
    response = client.list_transitions(transition_type=transition_type)
    logging.info(response)
    assert 'transitions' in response, 'Missing transitions in response'
    if transition_type:
        assert 'transitionType' in response, 'Missing transitionType in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_transitions_with_pagination(client: Client, max_results, next_token):
    response = client.list_transitions(max_results=max_results, next_token=next_token)
    logging.info(response)
    assert 'transitions' in response, 'Missing transitions in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_get_transition_execution(client: Client):
    response = client.get_transition_execution(
        service.create_transition_id(),
        service.create_transition_execution_id(),
    )
    logging.info(response)
    assert 'transitionId' in response, 'Missing transitionId in response'
    assert 'executionId' in response, 'Missing executionId in response'
    assert 'status' in response, 'Missing status in response'


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(True))
def test_update_transition(client: Client, name_and_description):
    response = client.update_transition(service.create_transition_id(), **name_and_description)
    logging.info(response)
    assert_transition(response)


@pytest.mark.parametrize('assets', [{'foo': service.create_asset_id()}])
def test_update_transition_parameters_manual(client: Client, assets):
    response = client.update_transition(
        service.create_transition_id(),
        assets=assets,
    )
    logging.info(response)
    assert_transition(response)


@pytest.mark.parametrize(('cpu', 'memory', 'image_url', 'secret_id'), [
    (256, 512, 'python3.8', service.create_secret_id()),
    (256, 1024, 'python3.9', service.create_secret_id()),
    (256, 512, 'python3.8', None),
    (256, 1024, 'python3.9', None),
])
@pytest.mark.parametrize(('environment', 'environment_secrets'), [
    (None, [service.create_secret_id(), service.create_secret_id()]),
    ({'foo': 'bar'}, None),
    ({'foo': 'bar'}, [service.create_secret_id(), service.create_secret_id()]),
    (None, None),
])
def test_update_transition_parameters_docker(
    client: Client,
    environment,
    environment_secrets,
    cpu,
    memory,
    image_url,
    secret_id,
):
    response = client.update_transition(
        service.create_transition_id(),
        environment=environment,
        environment_secrets=environment_secrets,
        cpu=cpu,
        memory=memory,
        image_url=image_url,
        secret_id=secret_id,
    )
    logging.info(response)
    assert_transition(response)


def test_execute_transition(client: Client):
    response = client.execute_transition(service.create_transition_id())
    logging.info(response)
    assert 'transitionId' in response, 'Missing transitionId in response'
    assert 'executionId' in response, 'Missing executionId in response'
    assert 'status' in response, 'Missing status in response'


@pytest.mark.parametrize('status,output,error', [
    ('succeeded', {'foo': 'bar'}, None),
    ('failed', None, {'message': 'foobar'}),
])
@pytest.mark.parametrize(
    'start_time', [
        datetime.utcnow().astimezone(timezone.utc),
        datetime.utcnow(),
        datetime.utcnow().astimezone(timezone.utc).isoformat(),
        None
    ])
def test_update_transition_execution(client: Client, status, output, error, start_time):
    transition_id = service.create_transition_id()
    execution_id = service.create_transition_execution_id()
    response = client.update_transition_execution(
        transition_id,
        execution_id,
        status,
        output=output,
        error=error,
        start_time=start_time,
    )
    logging.info(response)
    assert 'transitionId' in response, 'Missing transitionId in response'
    assert 'executionId' in response, 'Missing executionId in response'
    assert 'status' in response, 'Missing status in response'


def test_send_heartbeat(client: Client):
    transition_id = service.create_transition_id()
    execution_id = service.create_transition_execution_id()
    response = client.send_heartbeat(transition_id, execution_id)
    logging.info(response)
    assert response == {'Your request executed successfully': '204'}


def assert_transition(response):
    assert 'name' in response, 'Missing name in response'
    assert 'transitionId' in response, 'Missing transitionId in response'
    assert 'transitionType' in response, 'Missing transitionType in response'


@pytest.fixture
def execution_env():
    return {
        'TRANSITION_ID': 'xyz',
        'EXECUTION_ID': 'xyz',
    }


@patch('cradl.Client.get_transition_execution')
@patch('cradl.Client.update_transition_execution')
def test_transition_handler_updated_successfully(update_transition_exc, get_transition_exc, execution_env):
    output = {'result': 'All good'}

    @cradl.transition_handler
    def sample_handler(cradl_client: Client, event: dict):
        return output

    with patch.dict(cradl.os.environ, values=execution_env):
        sample_handler()

    update_transition_exc.assert_called_once_with(
        execution_id=execution_env['EXECUTION_ID'],
        transition_id=execution_env['TRANSITION_ID'],
        status='succeeded',
        output=ANY,
    )


@patch('cradl.Client.get_transition_execution')
@patch('cradl.Client.update_transition_execution')
def test_transition_handler_updated_on_failure(update_transition_exc, get_transition_exc, execution_env):
    @cradl.transition_handler
    def sample_handler(cradl_client: Client, event: dict):
        raise RuntimeError('Some error')

    with patch.dict(cradl.os.environ, values=execution_env):
        with pytest.raises(RuntimeError):
            sample_handler()

    update_transition_exc.assert_called_once_with(
        execution_id=execution_env['EXECUTION_ID'],
        transition_id=execution_env['TRANSITION_ID'],
        status='failed',
        error=ANY,
    )


@pytest.mark.parametrize('status', ['succeeded', 'rejected', 'failed'])
@patch('cradl.Client.get_transition_execution')
@patch('cradl.Client.update_transition_execution')
def test_transition_handler_custom_status(update_transition_exc, get_transition_exc, execution_env, status):
    result = 'Rejected task'
    status = 'rejected'

    @cradl.transition_handler
    def sample_handler(cradl_client: Client, event: dict):
        return result, status

    with patch.dict(cradl.os.environ, values=execution_env):
        if status == 'failed':
            with pytest.raises(RuntimeError):
                sample_handler()
        else:
            sample_handler()

    if status == 'succeeded':
        update_transition_exc.assert_called_once_with(
            execution_id=execution_env['EXECUTION_ID'],
            transition_id=execution_env['TRANSITION_ID'],
            status=status,
            output=result
        )
    else:
        update_transition_exc.assert_called_once_with(
            execution_id=execution_env['EXECUTION_ID'],
            transition_id=execution_env['TRANSITION_ID'],
            status=status,
            error=ANY,
    )
