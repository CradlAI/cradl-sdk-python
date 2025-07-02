import random

import pytest
from cradl.client import Client

from . import service


def assert_user(user):
    assert 'userId' in user, 'Missing userId in user'
    assert 'profileId' in user, 'Missing profileId in user'
    assert 'roleIds' in user, 'Missing roleIds in user'


def test_create_user(client: Client):
    email = 'foo@bar.com'
    user = client.create_user(
        email,
        app_client_id=service.create_app_client_id(),
        role_ids=[service.create_role_id()],
    )
    assert_user(user)


def test_list_users(client: Client):
    response = client.list_users()
    assert 'users' in response, 'Missing users in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for user in response['users']:
        assert_user(user)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_users_with_pagination(client: Client, max_results, next_token):
    response = client.list_users(max_results=max_results, next_token=next_token)
    assert 'users' in response, 'Missing users in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for user in response['users']:
        assert_user(user)


def test_get_user(client: Client):
    user_id = service.create_user_id()
    user = client.get_user(user_id)
    assert_user(user)


def test_update_user(client: Client):
    user_id = service.create_user_id()
    user = client.update_user(user_id, role_ids=[service.create_role_id()])
    assert_user(user)


def test_delete_user(client: Client):
    user_id = service.create_user_id()
    user = client.delete_user(user_id)
    assert_user(user)
