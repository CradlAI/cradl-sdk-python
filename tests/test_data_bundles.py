import logging
import random

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_data_bundle(client: Client, name_and_description):
    dataset_ids = [service.create_dataset_id() for _ in range(10)]
    response = client.create_data_bundle(service.create_model_id(), dataset_ids, **name_and_description)
    assert_data_bundle(response)


def test_get_data_bundle(client: Client):
    response = client.get_data_bundle(
        service.create_model_id(),
        service.create_data_bundle_id(),
    )
    assert_data_bundle(response)


def test_list_data_bundles(client: Client):
    response = client.list_data_bundles(service.create_model_id())
    logging.info(response)
    assert 'dataBundles' in response, 'Missing dataBundles in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_data_bundles_with_pagination(client: Client, max_results, next_token):
    response = client.list_data_bundles(service.create_model_id(), max_results=max_results, next_token=next_token)
    assert 'dataBundles' in response, 'Missing dataBundles in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_delete_data_bundle(client: Client):
    response = client.delete_data_bundle(service.create_model_id(), service.create_data_bundle_id())
    assert_data_bundle(response)


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(at_least_one=True))
def test_update_data_bundle(client: Client, name_and_description):
    response = client.update_data_bundle(
        model_id=service.create_model_id(),
        data_bundle_id=service.create_data_bundle_id(),
        **name_and_description
    )
    assert_data_bundle(response)


def assert_data_bundle(response):
    assert 'modelId' in response, 'Missing modelId in response'
    assert 'dataBundleId' in response, 'Missing dataBundleId in response'
    assert 'name' in response, 'Missing name in response'
    assert 'description' in response, 'Missing description in response'
    assert 'createdTime' in response, 'Missing createdTime in response'
    assert 'status' in response, 'Missing status in response'
