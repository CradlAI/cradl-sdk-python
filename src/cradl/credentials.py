import configparser
import json
import logging
import os
import time
from os.path import exists, expanduser
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth


NULL_TOKEN = '', 0


class MissingCredentials(Exception):
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
        cached_profile: str = None,
        cache_path: Path = Path(expanduser('~/.lucidtech/token-cache.json')),
    ):
        if not all([client_id, client_secret, auth_endpoint, api_endpoint]):
            raise MissingCredentials

        self._token = read_token_from_cache(cached_profile, cache_path) if cached_profile else NULL_TOKEN
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_endpoint = auth_endpoint
        self.api_endpoint = api_endpoint
        self.cached_profile = cached_profile
        self.cache_path = cache_path

    @property
    def access_token(self) -> str:
        access_token, expiration = self._token

        if not access_token or time.time() > expiration:
            access_token, expiration = self._get_client_credentials()
            self._token = (access_token, expiration)

            if self.cached_profile:
                write_token_to_cache(self.cached_profile, self._token, self.cache_path)

        return access_token

    def _get_client_credentials(self) -> Tuple[str, int]:
        url = f'https://{self.auth_endpoint}/token?grant_type=client_credentials'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        auth = HTTPBasicAuth(self.client_id, self.client_secret)

        response = requests.post(url, headers=headers, auth=auth)
        response.raise_for_status()

        response_data = response.json()
        return response_data['access_token'], time.time() + response_data['expires_in']


def read_token_from_cache(cached_profile: str, cache_path: Path):
    if not cache_path.exists():
        return NULL_TOKEN

    try:
        cache = json.loads(cache_path.read_text())
        return cache[cached_profile]['access_token'], cache[cached_profile]['expires_in']
    except Exception as e:
        logging.warning(e)

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


def read_from_environ() -> List[Optional[str]]:
    """Read the following environment variables and return them:
        - LAS_CLIENT_ID
        - LAS_CLIENT_SECRET
        - LAS_AUTH_ENDPOINT
        - LAS_API_ENDPOINT

    :return: List of client_id, client_secret, auth_endpoint, api_endpoint
    :rtype: List[Optional[str]]"""

    return [os.environ.get(k) for k in (
        'LAS_CLIENT_ID',
        'LAS_CLIENT_SECRET',
        'LAS_AUTH_ENDPOINT',
        'LAS_API_ENDPOINT',
    )]


def read_from_file(credentials_path: str = expanduser('~/.lucidtech/credentials.cfg'),
                   section: str = 'default') -> List[Optional[str]]:
    """Read a config file and return credentials from it. Defaults to '~/.lucidtech/credentials.cfg'.

    :param credentials_path: Path to read credentials from.
    :type credentials_path: str
    :param section: Section to read credentials from.
    :type section: str

    :return: List of client_id, client_secret, auth_endpoint, api_endpoint
    :rtype: List[Optional[str]]"""

    if not exists(credentials_path):
        raise MissingCredentials

    config = configparser.ConfigParser()
    config.read(credentials_path)

    client_id = config.get(section, 'client_id')
    client_secret = config.get(section, 'client_secret')
    auth_endpoint = config.get(section, 'auth_endpoint')
    api_endpoint = config.get(section, 'api_endpoint')
    cached_profile = section if config.get(section, 'use_cache', fallback=False) in ['true', 'True'] else None

    return [client_id, client_secret, auth_endpoint, api_endpoint, cached_profile]


def guess_credentials(profile=None) -> Credentials:
    """Tries to fetch Credentials first by looking at the environment variables, next by looking at the default
    credentials path ~/.lucidtech/credentials.cfg. Note that if not all the required environment variables
    are present, _all_ variables will be disregarded, and the credentials in the default path will be used.

    :return: Credentials from file
    :rtype: :py:class:`~las.Credentials`

    :raises: :py:class:`~las.MissingCredentials`"""

    if profile:
        try:
            return Credentials(*read_from_file(section=profile))
        except:
            raise MissingCredentials(f'Could not find valid credentials for {profile} in ~/.lucidtech/credentials.cfg')

    for guesser in [read_from_environ, read_from_file]:
        args = guesser()  # type: ignore
        if len(args) >= 4 and all(args[:4]):
            return Credentials(*args)
    raise MissingCredentials
