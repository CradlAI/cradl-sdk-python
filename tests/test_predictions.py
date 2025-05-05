import logging

import pytest
from cradl.client import Client, dictstrip

from . import service


@pytest.mark.parametrize('preprocess_config', [
    {'rotation': 0, 'autoRotate': True, 'maxPages': 1, 'imageQuality': 'LOW'},
    {'rotation': 90, 'autoRotate': False, 'maxPages': 2, 'imageQuality': 'HIGH'},
    {'rotation': 180, 'autoRotate': None, 'maxPages': 3, 'imageQuality': None},
    {'rotation': 270, 'autoRotate': True, 'maxPages': None, 'imageQuality': 'HIGH'},
    {'rotation': None, 'autoRotate': False, 'pages': [0, 1, -1], 'imageQuality': 'LOW'},
    None,
])
@pytest.mark.parametrize('postprocess_config', [
    {'strategy': 'BEST_FIRST', 'outputFormat': 'v2'},
    {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3}},
    {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3, 'collapse': False}},
    None,
])
@pytest.mark.parametrize('run_async', [True, False, None])
def test_create_prediction(client: Client, preprocess_config, postprocess_config, run_async):
    document_id = service.create_document_id()
    model_id = service.create_model_id()
    response = client.create_prediction(
        document_id,
        model_id,
        preprocess_config=dictstrip(preprocess_config) if preprocess_config else None,
        postprocess_config=postprocess_config,
        run_async=run_async,
    )
    assert 'predictionId' in response, 'Missing predictionId in response'


@pytest.mark.parametrize('sort_by', ['createdTime', None])
@pytest.mark.parametrize('order', ['ascending', 'descending', None])
@pytest.mark.parametrize('model_id', [service.create_model_id(), None])
def test_list_predictions(client: Client, sort_by, order, model_id):
    response = client.list_predictions(sort_by=sort_by, order=order, model_id=model_id)
    logging.info(response)
    assert 'predictions' in response, 'Missing predictions in response'


@pytest.mark.parametrize('prediction_id', [service.create_prediction_id(), None])
def test_get_prediction(client: Client, prediction_id):
    response = client.get_prediction(prediction_id)
    logging.info(response)
    assert 'predictionId' in response, 'Missing prediction in response'
    assert 'inferenceTime' in response, 'Missing inferenceTime in response'
    assert 'predictions' in response, 'Missing predictions in response'
