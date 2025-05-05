import logging
import random

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
@pytest.mark.parametrize('metadata', [util.metadata(), None])
def test_create_training(client: Client, name_and_description, metadata):
    data_bundle_ids = [service.create_data_bundle_id() for _ in range(10)]
    response = client.create_training(
        service.create_model_id(),
        data_bundle_ids,
        metadata=metadata,
        **name_and_description,
    )
    assert_training(response)


def test_get_training(client: Client):
    response = client.get_training(
        service.create_model_id(),
        service.create_training_id(),
    )
    assert_training(response)


def test_list_trainings(client: Client):
    response = client.list_trainings(service.create_model_id())
    assert 'trainings' in response, 'Missing dataBundles in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_trainings_with_pagination(client: Client, max_results, next_token):
    response = client.list_trainings(service.create_model_id(), max_results=max_results, next_token=next_token)
    assert 'trainings' in response, 'Missing dataBundles in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def assert_training(response):
    assert 'modelId' in response, 'Missing modelId in response'
    assert 'trainingId' in response, 'Missing trainingId in response'
    assert 'dataBundleIds' in response, 'Missing dataBundleIds in response'
    assert 'name' in response, 'Missing name in response'
    assert 'description' in response, 'Missing description in response'
    assert 'createdTime' in response, 'Missing createdTime in response'
