import logging
import sys
from datetime import datetime
from pprint import pformat

from . import dockerapi

image_info = {}

logger = logging.getLogger("docker_housekeep")


def short_id(id: str):
    return id.split(":")[1][:12]


def fromtimestamp(timestamp: int):
    timezone = datetime.now().astimezone().tzinfo
    return datetime.fromtimestamp(timestamp, tz=timezone)


def update_image_info(id: str, time: datetime | None):
    if time is not None:
        image_info[id] = time
        logger.info("updated image %s at %s", short_id(id), time.isoformat())
    else:
        try:
            del image_info[id]
            logger.info("removed image %s", short_id(id))
        except KeyError:
            logger.warning("inconsistent database: could not delete ID %s", short_id(id))


def handle_events():
    for event in dockerapi.events():
        logger.debug("Event: %s", pformat(event))

        if event["Type"] == "image" and event["Action"] in {"save", "tag", "untag", "delete"}:
            # Out of all actions: delete, import, load, pull, push, save, tag, untag
            # We do not consider import, load, pull because they are followed by the "save" event
            # We also do not consider "push" as an action that uses the image.

            if event["Action"] == "delete":
                update_image_info(event["id"], None)
            else:
                update_image_info(event["id"], fromtimestamp(event["time"]))
        elif event["Type"] == "container" and event["Action"] == "create":
            container = dockerapi.query(f"containers/{event['id']}/json")
            update_image_info(container["Image"], fromtimestamp(event["time"]))


def main():
    logging.basicConfig(level=logging.DEBUG)

    handle_events()


if __name__ == "__main__":
    sys.exit(main())
