import random
import pytest
from cradl.client import Client

from . import service

def assert_validation_task(task):
    assert 'taskId' in task, 'Missing taskId in validation task'
    assert 'validationId' in task, 'Missing validationId in validation task'


def test_create_validation_task(client: Client):
    validation_id = service.create_validation_id()
    task = client.create_validation_task(validation_id, input={'foo': 'bar'})
    assert_validation_task(task)


def test_list_validation_tasks(client: Client):
    validation_id = service.create_validation_id()
    response = client.list_validation_tasks(validation_id)
    assert 'tasks' in response, 'Missing tasks in response'


@pytest.mark.parametrize('max_results,next_token', [
    (random.randint(1, 100), None),
    (random.randint(1, 100), 'foo'),
    (None, None),
])
def test_list_validation_tasks_with_pagination(client: Client, max_results, next_token):
    validation_id = service.create_validation_id()
    response = client.list_validation_tasks(validation_id, max_results=max_results, next_token=next_token)
    assert 'tasks' in response, 'Missing tasks in response'


def test_get_validation_task(client: Client):
    validation_id = service.create_validation_id()
    task_id = service.create_validation_task_id()
    task = client.get_validation_task(validation_id, task_id)
    assert_validation_task(task)


def test_update_validation_task(client: Client):
    validation_id = service.create_validation_id()
    task_id = service.create_validation_task_id()
    task = client.update_validation_task(validation_id, task_id, status='succeeded', output={'result': 'ok'})
    assert_validation_task(task)
