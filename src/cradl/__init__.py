import json
import logging
import os
import traceback

from .client import Client
from .credentials import Credentials

__all__ = [
    'Client',
    'Credentials',
]

logging.getLogger(__name__).addHandler(logging.NullHandler())


def transition_handler(f):
    """
    Decorator used to manage transition states. The decorator assumes that the environment variables TRANSITION_ID and EXECUTION_ID exist,
    and ensures that the transition execution is updated after the handler is invoked. The return value of the handler can either be a `result`
    or a tuple `(result, status)`. If no status is provided, the handler is assumed to have run successfully. If the handler throws an exception,
    the status of the transition execution will be set to 'failed'. Status must be one of 'succeeded', 'rejected', 'retry' or 'failed'.

    >>> @transition_handler
    >>> def my_handler(las_client: las.Client, event: dict):
    >>>     prediction = las_client.create_prediction(
    >>>         document_id=event['documentId'],
    >>>         model_id=['modelId']
    >>>     )
    >>>
    >>>     return las_client.create_prediction()
    >>>
    >>>
    >>> if __name__ == '__main__':
    >>>     my_handler()

    :param f: The handler to wrap.
    :type f: Callable[[las.Client, dict], dict]
    :return: The wrapped callable.
    :type: Callable[[], dict]

    """

    def g():
        las_client = Client()

        transition_id = os.environ['TRANSITION_ID']
        execution_id = os.environ['EXECUTION_ID']
        logging.info(f'Execute {execution_id} of transition {transition_id}')
        error_messsage_max_len = 4096

        try:
            execution = las_client.get_transition_execution(transition_id, execution_id=execution_id)
            result = f(las_client, execution['input'])

            try:
                output, status = result
            except ValueError:
                output, status = result, 'succeeded'

            if status == 'succeeded':
                params = {'output': output}
            else:
                message = output if isinstance(output, str) else json.dumps(output, indent=2)
                params = {'error': {'message': message[:error_messsage_max_len]}}

            las_client.update_transition_execution(
                transition_id=transition_id,
                execution_id=execution_id,
                status=status,
                **params,
            )
        except Exception as e:
            logging.exception(e)

            las_client.update_transition_execution(
                transition_id=transition_id,
                execution_id=execution_id,
                status='failed',
                error={'message': traceback.format_exc()[-error_messsage_max_len:]}
            )

            raise

    return g
