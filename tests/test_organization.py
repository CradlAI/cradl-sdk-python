import logging

import pytest
from cradl.client import Client

from . import util


def test_get_organization(client: Client):
    response = client.get_organization('me')
    logging.info(response)
    assert_organization(response)


@pytest.mark.parametrize('name_and_description', util.name_and_description_combinations(at_least_one=True))
def test_update_organization(client: Client, name_and_description):
    response = client.update_organization(
        'me',
        **name_and_description,
    )
    logging.info(response)
    assert_organization(response)


def assert_organization(response):
    assert 'organizationId' in response, 'Missing organizationId in response'
    assert 'name' in response, 'Missing name in response'
    assert 'description' in response, 'Missing description in response'
    assert 'numberOfAppClientsAllowed' in response, 'Missing numberOfAppClientsAllowed in response'
    assert 'numberOfAppClientsCreated' in response, 'Missing numberOfAppClientsCreated in response'
    assert 'numberOfAssetsAllowed' in response, 'Missing numberOfAssetsAllowed in response'
    assert 'numberOfAssetsCreated' in response, 'Missing numberOfAssetsCreated in response'
    assert 'numberOfModelsAllowed' in response, 'Missing numberOfModelsAllowed in response'
    assert 'numberOfModelsCreated' in response, 'Missing numberOfModelsCreated in response'
    assert 'numberOfSecretsAllowed' in response, 'Missing numberOfSecretsAllowed in response'
    assert 'numberOfSecretsCreated' in response, 'Missing numberOfSecretsCreated in response'
    assert 'numberOfTransitionsAllowed' in response, 'Missing numberOfTransitionsAllowed in response'
    assert 'numberOfTransitionsCreated' in response, 'Missing numberOfTransitionsCreated in response'
    assert 'numberOfUsersAllowed' in response, 'Missing numberOfUsersAllowed in response'
    assert 'numberOfUsersCreated' in response, 'Missing numberOfUsersCreated in response'
    assert 'numberOfWorkflowsAllowed' in response, 'Missing numberOfWorkflowsAllowed in response'
    assert 'numberOfWorkflowsCreated' in response, 'Missing numberOfWorkflowsCreated in response'
    assert 'monthlyNumberOfDocumentsAllowed' in response, 'Missing monthlyNumberOfDocumentsAllowed in response'
    assert 'monthlyNumberOfDocumentsCreated' in response, 'Missing monthlyNumberOfDocumentsCreated in response'
    assert 'monthlyNumberOfPredictionsAllowed' in response, 'Missing monthlyNumberOfPredictionsAllowed in response'
    assert 'monthlyNumberOfPredictionsCreated' in response, 'Missing monthlyNumberOfPredictionsCreated in response'
    assert 'monthlyNumberOfTransitionExecutionsAllowed' in response, 'Missing monthlyNumberOfTransitionExecutionsAllowed in response'
    assert 'monthlyNumberOfTransitionExecutionsCreated' in response, 'Missing monthlyNumberOfTransitionExecutionsCreated in response'
    assert 'monthlyNumberOfWorkflowExecutionsAllowed' in response, 'Missing monthlyNumberOfWorkflowExecutionsAllowed in response'
    assert 'monthlyNumberOfWorkflowExecutionsCreated' in response, 'Missing monthlyNumberOfWorkflowExecutionsCreated in response'
    assert 'monthlyUsageSummary' in response, 'Missing monthlyUsageSummary in response'

