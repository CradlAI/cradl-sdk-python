import pytest
from cradl.client import Client

from . import service


def test_get_log(client: Client):
    log_id = service.create_log_id()
    response = client.get_log(log_id)
    assert 'logId' in response, 'Missing logId in response'
    assert isinstance(response['events'], list), 'Missing list of events'
