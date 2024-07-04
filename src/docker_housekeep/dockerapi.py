import json
import logging
from datetime import datetime
from typing import Iterable

from requests.compat import quote

from .unixsocket import Session

logger = logging.getLogger("docker_housekeep")


_session = Session()

SOCKET_PATH = "/var/run/docker.sock"
SOCKET_URL = f"http+unix://{quote(SOCKET_PATH, safe='')}"


def get(location):
    response = _session.get(SOCKET_URL + location)
    response.raise_for_status()
    return json.loads(response.text)


def get_events(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    filters: dict | None = None,
) -> Iterable[dict]:
    """Generator that yields json events from Docker socket as dicts."""
    arguments = {}
    if since is not None:
        arguments["since"] = int(since.timestamp())

    if until is not None:
        arguments["until"] = int(until.timestamp())

    if filters is not None:
        arguments["filters"] = quote(json.dumps(filters))

    response = _session.get(f"{SOCKET_URL}/events", params=arguments, stream=True)
    response.raise_for_status()

    for line in response.iter_lines():
        if line == "":
            # keep-alive line
            continue

        decoded_line = line.decode("utf-8")
        yield json.loads(decoded_line)


def get_container(id: str):
    response = _session.get(f"{SOCKET_URL}/containers/{id}/json")
    if response.status_code == 404:
        return None

    response.raise_for_status()
    return json.loads(response.text)


def delete_image(id: str):
    response = _session.delete(f"{SOCKET_URL}/images/{id}")
    response.raise_for_status()

    return json.loads(response.text)
