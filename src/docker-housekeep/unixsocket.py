"""Unix socket adapter for requests."""

import socket
from http.client import HTTPConnection

import requests
from requests.adapters import HTTPAdapter
from requests.compat import unquote, urlparse
from urllib3._collections import RecentlyUsedContainer
from urllib3.connectionpool import HTTPConnectionPool


# The following was adapted from some code from docker-py
# https://github.com/docker/docker-py/blob/master/docker/transport/unixconn.py
class UnixHTTPConnection(HTTPConnection, object):
    def __init__(self, url, timeout=60):
        super(UnixHTTPConnection, self).__init__("localhost", timeout=timeout)
        self.url = url
        self.timeout = timeout
        self.sock = None

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        socket_path = unquote(urlparse(self.url).netloc)
        sock.connect(socket_path)
        self.sock = sock

    def __del__(self):
        if self.sock:
            self.sock.close()


class UnixHTTPConnectionPool(HTTPConnectionPool):
    def __init__(self, url, timeout=60):
        super(UnixHTTPConnectionPool, self).__init__("localhost", timeout=timeout)
        self.url = url
        self.timeout = timeout

    def _new_conn(self):
        return UnixHTTPConnection(self.url, self.timeout)


class UnixAdapter(HTTPAdapter):
    def __init__(self, *args, timeout=60, pool_connections=25, **kwargs):
        super(UnixAdapter, self).__init__(*args, **kwargs)
        self.timeout = timeout
        self.pools = RecentlyUsedContainer(
            pool_connections, dispose_func=lambda p: p.close()
        )

    def get_connection(self, url, proxies=None):
        proxies = proxies or {}
        proxy = proxies.get(urlparse(url.lower()).scheme)

        if proxy:
            raise ValueError(
                f"{self.__class__.__name__} does not support specifying proxies"
            )

        with self.pools.lock:
            pool = self.pools.get(url)
            if pool:
                return pool

            pool = UnixHTTPConnectionPool(url, self.timeout)
            self.pools[url] = pool

        return pool

    def request_url(self, request, proxies):
        return request.path_url

    def close(self):
        self.pools.clear()


class Session(requests.Session):
    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.mount("http+unix://", UnixAdapter())
