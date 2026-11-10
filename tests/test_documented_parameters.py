"""Parameters of the API reference that methods take by name, sent to the mock API, which validates them"""
from uuid import uuid4

import pytest
from cradl.client import Client

from . import service


@pytest.mark.parametrize('method, args, kwargs', [
    ('update_document', [service.create_document_id()], {
        'name': 'Invoice', 'description': 'An invoice', 'retention_in_days': 30,
    }),
    ('create_prediction', [service.create_document_id(), service.create_model_id()], {
        'name': 'Prediction', 'metadata': {'a': 1},
    }),
    ('create_document', [b'%PDF-1.4'], {'content_type': 'application/pdf'}),
    ('create_model', [service.field_config()], {'llm_version': 'sonnet-5', 'confidence_version': 'v2'}),
    ('update_model', [service.create_model_id()], {'llm_version': 'haiku-5.5', 'confidence_version': 'v1'}),
    ('create_action', [service.create_function_id()], {'connection_id': f'cradl:connection:{uuid4().hex}'}),
    ('update_action', [service.create_action_id()], {'connection_id': f'cradl:connection:{uuid4().hex}'}),
    ('create_action_run', [service.create_action_id(), {'a': 1}], {'no_agent_run_update': True}),
    ('update_hook_run', [service.create_hook_id(), service.create_hook_run_id()], {
        'status': 'succeeded', 'output': {'a': 1},
    }),
    ('update_organization', ['me'], {'url': 'https://example.com', 'metadata': {'a': 1}}),
    ('create_user', ['foo@example.com'], {'app_client_id': service.create_app_client_id()}),
    ('update_app_client', [service.create_app_client_id()], {
        'login_urls': ['https://example.com/login'], 'default_login_url': 'https://example.com/login',
    }),
    ('list_logs', [], {'order': 'descending'}),
])
def test_documented_parameters(static_client: Client, method, args, kwargs):
    assert isinstance(getattr(static_client, method)(*args, **kwargs), dict)
