import random

import pytest
from cradl.client import Client

from . import service


def test_get_role(client: Client):
    role_id = service.create_role_id()
    response = client.get_role(role_id)
    assert_role(response)


def test_list_roles(client: Client):
    response = client.list_roles()
    assert 'roles' in response, 'Missing roles in response'
    for role in response['roles']:
        assert_role(role)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_roles_with_pagination(client: Client, max_results, next_token):
    response = client.list_roles(max_results=max_results, next_token=next_token)
    assert 'roles' in response, 'Missing roles in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for role in response['roles']:
        assert_role(role)


def assert_role(role):
    assert 'roleId' in role, 'Missing roleId in role'
    assert 'createdBy' in role, 'Missing createdBy in role'
    assert 'createdTime' in role, 'Missing createdTime in role'
    assert 'description' in role, 'Missing description in role'
    assert 'name' in role, 'Missing name in role'
    assert 'permissions' in role, 'Missing permissions in role'
    assert 'updatedBy' in role, 'Missing updatedBy in role'
    assert 'updatedTime' in role, 'Missing updatedTime in role'
