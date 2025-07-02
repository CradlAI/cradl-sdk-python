import logging
import random

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
@pytest.mark.parametrize('metadata', [util.metadata(), None])
def test_create_dataset(client: Client, name_and_description, metadata):
    response = client.create_dataset(**name_and_description, metadata=metadata)
    assert_dataset(response)


def test_list_datasets(client: Client):
    response = client.list_datasets()
    logging.info(response)
    assert 'datasets' in response, 'Missing datasets in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_datasets_with_pagination(client: Client, max_results, next_token):
    response = client.list_datasets(max_results=max_results, next_token=next_token)
    assert 'datasets' in response, 'Missing datasets in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_delete_dataset(client: Client):
    dataset_id = service.create_dataset_id()
    response = client.delete_dataset(dataset_id)
    assert_dataset(response)


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(at_least_one=True))
@pytest.mark.parametrize('metadata', [util.metadata(), None])
def test_update_dataset(client: Client, name_and_description, metadata):
    response = client.update_dataset(service.create_dataset_id(), metadata=metadata, **name_and_description)
    assert_dataset(response)


def assert_dataset(response):
    assert 'datasetId' in response, 'Missing datasetId in response'
    assert 'name' in response, 'Missing name in response'
    assert 'description' in response, 'Missing description in response'
    assert 'createdTime' in response, 'Missing createdTime in response'
    assert 'updatedTime' in response, 'Missing updatedTime in response'
    assert 'version' in response, 'Missing version in response'
