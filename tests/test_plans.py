import random

import pytest
from cradl.client import Client

from . import service


def assert_plan(plan):
    assert 'organizationId' in plan, 'Missing organizationId in plan'
    assert 'planId' in plan, 'Missing planId in plan'
    assert 'currency' in plan, 'Missing currency in plan'
    assert 'description' in plan, 'Missing description in plan'
    assert 'latest' in plan, 'Missing latest in plan'
    assert 'name' in plan, 'Missing name in plan'


def test_list_plans(client: Client):
    response = client.list_plans()
    assert 'plans' in response, 'Missing plans in response'
    for plan in response['plans']:
        assert_plan(plan)


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_plans_with_pagination(client: Client, max_results, next_token):
    response = client.list_plans(max_results=max_results, next_token=next_token)
    assert 'plans' in response, 'Missing plans in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for plan in response['plans']:
        assert_plan(plan)


def test_get_plan(client: Client):
    plan_id = service.create_plan_id()
    plan = client.get_plan(plan_id)
    assert_plan(plan)
