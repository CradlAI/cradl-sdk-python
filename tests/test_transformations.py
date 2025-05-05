import logging
import random

import pytest
from cradl.client import Client

from . import service, util
from .util import assert_in_response


@pytest.mark.parametrize('operations', [[{'type': 'remove-duplicates', 'options': {}}]])
@pytest.mark.parametrize('dataset_id', [service.create_dataset_id()])
def test_create_transformation(client: Client, dataset_id, operations):
    response = client.create_transformation(dataset_id, operations)
    assert_transformation(response)


@pytest.mark.parametrize('status', [None, 'failed', 'succeeded', 'running'])
def test_list_transformations(client: Client, status):
    response = client.list_transformations(service.create_dataset_id(), status=status)
    for transformation in response['transformations']:
        assert_transformation(transformation)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_transformations_with_pagination(client: Client, max_results, next_token):
    response = client.list_transformations(service.create_dataset_id(), max_results=max_results, next_token=next_token)
    assert_in_response('transformations', response)
    assert_in_response('nextToken', response)
    for transformation in response['transformations']:
        assert_transformation(transformation)


def test_delete_transformation(client: Client):
    response = client.delete_transformation(service.create_dataset_id(), service.create_transformation_id())
    assert_transformation(response)


def assert_transformation(response):
    assert_in_response('transformationId', response)
    assert_in_response('datasetId', response)
    assert_in_response('operations', response)
    assert_in_response('createdBy', response)
    assert_in_response('createdTime', response)
    assert_in_response('status', response)
