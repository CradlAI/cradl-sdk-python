import random
import pytest
from cradl.client import Client

from . import service


def assert_validation(validation):
    assert 'validationId' in validation, 'Missing validationId in validation'
    assert 'name' in validation, 'Missing name in validation'


def test_create_validation(client: Client):
    validation = client.create_validation(
        name='Test Validation',
        description='A test validation',
        config={'foo': 'bar'},
    )
    assert_validation(validation)


def test_list_validations(client: Client):
    response = client.list_validations()
    assert 'validations' in response, 'Missing validations in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for validation in response['validations']:
        assert_validation(validation)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_validations_with_pagination(client: Client, max_results, next_token):
    response = client.list_validations(max_results=max_results, next_token=next_token)
    assert 'validations' in response, 'Missing validations in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for validation in response['validations']:
        assert_validation(validation)


def test_get_validation(client: Client):
    validation_id = service.create_validation_id()
    validation = client.get_validation(validation_id)
    assert_validation(validation)


def test_update_validation(client: Client):
    validation_id = service.create_validation_id()
    validation = client.update_validation(validation_id, config={'foo': 'bar'})
    assert_validation(validation)


def test_delete_validation(client: Client):
    validation_id = service.create_validation_id()
    validation = client.delete_validation(validation_id)
    assert_validation(validation)
