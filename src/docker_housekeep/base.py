import logging
from datetime import datetime, timedelta

import requests
import yaml

from . import dockerapi
from .state import State

logger = logging.getLogger("docker_housekeep")


def fromtimestamp(timestamp: int) -> datetime:
    """Convert a docker event timestamp into a datetime object."""
    timezone = datetime.now().astimezone().tzinfo
    return datetime.fromtimestamp(timestamp, tz=timezone)


def update_state(state: State, id: str, time: datetime | None):
    if time is not None:
        state.last_used[id] = time
        logger.info("update entry: %s at %s", id, time.isoformat())
    else:
        try:
            del state.last_used[id]
            logger.info("remove entry: %s", id)
        except KeyError:
            logger.warning("remove failed, missing entry for: %s", id)


def process_event(event: dict, state: State):
    logger.debug("received docker event\n%s", yaml.dump(event).rstrip())
    state.timestamp = fromtimestamp(event["time"])

    if event["Type"] == "image" and event["Action"] in {"save", "tag", "untag", "delete"}:
        # Out of all actions: delete, import, load, pull, push, save, tag, untag
        # We do not consider import, load, pull because they are followed by the "save" event
        # We also do not consider "push" as an action that uses the image.

        if event["Action"] == "delete":
            update_state(state, event["id"], None)
        else:
            update_state(state, event["id"], fromtimestamp(event["time"]))
    elif event["Type"] == "container" and (
        event["Action"].startswith("create") or event["Action"].startswith("exec_create")
    ):
        container = dockerapi.get_container(event["id"])
        if container is not None:
            update_state(state, container["Image"], fromtimestamp(event["time"]))


def sweep(state: State, max_age: timedelta):
    cutoff = datetime.now().astimezone() - max_age

    for image, last_used in state.last_used.items():
        if last_used < cutoff:
            logger.info("deleting: %s", image)

            try:
                response = dockerapi.delete_image(image)
                logger.debug(yaml.dump(response).rstrip())
            except requests.HTTPError as e:
                status = e.response.status_code
                data = e.response.json()

                logger.debug("delete error %s: %s", status, data["message"])

                if status == 404:
                    logger.warning("cannot delete %s: no such image", image)
                elif status == 409:
                    logger.error("cannot delete %s: %s", image, data["message"])
                else:
                    raise
