import random
import pytest
from cradl.client import Client

from . import service

def assert_hook(hook):
    assert 'hookId' in hook, 'Missing hookId in hook'
    assert 'name' in hook, 'Missing name in hook'
    assert 'trigger' in hook, 'Missing trigger in hook'

def test_create_hook(client: Client):
    hook = client.create_hook(
        trigger='on_event',
        name='Test Hook',
        description='A test hook',
        config={'foo': 'bar'},
    )
    assert_hook(hook)

def test_list_hooks(client: Client):
    response = client.list_hooks()
    assert 'hooks' in response, 'Missing hooks in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for hook in response['hooks']:
        assert_hook(hook)

@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_hooks_with_pagination(client: Client, max_results, next_token):
    response = client.list_hooks(max_results=max_results, next_token=next_token)
    assert 'hooks' in response, 'Missing hooks in response'
    assert 'nextToken' in response, 'Missing nextToken in response'
    for hook in response['hooks']:
        assert_hook(hook)

def test_get_hook(client: Client):
    hook_id = 'las:hook:dummyid'
    hook = client.get_hook(hook_id)
    assert_hook(hook)

def test_update_hook(client: Client):
    hook_id = 'las:hook:dummyid'
    hook = client.update_hook(hook_id, name='Updated Hook', enabled=True)
    assert_hook(hook)

def test_delete_hook(client: Client):
    hook_id = 'las:hook:dummyid'
    hook = client.delete_hook(hook_id)
    assert_hook(hook)

