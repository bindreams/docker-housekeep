# Docker Housekeep
Docker Housekeep is a program that runs alongside Docker and monitors image usage. Based on this information, DH can periodically "sweep" the image list by deleting images that have not been used in a specified time.

DH can also be installed as a systemd service that runs automatically on startup, together with Docker.

## Installation
First, install the `docker-housekeep` package from GitHub:
```sh
pip install https://github.com/bindreams/docker-housekeep/archive/refs/heads/main.zip
```
After installation, you will have the `docker-housekeep` executable available:
```sh
docker-housekeep --help
```

## Usage
You can check out `docker-housekeep [command] --help` for more detailed information on the commands, but the main ones are:
- `watch`: the main way to use DH - launch a long-running process monitoring Docker events and optionally sweeping on schedule;
- `sweep`: perform a one-time sweep based on an existing state file which the `watch` command generates;
- `daemon`: install a systemd service which runs DH automatcally in background.

To customize the behavior of DH you may also want to create a config file and place it at `/etc/docker-housekeep.conf` or specify the path using `-c/--config` commandline flag. Config file is written in YAML, with missing fields replaces by defaults. A complete config file with all default values will look like this:
```yaml
# Cron-style schedule for sweeping during the `watch` command
sweep-schedule: 0 6 * * *
# Maximum time an image can go without being used before getting cleaned up
# Accepts values like "3d12h", "0.5 weeks", or "3 days, 12:00:00"
max-age: 1w
```
When a config file is missing, the defaults are used instead.

## License
<img align="right" width="150px" height="150px" src="https://www.apache.org/foundation/press/kit/img/the-apache-way-badge/Indigo-THE_APACHE_WAY_BADGE-rgb.svg">

Copyright 2024, Anna Zhukova

This project is licensed under the Apache 2.0 license. The license text can be found at [LICENSE.md](/LICENSE.md).
