import logging
import random

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('preprocess_config', [service.preprocess_config(), None])
@pytest.mark.parametrize('postprocess_config', [service.postprocess_config(), None])
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
@pytest.mark.parametrize('metadata', [util.metadata(), None])
@pytest.mark.parametrize('base_model', [
    {'organizationId': service.create_organization_id(), 'modelId': service.create_model_id()},
    None,
])
def test_create_model(
    client: Client,
    preprocess_config,
    postprocess_config,
    name_and_description,
    metadata,
    base_model,
):
    response = client.create_model(
        field_config=service.field_config(),
        preprocess_config=preprocess_config,
        postprocess_config=postprocess_config,
        metadata=metadata,
        base_model=base_model,
        **name_and_description,
    )
    logging.info(response)
    assert_model(response)


@pytest.mark.parametrize('owner', [[service.create_organization_id()], None])
def test_list_models(client: Client, owner):
    response = client.list_models(owner=owner)
    logging.info(response)
    assert 'models' in response, 'Missing models in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_models_with_pagination(client: Client, max_results, next_token):
    response = client.list_models(max_results=max_results, next_token=next_token)
    logging.info(response)
    assert 'models' in response, 'Missing models in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_get_model(client: Client):
    response = client.get_model(service.create_model_id())
    logging.info(response)
    assert_model(response)


@pytest.mark.parametrize('preprocess_config', [service.preprocess_config(), None])
@pytest.mark.parametrize('postprocess_config', [service.postprocess_config(), None])
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
@pytest.mark.parametrize('metadata', [util.metadata(), None])
def test_update_model(client: Client, preprocess_config, postprocess_config, name_and_description, metadata):
    response = client.update_model(
        service.create_model_id(),
        field_config=service.field_config(),
        metadata=metadata,
        preprocess_config=preprocess_config,
        postprocess_config=postprocess_config,
        **name_and_description,
    )
    logging.info(response)
    assert_model(response)


def assert_model(response):
    assert 'name' in response, 'Missing name in response'
    assert 'modelId' in response, 'Missing modelId in response'
    assert 'status' in response, 'Missing status in response'
    assert 'preprocessConfig' in response, 'Missing preprocessConfig in response'
    assert 'fieldConfig' in response, 'Missing fieldConfig in response'
    assert 'description' in response, 'Missing description in response'


def test_delete_model(client: Client):
    model_id = service.create_model_id()
    response = client.delete_model(model_id)
    assert 'modelId' in response, 'Missing modelId in response'


