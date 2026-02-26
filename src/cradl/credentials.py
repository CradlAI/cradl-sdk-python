import json
import os
import time
from base64 import b64decode
from os.path import exists, expanduser
from pathlib import Path
from typing import Optional, Tuple

import requests  # type: ignore
from requests.exceptions import RequestException  # type: ignore

from .backoff import exponential_backoff, fatal_code
from .log import setup_logging
from .response import TooManyRequestsException, BadRequest

logger = setup_logging(__name__)
NULL_TOKEN = '', 0


class MissingCredentials(Exception):
    pass


class MissingClaims(Exception):
    pass


class Credentials:
    """Used to fetch and store credentials and to generate/cache an access token.

    :param client_id: The client id
    :type str:
    :param client_secret: The client secret
    :type str:
    :param auth_endpoint: The auth endpoint
    :type str:
    :param api_endpoint: The api endpoint
    :type str:"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_endpoint: str,
        api_endpoint: str,
        cached_profile: Optional[str] = None,
        cache_path: Path = Path(expanduser('~/.cradl/token-cache.json')),
        access_token: Optional[str] = None,
    ):
        if not all([client_id, client_secret, auth_endpoint, api_endpoint]):
            raise MissingCredentials

        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_endpoint = auth_endpoint
        self.api_endpoint = api_endpoint
        self.cached_profile = cached_profile
        self.cache_path = cache_path

        if access_token:
            if not isinstance(access_token, str):
                raise ValueError(f'access_token must be a JWT token formatted as a string, got {type(access_token)}')
            try:
                access_token_payload = access_token.split('.')[1]
                padding = '=' * (len(access_token_payload) % 4)
                expiration = json.loads(b64decode(access_token_payload + padding))['exp']
            except IndexError:
                raise ValueError(f'Invalid access token "{access_token}". Expected a JWT token')
            except KeyError:
                raise ValueError(f'Invalid access token "{access_token}". Expected a JWT token with "exp" as a key')

            self._token = access_token, expiration
        elif cached_profile:
            self._token = read_token_from_cache(cached_profile, cache_path)
        else:
            self._token = NULL_TOKEN

    @property
    def access_token(self) -> str:
        access_token, expiration = self._token

        if not access_token or time.time() > expiration:
            access_token, expiration = self._get_client_credentials()
            self._token = (access_token, expiration)

            if self.cached_profile:
                write_token_to_cache(self.cached_profile, self._token, self.cache_path)

        return access_token

    # Backoff on BadRequest since Kinde seems to sometimes give bogus 400 responses
    @exponential_backoff(exceptions=(TooManyRequestsException, BadRequest), max_tries=4)  # type: ignore
    @exponential_backoff(exceptions=(RequestException, MissingClaims), max_tries=3, giveup=fatal_code)  # type: ignore
    def _get_client_credentials(self) -> Tuple[str, int]:
        get_credentials_from_kinde = any(endpoint in self.auth_endpoint for endpoint in ['auth.lucidtech.io', 'auth.cradl.ai', 'kinde.com'])
        if get_credentials_from_kinde:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials',
                'audience': 'https://api.cradl.ai/v1',
            }
            response = requests.post(self.auth_endpoint, data=data)
        else:
            url = f'https://{self.auth_endpoint}/token?grant_type=client_credentials'
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
            response = requests.post(url, headers=headers, auth=auth)

        response.raise_for_status()

        response_data = response.json()
        token = response_data['access_token']

        if get_credentials_from_kinde:
            # Confirm that Kinde has provided necessary claims
            _, payload, _ = token.split('.')
            claims = json.loads(b64decode(payload))
            if not all([claims.get(key) for key in ['external_app_client_id', 'external_organization_id', 'scope']]):
                raise MissingClaims

        return token, time.time() + response_data['expires_in']


def read_token_from_cache(cached_profile: str, cache_path: Path):
    if not cache_path.exists():
        return NULL_TOKEN

    try:
        cache = json.loads(cache_path.read_text())
        return cache[cached_profile]['access_token'], cache[cached_profile]['expires_in']
    except Exception as e:
        logger.warning(e)

    return NULL_TOKEN


def write_token_to_cache(cached_profile, token, cache_path: Path):
    if not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = {}
    else:
        cache = json.loads(cache_path.read_text())

    access_token, expires_in = token
    cache[cached_profile] = {
        'access_token': access_token,
        'expires_in': expires_in,
    }

    cache_path.write_text(json.dumps(cache, indent=2))


def read_from_environ() -> dict[str, Optional[str]]:
    """Read the following environment variables and return them:
        - CRADL_CLIENT_ID
        - CRADL_CLIENT_SECRET
        - CRADL_AUTH_ENDPOINT
        - CRADL_API_ENDPOINT
        - CRADL_ACCESS_TOKEN (optional)

    :return: Dictionary of client_id, client_secret, auth_endpoint, api_endpoint, cached_profile
    :rtype: dict[str, Optional[str]]"""

    return dict(
        access_token=os.environ.get('CRADL_ACCESS_TOKEN'),
        api_endpoint=os.environ.get('CRADL_API_ENDPOINT'),
        auth_endpoint=os.environ.get('CRADL_AUTH_ENDPOINT'),
        client_id=os.environ.get('CRADL_CLIENT_ID'),
        client_secret=os.environ.get('CRADL_CLIENT_SECRET'),
    )


def read_from_file(
    credentials_path: str = expanduser('~/.cradl/credentials.json'),
    profile: str = 'default',
) -> dict[str, Optional[str]]:
    """Read a json file and return credentials from it. Defaults to '~/.cradl/credentials.json'.

    :param credentials_path: Path to read credentials from.
    :type credentials_path: str
    :param profile: profile to read credentials from.
    :type profile: str

    :return: Dictionary of client_id, client_secret, auth_endpoint, api_endpoint, cached_profile
    :rtype: dict[str, Optional[str]]"""

    if not exists(credentials_path):
        raise MissingCredentials

    all_credentials = json.loads(Path(credentials_path).read_text())
    if profile not in all_credentials:
        raise MissingCredentials(f'Could not find credentials for profile {profile}')

    credentials = all_credentials[profile]

    return dict(
        access_token=credentials.get('access_token'),
        api_endpoint=credentials.get('api_endpoint'),
        auth_endpoint=credentials.get('auth_endpoint'),
        cached_profile=profile if credentials.get('use_cache', False) else None,
        client_id=credentials.get('client_id'),
        client_secret=credentials.get('client_secret'),
    )


def guess_credentials(profile=None) -> Credentials:
    """Tries to fetch Credentials first by looking at the environment variables, next by looking at the default
    credentials path ~/.cradl/credentials.json. Note that if not all the required environment variables
    are present, _all_ variables will be disregarded, and the credentials in the default path will be used.

    :return: Credentials from file
    :rtype: :py:class:`~cradl.Credentials`

    :raises: :py:class:`~cradl.MissingCredentials`"""

    if profile:
        try:
            return Credentials(**read_from_file(profile=profile))  # type: ignore
        except Exception:
            raise MissingCredentials(f'Could not find valid credentials for {profile} in ~/.cradl/credentials.json')

    for guesser in [read_from_environ, read_from_file]:
        try:
            return Credentials(**guesser())  # type: ignore
        except (TypeError, MissingCredentials):
            continue
    raise MissingCredentials
