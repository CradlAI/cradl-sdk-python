import logging
import random

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_secret(client: Client, name_and_description):
    data = {'username': 'foo', 'password': 'bar'}
    response = client.create_secret(data, **name_and_description)
    assert 'secretId' in response, 'Missing secretId in response'


def test_list_secrets(client: Client):
    response = client.list_secrets()
    logging.info(response)
    assert 'secrets' in response, 'Missing secrets in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_secrets_with_pagination(client: Client, max_results, next_token):
    response = client.list_secrets(max_results=max_results, next_token=next_token)
    assert 'secrets' in response, 'Missing secrets in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_update_secret(client: Client, name_and_description):
    secret_id = service.create_secret_id()
    data = {'username': 'foo', 'password': 'bar'}
    response = client.update_secret(secret_id, data=data, **name_and_description)
    assert 'secretId' in response, 'Missing secretId in response'


def test_delete_secret(client: Client):
    secret_id = service.create_secret_id()
    response = client.delete_secret(secret_id)
    assert 'secretId' in response, 'Missing secretId in response'

