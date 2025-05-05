from pathlib import Path
from uuid import uuid4


def create_app_client_id():
    return f'cradl:app-client:{uuid4().hex}'


def create_asset_id():
    return f'cradl:asset:{uuid4().hex}'


def create_dataset_id():
    return f'cradl:dataset:{uuid4().hex}'


def create_consent_id():
    return f'cradl:consent:{uuid4().hex}'


def create_document_id():
    return f'cradl:document:{uuid4().hex}'


def create_log_id():
    return f'cradl:log:{uuid4().hex}'


def create_model_id():
    return f'cradl:model:{uuid4().hex}'


def create_payment_method_id():
    return f'cradl:payment-method:{uuid4().hex}'


def create_prediction_id():
    return f'cradl:prediction:{uuid4().hex}'


def create_deployment_environment_id():
    return f'cradl:deployment-environment:{uuid4().hex}'


def create_plan_id():
    return f'cradl:plan:{uuid4().hex}'


def create_data_bundle_id():
    return f'cradl:model-data-bundle:{uuid4().hex}'


def create_training_id():
    return f'cradl:model-training:{uuid4().hex}'


def create_organization_id():
    return f'cradl:organization:{uuid4().hex}'



def create_secret_id():
    return f'cradl:secret:{uuid4().hex}'


def create_transition_id():
    return f'cradl:transition:{uuid4().hex}'


def create_transition_execution_id():
    return f'cradl:transition-execution:{uuid4().hex}'


def create_user_id():
    return f'cradl:user:{uuid4().hex}'


def create_workflow_id():
    return f'cradl:workflow:{uuid4().hex}'


def create_role_id():
    return f'cradl:role:{uuid4().hex}'


def create_workflow_execution_id():
    return f'cradl:workflow-execution:{uuid4().hex}'


def create_transformation_id():
    return f'cradl:dataset-transformation:{uuid4().hex}'


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
