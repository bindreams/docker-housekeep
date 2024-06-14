import json
import logging
from datetime import datetime
from typing import Generator

from requests.compat import quote

from .unixsocket import Session

logger = logging.getLogger("docker-housekeep")


def events(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    filters: dict | None = None,
) -> Generator[dict]:
    """Generator that yields json events from Docker socket as dicts."""
    session = Session()

    host = quote("/var/run/docker.sock", safe="")
    uri = f"http+unix://{host}/events"

    params = []
    if since is not None:
        params.append(f"since={int(since.timestamp())}")

    if until is not None:
        params.append(f"until={int(until.timestamp())}")

    if filters is not None:
        params.append(f"filters={quote(json.dumps(filters))}")

    if len(params) > 0:
        uri += "?" + "&".join(params)

    logger.debug("Getting events using uri: %s", uri)
    response = session.get(uri, stream=True)

    for line in response.iter_lines():
        if line == "":
            # keep-alive line
            continue

        decoded_line = line.decode("utf-8")
        yield json.loads(decoded_line)
