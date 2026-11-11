import random
import warnings

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.skip(reason='This resource is currently not intended for use with the new API')
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_app_client(client: Client, name_and_description):
    response = client.create_app_client(role_ids=[service.create_role_id()], **name_and_description)
    assert_app_client(response)


@pytest.mark.skip(reason='This resource is currently not intended to use in the new API')
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_app_client_without_secret(client: Client, name_and_description):
    response = client.create_app_client(
        **name_and_description,
        generate_secret=False,
        callback_urls=['http://localhost:3000/authCallback'],
        logout_urls=['http://localhost:3000/logout'],
        login_urls=['http://localhost:3000/login'],
        default_login_url='http://localhost:3000/login',
    )
    assert_app_client(response)


def test_login_logout_and_callback_urls_are_deprecated(client: Client, sent):
    """They still reach the API, which still accepts them"""
    urls = {
        'callback_urls': ['http://localhost:3000/authCallback'],
        'logout_urls': ['http://localhost:3000/logout'],
        'login_urls': ['http://localhost:3000/login'],
        'default_login_url': 'http://localhost:3000/login',
    }
    deprecated = 'logout_urls, callback_urls, login_urls, default_login_url are deprecated'
    with pytest.warns(DeprecationWarning, match=deprecated):
        client.create_app_client(generate_secret=False, **urls)
    assert sent[0][2] == {
        'callbackUrls': urls['callback_urls'],
        'logoutUrls': urls['logout_urls'],
        'loginUrls': urls['login_urls'],
        'defaultLoginUrl': urls['default_login_url'],
        'generateSecret': False,
    }


def test_an_app_client_with_a_secret_does_not_warn(client: Client, sent):
    with warnings.catch_warnings():
        warnings.simplefilter('error', DeprecationWarning)
        client.create_app_client(name='Integration')
    assert sent[0][2] == {'name': 'Integration', 'generateSecret': True}


@pytest.mark.skip(reason='This resource is currently not intended to use in the new API')
def test_list_app_clients(client: Client):
    response = client.list_app_clients()
    assert 'appClients' in response, 'Missing appClients in response'


@pytest.mark.skip(reason='This resource is currently not intended to use in the new API')
@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_app_clients_with_pagination(client: Client, max_results, next_token):
    response = client.list_app_clients(max_results=max_results, next_token=next_token)
    assert 'appClients' in response, 'Missing appClients in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


@pytest.mark.skip(reason='This resource is currently not intended to use in the new API')
def test_delete_app_client(client: Client):
    app_client_id = service.create_app_client_id()
    response = client.delete_app_client(app_client_id)
    assert_app_client(response)


@pytest.mark.skip(reason='This resource is currently not intended to use in the new API')
@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(at_least_one=True))
def test_update_app_client(client: Client, name_and_description):
    response = client.update_app_client(
        app_client_id=service.create_app_client_id(),
        role_ids=[service.create_role_id()],
        **name_and_description,
    )
    assert_app_client(response)


def assert_app_client(response):
    assert 'appClientId' in response, 'Missing appClientId in response'
    assert 'name' in response, 'Missing name in response'
    assert 'description' in response, 'Missing description in response'


@pytest.mark.skip(reason='This resource is currently not intended to use in the new API')
def test_get_app_client(client: Client):
    app_client_id = service.create_app_client_id()
    response = client.get_app_client(app_client_id)
    assert_app_client(response)
