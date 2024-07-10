import logging
import shlex
import sys
from pathlib import Path
from subprocess import run

logger = logging.getLogger("docker_housekeep")

SYSTEMD_SERVICE_TEMPLATE = """\
[Unit]
Description=Docker image housekeeping daemon
After=docker.service

[Service]
Type=notify
ExecStart={executable} watch --state-file /var/lib/docker-housekeep/state.json

[Install]
WantedBy=multi-user.target
"""


def install_daemon(*, enable=True):
    # Find the docker-housekeep executable
    executable_path = Path(sys.executable).parent / "docker-housekeep"
    if not executable_path.exists():
        logger.error(
            "Could not find the docker-housekeep executable in '%s'. "
            "Make sure docker-housekeep is installed as a package before installing the executable.",
            Path(sys.executable).parent,
        )
        sys.exit(1)

    # Systemd service ==================================================================================================
    Path("/var/lib/docker-housekeep").mkdir(parents=True, exist_ok=True)

    with open("/etc/systemd/system/docker-housekeep.service", "w", encoding="utf-8") as fd:
        fd.write(SYSTEMD_SERVICE_TEMPLATE.format(executable=shlex.quote(str(executable_path))))

    logger.info("daemon installed at /etc/systemd/system/docker-housekeep.service")

    if enable:
        run(["systemctl", "enable", "docker-housekeep.service"], check=True)
        run(["systemctl", "start", "docker-housekeep.service"], check=True)
        logger.info("daemon started")
