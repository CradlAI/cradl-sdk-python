import random
import pytest
from cradl.client import Client

from . import service


def assert_action(action):
    assert 'actionId' in action, 'Missing actionId in action'
    assert 'functionId' in action, 'Missing functionId in action'


def test_create_action(client: Client):
    action = client.create_action(
        function_id=service.create_function_id(),
        name='Test Action',
        description='A test action',
        config={'foo': 'bar'},
    )
    assert_action(action)


def test_list_actions(client: Client):
    response = client.list_actions()
    assert 'actions' in response, 'Missing actions in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for action in response['actions']:
        assert_action(action)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_actions_with_pagination(client: Client, max_results, next_token):
    response = client.list_actions(max_results=max_results, next_token=next_token)
    assert 'actions' in response, 'Missing actions in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for action in response['actions']:
        assert_action(action)


def test_get_action(client: Client):
    action_id = service.create_action_id()
    action = client.get_action(action_id)
    assert_action(action)


def test_update_action(client: Client):
    action_id = service.create_action_id()
    action = client.update_action(action_id, name='Updated Action', enabled=True)
    assert_action(action)


def test_delete_action(client: Client):
    action_id = service.create_action_id()
    action = client.delete_action(action_id)
    assert_action(action)
