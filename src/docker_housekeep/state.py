import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import datetime


@dataclass
class State:
    timestamp: datetime | None = None
    last_used: dict = dataclasses.field(default_factory=dict)


def load(fd):
    result = State()

    pos = fd.tell()
    fd.seek(0, os.SEEK_END)
    if fd.tell() == 0:
        return result

    fd.seek(pos)
    state_data = json.load(fd)
    result.timestamp = datetime.fromisoformat(state_data["timestamp"])
    result.last_used = state_data["last_used"]
    for id in result.last_used:
        result.last_used[id] = datetime.fromisoformat(result.last_used[id])

    return result


def dump(state: State, fd):
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder().default(obj)

    json.dump(dataclasses.asdict(state), fd, default=default, indent="\t")
