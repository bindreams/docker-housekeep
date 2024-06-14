"""Unix socket adapter for requests.

The following was adapted from some code from docker-py
https://github.com/docker/docker-py/blob/master/docker/transport/unixconn.py
"""

import socket
from http.client import HTTPConnection

import requests
import requests.adapters
import urllib3
import urllib3.connection
from requests.compat import unquote, urlparse
from urllib3._collections import RecentlyUsedContainer

DEFAULT_NUM_POOLS = 25
DEFAULT_MAX_POOL_SIZE = 10


class BaseHTTPAdapter(requests.adapters.HTTPAdapter):
    def close(self):
        super().close()
        if hasattr(self, "pools"):
            self.pools.clear()

    # Fix for requests 2.32.2+:
    # https://github.com/psf/requests/commit/c98e4d133ef29c46a9b68cd783087218a8075e05
    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        return self.get_connection(request.url, proxies)


class UnixHTTPConnection(urllib3.connection.HTTPConnection):

    def __init__(self, url, timeout=60):
        super().__init__("localhost", timeout=timeout)
        self.url = url
        self.timeout = timeout

    def connect(self):
        socket_path = unquote(urlparse(self.url).netloc)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(socket_path)
        self.sock = sock


class UnixHTTPConnectionPool(urllib3.connectionpool.HTTPConnectionPool):
    def __init__(self, url, timeout=60, maxsize=10):
        super().__init__("localhost", timeout=timeout, maxsize=maxsize)
        self.url = url
        self.timeout = timeout

    def _new_conn(self):
        return UnixHTTPConnection(self.url, self.timeout)


class UnixHTTPAdapter(BaseHTTPAdapter):

    __attrs__ = requests.adapters.HTTPAdapter.__attrs__ + ["pools", "timeout", "max_pool_size"]

    def __init__(
        self,
        timeout=60,
        pool_connections=DEFAULT_NUM_POOLS,
        max_pool_size=DEFAULT_MAX_POOL_SIZE,
    ):
        self.timeout = timeout
        self.max_pool_size = max_pool_size
        self.pools = RecentlyUsedContainer(pool_connections, dispose_func=lambda p: p.close())
        super().__init__()

    def get_connection(self, url, proxies=None):
        with self.pools.lock:
            pool = self.pools.get(url)
            if pool:
                return pool

            pool = UnixHTTPConnectionPool(url, self.timeout, maxsize=self.max_pool_size)
            self.pools[url] = pool

        return pool

    def request_url(self, request, proxies):
        # The select_proxy utility in requests errors out when the provided URL
        # doesn't have a hostname, like is the case when using a UNIX socket.
        # Since proxies are an irrelevant notion in the case of UNIX sockets
        # anyway, we simply return the path URL directly.
        # See also: https://github.com/docker/docker-py/issues/811
        return request.path_url


class Session(requests.Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mount("http+unix://", UnixHTTPAdapter())
