import io
import json
import warnings
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib.parse import urlparse, quote

import requests  # type: ignore
from requests.exceptions import RequestException  # type: ignore

from .backoff import exponential_backoff, fatal_code
from .content import parse_content
from .credentials import Credentials, guess_credentials
from .log import setup_logging
from .response import decode_response, TooManyRequestsException, EmptyRequestError

logger = setup_logging(__name__)
Content = Union[bytes, bytearray, str, Path, io.IOBase]
Queryparam = Union[str, List[str]]


def datetimestr(d: Optional[Union[str, datetime]]) -> Optional[str]:
    if isinstance(d, datetime):
        if not d.tzinfo:
            d = d.astimezone()
        return d.isoformat()
    return d


def _warn_app_client_urls(names: List[str]):
    warnings.warn(
        f'{", ".join(names)} {"is" if len(names) == 1 else "are"} deprecated: login, logout and callback urls only '
        'configure the public app clients of organizations that sign in with Cognito',
        DeprecationWarning,
        stacklevel=3,
    )


class _Unset:
    """The default of a parameter where None is a value, which clears the field: an argument that wasn't given"""
    def __repr__(self):
        return 'UNSET'


UNSET: Any = _Unset()


def _function_code(content: 'Content') -> bytes:
    """A function's code as it's uploaded. Bytes are code as they are, not base64 as parse_content takes them to be"""
    if isinstance(content, (bytes, bytearray)):
        content = io.BytesIO(content)
    content_bytes, _ = parse_content(content, False, False)
    return content_bytes


def _path_id(resource_id: str) -> str:
    """A resource ID as a path segment: an ID naming its organization ('cradl:organization:cradl/cradl:function:x')
    has a '/'. A version (':3'), alias (':@prod') or ':$latest' qualifier is kept as it is."""
    return quote(str(resource_id), safe=':$@')


def dictstrip(d):
    """Given a dict, return the dict with keys mapping to falsey values removed."""
    return {k: v for k, v in d.items() if v is not None}


class Client:
    """A low level client to invoke api methods from Cradl."""
    def __init__(self, credentials: Optional[Credentials] = None, profile=None):
        """:param credentials: Credentials to use, instance of :py:class:`~cradl.Credentials`
        :type credentials: Credentials"""
        self.credentials = credentials or guess_credentials(profile)

    @exponential_backoff(TooManyRequestsException, max_tries=4)
    @exponential_backoff(RequestException, max_tries=3, giveup=fatal_code)
    def _make_request(
        self,
        requests_fn: Callable,
        path: str,
        body: Optional[dict] = None,
        params: Optional[dict] = None,
        extra_headers: Optional[dict] = None,
    ) -> Dict:
        """Make signed headers, use them to make a HTTP request of arbitrary form and return the result
        as decoded JSON. Optionally pass a payload to JSON-dump and parameters for the request call."""

        if not body and requests_fn in [requests.patch]:
            raise EmptyRequestError

        kwargs = {'params': params}
        None if body is None else kwargs.update({'data': json.dumps(body)})  # type: ignore
        uri = urlparse(f'{self.credentials.api_endpoint}{path}')

        headers = {
            'Authorization': f'Bearer {self.credentials.access_token}',
            'Content-Type': 'application/json',
            **(extra_headers or {}),
        }
        response = requests_fn(
            url=uri.geturl(),
            headers=headers,
            **kwargs,
        )
        return decode_response(response)

    @exponential_backoff(TooManyRequestsException, max_tries=4)
    @exponential_backoff(RequestException, max_tries=3, giveup=fatal_code)
    def _make_fileserver_request(
        self,
        requests_fn: Callable,
        file_url: str,
        content: Optional[bytes] = None,
        query_params: Optional[dict] = None,
    ) -> bytes:
        if not content and requests_fn == requests.put:
            raise EmptyRequestError

        kwargs = {'params': query_params}
        if content:
            kwargs.update({'data': content})  # type: ignore
        uri = urlparse(file_url)

        headers = {'Authorization': f'Bearer {self.credentials.access_token}'}
        response = requests_fn(
            url=uri.geturl(),
            headers=headers,
            **kwargs,
        )
        return decode_response(response, return_json=False)

    def create_app_client(
        self,
        generate_secret=True,
        logout_urls=None,
        callback_urls=None,
        login_urls=None,
        default_login_url=None,
        **optional_args,
    ) -> Dict:
        """Creates an appClient, calls the POST /appClients endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_app_client(name='<name>', description='<description>')

        :param name: Name of the appClient
        :type name: str, optional
        :param description: Description of the appClient
        :type description: str, optional
        :param generate_secret: Set to False to create a public app client, default: True. Only organizations that \
sign in with Cognito can create one
        :type generate_secret: Boolean
        :param logout_urls: Deprecated, and warns: a public app client's logout urls
        :type logout_urls: List[str]
        :param callback_urls: Deprecated, and warns: a public app client's callback urls
        :type callback_urls: List[str]
        :param login_urls: Deprecated, and warns: a public app client's login urls
        :type login_urls: List[str]
        :param default_login_url: Deprecated, and warns: a public app client's default login url
        :type default_login_url: str
        :param role_ids: List of roles to assign appClient
        :type role_ids: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: AppClient response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        urls = {
            'logout_urls': logout_urls,
            'callback_urls': callback_urls,
            'login_urls': login_urls,
            'default_login_url': default_login_url,
        }
        if deprecated := [name for name, value in urls.items() if value is not None]:
            _warn_app_client_urls(deprecated)
        body = dictstrip({
            'logoutUrls': logout_urls,
            'callbackUrls': callback_urls,
            'loginUrls': login_urls,
            'defaultLoginUrl': default_login_url,
            **optional_args,
        })
        body['generateSecret'] = generate_secret
        if 'role_ids' in body:
            body['roleIds'] = body.pop('role_ids') or []

        return self._make_request(requests.post, '/appClients', body=body)

    def get_app_client(self, app_client_id: str) -> Dict:
        """Get appClient, calls the GET /appClients/{appClientId} endpoint.

        :param app_client_id: Id of the appClient
        :type app_client_id: str
        :return: AppClient response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/appClients/{_path_id(app_client_id)}')

    def list_app_clients(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List appClients available, calls the GET /appClients endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_app_clients()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: AppClients response from REST API without the content of each appClient
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/appClients', params=params)

    def update_app_client(self, app_client_id, **optional_args) -> Dict:
        """Updates an appClient, calls the PATCH /appClients/{appClientId} endpoint.

        :param app_client_id: Id of the appClient
        :type app_client_id: str
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param name: Name of the appClient
        :type name: str, optional
        :param description: Description of the appClient
        :type description: str, optional
        :param role_ids: List of roles to assign appClient
        :type role_ids: str, optional
        :return: AppClient response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        if 'role_ids' in optional_args:
            optional_args['roleIds'] = optional_args.pop('role_ids') or []

        return self._make_request(requests.patch, f'/appClients/{_path_id(app_client_id)}', body=optional_args)

    def delete_app_client(self, app_client_id: str) -> Dict:
        """Delete the appClient with the provided appClientId, calls the DELETE /appClients/{appClientId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_app_client('<app_client_id>')

        :param app_client_id: Id of the appClient
        :type app_client_id: str
        :return: AppClient response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/appClients/{_path_id(app_client_id)}')

    def create_payment_method(self, **optional_args) -> Dict:
        """Creates a payment_method, calls the POST /paymentMethods endpoint.

        :param name: Name of the payment method
        :type name: str, optional
        :param description: Description of the payment method
        :type description: str, optional
        :return: PaymentMethod response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.post, '/paymentMethods', body=optional_args)

    def list_payment_methods(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List payment_methods available, calls the GET /paymentMethods endpoint.

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: PaymentMethods response from REST API without the content of each payment method
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/paymentMethods', params=params)

    def get_payment_method(self, payment_method_id: str) -> Dict:
        """Get payment_method, calls the GET /paymentMethods/{paymentMethodId} endpoint.

        :param payment_method_id: Id of the payment method
        :type payment_method_id: str
        :return: PaymentMethod response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/paymentMethods/{_path_id(payment_method_id)}')

    def update_payment_method(
        self,
        payment_method_id: str,
        *,
        stripe_setup_intent_secret: Optional[str] = None,
        **optional_args
    ) -> Dict:
        """Updates a payment_method, calls the PATCH /paymentMethods/{paymentMethodId} endpoint.

        :param payment_method_id: Id of the payment method
        :type payment_method_id: str
        :param stripe_setup_intent_secret: Stripe setup intent secret as returned from create_payment_method
        :type stripe_setup_intent_secret: str, optional
        :param name: Name of the payment method
        :type name: str, optional
        :param description: Description of the payment method
        :type description: str, optional
        :return: PaymentMethod response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        body = {**optional_args}
        if stripe_setup_intent_secret:
            body['stripeSetupIntentSecret'] = stripe_setup_intent_secret

        return self._make_request(requests.patch, f'/paymentMethods/{_path_id(payment_method_id)}', body=body)

    def delete_payment_method(self, payment_method_id: str) -> Dict:
        """Delete the payment_method with the provided payment_method_id, calls the DELETE \
/paymentMethods/{paymentMethodId} endpoint.

        :param payment_method_id: Id of the payment method
        :type payment_method_id: str
        :return: PaymentMethod response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        return self._make_request(requests.delete, f'/paymentMethods/{_path_id(payment_method_id)}')

    def create_document(
        self,
        content: Content,
        *,
        consent_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        description: Optional[str] = None,
        ground_truth: Optional[Sequence[Dict[str, str]]] = None,
        metadata: Optional[dict] = None,
        name: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        retention_in_days: Optional[int] = None,
        content_type: Optional[str] = None,
    ) -> Dict:
        """Creates a document, calls the POST /documents endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_document(b'<bytes data>', 'image/jpeg', consent_id='<consent id>')

        :param content: Content to POST
        :type content: Content
        :param consent_id: Id of the consent that marks the owner of the document
        :type consent_id: str, optional
        :param dataset_id: Id of the associated dataset
        :type dataset_id: str, optional
        :param agent_run_id: Id of the associated agent_run
        :type agent_run_id: str, optional
        :param ground_truth: List of items {'label': label, 'value': value} \
            representing the ground truth values for the document
        :type ground_truth: Sequence [ Dict [ str, Union [ str, bool ]  ] ], optional
        :param retention_in_days: How many days the document should be stored
        :type retention_in_days: int, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param name: Name of the document
        :type name: str, optional
        :param content_type: MIME type of the content, e.g. 'application/pdf'. Detected by the API when left out
        :type content_type: str, optional
        :return: Document response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        content_bytes, _ = parse_content(content, False, False)

        body = {
            'contentType': content_type,
            'consentId': consent_id,
            'datasetId': dataset_id,
            'description': description,
            'groundTruth': ground_truth,
            'metadata': metadata,
            'name': name,
            'agentRunId': agent_run_id,
            'retentionInDays': retention_in_days,
        }

        document = self._make_request(requests.post, '/documents', body=dictstrip(body))
        try:
            self._make_fileserver_request(requests.put, document['fileUrl'], content=content_bytes)
        except Exception as e:
            self.delete_document(document['documentId'])
            raise e

        return document

    def list_documents(
        self,
        *,
        document_id: Optional[Queryparam] = None,
        consent_id: Optional[Queryparam] = None,
        dataset_id: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        order: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> Dict:
        """List documents available for inference, calls the GET /documents endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_documents(consent_id='<consent_id>')

        :param document_id: Only these documents
        :type document_id: Queryparam, optional
        :param consent_id: Ids of the consents that marks the owner of the document
        :type consent_id: Queryparam, optional
        :param dataset_id: Ids of datasets that contains the documents of interest
        :type dataset_id: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param order: Order of the executions, either 'ascending' or 'descending'
        :type order: str, optional
        :param sort_by: the sorting variable of the executions, currently only supports 'createdTime'
        :type sort_by: str, optional
        :return: Documents response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'documentId': document_id,
            'consentId': consent_id,
            'datasetId': dataset_id,
            'maxResults': max_results,
            'nextToken': next_token,
            'order': order,
            'sortBy': sort_by,
        }
        return self._make_request(requests.get, '/documents', params=dictstrip(params))

    def delete_documents(
        self,
        *,
        consent_id: Optional[Queryparam] = None,
        dataset_id: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        delete_all: Optional[bool] = False,
    ) -> Dict:
        """Delete documents with the provided consent_id, calls the DELETE /documents endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_documents(consent_id='<consent id>')

        :param consent_id: Ids of the consents that marks the owner of the document
        :type consent_id: Queryparam, optional
        :param dataset_id: Ids of the datasets to be deleted
        :type dataset_id: Queryparam, optional
        :param max_results: Maximum number of documents that will be deleted
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param delete_all: Delete all documents that match the given parameters doing multiple API calls if necessary. \
            Will throw an error if parameter max_results is also specified.
        :type delete_all: bool, optional
        :return: Documents response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({
            'consentId': consent_id,
            'datasetId': dataset_id,
            'nextToken': next_token,
            'maxResults': max_results,
        })

        if delete_all and max_results:
            raise ValueError('Cannot specify max results when delete_all=True')

        response = self._make_request(requests.delete, '/documents', params=params)

        if delete_all:
            params['nextToken'] = response['nextToken']

            while params['nextToken']:
                intermediate_response = self._make_request(requests.delete, '/documents', params=params)
                response['documents'].extend(intermediate_response.get('documents'))
                params['nextToken'] = intermediate_response['nextToken']
                logger.info(f'Deleted {len(response["documents"])} documents so far')

        return response

    def get_document(
        self,
        document_id: str,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        page: Optional[int] = None,
        rotation: Optional[int] = None,
        density: Optional[int] = None,
        quality: Optional[str] = None,
    ) -> Dict:
        """Get document, calls the GET /documents/{documentId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_document('<document id>')

        :param document_id: Id of the document
        :type document_id: str
        :param width: Convert document file to JPEG with this px width
        :type width: int, optional
        :param height: Convert document file to JPEG with this px height
        :type height: int, optional
        :param page: Convert this page from PDF/TIFF document to JPEG, 0-indexed. Negative indices supported.
        :type page: int, optional
        :param rotation: Convert document file to JPEG and rotate it by rotation amount degrees
        :type rotation: int, optional
        :param density: Convert PDF/TIFF document to JPEG with this density setting
        :type density: int, optional
        :param quality: The returned quality of the document. Currently the only valid quality is "low", and only PDFs
        will have their quality adjusted.
        :type quality: str, optional
        :return: Document response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        document = self._make_request(requests.get, f'/documents/{_path_id(document_id)}')
        query_params = dictstrip({
            'width': width,
            'height': height,
            'page': page,
            'rotation': rotation,
            'density': density,
            'quality': quality,
        })

        if query_params or 'content' not in document:
            document['content'] = b64encode(self._make_fileserver_request(
                requests_fn=requests.get,
                file_url=document['fileUrl'],
                query_params=query_params,
            )).decode()

        return document

    def update_document(
        self,
        document_id: str,
        # For backwards compatibility reasons, ground truth is placed before the *
        ground_truth: Optional[Sequence[Dict[str, Union[Optional[str], bool]]]] = None,
        *,
        metadata: Optional[dict] = None,
        dataset_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        retention_in_days: Optional[int] = None,
    ) -> Dict:
        """Update ground truth for a document, calls the PATCH /documents/{documentId} endpoint.
        Updating ground truth means adding the ground truth data for the particular document.
        This enables the API to learn from past mistakes.

        :param document_id: Id of the document
        :type document_id: str
        :param dataset_id: Id of the dataset you want to associate your document with
        :type dataset_id: str, optional
        :param ground_truth: List of items {label: value} representing the ground truth values for the document
        :type ground_truth: Sequence [ Dict [ str, Union [ str, bool ]  ] ], optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param name: Name of the document
        :type name: str, optional
        :param description: Description of the document
        :type description: str, optional
        :param retention_in_days: How many days the document should be stored, 1 to 1825
        :type retention_in_days: int, optional
        :return: Document response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'groundTruth': ground_truth,
            'datasetId': dataset_id,
            'metadata': metadata,
            'name': name,
            'description': description,
            'retentionInDays': retention_in_days,
        })

        return self._make_request(requests.patch, f'/documents/{_path_id(document_id)}', body=body)

    def delete_document(self, document_id: str) -> Dict:
        """Delete the document with the provided document_id, calls the DELETE /documents/{documentId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_document('<document_id>')

        :param document_id: Id of the document
        :type document_id: str
        :return: Model response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/documents/{_path_id(document_id)}')

    def list_logs(
        self,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        order: Optional[str] = None,
    ) -> Dict:
        """List logs, calls the GET /logs endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_logs()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param order: Order of the logs, either 'ascending' or 'descending'
        :type order: str, optional
        :return: Logs response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = '/logs'
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
            'order': order,
        }

        return self._make_request(requests.get, url, params=dictstrip(params))

    def get_log(self, log_id) -> Dict:
        """get log, calls the GET /logs/{logId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_log('<log_id>')

        :param log_id: Id of the log
        :type log_id: str
        :return: Log response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/logs/{_path_id(log_id)}')

    def create_model(
        self,
        field_config: dict,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        preprocess_config: Optional[dict] = None,
        postprocess_config: Optional[dict] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        base_model: Optional[dict] = None,
        agent_id: Optional[str] = None,
        llm_version: Optional[str] = None,
        confidence_version: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Creates a model, calls the POST /models endpoint.

        :param field_config: Specification of the fields that the model is going to predict
        :type field_config: dict
        :param width: The number of pixels to be used for the input image width of your model
        :type width: int, optional
        :param height: The number of pixels to be used for the input image height of your model
        :type height: int, optional
        :param preprocess_config: Preprocessing configuration for predictions.
            {
                'autoRotate': True | False                          (optional)
                'maxPages': 1 - 3                                   (optional)
                'imageQuality': 'LOW' | 'HIGH'                      (optional)
                'pages': List with up to 3 page-indices to process  (optional)
                'rotation': 0, 90, 180 or 270                       (optional)
            }
            Examples:
            {'pages': [0, 1, 5], 'autoRotate': True}
            {'pages': [0, 1, -1], 'rotation': 90, 'imageQuality': 'HIGH'}
            {'maxPages': 3, 'imageQuality': 'LOW'}
        :type preprocess_config: dict, optional
        :param postprocess_config: Post processing configuration for predictions.
            {
                'strategy': 'BEST_FIRST' | 'BEST_N_PAGES',  (required)
                'outputFormat': 'v1' | 'v2',                (optional)
                'parameters': {                             (required if strategy=BEST_N_PAGES, omit otherwise)
                    'n': int,                               (required if strategy=BEST_N_PAGES, omit otherwise)
                    'collapse': True | False                (optional if strategy=BEST_N_PAGES, omit otherwise)
                }
            }
            Examples:
            {'strategy': 'BEST_FIRST', 'outputFormat': 'v2'}
            {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3}}
            {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3, 'collapse': False}}
        :type postprocess_config: dict, optional
        :param name: Name of the model
        :type name: str, optional
        :param description: Description of the model
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param base_model: Specify which model to use as base model. Example: \
{"organizationId": "cradl:organization:cradl", "modelId": "cradl:model:invoice"}
        :type base_model: dict, optional
        :param agent_id: Id of the agent the model belongs to: one of the agent's resources from the start,\
 until it's deleted
        :type agent_id: str, optional
        :param llm_version: The language model the model predicts with: 'sonnet-4.0', 'sonnet-4.5', 'sonnet-4.6', \
'sonnet-5', 'sonnet-5.5', 'haiku-5.5' or 'qwen3-vl'
        :type llm_version: str, optional
        :param confidence_version: How confidences are estimated: 'v1' or 'v2'
        :type confidence_version: str, optional
        :return: Model response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        if base_model:
            metadata = {
                **(metadata or {}),
                'baseModel': base_model,
            }

        body = dictstrip({
            'agentId': agent_id,
            'width': width,
            'height': height,
            'fieldConfig': field_config,
            'preprocessConfig': preprocess_config,
            'postprocessConfig': postprocess_config,
            'name': name,
            'description': description,
            'metadata': metadata,
            'llmVersion': llm_version,
            'confidenceVersion': confidence_version,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, '/models', body=body)

    def list_models(
        self,
        *,
        model_id: Optional[Queryparam] = None,
        owner: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List models available, calls the GET /models endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_models()

        :param model_id: Only these models, at most 100 ids
        :type model_id: Queryparam, optional
        :param owner: Organizations to retrieve plans from
        :type owner: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Models response from REST API without the content of each model
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'modelId': model_id,
            'maxResults': max_results,
            'nextToken': next_token,
            'owner': owner,
        }
        return self._make_request(requests.get, '/models', params=dictstrip(params))

    def get_model(self, model_id: str, *, statistics_last_n_days: Optional[int] = None) -> Dict:
        """Get a model, calls the GET /models/{modelId} endpoint.

        :param model_id: The Id of the model, optionally qualified with a version (``:3``), an alias (``:@prod``) \
or ``:$latest``
        :type model_id: str
        :param statistics_last_n_days: Integer between 1 and 30
        :type statistics_last_n_days: int, optional
        :return: Model response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {'statisticsLastNDays': statistics_last_n_days}
        return self._make_request(requests.get, f'/models/{_path_id(model_id)}', params=params)

    def update_model(
        self,
        model_id: str,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        field_config: Optional[dict] = None,
        preprocess_config: Optional[dict] = None,
        postprocess_config: Optional[dict] = None,
        metadata: Optional[dict] = None,
        llm_version: Optional[str] = None,
        confidence_version: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Updates a model, calls the PATCH /models/{modelId} endpoint.

        :param model_id: The Id of the model
        :type model_id: str, optional
        :param width: The number of pixels to be used for the input image width of your model
        :type width: int, optional
        :param height: The number of pixels to be used for the input image height of your model
        :type height: int, optional
        :param field_config: Specification of the fields that the model is going to predict
        :type field_config: dict
        :param preprocess_config: Preprocessing configuration for predictions.
            {
                'autoRotate': True | False                          (optional)
                'maxPages': 1 - 3                                   (optional)
                'imageQuality': 'LOW' | 'HIGH'                      (optional)
                'pages': List with up to 3 page-indices to process  (optional)
                'rotation': 0, 90, 180 or 270                       (optional)
            }
            Examples:
            {'pages': [0, 1, 5], 'autoRotate': True}
            {'pages': [0, 1, -1], 'rotation': 90, 'imageQuality': 'HIGH'}
            {'maxPages': 3, 'imageQuality': 'LOW'}
        :type preprocess_config: dict, optional
        :param postprocess_config: Post processing configuration for predictions.
            {
                'strategy': 'BEST_FIRST' | 'BEST_N_PAGES',  (required)
                'outputFormat': 'v1' | 'v2',                (optional)
                'parameters': {                             (required if strategy=BEST_N_PAGES, omit otherwise)
                    'n': int,                               (required if strategy=BEST_N_PAGES, omit otherwise)
                    'collapse': True | False                (optional if strategy=BEST_N_PAGES, omit otherwise)
                }
            }
            Examples:
            {'strategy': 'BEST_FIRST', 'outputFormat': 'v2'}
            {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3}}
            {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3, 'collapse': False}}
        :type postprocess_config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param training_id: Use this training for model inference in POST /predictions
        :type training_id: str, optional
        :param name: Name of the model
        :type name: str, optional
        :param description: Description of the model
        :type description: str, optional
        :param llm_version: The language model the model predicts with: 'sonnet-4.0', 'sonnet-4.5', 'sonnet-4.6', \
'sonnet-5', 'sonnet-5.5', 'haiku-5.5' or 'qwen3-vl'
        :type llm_version: str, optional
        :param confidence_version: How confidences are estimated: 'v1' or 'v2'
        :type confidence_version: str, optional
        :return: Model response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'width': width,
            'height': height,
            'fieldConfig': field_config,
            'metadata': metadata,
            'llmVersion': llm_version,
            'confidenceVersion': confidence_version,
            'preprocessConfig': preprocess_config,
            'postprocessConfig': postprocess_config,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/models/{_path_id(model_id)}', body=body)

    def delete_model(self, model_id: str) -> Dict:
        """Delete the model with the provided model_id, calls the DELETE /models/{modelId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_model('<model_id>')

        :param model_id: Id of the model
        :type model_id: str
        :return: Model response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/models/{_path_id(model_id)}')

    def list_model_versions(
        self,
        model_id: str,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List the model's published versions, calls the GET /models/{modelId}/versions endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Versions response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({'maxResults': max_results, 'nextToken': next_token})
        return self._make_request(requests.get, f'/models/{_path_id(model_id)}/versions', params=params)

    def create_model_version(self, model_id: str) -> Dict:
        """Publish the model as it is now as a new version, calls the POST /models/{modelId}/versions
        endpoint. If nothing changed since the latest version, that version is returned.

        :param model_id: Id of the model
        :type model_id: str
        :return: The version from REST API, its ``modelId`` qualified with the version number
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.post, f'/models/{_path_id(model_id)}/versions', body={})

    def list_model_aliases(self, model_id: str) -> Dict:
        """List the model's aliases, calls the GET /models/{modelId}/aliases endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :return: Aliases response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/models/{_path_id(model_id)}/aliases')

    def get_model_alias(self, model_id: str, alias: str) -> Dict:
        """Get an alias of the model, calls the GET /models/{modelId}/aliases/{aliasId} endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/models/{_path_id(model_id)}/aliases/{_path_id(alias)}')

    def set_model_alias(self, model_id: str, alias: str, *, resource_version: int) -> Dict:
        """Create an alias of the model, or move it to another version, calls the
        PUT /models/{modelId}/aliases/{aliasId} endpoint. ``<model_id>:@<alias>`` refers to that version.

        :param model_id: Id of the model
        :type model_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :param resource_version: The version the alias points to
        :type resource_version: int
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body: Dict[str, Any] = {'resourceVersion': resource_version}
        return self._make_request(requests.put, f'/models/{_path_id(model_id)}/aliases/{_path_id(alias)}', body=body)

    def delete_model_alias(self, model_id: str, alias: str) -> Dict:
        """Delete an alias of the model, calls the DELETE /models/{modelId}/aliases/{aliasId} endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/models/{_path_id(model_id)}/aliases/{_path_id(alias)}')

    def list_functions(
        self,
        *,
        function_id: Optional[Queryparam] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List functions available, calls the GET /functions endpoint.

        :param function_id: Only these functions, at most 100 ids
        :type function_id: Queryparam, optional
        :param sort_by: The sorting variable, currently only supports 'createdTime'
        :type sort_by: str, optional
        :param order: Order of the functions, either 'ascending' (the default) or 'descending'
        :type order: str, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Functions response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({
            'functionId': function_id,
            'sortBy': sort_by,
            'order': order,
            'maxResults': max_results,
            'nextToken': next_token,
        })
        return self._make_request(requests.get, '/functions', params=params)

    def create_function(
        self,
        runtime: str,
        *,
        content: Optional[Content] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Dict:
        """Create a function, calls the POST /functions endpoint, and uploads its code.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_function('python', content='path/to/main.py', name='<name>')

        :param runtime: 'python' or 'nodejs'
        :type runtime: str
        :param content: The function's code: a path to a file, bytes or a stream
        :type content: Content, optional
        :param name: Name of the function
        :type name: str, optional
        :param description: Description of the function
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Function response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        # Read before the function is created, so a file that can't be read leaves no function behind
        code = None if content is None else _function_code(content)
        body = dictstrip({
            'runtime': runtime,
            'name': name,
            'description': description,
            'metadata': metadata,
        })
        function = self._make_request(requests.post, '/functions', body=body)
        if code is not None:
            try:
                self._make_fileserver_request(requests.put, function['fileUrl'], content=code)
            except Exception as e:
                self.delete_function(function['functionId'])
                raise e
        return function

    def get_function(self, function_id: str, *, get_content: bool = False) -> Dict:
        """Get a function, calls the GET /functions/{functionId} endpoint.

        :param function_id: Id of the function, optionally qualified with a version (``:3``), an alias (``:@prod``) \
or ``:$latest``
        :type function_id: str
        :param get_content: Also get the function's code, as ``content``. A function without a code file of its own, \
such as a managed one, has no ``fileUrl`` and gets no ``content``
        :type get_content: bool, optional
        :return: Function response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        function = self._make_request(requests.get, f'/functions/{_path_id(function_id)}')
        if get_content and function.get('fileUrl'):
            function['content'] = self._make_fileserver_request(requests.get, function['fileUrl']).decode()
        return function

    def update_function(self, function_id: str, *, content: Optional[Content] = None, **optional_args) -> Dict:
        """Update a function, calls the PATCH /functions/{functionId} endpoint, and uploads its new code.

        :param function_id: Id of the function
        :type function_id: str
        :param content: The function's new code: a path to a file, bytes or a stream. A function without a code file \
of its own, such as a managed one, can't be given code (ValueError)
        :type content: Content, optional
        :param name: Name of the function
        :type name: str, optional
        :param description: Description of the function
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Function response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        code = None if content is None else _function_code(content)
        if optional_args or code is None:
            function = self._make_request(requests.patch, f'/functions/{_path_id(function_id)}', body=optional_args)
        else:
            function = self.get_function(function_id)
        if code is not None:
            if not function.get('fileUrl'):
                raise ValueError(f'Function {function_id} has no code file of its own to upload to')
            self._make_fileserver_request(requests.put, function['fileUrl'], content=code)
        return function

    def delete_function(self, function_id: str) -> Dict:
        """Delete a function, calls the DELETE /functions/{functionId} endpoint.

        :param function_id: Id of the function
        :type function_id: str
        :return: Function response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/functions/{_path_id(function_id)}')

    def list_function_versions(
        self,
        function_id: str,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List the function's published versions, calls the GET /functions/{functionId}/versions endpoint.

        :param function_id: Id of the function
        :type function_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Versions response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({'maxResults': max_results, 'nextToken': next_token})
        return self._make_request(requests.get, f'/functions/{_path_id(function_id)}/versions', params=params)

    def create_function_version(self, function_id: str) -> Dict:
        """Publish the function as it is now as a new version, calls the POST /functions/{functionId}/versions
        endpoint. If nothing changed since the latest version, that version is returned.

        :param function_id: Id of the function
        :type function_id: str
        :return: The version from REST API, its ``functionId`` qualified with the version number
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.post, f'/functions/{_path_id(function_id)}/versions', body={})

    def list_function_aliases(self, function_id: str) -> Dict:
        """List the function's aliases, calls the GET /functions/{functionId}/aliases endpoint.

        :param function_id: Id of the function
        :type function_id: str
        :return: Aliases response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/functions/{_path_id(function_id)}/aliases')

    def get_function_alias(self, function_id: str, alias: str) -> Dict:
        """Get an alias of the function, calls the GET /functions/{functionId}/aliases/{aliasId} endpoint.

        :param function_id: Id of the function
        :type function_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/functions/{_path_id(function_id)}/aliases/{_path_id(alias)}')

    def set_function_alias(self, function_id: str, alias: str, *, resource_version: int) -> Dict:
        """Create an alias of the function, or move it to another version, calls the
        PUT /functions/{functionId}/aliases/{aliasId} endpoint. ``<function_id>:@<alias>`` refers to that version.

        :param function_id: Id of the function
        :type function_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :param resource_version: The version the alias points to
        :type resource_version: int
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body: Dict[str, Any] = {'resourceVersion': resource_version}
        path = f'/functions/{_path_id(function_id)}/aliases/{_path_id(alias)}'
        return self._make_request(requests.put, path, body=body)

    def delete_function_alias(self, function_id: str, alias: str) -> Dict:
        """Delete an alias of the function, calls the DELETE /functions/{functionId}/aliases/{aliasId} endpoint.

        :param function_id: Id of the function
        :type function_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/functions/{_path_id(function_id)}/aliases/{_path_id(alias)}')

    def list_organizations(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List the organizations you're a member of, calls the GET /organizations endpoint.

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Organizations response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({'maxResults': max_results, 'nextToken': next_token})
        return self._make_request(requests.get, '/organizations', params=params)

    def create_organization(self, *, name: Optional[str] = None, **optional_args) -> Dict:
        """Create an organization, calls the POST /organizations endpoint.

        :param name: Name of the organization
        :type name: str, optional
        :param description: Description of the organization
        :type description: str, optional
        :param url: The organization's website
        :type url: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Organization response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'name': name, **optional_args})
        return self._make_request(requests.post, '/organizations', body=body)

    def get_organization(self, organization_id: str) -> Dict:
        """Get an organization, calls the GET /organizations/{organizationId} endpoint.

        :param organization_id: The Id of the organization
        :type organization_id: str
        :return: Organization response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/organizations/{_path_id(organization_id)}')

    def update_organization(
        self,
        organization_id: str,
        *,
        payment_method_id: Optional[str] = None,
        document_retention_in_days: Optional[int] = None,
        plan_id: Optional[str] = None,
        url: Optional[str] = None,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:
        """Updates an organization, calls the PATCH /organizations/{organizationId} endpoint.

        :param organization_id: Id of organization
        :type organization_id: str, optional
        :param payment_method_id: Id of paymentMethod to use
        :type payment_method_id: str, optional
        :param name: Name of the organization
        :type name: str, optional
        :param description: Description of the organization
        :type description: str, optional
        :param plan_id: Id of the plan to subscribe to
        :type plan_id: str, optional
        :param url: The organization's website
        :type url: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Organization response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {**dictstrip({'planId': plan_id, 'url': url, 'metadata': metadata}), **optional_args}
        if payment_method_id:
            body['paymentMethodId'] = payment_method_id

        if document_retention_in_days:
            body['documentRetentionInDays'] = document_retention_in_days

        return self._make_request(requests.patch, f'/organizations/{_path_id(organization_id)}', body=body)

    def create_prediction(
        self,
        document_id: str,
        model_id: str,
        *,
        training_id: Optional[str] = None,
        preprocess_config: Optional[dict] = None,
        postprocess_config: Optional[dict] = None,
        run_async: Optional[bool] = None,
        agent_run_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Dict:
        """Create a prediction on a document using specified model, calls the POST /predictions endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_prediction(document_id='<document id>', model_id='<model id>')

        :param document_id: Id of the document to run inference and create a prediction on
        :type document_id: str
        :param model_id: Id of the model to use for predictions
        :type model_id: str
        :param training_id: Id of training to use for predictions
        :type training_id: str
        :param preprocess_config: Preprocessing configuration for prediction.
            {
                'autoRotate': True | False                          (optional)
                'maxPages': 1 - 3                                   (optional)
                'imageQuality': 'LOW' | 'HIGH'                      (optional)
                'pages': List with up to 3 page-indices to process  (optional)
                'rotation': 0, 90, 180 or 270                       (optional)
            }
            Examples:
            {'pages': [0, 1, 5], 'autoRotate': True}
            {'pages': [0, 1, -1], 'rotation': 90, 'imageQuality': 'HIGH'}
            {'maxPages': 3, 'imageQuality': 'LOW'}
        :type preprocess_config: dict, optional
        :param postprocess_config: Post processing configuration for prediction.
            {
                'strategy': 'BEST_FIRST' | 'BEST_N_PAGES',  (required)
                'outputFormat': 'v1' | 'v2',                (optional)
                'parameters': {                             (required if strategy=BEST_N_PAGES, omit otherwise)
                    'n': int,                               (required if strategy=BEST_N_PAGES, omit otherwise)
                    'collapse': True | False                (optional if strategy=BEST_N_PAGES, omit otherwise)
                }
            }
            Examples:
            {'strategy': 'BEST_FIRST', 'outputFormat': 'v2'}
            {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3}}
            {'strategy': 'BEST_N_PAGES', 'parameters': {'n': 3, 'collapse': False}}
        :type postprocess_config: dict, optional
        :param run_async: If True run the prediction async, if False run sync. if omitted run synchronously.
        :type run_async: bool
        :param agent_run_id: Id of an agent run to associate with the prediction
        :type agent_run_id: str, optional
        :param name: Name of the prediction
        :type name: str, optional
        :param description: Description of the prediction
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Prediction response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {
            'documentId': document_id,
            'modelId': model_id,
            'trainingId': training_id,
            'preprocessConfig': preprocess_config,
            'postprocessConfig': postprocess_config,
            'async': run_async,
            'agentRunId': agent_run_id,
            'name': name,
            'description': description,
            'metadata': metadata,
        }
        prediction = self._make_request(requests.post, '/predictions', body=dictstrip(body))
        predictions_format = prediction['postprocessConfig'].get('outputFormat')

        if prediction['status'] == 'succeeded' and prediction.get('predictions') is None:
            prediction['predictions'] = json.loads(self._make_fileserver_request(
                requests_fn=requests.get,
                file_url=prediction['fileUrl'],
                query_params={'predictionsFormat': predictions_format} if predictions_format else {},
            ).decode())

        return prediction

    def list_predictions(
        self,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        order: Optional[str] = None,
        sort_by: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Dict:
        """List predictions available, calls the GET /predictions endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_predictions()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param order: Order of the predictions, either 'ascending' or 'descending'
        :type order: str, optional
        :param sort_by: the sorting variable of the predictions, currently only supports 'createdTime'
        :type sort_by: str, optional
        :param model_id: Model ID of predictions
        :type model_id: str, optional
        :return: Predictions response from REST API without the content of each prediction
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'modelId': model_id,
            'nextToken': next_token,
            'order': order,
            'sortBy': sort_by,
        }
        return self._make_request(requests.get, '/predictions', params=dictstrip(params))

    def get_prediction(self, prediction_id: str) -> Dict:
        """Get prediction, calls the GET /predictions/{predictionId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_prediction(prediction_id='<prediction id>')

        :param prediction_id: Id of the prediction
        :type prediction_id: str
        :return: Asset response from REST API with content
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        prediction = self._make_request(requests.get, f'/predictions/{_path_id(prediction_id)}')
        predictions_format = prediction['postprocessConfig'].get('outputFormat')

        if prediction['status'] == 'succeeded' and prediction.get('predictions') is None:
            prediction['predictions'] = json.loads(self._make_fileserver_request(
                requests_fn=requests.get,
                file_url=prediction['fileUrl'],
                query_params={'predictionsFormat': predictions_format} if predictions_format else {},
            ).decode())

        return prediction

    def get_plan(self, plan_id: str) -> Dict:
        """Get information about a specific plan, calls the GET /plans/{plan_id} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_plan('<plan_id>')

        :param plan_id: Id of the plan
        :type plan_id: str
        :return: Plan response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        return self._make_request(requests.get, f'/plans/{_path_id(plan_id)}')

    def list_plans(
        self,
        *,
        owner: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List plans available, calls the GET /plans endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_plans()

        :param owner: Organizations to retrieve plans from
        :type owner: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Plans response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
            'owner': owner,
        }
        return self._make_request(requests.get, '/plans', params=dictstrip(params))

    def create_secret(self, data: dict, **optional_args) -> Dict:
        """Creates a secret, calls the POST /secrets endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> data = {'username': '<username>', 'password': '<password>'}
        >>> client.create_secret(data, description='<description>')

        :param data: Dict containing the data you want to keep secret
        :type data: str
        :param name: Name of the secret
        :type name: str, optional
        :param description: Description of the secret
        :type description: str, optional
        :return: Secret response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {
            'data': data,
            **optional_args,
        }
        return self._make_request(requests.post, '/secrets', body=body)

    def list_secrets(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List secrets available, calls the GET /secrets endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_secrets()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Secrets response from REST API without the username of each secret
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/secrets', params=params)

    def update_secret(self, secret_id: str, *, data: Optional[dict] = None, **optional_args) -> Dict:
        """Updates a secret, calls the PATCH /secrets/secretId endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> data = {'username': '<username>', 'password': '<password>'}
        >>> client.update_secret('<secret id>', data, description='<description>')

        :param secret_id: Id of the secret
        :type secret_id: str
        :param data: Dict containing the data you want to keep secret
        :type data: dict, optional
        :param name: Name of the secret
        :type name: str, optional
        :param description: Description of the secret
        :type description: str, optional
        :return: Secret response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'data': data})
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/secrets/{_path_id(secret_id)}', body=body)

    def delete_secret(self, secret_id: str) -> Dict:
        """Delete the secret with the provided secret_id, calls the DELETE /secrets/{secretId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_secret('<secret_id>')

        :param secret_id: Id of the secret
        :type secret_id: str
        :return: Secret response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/secrets/{_path_id(secret_id)}')

    def create_user(self, email: str, *, role_ids=None, app_client_id: Optional[str] = None, **optional_args) -> Dict:
        """Creates a new user, calls the POST /users endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_user('<email>', name='John Doe')

        :param email: Email to the new user
        :type email: str
        :param role_ids: List of roles to assign user
        :type role_ids: list, optional
        :param app_client_id: Id of the app client the user signs in with
        :type app_client_id: str, optional
        :param name: Name of the user
        :type name: str, optional
        :param description: Description of the user
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: User response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {
            'email': email,
            'roleIds': role_ids,
            'appClientId': app_client_id,
            **optional_args,
        }

        return self._make_request(requests.post, '/users', body=dictstrip(body))

    def list_users(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List users, calls the GET /users endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_users()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Users response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/users', params=params)

    def get_user(self, user_id: str) -> Dict:
        """Get information about a specific user, calls the GET /users/{user_id} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_user('<user_id>')

        :param user_id: Id of the user
        :type user_id: str
        :return: User response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/users/{_path_id(user_id)}')

    def update_user(self, user_id: str, **optional_args) -> Dict:
        """Updates a user, calls the PATCH /users/{userId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.update_user('<user id>', name='John Doe')

        :param user_id: Id of the user
        :type user_id: str
        :param role_ids: List of roles to assign user
        :type role_ids: list, optional
        :param name: Name of the user
        :type name: str, optional
        :param description: Description of the user
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: User response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        if 'role_ids' in optional_args:
            optional_args['roleIds'] = optional_args.pop('role_ids') or []

        return self._make_request(requests.patch, f'/users/{_path_id(user_id)}', body=optional_args)

    def delete_user(self, user_id: str) -> Dict:
        """Delete the user with the provided user_id, calls the DELETE /users/{userId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_user('<user_id>')

        :param user_id: Id of the user
        :type user_id: str
        :return: User response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/users/{_path_id(user_id)}')

    def create_role(self, permissions: List[Dict], **optional_args) -> Dict:
        """Creates a role, calls the POST /roles endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> permissions = [{'resource': '<resource-identifier>', 'action': 'read|write', 'effect': 'allow|deny'}]
        >>> client.create_role(permissions, description='<description>')

        :param permissions: List of permissions the role will have
        :type permissions: list
        :param name: Name of the role
        :type name: str, optional
        :param description: Description of the role
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Role response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {
            'permissions': permissions,
            **optional_args,
        }
        return self._make_request(requests.post, '/roles', body=body)

    def update_role(self, role_id: str, *, permissions: Optional[List[Dict]] = None, **optional_args) -> Dict:
        """Updates a role, calls the PATCH /roles/{roleId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> permissions = [{'resource': '<resource-identifier>', 'action': 'read|write', 'effect': 'allow|deny'}]
        >>> client.update_role('<role id>', permissions=permissions, description='<description>')

        :param role_id: Id of the role
        :type role_id: str
        :param permissions: List of permissions the role will have
        :type permissions: list
        :param name: Name of the role
        :type name: str, optional
        :param description: Description of the role
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Role response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'permissions': permissions})
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/roles/{_path_id(role_id)}', body=body)

    def list_roles(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List roles available, calls the GET /roles endpoint.

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Roles response from REST API without the content of each role
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/roles', params=params)

    def get_role(self, role_id: str) -> Dict:
        """Get role, calls the GET /roles/{roleId} endpoint.

        :param role_id: Id of the role
        :type role_id: str
        :return: Role response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/roles/{_path_id(role_id)}')

    def delete_role(self, role_id: str) -> Dict:
        """Delete the role with the provided role_id, calls the DELETE /roles/{roleId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_role('<role_id>')

        :param role_id: Id of the role
        :type role_id: str
        :return: Role response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/roles/{_path_id(role_id)}')

    def get_validation(self, validation_id: str) -> Dict:
        """Get validation, calls the GET /validations/{validationId} endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :return: Validation response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/validations/{_path_id(validation_id)}')

    def list_validations(
        self,
        *,
        validation_id: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List validations available, calls the GET /validations endpoint.

        :param validation_id: Only these validations, at most 100 ids
        :type validation_id: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Validations response from REST API without the content of each validation
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'validationId': validation_id,
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/validations', params=dictstrip(params))

    def create_validation(
        self,
        *,
        config: Optional[dict] = None,
        metadata: Optional[dict] = None,
        agent_id: Optional[str] = None,
        **optional_args,
    ) -> Dict:

        """Creates a validation, calls the POST /validations endpoint.

        :param name: Name of the validation
        :type name: str, optional
        :param description: Description of the validation
        :type description: str, optional
        :param config: Dictionary that is used for configuration of the validation
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param agent_id: Id of the agent the validation belongs to: one of the agent's resources from the start,\
 until it's deleted
        :type agent_id: str, optional
        :param enabled: If the validation is enabled or not
        :type enabled: bool, optional
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'agentId': agent_id,
            'config': config,
            'metadata': metadata,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, '/validations', body=body)

    def update_validation(self, validation_id: str, *, config: Optional[dict] = None, **optional_args) -> Dict:
        """Update the validation with the provided validation_id, calls the PATCH /validations/{validation_id} endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :param config: New configuration for the validation
        :type config: str
        :param name: Name of the validation
        :type name: str, optional
        :param description: Description of the validation
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Validation response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {'config': config, **optional_args}
        return self._make_request(requests.patch, f'/validations/{_path_id(validation_id)}', body=body)

    def delete_validation(self, validation_id: str) -> Dict:
        """Delete the validation defined by validation_id, calls the DELETE /validations/{validation_id} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_validation('<validation_id>')

        :param validation_id: Id of the validation
        :type validation_id: str
        :return: Validation response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/validations/{_path_id(validation_id)}')

    def create_validation_task(
        self,
        validation_id: str,
        input: dict,
        *,
        metadata: Optional[dict] = None,
        agent_run_id: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Creates a validation, calls the POST /validations endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :param input: Dictionary that can be used to store additional information
        :type input: dict, optional
        :param name: Name of the validation
        :type name: str, optional
        :param description: Description of the validation
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'input': input,
            'metadata': metadata,
            'agentRunId': agent_run_id,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, f'/validations/{_path_id(validation_id)}/tasks', body=body)

    def update_validation_task(
        self,
        validation_id: str,
        task_id: str,
        output: dict,
        status: str,
        *,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:
        """Creates a validation, calls the POST /validations endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :param task_id: Id of the validation task
        :type task_id: str
        :param output: Dictionary that can be used to store additional information
        :type output: dict, required if status is present, otherwise optional
        :param status: Status of the task
        :type status: str, required if output is present, otherwise optional
        :param name: Name of the validation
        :type name: str, optional
        :param description: Description of the validation
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'output': output, 'metadata': metadata, 'status': status})
        body.update(**optional_args)
        return self._make_request(
            requests_fn=requests.patch,
            path=f'/validations/{_path_id(validation_id)}/tasks/{_path_id(task_id)}',
            body=body,
        )

    def list_validation_tasks(
        self,
        validation_id: str,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        status: Optional[Queryparam] = None,
    ) -> Dict:
        """List validation tasks, calls the GET /validations/{validationId}/tasks endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param status: Statuses of the validation tasks
        :type status: Queryparam, optional
        :return: ValidationTasks response from REST API without the content of each validation
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({
            'maxResults': max_results,
            'nextToken': next_token,
            'status': status,
        })
        path = f'/validations/{_path_id(validation_id)}/tasks'
        return self._make_request(requests.get, path, params=dictstrip(params))

    def get_validation_task(self, validation_id: str, task_id: str) -> Dict:
        """Get a validation, calls the GET /validations/{validationId}/tasks/{taskId} endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :param task_id: Id of the validation task
        :type task_id: str
        :return: ValidationTask response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/validations/{_path_id(validation_id)}/tasks/{_path_id(task_id)}')

    def create_agent(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Dict:
        """Create agent, calls the POST /agents endpoint. Create its hooks, actions, models and validations with
        ``agent_id`` to make them the agent's.

        :param name: Name of the agent
        :type name: str, optional
        :param description: Description of the agent
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'description': description,
            'metadata': metadata,
            'name': name,
        })
        return self._make_request(requests.post, '/agents', body=body)

    def get_agent(self, agent_id: str) -> Dict:
        """Get agent, calls the GET /agents/{agentId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_agent('<agent_id>')  # the draft
        >>> client.get_agent('<agent_id>:3')  # version 3
        >>> client.get_agent('<agent_id>:@prod')  # the version the alias prod points to

        :param agent_id: Id of the agent, optionally qualified with a version (``:3``), an alias (``:@prod``) \
or ``:$latest``
        :type agent_id: str
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/agents/{_path_id(agent_id)}')

    def update_agent(
        self,
        agent_id: str,
        *,
        metadata: Optional[dict] = None,
        environments: Optional[List[dict]] = None,
        draft_environment_id: Optional[str] = UNSET,
        **optional_args,
    ) -> Dict:
        """Update agent, calls the PATCH /agents/{agentId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param name: Name of the agent
        :type name: str, optional
        :param description: Description of the agent
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param environments: The agent's environments, each \
``{'id': 'env-…', 'name': '…', 'variables': [{'name': '…', 'value': …, 'description': '…'}]}``. Leave out \
``id`` to add an environment. Replaces the list
        :type environments: list[dict], optional
        :param draft_environment_id: Id of the environment the draft runs with. None clears it
        :type draft_environment_id: str or None, optional
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'metadata': metadata,
            'environments': environments,
        })
        if draft_environment_id is not UNSET:
            body['draftEnvironmentId'] = draft_environment_id
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/agents/{_path_id(agent_id)}', body=body)

    def delete_agent(self, agent_id: str, *, delete_resources: bool = False) -> Dict:
        """Delete agent, calls the DELETE /agents/{agentId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param delete_resources: Also delete the agent's hooks, actions, models and validations
        :type delete_resources: bool, optional
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {'deleteResources': 'true'} if delete_resources else None
        return self._make_request(requests.delete, f'/agents/{_path_id(agent_id)}', params=params)

    def get_agent_graph(self, agent_id: str) -> Dict:
        """Get the agent's graph of resources, calls the GET /agents/{agentId}/graph endpoint.

        :param agent_id: Id of the agent, optionally qualified with a version, an alias or ``:$latest``
        :type agent_id: str
        :return: Graph response from REST API, with ``nodes`` and ``edges``
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/graph')

    def update_agent_graph(self, agent_id: str, *, layout: Dict[str, Optional[dict]]) -> Dict:
        """Update where the agent's resources are drawn, calls the PATCH /agents/{agentId}/graph endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param layout: Positions by resource id, e.g. ``{'<hook_id>': {'x': 0, 'y': 225}}``. ``None`` removes \
a resource's saved position
        :type layout: dict
        :return: Graph response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.patch, f'/agents/{_path_id(agent_id)}/graph', body={'layout': layout})

    def list_agent_versions(
        self,
        agent_id: str,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List the agent's published versions, calls the GET /agents/{agentId}/versions endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Versions response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({'maxResults': max_results, 'nextToken': next_token})
        return self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/versions', params=params)

    def create_agent_version(self, agent_id: str) -> Dict:
        """Publish the agent as it is now, with its resources, as a new version, calls the
        POST /agents/{agentId}/versions endpoint. If nothing changed since the latest version, that version is returned.

        :param agent_id: Id of the agent
        :type agent_id: str
        :return: The version from REST API, its ``agentId`` qualified with the version number
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.post, f'/agents/{_path_id(agent_id)}/versions', body={})

    def list_agent_aliases(self, agent_id: str) -> Dict:
        """List the agent's aliases, calls the GET /agents/{agentId}/aliases endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :return: Aliases response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/aliases')

    def get_agent_alias(self, agent_id: str, alias: str) -> Dict:
        """Get an alias of the agent, calls the GET /agents/{agentId}/aliases/{aliasId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/aliases/{_path_id(alias)}')

    def set_agent_alias(
        self,
        agent_id: str,
        alias: str,
        *,
        resource_version: int,
        environment_id: Optional[str] = UNSET,
    ) -> Dict:
        """Create an alias of the agent, or move it to another version, calls the
        PUT /agents/{agentId}/aliases/{aliasId} endpoint. Runs of ``<agent_id>:@<alias>`` run that version.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :param resource_version: The version the alias points to
        :type resource_version: int
        :param environment_id: Id of the environment the alias's runs run with. None clears it, and leaving it out \
keeps the alias's environment
        :type environment_id: str or None, optional
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body: Dict[str, Any] = {'resourceVersion': resource_version}
        if environment_id is not UNSET:
            body['environmentId'] = environment_id
        return self._make_request(requests.put, f'/agents/{_path_id(agent_id)}/aliases/{_path_id(alias)}', body=body)

    def delete_agent_alias(self, agent_id: str, alias: str) -> Dict:
        """Delete an alias of the agent, calls the DELETE /agents/{agentId}/aliases/{aliasId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param alias: Name of the alias, e.g. ``prod``
        :type alias: str
        :return: Alias response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/agents/{_path_id(agent_id)}/aliases/{_path_id(alias)}')

    def list_agents(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List agents available, calls the GET /agents endpoint.

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Agents response from REST API without the content of each agent
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/agents', params=params)

    def create_agent_run(
        self,
        agent_id: str,
        *,
        variables: Optional[dict] = None,
        trigger_id: Optional[str] = None,
    ) -> Dict:
        """Create agent run, calls the POST /agents/{agentId}/runs endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_agent_run('<agent_id>')  # runs the draft
        >>> client.create_agent_run('<agent_id>:@prod')  # runs the version the alias prod points to

        :param agent_id: Id of the agent, optionally qualified with a version (``:3``), an alias (``:@prod``) \
or ``:$latest``
        :type agent_id: str
        :param variables: additional variables to pass to the agent run
        :type variables: dict, optional
        :param trigger_id: Id of the agent's action that starts the run
        :type trigger_id: str, optional
        :return: Agent run response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'triggerId': trigger_id,
            'variables': variables or None,
        })
        return self._make_request(requests.post, f'/agents/{_path_id(agent_id)}/runs', body=body)

    def list_agent_runs(
        self,
        agent_id: str,
        *,
        history: Optional[str] = None,
        status: Optional[Union[str, List[str]]] = None,
        sort: Optional[Union[str, List[str]]] = None,
        created_time_after: Optional[Union[str, datetime]] = None,
        created_time_before: Optional[Union[str, datetime]] = None,
        updated_time_after: Optional[Union[str, datetime]] = None,
        updated_time_before: Optional[Union[str, datetime]] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List agent runs available, calls the GET /agents/{agentId}/runs endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_agent_runs('<agent_id>', status=['error', 'ready-for-review'], sort='createdTime:asc')

        :param agent_id: Id of the agent
        :type agent_id: str
        :param status: Only runs with this status, or one of these
        :type status: str or list[str], optional
        :param sort: Sort keys, e.g. ``'createdTime:asc'``: ``runId``, ``createdBy``, ``createdTime``, \
``status``, ``updatedBy`` or ``updatedTime``, then ``:asc`` or ``:desc`` (the default)
        :type sort: str or list[str], optional
        :param created_time_after: Only runs created after this time
        :type created_time_after: str or datetime, optional
        :param created_time_before: Only runs created before this time
        :type created_time_before: str or datetime, optional
        :param updated_time_after: Only runs updated after this time
        :type updated_time_after: str or datetime, optional
        :param updated_time_before: Only runs updated before this time
        :type updated_time_before: str or datetime, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: AgentRuns response from REST API without the content of each agent
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({
            'history': history,
            'status': status,
            'sort': sort,
            'createdTimeAfter': datetimestr(created_time_after),
            'createdTimeBefore': datetimestr(created_time_before),
            'updatedTimeAfter': datetimestr(updated_time_after),
            'updatedTimeBefore': datetimestr(updated_time_before),
            'maxResults': max_results,
            'nextToken': next_token,
        })
        return self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/runs', params=params)

    def get_agent_run(self, agent_id: str, run_id: str, *, get_variables: bool = False) -> Dict:
        """Get agent run, calls the GET /agents/{agentId}/runs/{runId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param run_id: Id of the run
        :type run_id: str
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        agent_run = self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/runs/{_path_id(run_id)}')
        if get_variables and agent_run.get('variablesFileUrl'):
            agent_run['variables'] = json.loads(self._make_fileserver_request(
                requests_fn=requests.get,
                file_url=agent_run['variablesFileUrl'],
                query_params={},
            ).decode())
        return agent_run

    def update_agent_run(self, agent_id: str, run_id: str, status: str) -> Dict:
        """Update agent run, calls the PATCH /agents/{agentId}/runs/{runId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param run_id: Id of the run
        :type run_id: str
        :param status: New status of the agent run
        :type status: str
        :return: AgentRun response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        path = f'/agents/{_path_id(agent_id)}/runs/{_path_id(run_id)}'
        return self._make_request(requests.patch, path, body={'status': status})

    def delete_agent_run(self, agent_id: str, run_id: str) -> Dict:
        """Delete agent run, calls the DELETE /agents/{agentId}/runs/{runId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param run_id: Id of the run
        :type run_id: str
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/agents/{_path_id(agent_id)}/runs/{_path_id(run_id)}')

    def get_agent_statistics(self, agent_id: str, *, after: Union[str, datetime], before: Union[str, datetime]) -> Dict:
        """Get agent statistics, calls the GET /agents/{agentId}/statistics endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param after: Start time for statistics interval
        :type after: str or datetime, optional
        :param before: End time for statistics interval
        :type before: str or datetime, optional
        :return: Agent statistics response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'after': datetimestr(after),
            'before': datetimestr(before),
        }

        agent_statistics = self._make_request(requests.get, f'/agents/{_path_id(agent_id)}/statistics', params=params)
        return agent_statistics

    def list_hooks(
        self,
        *,
        hook_id: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List hooks available, calls the GET /hooks endpoint.

        :param hook_id: Only these hooks, at most 100 ids
        :type hook_id: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Hooks response from REST API without the content of each hook
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'hookId': hook_id,
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/hooks', params=dictstrip(params))

    def get_hook(self, hook_id: str) -> Dict:
        """Get hook, calls the GET /hooks/{hookId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/hooks/{_path_id(hook_id)}')

    def create_hook(
        self,
        trigger: str,
        *,
        config: Optional[dict] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None,
        function_id: Optional[str] = None,
        true_action_id: Optional[str] = None,
        false_action_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        name: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict:

        """Create hook, calls the POST /hooks endpoint.

        :param trigger: What will trigger the hook to be run: 'ActionRun has Completed', 'ActionRun has Failed', \
'ActionRun has Succeeded', 'Document is Created', 'Prediction is Created' or 'ValidationTask has Completed'
        :type trigger: str
        :param function_id: Id of the function to evaluate whether to run the false or true action
        :type function_id: str, optional
        :param true_action_id: Id of the action that will happen when hook run evaluates to true
        :type true_action_id: str, optional
        :param enabled: If the hook is enabled or not
        :type enabled: bool, optional
        :param name: Name of the hook
        :type name: str, optional
        :param description: Description of the hook
        :type description: str, optional
        :param config: Dictionary that can be sent as input to true_action_id and false_action_id
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param false_action_id: Id of the action that will happen when hook run evaluates to false
        :type false_action_id: str, optional
        :param agent_id: Id of the agent the hook belongs to: one of the agent's resources from the start,\
 until it's deleted
        :type agent_id: str, optional
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'agentId': agent_id,
            'config': config,
            'description': description,
            'enabled': enabled,
            'falseActionId': false_action_id,
            'functionId': function_id,
            'metadata': metadata,
            'name': name,
            'trigger': trigger,
            'trueActionId': true_action_id,
        })
        return self._make_request(requests.post, '/hooks', body=body)

    def delete_hook(self, hook_id: str) -> Dict:
        """Delete hook, calls the DELETE /hooks/{hookId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/hooks/{_path_id(hook_id)}')

    def update_hook(
        self,
        hook_id: str,
        *,
        trigger: Optional[str] = None,
        true_action_id: Optional[str] = None,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
        false_action_id: Optional[str] = None,
        function_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:

        """Update hook, calls the PATCH /hooks/{hookId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :param trigger: What will trigger the hook to be run
        :type trigger: str, optional
        :param true_action_id: Id of the action that will happen when hook run evaluates to true
        :type true_action_id: str, optional
        :param enabled: If the hook is enabled or not
        :type enabled: bool, optional
        :param name: Name of the hook
        :type name: str, optional
        :param description: Description of the hook
        :type description: str, optional
        :param config: Dictionary that can be sent as input to true_action_id and false_action_id
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param false_action_id: Id of the action that will happen when hook run evaluates to false
        :type false_action_id: str, optional
        :param function_id: Id of the function to evaluate whether to run the false or true action
        :type function_id: str, optional
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'config': config,
            'enabled': enabled,
            'falseActionId': false_action_id,
            'functionId': function_id,
            'metadata': metadata,
            'trigger': trigger,
            'trueActionId': true_action_id,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/hooks/{_path_id(hook_id)}', body=body)

    def list_hook_runs(
        self,
        hook_id: str,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        status: Optional[Queryparam] = None,
    ) -> Dict:
        """List hook runs, calls the GET /hooks/{hookId}/runs endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param status: Statuses of the hook runs
        :type status: Queryparam, optional
        :return: HookRuns response from REST API without the content of each hook
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({
            'maxResults': max_results,
            'nextToken': next_token,
            'status': status,
        })
        return self._make_request(requests.get, f'/hooks/{_path_id(hook_id)}/runs', params=dictstrip(params))

    def get_hook_run(self, hook_id: str, run_id: str) -> Dict:
        """Get hook run, calls the GET /hooks/{hookId}/runs/{runId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :param run_id: Id of the run
        :type run_id: str
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/hooks/{_path_id(hook_id)}/runs/{_path_id(run_id)}')

    def create_hook_run(
        self,
        hook_id: str,
        input: dict,
        *,
        agent_run_id: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Run a hook, calls the POST /hooks/{hookId}/runs endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :param input: Dictionary with input to the run
        :type input: dict
        :param agent_run_id: Id of an agent run to associate with the hook run
        :type agent_run_id: str, optional
        :param name: Name of the run
        :type name: str, optional
        :param description: Description of the run
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Hook run response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'input': input, 'agentRunId': agent_run_id, **optional_args})
        return self._make_request(requests.post, f'/hooks/{_path_id(hook_id)}/runs', body=body)

    def update_hook_run(
        self,
        hook_id: str,
        run_id: str,
        *,
        status: Optional[str] = None,
        output: Optional[dict] = None,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:
        """Update hook run, calls the PATCH /hooks/{hookId}/runs/{runId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :param run_id: Id of the run
        :type run_id: str
        :param status: New status of the hook run: 'failed', 'ignored' or 'succeeded'
        :type status: str, optional
        :param output: Output dictionary of the hook run
        :type output: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        path = f'/hooks/{_path_id(hook_id)}/runs/{_path_id(run_id)}'
        body = dictstrip({'status': status, 'output': output, 'metadata': metadata})
        body.update(**optional_args)
        return self._make_request(requests.patch, path, body=body)

    def list_actions(
        self,
        *,
        action_id: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List actions available, calls the GET /actions endpoint.

        :param action_id: Only these actions, at most 100 ids
        :type action_id: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Actions response from REST API without the content of each action
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'actionId': action_id,
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/actions', params=dictstrip(params))

    def get_action(self, action_id: str) -> Dict:
        """Get action, calls the GET /actions/{actionId} endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/actions/{_path_id(action_id)}')

    def create_action(
        self,
        function_id: str,
        *,
        config: Optional[dict] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None,
        metadata: Optional[dict] = None,
        name: Optional[str] = None,
        secret_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> Dict:

        """Create action, calls the POST /actions endpoint.

        :param function_id: Id of the function to run
        :type function_id: str
        :param enabled: If the action is enabled or not
        :type enabled: bool, optional
        :param name: Name of the action
        :type name: str, optional
        :param description: Description of the action
        :type description: str, optional
        :param config: Dictionary that can be sent as input to the function
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param secret_id: Id of the secret to expand as input to functionId
        :type secret_id: str, optional
        :param agent_id: Id of the agent the action belongs to: one of the agent's resources from the start,\
 until it's deleted
        :type agent_id: str, optional
        :param connection_id: Id of the connection (e.g. to Google Drive) the function uses
        :type connection_id: str, optional
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'agentId': agent_id,
            'config': config,
            'connectionId': connection_id,
            'description': description,
            'enabled': enabled,
            'functionId': function_id,
            'metadata': metadata,
            'name': name,
            'secretId': secret_id,
        })
        return self._make_request(requests.post, '/actions', body=body)

    def delete_action(self, action_id: str) -> Dict:
        """Delete action, calls the DELETE /actions/{actionId} endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/actions/{_path_id(action_id)}')

    def update_action(
        self,
        action_id: str,
        *,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
        function_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        secret_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        **optional_args,
    ) -> Dict:

        """Update action, calls the PATCH /actions/{actionId} endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :param enabled: If the action is enabled or not
        :type enabled: bool, optional
        :param function_id: Id of the function to run
        :type function_id: str, optional
        :param name: Name of the action
        :type name: str, optional
        :param description: Description of the action
        :type description: str, optional
        :param config: Dictionary that can be sent as input to the function
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param secret_id: Id of the secret to expand as input to functionId
        :type secret_id: str, optional
        :param connection_id: Id of the connection (e.g. to Google Drive) the function uses
        :type connection_id: str, optional
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'config': config,
            'connectionId': connection_id,
            'enabled': enabled,
            'functionId': function_id,
            'metadata': metadata,
            'secretId': secret_id,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/actions/{_path_id(action_id)}', body=body)

    def list_action_runs(
        self,
        action_id: str,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        status: Optional[Queryparam] = None,
    ) -> Dict:
        """List action runs, calls the GET /actions/{actionId}/runs endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param status: Statuses of the action runs
        :type status: Queryparam, optional
        :return: ActionRuns response from REST API without the content of each action
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = dictstrip({
            'maxResults': max_results,
            'nextToken': next_token,
            'status': status,
        })
        return self._make_request(requests.get, f'/actions/{_path_id(action_id)}/runs', params=dictstrip(params))

    def get_action_run(self, action_id: str, run_id: str) -> Dict:
        """Get action run, calls the GET /actions/{actionId}/runs/{runId} endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :param run_id: Id of the run
        :type run_id: str
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/actions/{_path_id(action_id)}/runs/{_path_id(run_id)}')

    def create_action_run(
        self,
        action_id: str,
        input: dict,
        *,
        agent_run_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        no_agent_run_update: Optional[bool] = None,
    ) -> Dict:
        """Create action run, calls the POST /actions/{actionId}/runs endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :param input: Dictionary with input to the run
        :type input: dict
        :param agent_run_id: Id of an agent run to associate with the action run
        :type agent_run_id: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param no_agent_run_update: If True, the run doesn't change its agent run's status
        :type no_agent_run_update: bool, optional
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'agentRunId': agent_run_id,
            'input': input,
            'metadata': metadata,
            'noAgentRunUpdate': no_agent_run_update,
        })
        return self._make_request(requests.post, f'/actions/{_path_id(action_id)}/runs', body=body)

    def update_action_run(
        self,
        action_id: str,
        run_id: str,
        *,
        output: Optional[dict] = None,
        status: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Update action run, calls the PATCH /actions/{actionId}/runs/{runId} endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :param run_id: Id of the run
        :type run_id: str
        :param output: output dictionary of the action run
        :type output: dict
        :param status: New status of the action run
        :type status: str
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'output': output,
            'status': status,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/actions/{_path_id(action_id)}/runs/{_path_id(run_id)}', body=body)
