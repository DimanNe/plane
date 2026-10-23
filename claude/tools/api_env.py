#!/usr/bin/env python3
"""
Runs a command in apps/api of this checkout against the stores of a running local instance.

The API's tests need a postgres, a redis and a minio. A running instance has them, but they listen only inside
the instance's network namespace, so the command is run inside that namespace with the settings the instance's
own API gets. It works in a database and in redis databases of its own, and leaves the instance's data alone.

    claude/tools/api_env.py --run-dir RUN_DIR --port PORT --venv VENV --db-name plane_checks --redis-db 6 -- \\
        python -m pytest -q -o addopts="--strict-markers --create-db --nomigrations" plane/tests
"""

import argparse
import dataclasses as dc
import os
import pathlib as pl
import subprocess
import sys
import typing as t

REPOSITORY: pl.Path = pl.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "scripts"))

import plane_config  # noqa: E402
import plane_runtime  # noqa: E402


def get_pid_of_network_container(run_dir: pl.Path) -> str:
    container: str = subprocess.check_output(
        [
            "docker",
            "ps",
            "--quiet",
            "--filter",
            f"label=org.plane.local.target={run_dir}",
            "--filter",
            f"label=org.plane.local.service={plane_config.Service.NETWORK}",
        ],
        text=True,
    ).strip()
    if not container:
        raise SystemExit(f"No running instance in {run_dir}")
    return subprocess.check_output(
        ["docker", "inspect", "--format", "{{.State.Pid}}", container], text=True
    ).strip()


def get_environment_of_command(
    port: int,
    config: plane_config.InstanceConfig,
    venv: pl.Path,
    db_name: str,
    redis_db: int,
) -> t.Dict[str, str]:
    environment: t.Dict[str, str] = plane_runtime.get_plane_environment(port, config)
    redis: str = (
        f"redis://127.0.0.1:{plane_runtime.SERVICE_PORTS[plane_config.Service.REDIS]}"
    )
    postgres: str = environment["DATABASE_URL"].rsplit("/", 1)[0]
    environment.update(
        {
            "PATH": f"{venv / 'bin'}:{os.environ.get('PATH', os.defpath)}",
            "HOME": str(pl.Path.home()),
            "DJANGO_SETTINGS_MODULE": "plane.settings.test",
            "DATABASE_URL": f"{postgres}/{db_name}",
            "REDIS_URL": f"{redis}/{redis_db}",
            "AMQP_URL": f"{redis}/{redis_db + 1}",
            # a name that does not resolve: nothing a test does may send mail
            "EMAIL_HOST": "test-smtp.invalid",
        }
    )
    return environment


@dc.dataclass(frozen=True)
class RunInApiEnvironment:
    run_dir: pl.Path
    port: int
    venv: pl.Path
    db_name: str
    redis_db: int
    command: t.List[str]

    def run(self) -> int:
        config: t.Optional[plane_config.InstanceConfig] = (
            plane_config.InstanceConfig.read_existing(self.run_dir)
        )
        if config is None:
            raise SystemExit(f"No instance in {self.run_dir}")
        return subprocess.call(
            [
                "nsenter",
                "--user",
                "--net",
                "--preserve-credentials",
                "--target",
                get_pid_of_network_container(self.run_dir),
                "--",
                *self.command,
            ],
            cwd=REPOSITORY / "apps/api",
            env=get_environment_of_command(
                self.port, config, self.venv, self.db_name, self.redis_db
            ),
        )


def parse_arguments(arguments: t.List[str]) -> RunInApiEnvironment:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--run-dir",
        type=pl.Path,
        required=True,
        help="directory of the running instance",
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="port of the --bind the instance was started with",
    )
    parser.add_argument(
        "--venv",
        type=pl.Path,
        required=True,
        help="Python environment that has the API's packages",
    )
    parser.add_argument(
        "--db-name",
        required=True,
        help="Django's tests use test_<name>; it need not exist",
    )
    parser.add_argument(
        "--redis-db",
        type=int,
        required=True,
        help="this redis database and the next one are used",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="after --: the command and its arguments",
    )
    parsed: argparse.Namespace = parser.parse_args(arguments)
    command: t.List[str] = (
        parsed.command[1:] if parsed.command[:1] == ["--"] else parsed.command
    )
    if not command:
        parser.error("no command after --")
    return RunInApiEnvironment(
        run_dir=parsed.run_dir.resolve(),
        port=parsed.port,
        venv=parsed.venv.resolve(),
        db_name=parsed.db_name,
        redis_db=parsed.redis_db,
        command=command,
    )


if __name__ == "__main__":
    sys.exit(parse_arguments(sys.argv[1:]).run())
