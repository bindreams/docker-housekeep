import json
import logging
from datetime import datetime
from typing import Iterable

from requests.compat import quote

from .unixsocket import Session

logger = logging.getLogger("docker_housekeep")


_session = Session()


def _request(location, arguments: dict, stream=False):
    host = quote("/var/run/docker.sock", safe="")
    url = f"http+unix://{host}/{location}"

    url_args = []
    for argname, argval in arguments.values():
        url_args.append(f"{argname}={argval}")

    if len(url_args) > 0:
        url += "?" + "&".join(url_args)

    logger.debug("Socket request: %s", url)
    return _session.get(url, stream=stream)


def query(location):
    response = _request(location, {})
    return json.loads(response.text)


def events(
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

    response = _request("events", arguments=arguments, stream=True)

    for line in response.iter_lines():
        if line == "":
            # keep-alive line
            continue

        decoded_line = line.decode("utf-8")
        yield json.loads(decoded_line)
