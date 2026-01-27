from pathlib import Path
from uuid import uuid4


def create_app_client_id():
    return f'las:app-client:{uuid4().hex}'


def create_dataset_id():
    return f'las:dataset:{uuid4().hex}'


def create_consent_id():
    return f'las:consent:{uuid4().hex}'


def create_document_id():
    return f'las:document:{uuid4().hex}'


def create_log_id():
    return f'las:log:{uuid4().hex}'


def create_model_id():
    return f'las:model:{uuid4().hex}'


def create_payment_method_id():
    return f'las:payment-method:{uuid4().hex}'


def create_prediction_id():
    return f'las:prediction:{uuid4().hex}'


def create_plan_id():
    return f'las:plan:{uuid4().hex}'


def create_organization_id():
    return f'las:organization:{uuid4().hex}'


def create_secret_id():
    return f'las:secret:{uuid4().hex}'


def create_user_id():
    return f'las:user:{uuid4().hex}'


def create_role_id():
    return f'las:role:{uuid4().hex}'


def create_error_config():
    return {'email': 'foo@bar.com'}


def create_email_config():
    return {
        'additionalWorkflowInput': {'foo': 'bar'},
        'allowedOrigins': ['.+', 'foobar@myemaildomain.com'],
        'secretId': create_secret_id(),
    }


def create_completed_config():
    return {
        'imageUrl': 'my/docker:image',
        'secretId': create_secret_id(),
        'environment': {'FOO': 'BAR'},
        'environmentSecrets': [create_secret_id()],
    }


def field_config():
    return {
        'total': {
            'description': 'the total amount of the receipt',
            'type': 'amount',
            'maxLength': 10,
        },
        'due_date': {
            'description': 'the due date of the invoice',
            'type': 'date',
            'maxLength': 10,
        },
    }


def preprocess_config():
    return {
        'imageQuality': 'HIGH',
        'autoRotate': False,
        'maxPages': 3,
    }


def postprocess_config():
    return {
        'strategy': 'BEST_N_PAGES',
        'outputFormat': 'v2',
        'parameters': {'n': 3, 'collapse': True},
    }


def document_path():
    return Path(__file__)


def create_action_id():
    return f'cradl:action:{uuid4().hex}'


def create_action_run_id():
    return f'cradl:action-run:{uuid4().hex}'


def create_hook_id():
    return f'cradl:hook:{uuid4().hex}'


def create_hook_run_id():
    return f'cradl:hook-run:{uuid4().hex}'


def create_validation_id():
    return f'cradl:validation:{uuid4().hex}'


def create_validation_task_id():
    return f'cradl:validation-task:{uuid4().hex}'


def create_agent_id():
    return f'cradl:agent:{uuid4().hex}'


def create_agent_run_id():
    return f'cradl:agent-run:{uuid4().hex}'


def create_function_id():
    return f'cradl:function:{uuid4().hex}'
