from dataclasses import dataclass
from datetime import timedelta

import pytimeparse
import yaml
from croniter import croniter


@dataclass
class Config:
    sweep_schedule: str
    max_age: timedelta

    def __init__(self, sweep_schedule: str, max_age: timedelta | str):
        if not croniter.is_valid(sweep_schedule):
            raise ValueError(
                f"invalid value '{sweep_schedule}' for config field 'sweep-shedule'. "
                "Expected a cron-style expression, like '59 23 * * *'"
            )
        self.sweep_schedule = sweep_schedule

        if isinstance(max_age, timedelta):
            self.max_age = max_age
        else:
            max_age_seconds = pytimeparse.parse(max_age)
            if max_age_seconds is None:
                raise ValueError(
                    f"invalid value '{max_age}' for config field 'max-age'. "
                    "Expected a qualified time duration, like '3d12h'."
                )
            self.max_age = timedelta(seconds=max_age_seconds)


default_config = Config(sweep_schedule="0 6 * * *", max_age="1w")


def load(fd):
    data = yaml.safe_load(fd)
    data |= dump_dict(default_config)  # Fill in missing fields

    return load_dict(data)


def load_dict(data: dict):
    return Config(sweep_schedule=data["sweep-schedule"], max_age=data["max-age"])


def dumps(config: Config):
    return yaml.safe_dump(dump_dict(config)).rstrip()


def dump_dict(config: Config):
    return {"sweep-schedule": config.sweep_schedule, "max-age": str(config.max_age)}
