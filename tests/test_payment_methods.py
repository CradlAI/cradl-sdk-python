import logging
import random

import pytest
from cradl.client import Client

from . import service, util


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations())
def test_create_payment_method(client: Client, name_and_description):
    response = client.create_payment_method(**name_and_description)
    assert_payment_method(response)


def test_list_payment_methods(client: Client):
    response = client.list_payment_methods()
    logging.info(response)
    assert 'paymentMethods' in response, 'Missing payment_methods in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_payment_methods_with_pagination(client: Client, max_results, next_token):
    response = client.list_payment_methods(max_results=max_results, next_token=next_token)
    assert 'paymentMethods' in response, 'Missing payment_methods in response'
    assert 'nextToken' in response, 'Missing nextToken in response'


def test_delete_payment_method(client: Client):
    payment_method_id = service.create_payment_method_id()
    response = client.delete_payment_method(payment_method_id)
    assert_payment_method(response)


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(at_least_one=True))
def test_update_payment_method(client: Client, name_and_description):
    response = client.update_payment_method(service.create_payment_method_id(), **name_and_description)
    assert_payment_method(response)


def assert_payment_method(response):
    assert 'paymentMethodId' in response, 'Missing paymentMethodId in response'
    assert 'createdBy' in response, 'Missing createdBy in response'
    assert 'createdTime' in response, 'Missing createdTime in response'
    assert 'description' in response, 'Missing description in response'
    assert 'details' in response, 'Missing details in response'
    assert 'name' in response, 'Missing name in response'
    assert 'updatedBy' in response, 'Missing updatedBy in response'
    assert 'updatedTime' in response, 'Missing updatedTime in response'
