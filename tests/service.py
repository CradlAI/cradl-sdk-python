from pathlib import Path
from uuid import uuid4


def create_app_client_id():
    return f'las:app-client:{uuid4().hex}'


def create_asset_id():
    return f'las:asset:{uuid4().hex}'


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


def create_deployment_environment_id():
    return f'las:deployment-environment:{uuid4().hex}'


def create_plan_id():
    return f'las:plan:{uuid4().hex}'


def create_data_bundle_id():
    return f'las:model-data-bundle:{uuid4().hex}'


def create_training_id():
    return f'las:model-training:{uuid4().hex}'


def create_organization_id():
    return f'las:organization:{uuid4().hex}'



def create_secret_id():
    return f'las:secret:{uuid4().hex}'


def create_transition_id():
    return f'las:transition:{uuid4().hex}'


def create_transition_execution_id():
    return f'las:transition-execution:{uuid4().hex}'


def create_user_id():
    return f'las:user:{uuid4().hex}'


def create_workflow_id():
    return f'las:workflow:{uuid4().hex}'


def create_role_id():
    return f'las:role:{uuid4().hex}'


def create_workflow_execution_id():
    return f'las:workflow-execution:{uuid4().hex}'


def create_transformation_id():
    return f'las:dataset-transformation:{uuid4().hex}'


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
