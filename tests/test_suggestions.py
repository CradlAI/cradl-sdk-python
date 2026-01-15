import logging
import random
from pathlib import Path

import pytest
from cradl.client import Client

from . import service


def test_create_suggestion(client: Client):
    text = 'foobar'
    document_id = service.create_document_id()
    response = client.create_suggestion(text, document_id, 'raw')
    assert 'suggestion' in response, 'Missing suggestion in response'
