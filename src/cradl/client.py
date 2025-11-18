import io
import json
from base64 import b64encode
from datetime import datetime
from pathlib import Path

from typing import Callable, Dict, List, Optional, Sequence, Union
from urllib.parse import urlparse, quote

import requests
from requests.exceptions import RequestException

from .credentials import Credentials, guess_credentials
from .content import parse_content
from .log import setup_logging
from .backoff import exponential_backoff
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


def dictstrip(d):
    """Given a dict, return the dict with keys mapping to falsey values removed."""
    return {k: v for k, v in d.items() if v is not None}


def _fatal_code(e: RequestException):
    if isinstance(e.response, requests.Response) and isinstance(e.response.status_code, int):
        return 400 <= e.response.status_code < 500
    raise e


class Client:
    """A low level client to invoke api methods from Cradl."""
    def __init__(self, credentials: Optional[Credentials] = None, profile=None):
        """:param credentials: Credentials to use, instance of :py:class:`~cradl.Credentials`
        :type credentials: Credentials"""
        self.credentials = credentials or guess_credentials(profile)

    @exponential_backoff(TooManyRequestsException, max_tries=4)
    @exponential_backoff(RequestException, max_tries=3, giveup=_fatal_code)
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
        None if body is None else kwargs.update({'data': json.dumps(body)})
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
    @exponential_backoff(RequestException, max_tries=3, giveup=_fatal_code)
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
            kwargs.update({'data': content})
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
        :param generate_secret: Set to False to create a Public app client, default: True
        :type generate_secret: Boolean
        :param logout_urls: List of logout urls
        :type logout_urls: List[str]
        :param callback_urls: List of callback urls
        :type callback_urls: List[str]
        :param login_urls: List of login urls
        :type login_urls: List[str]
        :param default_login_url: Default login url
        :type default_login_url: str
        :param role_ids: List of roles to assign appClient
        :type role_ids: str, optional
        :return: AppClient response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
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
        return self._make_request(requests.get, f'/appClients/{app_client_id}')

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

        return self._make_request(requests.patch, f'/appClients/{app_client_id}', body=optional_args)

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
        return self._make_request(requests.delete, f'/appClients/{app_client_id}')

    def create_asset(self, content: Content, **optional_args) -> Dict:
        """Creates an asset, calls the POST /assets endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_asset(b'<bytes data>')

        :param content: Content to POST
        :type content: Content
        :param name: Name of the asset
        :type name: str, optional
        :param description: Description of the asset
        :type description: str, optional
        :return: Asset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        content, _ = parse_content(content)
        body = {
            'content': content,
            **optional_args,
        }
        return self._make_request(requests.post, '/assets', body=body)

    def list_assets(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List assets available, calls the GET /assets endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_assets()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Assets response from REST API without the content of each asset
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/assets', params=params)

    def get_asset(self, asset_id: str) -> Dict:
        """Get asset, calls the GET /assets/{assetId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_asset(asset_id='<asset id>')

        :param asset_id: Id of the asset
        :type asset_id: str
        :return: Asset response from REST API with content
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/assets/{asset_id}')

    def update_asset(self, asset_id: str, **optional_args) -> Dict:
        """Updates an asset, calls the PATCH /assets/{assetId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.update_asset('<asset id>', content=b'<bytes data>')

        :param asset_id: Id of the asset
        :type asset_id: str
        :param content: Content to PATCH
        :type content: Content, optional
        :param name: Name of the asset
        :type name: str, optional
        :param description: Description of the asset
        :type description: str, optional
        :return: Asset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        content = optional_args.get('content')

        if content:
            parsed_content, _ = parse_content(content)
            optional_args['content'] = parsed_content

        return self._make_request(requests.patch, f'/assets/{asset_id}', body=optional_args)

    def delete_asset(self, asset_id: str) -> Dict:
        """Delete the asset with the provided asset_id, calls the DELETE /assets/{assetId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_asset('<asset_id>')

        :param asset_id: Id of the asset
        :type asset_id: str
        :return: Asset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/assets/{asset_id}')

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
        return self._make_request(requests.get, f'/paymentMethods/{payment_method_id}')

    def update_payment_method(
        self,
        payment_method_id: str,
        *,
        stripe_setup_intent_secret: str = None,
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

        return self._make_request(requests.patch, f'/paymentMethods/{payment_method_id}', body=body)

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

        return self._make_request(requests.delete, f'/paymentMethods/{payment_method_id}')

    def create_dataset(self, *, metadata: Optional[dict] = None, **optional_args) -> Dict:
        """Creates a dataset, calls the POST /datasets endpoint.

        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'metadata': metadata})
        body.update(**optional_args)
        return self._make_request(requests.post, '/datasets', body=body)

    def list_datasets(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List datasets available, calls the GET /datasets endpoint.

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Datasets response from REST API without the content of each dataset
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/datasets', params=params)

    def get_dataset(self, dataset_id: str) -> Dict:
        """Get dataset, calls the GET /datasets/{datasetId} endpoint.

        :param dataset_id: Id of the dataset
        :type dataset_id: str
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/datasets/{dataset_id}')

    def update_dataset(self, dataset_id, metadata: Optional[dict] = None, **optional_args) -> Dict:
        """Updates a dataset, calls the PATCH /datasets/{datasetId} endpoint.

        :param dataset_id: Id of the dataset
        :type dataset_id: str
        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        body = dictstrip({'metadata': metadata})
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/datasets/{dataset_id}', body=body)

    def delete_dataset(self, dataset_id: str, delete_documents: bool = False) -> Dict:
        """Delete the dataset with the provided dataset_id, calls the DELETE /datasets/{datasetId} endpoint.

        :param dataset_id: Id of the dataset
        :type dataset_id: str
        :param delete_documents: Set to True to delete documents in dataset before deleting dataset
        :type delete_documents: bool
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        if delete_documents:
            self.delete_documents(dataset_id=dataset_id, delete_all=True)

        return self._make_request(requests.delete, f'/datasets/{dataset_id}')

    def create_transformation(self, dataset_id, operations) -> Dict:
        """Creates a transformation on a dataset, calls the POST /datasets/{datasetId}/transformations endpoint.

        :param dataset_id: Id of the dataset
        :type dataset_id: str
        :param operations: Operations to perform on the dataset
        :type operations: dict
        :return: Transformation response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        body = {'operations': operations}
        return self._make_request(requests.post, f'/datasets/{dataset_id}/transformations', body=body)

    def list_transformations(
        self,
        dataset_id,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        status: Optional[Queryparam] = None,
    ) -> Dict:
        """List transformations, calls the GET /datasets/{datasetId}/transformations endpoint.

        :param dataset_id: Id of the dataset
        :type dataset_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param status: Statuses of the transformations
        :type status: Queryparam, optional
        :return: Transformations response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
            'status': status,
        }
        return self._make_request(requests.get, f'/datasets/{dataset_id}/transformations', params=dictstrip(params))

    def delete_transformation(self, dataset_id: str, transformation_id: str) -> Dict:
        """Delete the transformation with the provided transformation_id,
        calls the DELETE /datasets/{datasetId}/transformations/{transformationId} endpoint.

        :param dataset_id: Id of the dataset
        :type dataset_id: str
        :param transformation_id: Id of the transformation
        :type transformation_id: str
        :return: Transformation response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/datasets/{dataset_id}/transformations/{transformation_id}')

    def create_document(
        self,
        content: Content,
        *,
        consent_id: Optional[str] = None,
        dataset_id: str = None,
        description: str = None,
        ground_truth: Sequence[Dict[str, str]] = None,
        metadata: Optional[dict] = None,
        name: str = None,
        agent_run_id: str = None,
        retention_in_days: int = None,
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
        :return: Document response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        content_bytes, _ = parse_content(content, False, False)

        body = {
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
        document = self._make_request(requests.get, f'/documents/{document_id}')
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
        ground_truth: Sequence[Dict[str, Union[Optional[str], bool]]] = None,  # For backwards compatibility reasons, this is placed before the *
        *,
        metadata: Optional[dict] = None,
        dataset_id: str = None,
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
        :return: Document response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'groundTruth': ground_truth,
            'datasetId': dataset_id,
            'metadata': metadata,
        })

        return self._make_request(requests.patch, f'/documents/{document_id}', body=body)

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
        return self._make_request(requests.delete, f'/documents/{document_id}')

    def list_logs(
        self,
        *,
        workflow_id: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
        transition_id: Optional[str] = None,
        transition_execution_id: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List logs, calls the GET /logs endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_logs()

        :param workflow_id: Only show logs from this workflow
        :type workflow_id: str, optional
        :param workflow_execution_id: Only show logs from this workflow execution
        :type workflow_execution_id: str, optional
        :param transition_id: Only show logs from this transition
        :type transition_id: str, optional
        :param transition_execution_id: Only show logs from this transition execution
        :type transition_execution_id: str, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Logs response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = '/logs'
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
            'workflowId': workflow_id,
            'workflowExecutionId': workflow_execution_id,
            'transitionId': transition_id,
            'transitionExecutionId': transition_execution_id,
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
        return self._make_request(requests.get, f'/logs/{log_id}')

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
            'width': width,
            'height': height,
            'fieldConfig': field_config,
            'preprocessConfig': preprocess_config,
            'postprocessConfig': postprocess_config,
            'name': name,
            'description': description,
            'metadata': metadata,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, '/models', body=body)

    def list_models(
        self,
        *,
        owner: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List models available, calls the GET /models endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_models()

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
            'maxResults': max_results,
            'nextToken': next_token,
            'owner': owner,
        }
        return self._make_request(requests.get, '/models', params=dictstrip(params))

    def get_model(self, model_id: str, *, statistics_last_n_days: Optional[int] = None) -> Dict:
        """Get a model, calls the GET /models/{modelId} endpoint.

        :param model_id: The Id of the model
        :type model_id: str
        :param statistics_last_n_days: Integer between 1 and 30
        :type statistics_last_n_days: int, optional
        :return: Model response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {'statisticsLastNDays': statistics_last_n_days}
        return self._make_request(requests.get, f'/models/{quote(model_id, safe="")}', params=params)

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
            'preprocessConfig': preprocess_config,
            'postprocessConfig': postprocess_config,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/models/{model_id}', body=body)

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
        return self._make_request(requests.delete, f'/models/{model_id}')

    def create_data_bundle(self, model_id, dataset_ids, **optional_args) -> Dict:
        """Creates a data bundle, calls the POST /models/{modelId}/dataBundles endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param dataset_ids: Dataset Ids that will be included in the data bundle
        :type dataset_ids: List[str]
        :param name: Name of the data bundle
        :type name: str, optional
        :param description: Description of the data bundle
        :type description: str, optional
        :return: Data Bundle response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        body = {'datasetIds': dataset_ids}
        body.update(**optional_args)
        return self._make_request(requests.post, f'/models/{model_id}/dataBundles', body=body)

    def get_data_bundle(self, model_id: str, data_bundle_id: str) -> Dict:
        """Get data bundle, calls the GET /models/{modelId}/dataBundles/{dataBundleId} endpoint.

        :param model_id: ID of the model
        :type model_id: str
        :param data_bundle_id: ID of the data_bundle
        :type data_bundle_id: str
        :return: DataBundle response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/models/{model_id}/dataBundles/{data_bundle_id}')

    def create_training(
        self,
        model_id,
        data_bundle_ids,
        *,
        metadata: Optional[dict] = None,
        data_scientist_assistance: Optional[bool] = None,
        **optional_args,
    ) -> Dict:
        """Requests a training, calls the POST /models/{modelId}/trainings endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param data_bundle_ids: Data bundle ids that will be used for training
        :type data_bundle_ids: List[str]
        :param name: Name of the data bundle
        :type name: str, optional
        :param description: Description of the training
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param data_scientist_assistance: Request that one of Cradl's data scientists reviews and optimizes your training
        :type data_scientist_assistance: bool, optional
        :return: Training response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        body = dictstrip({
            'dataBundleIds': data_bundle_ids,
            'dataScientistAssistance': data_scientist_assistance,
            'metadata': metadata,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, f'/models/{model_id}/trainings', body=body)

    def get_training(self, model_id: str, training_id: str, statistics_last_n_days: Optional[int] = None) -> Dict:
        """Get training, calls the GET /models/{modelId}/trainings/{trainingId} endpoint.

        :param model_id: ID of the model
        :type model_id: str
        :param training_id: ID of the training
        :type training_id: str
        :param statistics_last_n_days: Integer between 1 and 30
        :type statistics_last_n_days: int, optional
        :return: Training response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {'statisticsLastNDays': statistics_last_n_days}
        return self._make_request(requests.get, f'/models/{model_id}/trainings/{training_id}', params=params)

    def list_trainings(self, model_id, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List trainings available, calls the GET /models/{modelId}/trainings endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Trainings response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, f'/models/{model_id}/trainings', params=params)

    def update_training(
        self,
        model_id: str,
        training_id: str,
        **optional_args,
    ) -> Dict:
        """Updates a training, calls the PATCH /models/{modelId}/trainings/{trainingId} endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param training_id: Id of the training
        :type training_id: str
        :param deployment_environment_id: Id of deploymentEnvironment
        :type deployment_environment_id: str, optional
        :param name: Name of the training
        :type name: str, optional
        :param description: Description of the training
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :return: Training response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {}
        if 'deployment_environment_id' in optional_args:
            body['deploymentEnvironmentId'] = optional_args.pop('deployment_environment_id')
        body.update(optional_args)

        return self._make_request(requests.patch, f'/models/{model_id}/trainings/{training_id}', body=body)

    def list_data_bundles(
        self,
        model_id,
        *,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List data bundles available, calls the GET /models/{modelId}/dataBundles endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Data Bundles response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, f'/models/{model_id}/dataBundles', params=params)

    def update_data_bundle(
        self,
        model_id: str,
        data_bundle_id: str,
        **optional_args,
    ) -> Dict:
        """Updates a data bundle, calls the PATCH /models/{modelId}/dataBundles/{dataBundleId} endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param data_bundle_id: Id of the data bundle
        :type data_bundle_id: str
        :param name: Name of the data bundle
        :type name: str, optional
        :param description: Description of the data bundle
        :type description: str, optional
        :return: Data Bundle response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.patch, f'/models/{model_id}/dataBundles/{data_bundle_id}', body=optional_args)

    def delete_data_bundle(self, model_id: str, data_bundle_id: str) -> Dict:
        """Delete the data bundle with the provided data_bundle_id,
        calls the DELETE /models/{modelId}/dataBundles/{dataBundleId} endpoint.

        :param model_id: Id of the model
        :type model_id: str
        :param data_bundle_id: Id of the data bundle
        :type data_bundle_id: str
        :return: Data Bundle response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/models/{model_id}/dataBundles/{data_bundle_id}')

    def get_organization(self, organization_id: str) -> Dict:
        """Get an organization, calls the GET /organizations/{organizationId} endpoint.

        :param organization_id: The Id of the organization
        :type organization_id: str
        :return: Organization response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/organizations/{organization_id}')

    def update_organization(
        self,
        organization_id: str,
        *,
        payment_method_id: str = None,
        document_retention_in_days: int = None,
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
        :return: Organization response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {**optional_args}
        if payment_method_id:
            body['paymentMethodId'] = payment_method_id

        if document_retention_in_days:
            body['documentRetentionInDays'] = document_retention_in_days

        return self._make_request(requests.patch, f'/organizations/{organization_id}', body=body)

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
        }
        return self._make_request(requests.post, '/predictions', body=dictstrip(body))

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
        return self._make_request(requests.get, f'/predictions/{prediction_id}')

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

        return self._make_request(requests.get, f'/plans/{quote(plan_id, safe="")}')

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

    def get_deployment_environment(self, deployment_environment_id: str) -> Dict:
        """Get information about a specific DeploymentEnvironment, calls the
        GET /deploymentEnvironments/{deploymentEnvironmentId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_deployment_environment('<deployment_environment_id>')

        :param deployment_environment_id: Id of the DeploymentEnvironment
        :type deployment_environment_id: str
        :return: DeploymentEnvironment response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        return self._make_request(requests.get, f'/deploymentEnvironments/{quote(deployment_environment_id, safe="")}')

    def list_deployment_environments(
        self,
        *,
        owner: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None
    ) -> Dict:
        """List DeploymentEnvironments available, calls the GET /deploymentEnvironments endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_deployment_environments()

        :param owner: Organizations to retrieve DeploymentEnvironments from
        :type owner: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: DeploymentEnvironments response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'owner': owner,
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/deploymentEnvironments', params=dictstrip(params))

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
        return self._make_request(requests.patch, f'/secrets/{secret_id}', body=body)

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
        return self._make_request(requests.delete, f'/secrets/{secret_id}')

    def create_transition(
        self,
        transition_type: str,
        *,
        parameters: Optional[dict] = None,
        **optional_args,
    ) -> Dict:
        """Creates a transition, calls the POST /transitions endpoint.

        >>> import json
        >>> from pathlib import Path
        >>> from cradl.client import Client
        >>> client = Client()
        >>> # A typical docker transition
        >>> docker_params = {
        >>>     'imageUrl': '<image_url>',
        >>>     'credentials': {'username': '<username>', 'password': '<password>'}
        >>> }
        >>> client.create_transition('docker', params=docker_params)
        >>> # A manual transition with UI
        >>> assets = {'jsRemoteComponent': 'cradl:asset:<hex-uuid>', '<other asset name>': 'cradl:asset:<hex-uuid>'}
        >>> manual_params = {'assets': assets}
        >>> client.create_transition('manual', params=manual_params)

        :param transition_type: Type of transition "docker"|"manual"
        :type transition_type: str
        :param name: Name of the transition
        :type name: str, optional
        :param parameters: Parameters to the corresponding transition type
        :type parameters: dict, optional
        :param description: Description of the transition
        :type description: str, optional
        :return: Transition response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'transitionType': transition_type,
            'parameters': parameters,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, '/transitions', body=body)

    def list_transitions(
        self,
        *,
        transition_type: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List transitions, calls the GET /transitions endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_transitions('<transition_type>')

        :param transition_type: Types of transitions
        :type transition_type: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Transitions response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = '/transitions'
        params = {
            'transitionType': transition_type,
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, url, params=dictstrip(params))

    def get_transition(self, transition_id: str) -> Dict:
        """Get the transition with the provided transition_id, calls the GET /transitions/{transitionId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_transition('<transition_id>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :return: Transition response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/transitions/{transition_id}')

    def update_transition(
        self,
        transition_id: str,
        *,
        assets: Optional[dict] = None,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        image_url: Optional[str] = None,
        lambda_id: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Updates a transition, calls the PATCH /transitions/{transitionId} endpoint.

        >>> import json
        >>> from pathlib import Path
        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.update_transition('<transition-id>', name='<name>', description='<description>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :param name: Name of the transition
        :type name: str, optional
        :param description: Description of the transition
        :type description: str, optional
        :param assets: A dictionary where the values are assetIds that can be used in a manual transition
        :type assets: dict, optional
        :param environment: Environment variables to use for a docker transition
        :type environment: dict, optional
        :param environment_secrets: \
            A list of secretIds that contains environment variables to use for a docker transition
        :type environment_secrets: list, optional
        :param cpu: Number of CPU units to use for a docker transition
        :type cpu: int, optional
        :param memory: Memory in MiB to use for a docker transition
        :type memory: int, optional
        :param image_url: Docker image url to use for a docker transition
        :type image_url: str, optional
        :param lambda_id: Lambda ID to use for a lambda transition
        :type lambda_id: str, optional
        :param secret_id: Secret containing a username and password if image_url points to a private docker image
        :type secret_id: str, optional
        :return: Transition response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {}
        parameters = dictstrip({
            'assets': assets,
            'cpu': cpu,
            'imageUrl': image_url,
            'lambdaId': lambda_id,
            'memory': memory,
        })

        if 'environment' in optional_args:
            parameters['environment'] = optional_args.pop('environment')
        if 'environment_secrets' in optional_args:
            parameters['environmentSecrets'] = optional_args.pop('environment_secrets')
        if 'secret_id' in optional_args:
            parameters['secretId'] = optional_args.pop('secret_id')
        if parameters:
            body['parameters'] = parameters

        body.update(**optional_args)
        return self._make_request(requests.patch, f'/transitions/{transition_id}', body=body)

    def execute_transition(self, transition_id: str) -> Dict:
        """Start executing a manual transition, calls the POST /transitions/{transitionId}/executions endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.execute_transition('<transition_id>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :return: Transition execution response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        endpoint = f'/transitions/{transition_id}/executions'
        return self._make_request(requests.post, endpoint, body={})

    def delete_transition(self, transition_id: str) -> Dict:
        """Delete the transition with the provided transition_id, calls the DELETE /transitions/{transitionId} endpoint.
           Will fail if transition is in use by one or more workflows.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_transition('<transition_id>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :return: Transition response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/transitions/{transition_id}')

    def list_transition_executions(
        self,
        transition_id: str,
        *,
        status: Optional[Queryparam] = None,
        execution_id: Optional[Queryparam] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
    ) -> Dict:
        """List executions in a transition, calls the GET /transitions/{transitionId}/executions endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_transition_executions('<transition_id>', '<status>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :param status: Statuses of the executions
        :type status: Queryparam, optional
        :param order: Order of the executions, either 'ascending' or 'descending'
        :type order: str, optional
        :param sort_by: the sorting variable of the executions, either 'endTime', or 'startTime'
        :type sort_by: str, optional
        :param execution_id: Ids of the executions
        :type execution_id: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Transition executions responses from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = f'/transitions/{transition_id}/executions'
        params = {
            'status': status,
            'executionId': execution_id,
            'maxResults': max_results,
            'nextToken': next_token,
            'order': order,
            'sortBy': sort_by,
        }
        return self._make_request(requests.get, url, params=dictstrip(params))

    def get_transition_execution(self, transition_id: str, execution_id: str) -> Dict:
        """Get an execution of a transition, calls the GET /transitions/{transitionId}/executions/{executionId} endpoint

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_transition_execution('<transition_id>', '<execution_id>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :param execution_id: Id of the executions
        :type execution_id: str
        :return: Transition execution responses from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = f'/transitions/{transition_id}/executions/{execution_id}'
        return self._make_request(requests.get, url)

    def update_transition_execution(
        self,
        transition_id: str,
        execution_id: str,
        status: str,
        *,
        output: Optional[dict] = None,
        error: Optional[dict] = None,
        start_time: Optional[Union[str, datetime]] = None,
    ) -> Dict:
        """Ends the processing of the transition execution,
        calls the PATCH /transitions/{transition_id}/executions/{execution_id} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> output = {...}
        >>> client.update_transition_execution('<transition_id>', '<execution_id>', 'succeeded', output)
        >>> error = {"message": 'The execution could not be processed due to ...'}
        >>> client.update_transition_execution('<transition_id>', '<execution_id>', 'failed', error)

        :param transition_id: Id of the transition that performs the execution
        :type transition_id: str
        :param execution_id: Id of the execution to update
        :type execution_id: str
        :param status: Status of the execution 'succeeded|failed'
        :type status: str
        :param output: Output from the execution, required when status is 'succeded'
        :type output: dict, optional
        :param error: Error from the execution, required when status is 'failed', needs to contain 'message'
        :type error: dict, optional
        :param start_time: start time that will replace the original start time of the execution
        :type start_time: str, optional
        :return: Transition execution response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """

        url = f'/transitions/{transition_id}/executions/{execution_id}'
        body = {
            'status': status,
            'output': output,
            'error': error,
            'startTime': datetimestr(start_time),
        }
        return self._make_request(requests.patch, url, body=dictstrip(body))

    def send_heartbeat(self, transition_id: str, execution_id: str) -> Dict:
        """Send heartbeat for a manual execution to signal that we are still working on it.
        Must be done at minimum once every 60 seconds or the transition execution will time out,
        calls the POST /transitions/{transitionId}/executions/{executionId}/heartbeats endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.send_heartbeat('<transition_id>', '<execution_id>')

        :param transition_id: Id of the transition
        :type transition_id: str
        :param execution_id: Id of the transition execution
        :type execution_id: str
        :return: Empty response
        :rtype: None

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        endpoint = f'/transitions/{transition_id}/executions/{execution_id}/heartbeats'
        return self._make_request(requests.post, endpoint, body={})

    def create_user(self, email: str, *, app_client_id, **optional_args) -> Dict:
        """Creates a new user, calls the POST /users endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.create_user('<email>', name='John Doe')

        :param email: Email to the new user
        :type email: str
        :param role_ids: List of roles to assign user
        :type role_ids: str, optional
        :return: User response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = {
            'email': email,
            'appClientId': app_client_id,
            **optional_args,
        }
        if 'role_ids' in body:
            body['roleIds'] = body.pop('role_ids') or []

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
        return self._make_request(requests.get, f'/users/{user_id}')

    def update_user(self, user_id: str, **optional_args) -> Dict:
        """Updates a user, calls the PATCH /users/{userId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.update_user('<user id>', name='John Doe')

        :param user_id: Id of the user
        :type user_id: str
        :param role_ids: List of roles to assign user
        :type role_ids: str, optional
        :return: User response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        if 'role_ids' in optional_args:
            optional_args['roleIds'] = optional_args.pop('role_ids') or []

        return self._make_request(requests.patch, f'/users/{user_id}', body=optional_args)

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
        return self._make_request(requests.delete, f'/users/{user_id}')

    def create_workflow(
        self,
        specification: dict,
        *,
        email_config: Optional[dict] = None,
        error_config: Optional[dict] = None,
        completed_config: Optional[dict] = None,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:
        """Creates a new workflow, calls the POST /workflows endpoint.
        Check out Cradl's tutorials for more info on how to create a workflow.

        >>> from cradl.client import Client
        >>> from pathlib import Path
        >>> client = Client()
        >>> specification = {'language': 'ASL', 'version': '1.0.0', 'definition': {...}}
        >>> error_config = {'email': '<error-recipient>'}
        >>> client.create_workflow(specification, error_config=error_config)

        :param specification: Specification of the workflow, \
            currently supporting ASL: https://states-language.net/spec.html
        :type specification: dict
        :param email_config: Create workflow with email input
        :type email_config: dict, optional
        :param error_config: Configuration of error handler
        :type error_config: dict, optional
        :param completed_config: Configuration of a job to run whenever a workflow execution ends
        :type completed_config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param name: Name of the workflow
        :type name: str, optional
        :param description: Description of the workflow
        :type description: str, optional
        :return: Workflow response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'completedConfig': completed_config,
            'emailConfig': email_config,
            'errorConfig': error_config,
            'metadata': metadata,
            'specification': specification,
        })
        body.update(**optional_args)

        return self._make_request(requests.post, '/workflows', body=body)

    def list_workflows(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List workflows, calls the GET /workflows endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_workflows()

        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :return: Workflows response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        params = {
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/workflows', params=params)

    def get_workflow(self, workflow_id: str) -> Dict:
        """Get the workflow with the provided workflow_id, calls the GET /workflows/{workflowId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_workflow('<workflow_id>')

        :param workflow_id: Id of the workflow
        :type workflow_id: str
        :return: Workflow response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/workflows/{workflow_id}')

    def update_workflow(
        self,
        workflow_id: str,
        *,
        error_config: Optional[dict] = None,
        completed_config: Optional[dict] = None,
        metadata: Optional[dict] = None,
        status: Optional[str] = None,
        **optional_args,
    ) -> Dict:
        """Updates a workflow, calls the PATCH /workflows/{workflowId} endpoint.

        >>> import json
        >>> from pathlib import Path
        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.update_workflow('<workflow-id>', name='<name>', description='<description>')

        :param workflow_id: Id of the workflow
        :param error_config: Configuration of error handler
        :type error_config: dict, optional
        :param completed_config: Configuration of a job to run whenever a workflow execution ends
        :type completed_config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :type name: str
        :param name: Name of the workflow
        :type name: str, optional
        :param description: Description of the workflow
        :type description: str, optional
        :param email_config: Update workflow with email input
        :type email_config: dict, optional
        :param status: Set status of workflow to development or production
        :type status: str, optional
        :return: Workflow response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'completedConfig': completed_config,
            'errorConfig': error_config,
            'metadata': metadata,
            'status': status,
        })

        if 'email_config' in optional_args:
            optional_args['emailConfig'] = optional_args.pop('email_config')
        body.update(**optional_args)

        return self._make_request(requests.patch, f'/workflows/{workflow_id}', body=body)

    def delete_workflow(self, workflow_id: str) -> Dict:
        """Delete the workflow with the provided workflow_id, calls the DELETE /workflows/{workflowId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_workflow('<workflow_id>')

        :param workflow_id: Id of the workflow
        :type workflow_id: str
        :return: Workflow response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/workflows/{workflow_id}')

    def execute_workflow(self, workflow_id: str, content: dict) -> Dict:
        """Start a workflow execution, calls the POST /workflows/{workflowId}/executions endpoint.

        >>> from cradl.client import Client
        >>> from pathlib import Path
        >>> client = Client()
        >>> content = {...}
        >>> client.execute_workflow('<workflow_id>', content)

        :param workflow_id: Id of the workflow
        :type workflow_id: str
        :param content: Input to the first step of the workflow
        :type content: dict
        :return: Workflow execution response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        endpoint = f'/workflows/{workflow_id}/executions'
        return self._make_request(requests.post, endpoint, body={'input': content})

    def list_workflow_executions(
        self,
        workflow_id: str,
        *,
        status: Optional[Queryparam] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        from_start_time: Optional[Union[str, datetime]] = None,
        to_start_time: Optional[Union[str, datetime]] = None,
    ) -> Dict:
        """List executions in a workflow, calls the GET /workflows/{workflowId}/executions endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.list_workflow_executions('<workflow_id>', '<status>')

        :param workflow_id: Id of the workflow
        :type workflow_id: str
        :param order: Order of the executions, either 'ascending' or 'descending'
        :type order: str, optional
        :param sort_by: the sorting variable of the executions, either 'endTime', or 'startTime'
        :type sort_by: str, optional
        :param status: Statuses of the executions
        :type status: Queryparam, optional
        :param max_results: Maximum number of results to be returned
        :type max_results: int, optional
        :param next_token: A unique token for each page, use the returned token to retrieve the next page.
        :type next_token: str, optional
        :param from_start_time: Specify a datetime range for start_time with from_start_time as lower bound
        :type from_start_time: str or datetime, optional
        :param to_start_time: Specify a datetime range for start_time with to_start_time as upper bound
        :type to_start_time: str or datetime, optional
        :return: Workflow executions responses from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = f'/workflows/{workflow_id}/executions'
        params = {
            'status': status,
            'order': order,
            'sortBy': sort_by,
            'maxResults': max_results,
            'nextToken': next_token,
        }

        if any([from_start_time, to_start_time]):
            params['fromStartTime'] = datetimestr(from_start_time)
            params['toStartTime'] = datetimestr(to_start_time)

        return self._make_request(requests.get, url, params=params)

    def get_workflow_execution(self, workflow_id: str, execution_id: str) -> Dict:
        """Get a workflow execution, calls the GET /workflows/{workflow_id}/executions/{execution_id} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.get_workflow_execution('<workflow_id>', '<execution_id>')

        :param workflow_id: Id of the workflow that performs the execution
        :type workflow_id: str
        :param execution_id: Id of the execution to get
        :type execution_id: str
        :return: Workflow execution response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = f'/workflows/{workflow_id}/executions/{execution_id}'
        return self._make_request(requests.get, url)

    def update_workflow_execution(
        self,
        workflow_id: str,
        execution_id: str,
        *,
        next_transition_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict:
        """Retry or end the processing of a workflow execution,
        calls the PATCH /workflows/{workflow_id}/executions/{execution_id} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.update_workflow_execution('<workflow_id>', '<execution_id>', '<next_transition_id>')

        :param workflow_id: Id of the workflow that performs the execution
        :type workflow_id: str
        :param execution_id: Id of the execution to update
        :type execution_id: str
        :param next_transition_id: the next transition to transition into, to end the workflow-execution, \
        use: cradl:transition:commons-failed
        :type next_transition_id: str, optional
        :param status: Update the execution with this status, can only update from succeeded to completed and vice versa
        :type status: str, optional
        :return: Workflow execution response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        url = f'/workflows/{workflow_id}/executions/{execution_id}'
        body = {
            'nextTransitionId': next_transition_id,
            'status': status,
        }
        return self._make_request(requests.patch, url, body=dictstrip(body))

    def delete_workflow_execution(self, workflow_id: str, execution_id: str) -> Dict:
        """Deletes the execution with the provided execution_id from workflow_id,
        calls the DELETE /workflows/{workflowId}/executions/{executionId} endpoint.

        >>> from cradl.client import Client
        >>> client = Client()
        >>> client.delete_workflow_execution('<workflow_id>', '<execution_id>')

        :param workflow_id: Id of the workflow
        :type workflow_id: str
        :param execution_id: Id of the execution
        :type execution_id: str
        :return: WorkflowExecution response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/workflows/{workflow_id}/executions/{execution_id}')

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
        :return: Role response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({'permissions': permissions})
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/roles/{role_id}', body=body)


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
        return self._make_request(requests.get, f'/roles/{role_id}')

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
        return self._make_request(requests.delete, f'/roles/{role_id}')

    def get_validation(self, validation_id: str) -> Dict:
        """Get validation, calls the GET /validations/{validationId} endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :return: Validation response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/validations/{validation_id}')

    def list_validations(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List validations available, calls the GET /validations endpoint.

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
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/validations', params=params)

    def create_validation(
        self,
        *,
        config: Optional[dict] = None,
        metadata: Optional[dict] = None,
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
        :return: Dataset response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'config': config,
            'metadata': metadata,
        })
        body.update(**optional_args)
        return self._make_request(requests.post, '/validations', body=body)

    def delete_validation(self, validation_id: str) -> Dict:
        """Delete the validation with the provided validation_id, calls the DELETE /validations/{validation_id} endpoint.

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
        return self._make_request(requests.delete, f'/validations/{validation_id}')

    def create_validation_task(
        self,
        validation_id: str,
        input: dict,
        *,
        metadata: Optional[dict] = None,
        agent_run_id: str = None,
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
        return self._make_request(requests.post, f'/validations/{validation_id}/tasks', body=body)

    def update_validation_task(
        self,
        validation_id: str,
        validation_task_id: str,
        output: dict,
        status: str,
        *,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:
        """Creates a validation, calls the POST /validations endpoint.

        :param validation_id: Id of the validation
        :type validation_id: str
        :param validation_task_id: Id of the validation task
        :type validation_task_id: str
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
            path=f'/validations/{validation_id}/tasks/{validation_task_id}',
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
        return self._make_request(requests.get, f'/validations/{validation_id}/tasks', params=dictstrip(params))

    def create_agent(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        resource_ids: Optional[list[str]] = None,
    ) -> Dict:
        """Get agent, calls the POST /agents endpoint.

        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param resource_ids: Description of the dataset
        :type resource_ids: list[str], optional
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'description': description,
            'metadata': metadata,
            'name': name,
            'resourceIds': resource_ids,
        })
        return self._make_request(requests.post, '/agents', body=body)

    def get_agent(self, agent_id: str) -> Dict:
        """Get agent, calls the GET /agents/{agentId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/agents/{agent_id}')

    def update_agent(
        self,
        agent_id: str,
        *,
        metadata: Optional[dict] = None,
        resource_ids: Optional[list[str]] = None,
        **optional_args,
    ) -> Dict:
        """Get agent, calls the PATCH /agents/{agentId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param resource_ids: Description of the dataset
        :type resource_ids: list[str], optional
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'metadata': metadata,
            'resourceIds': resource_ids,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/agents/{agent_id}', body=body)

    def delete_agent(self, agent_id: str) -> Dict:
        """Delete agent, calls the DELETE /agents/{agentId} endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.delete, f'/agents/{agent_id}')

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

    def create_agent_run(self, agent_id: str, *, variables: dict = None) -> Dict:
        """Create agent run, calls the POST /agents/{agentId}/runs endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
        :return: Agent response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        if variables:
            body = {'variables': variables}
        else:
            body = {}
        return self._make_request(requests.post, f'/agents/{agent_id}/runs', body=body)

    def list_agent_runs(
        self,
        agent_id: str,
        *,
        history: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List agent runs available, calls the GET /agents/{agentId}/runs endpoint.

        :param agent_id: Id of the agent
        :type agent_id: str
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
            'maxResults': max_results,
            'nextToken': next_token,
        })
        return self._make_request(requests.get, f'/agents/{agent_id}/runs', params=params)

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
        agent_run = self._make_request(requests.get, f'/agents/{agent_id}/runs/{run_id}')
        if get_variables and agent_run.get('variablesFileUrl'):
            agent_run['variables'] = json.loads(self._make_fileserver_request(
                requests_fn=requests.get,
                file_url=agent_run['variablesFileUrl'],
                query_params={},
            ).decode())
        return agent_run

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
        return self._make_request(requests.delete, f'/agents/{agent_id}/runs/{run_id}')

    def list_hooks(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List hooks available, calls the GET /hooks endpoint.

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
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/hooks', params=params)

    def get_hook(self, hook_id: str) -> Dict:
        """Get hook, calls the GET /hooks/{hookId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/hooks/{hook_id}')

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
    ) -> Dict:

        """Get hook, calls the POST /hooks endpoint.

        :param trigger: What will trigger the hook to be run
        :type trigger: str
        :param function_id: Id of the function to evaluate whether to run the false or true action
        :type function_id: str
        :param true_action_id: Id of the action that will happen when hook run evaluates to true
        :type true_action_id: str
        :param enabled: If the hook is enabled or not
        :type enabled: bool, optional
        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param config: Dictionary that can be sent as input to true_action_id and false_action_id
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param false_action_id: Id of the action that will happen when hook run evaluates to false
        :type false_action_id: str, optional
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
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
        return self._make_request(requests.delete, f'/hooks/{hook_id}')

    def update_hook(
        self,
        hook_id: str,
        *,
        trigger: Optional[str] = None,
        true_action_id: Optional[str] = None,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
        false_action_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        **optional_args,
    ) -> Dict:

        """Get hook, calls the PATCH /hooks/{hookId} endpoint.

        :param hook_id: Id of the hook the hook belongs to
        :type hook_id: str
        :param trigger: What will trigger the hook to be run
        :type trigger: str, optional
        :param true_action_id: Id of the action that will happen when hook run evaluates to true
        :type true_action_id: str, optional
        :param enabled: If the hook is enabled or not
        :type enabled: bool, optional
        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param config: Dictionary that can be sent as input to true_action_id and false_action_id
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param false_action_id: Id of the action that will happen when hook run evaluates to false
        :type false_action_id: str, optional
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'config': config,
            'enabled': enabled,
            'falseActionId': false_action_id,
            'metadata': metadata,
            'trigger': trigger,
            'trueActionId': true_action_id,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/hooks/{hook_id}', body=body)

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
        return self._make_request(requests.get, f'/hooks/{hook_id}/runs', params=dictstrip(params))

    def get_hook_run(self, hook_id: str, run_id: str) -> Dict:
        """Get hook, calls the GET /hooks/{hookId}/runs/{runId} endpoint.

        :param hook_id: Id of the hook
        :type hook_id: str
        :param run_id: Id of the run
        :type run_id: str
        :return: Hook response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/hooks/{hook_id}/runs/{run_id}')

    def list_actions(self, *, max_results: Optional[int] = None, next_token: Optional[str] = None) -> Dict:
        """List actions available, calls the GET /actions endpoint.

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
            'maxResults': max_results,
            'nextToken': next_token,
        }
        return self._make_request(requests.get, '/actions', params=params)

    def get_action(self, action_id: str) -> Dict:
        """Get action, calls the GET /actions/{actionId} endpoint.

        :param action_id: Id of the action
        :type action_id: str
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        return self._make_request(requests.get, f'/actions/{action_id}')

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
    ) -> Dict:

        """Create action, calls the POST /actions endpoint.

        :param function_id: Id of the function to run
        :type function_id: str
        :param enabled: If the action is enabled or not
        :type enabled: bool, optional
        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param config: Dictionary that can be sent as input to true_action_id and false_action_id
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param secret_id: Id of the secret to expand as input to functionId
        :type secret_id: str, optional
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'config': config,
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
        return self._make_request(requests.delete, f'/actions/{action_id}')

    def update_action(
        self,
        action_id: str,
        *,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
        function_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        secret_id: Optional[str] = None,
        **optional_args,
    ) -> Dict:

        """Get action, calls the PATCH /actions/{actionId} endpoint.

        :param action_id: Id of the action the action belongs to
        :type action_id: str
        :param enabled: If the action is enabled or not
        :type enabled: bool, optional
        :param function_id: Id of the function to run
        :type function_id: str
        :param name: Name of the dataset
        :type name: str, optional
        :param description: Description of the dataset
        :type description: str, optional
        :param config: Dictionary that can be sent as input to true_action_id and false_action_id
        :type config: dict, optional
        :param metadata: Dictionary that can be used to store additional information
        :type metadata: dict, optional
        :param secret_id: Id of the secret to expand as input to functionId
        :type secret_id: str
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
 :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'config': config,
            'enabled': enabled,
            'functionId': function_id,
            'metadata': metadata,
            'secretId': secret_id,
        })
        body.update(**optional_args)
        return self._make_request(requests.patch, f'/actions/{action_id}', body=body)

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
        return self._make_request(requests.get, f'/actions/{action_id}/runs', params=dictstrip(params))

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
        return self._make_request(requests.get, f'/actions/{action_id}/runs/{run_id}')

    def create_action_run(
        self,
        action_id: str,
        input: dict,
        *,
        agent_run_id: Optional[str] = None,
        metadata: Optional[dict] = None,
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
        :return: Action response from REST API
        :rtype: dict

        :raises: :py:class:`~cradl.InvalidCredentialsException`, :py:class:`~cradl.TooManyRequestsException`,\
    :py:class:`~cradl.LimitExceededException`, :py:class:`requests.exception.RequestException`
        """
        body = dictstrip({
            'agentRunId': agent_run_id,
            'input': input,
            'metadata': metadata,
        })
        return self._make_request(requests.post, f'/actions/{action_id}/runs', body=body)

