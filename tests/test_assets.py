import logging
import random
from pathlib import Path

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_asset(client: Client, name_and_description):
    content = Path('tests/remote_component.js').read_bytes()
    response = client.create_asset(content, **name_and_description)
    assert 'assetId' in response, 'Missing assetId in response'


def test_list_assets(client: Client):
    response = client.list_assets()
    logging.info(response)
    assert 'assets' in response, 'Missing assets in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_assets_with_pagination(client: Client, max_results, next_token):
    response = client.list_assets(max_results=max_results, next_token=next_token)
    assert 'assets' in response, 'Missing assets in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_get_asset(client: Client):
    asset_id = service.create_asset_id()
    response = client.get_asset(asset_id)
    assert 'assetId' in response, 'Missing assetId in response'
    assert 'content' in response, 'Missing content in response'


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_update_asset(client: Client, name_and_description):
    asset_id = service.create_asset_id()
    content = Path('tests/remote_component.js').read_bytes()
    response = client.update_asset(asset_id, content=content, **name_and_description)
    assert 'assetId' in response, 'Missing assetId in response'


def test_delete_asset(client: Client):
    asset_id = service.create_asset_id()
    response = client.delete_asset(asset_id)
    assert 'assetId' in response, 'Missing assetId in response'
    assert 'content' in response, 'Missing content in response'

