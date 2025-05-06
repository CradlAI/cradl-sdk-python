from json.decoder import JSONDecodeError

from .log import setup_logging


logger = setup_logging(__name__)


def decode_response(response, return_json=True):
    try:
        response.raise_for_status()
        if return_json:
            return response.json()
        else:
            return response.content
    except JSONDecodeError as e:

        if response.status_code == 204:
            return {'Your request executed successfully': '204'}

        logger.error('Status code {} body:\n{}'.format(response.status_code, response.text))
        raise e
    except Exception as e:
        logger.error('Status code {} body:\n{}'.format(response.status_code, response.text))

        if response.status_code == 400:
            message = response.json().get('message', response.text)
            raise BadRequest(message)

        if response.status_code == 403 and 'Forbidden' in response.json().values():
            raise InvalidCredentialsException('Credentials provided are not valid.')

        if response.status_code == 404:
            message = response.json().get('message', response.text)
            raise NotFound(message)

        if response.status_code == 429 and 'Too Many Requests' in response.json().values():
            raise TooManyRequestsException('You have reached the limit of requests per second.')

        if response.status_code == 429 and 'Limit Exceeded' in response.json().values():
            raise LimitExceededException('You have reached the limit of total requests per month.')

        raise e


class EmptyRequestError(ValueError):
    """An EmptyRequestError is raised if the request body is empty when expected not to be empty."""
    pass


class ClientException(Exception):
    """A ClientException is raised if the client refuses to
    send request due to incorrect usage or bad request data."""
    pass


class InvalidCredentialsException(ClientException):
    """An InvalidCredentialsException is raised if api key, access key id or secret access key is invalid."""
    pass


class TooManyRequestsException(ClientException):
    """A TooManyRequestsException is raised if you have reached the number of requests per second limit
    associated with your credentials."""
    pass


class LimitExceededException(ClientException):
    """A LimitExceededException is raised if you have reached the limit of total requests per month
    associated with your credentials."""
    pass


class BadRequest(ClientException):
    """BadRequest is raised if you have made a request that is disqualified based on the input"""
    pass


class NotFound(ClientException):
    """NotFound is raised when you try to access a resource that is not found"""
    pass


class FileFormatException(ClientException):
    """A FileFormatException is raised if the file format is not supported by the api."""
    pass
