import random

import pytest
from cradl.client import Client

from . import service


def assert_deployment_environment(deployment_environment):
    assert 'organizationId' in deployment_environment, 'Missing organizationId in deployment_environment'
    assert 'deploymentEnvironmentId' in deployment_environment, 'Missing deploymentEnvironmentId in deployment_environment'
    assert 'description' in deployment_environment, 'Missing description in deployment_environment'
    assert 'name' in deployment_environment, 'Missing name in deployment_environment'


def test_list_deployment_environments(client: Client):
    response = client.list_deployment_environments()
    assert 'deploymentEnvironments' in response, 'Missing deploymentEnvironments in response'
    for deployment_environment in response['deploymentEnvironments']:
        assert_deployment_environment(deployment_environment)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_deployment_environments_with_pagination(client: Client, max_results, next_token):
    response = client.list_deployment_environments(max_results=max_results, next_token=next_token)
    assert 'deploymentEnvironments' in response, 'Missing deploymentEnvironments in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for deployment_environment in response['deploymentEnvironments']:
        assert_deployment_environment(deployment_environment)


def test_get_deployment_environment(client: Client):
    deployment_environment_id = service.create_deployment_environment_id()
    deployment_environment = client.get_deployment_environment(deployment_environment_id)
    assert_deployment_environment(deployment_environment)
