import logging
import sys
from datetime import datetime
from pprint import pformat

from .dockerapi import events

image_info = {}

logger = logging.getLogger("docker-housekeep")


def handle_events():
    for event in events():
        logger.debug("Event: %s", pformat(event))

        if event["Type"] == "image" and event["Action"] in {"save", "tag", "untag", "delete"}:
            # Out of all actions: delete, import, load, pull, push, save, tag, untag
            # We do not consider import, load, pull because they are followed by the "save" event
            # We also do not consider "push" as an action that uses the image.

            if event["Action"] == "delete":
                try:
                    del image_info[event["id"]]
                except KeyError:
                    print(f"Warning: inconsistent database: could not delete ID {event["id"]}")
            else:
                image_info[event["id"]] = datetime.fromtimestamp(event["time"])
        elif event["Type"] == "container" and event["Action"] == "create":
            # container = query(f"/containers/{event['id']}/json").json()

            # image_info[container["Image"]] = datetime.fromtimestamp(event["time"])
            pass


def main():
    handle_events()

if __name__ == "__main__":
    sys.exit(main())
