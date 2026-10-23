#!/usr/bin/env python3
import abc
import argparse
import concurrent.futures
import contextlib
import csv
import ctypes
import dataclasses as dc
import functools
import hashlib
import http.client
import io
import ipaddress
import json
import os
import pathlib as pl
import pwd
import re
import resource
import secrets
import selectors
import signal
import shlex
import socket
import struct
import subprocess
import sys
import textwrap
import threading
import time
import types
import typing as t
import urllib.error
import urllib.request

import plane_config

PERSISTENT_DIR_NAMES: t.Tuple[str, ...] = (
    "config",
    plane_config.Service.POSTGRES.value,
    plane_config.Service.REDIS.value,
    "uploads",
)

START_TIMEOUT: int = 180
STOP_TIMEOUT: int = 180
EXTERNAL_DEPS: t.Dict[plane_config.Service, str] = {
    plane_config.Service.POSTGRES: "postgres:18.0-bookworm",
    plane_config.Service.REDIS: "redis:8.2.2-alpine",
    plane_config.Service.MINIO: "pgsty/silo:RELEASE.2026-09-16T00-00-00Z",
}
OUR_IMAGE_NAMES: t.Dict[plane_config.Service, str] = {
    plane_config.Service.API: "plane-local-api",
    plane_config.Service.LIVE: "plane-local-live",
    plane_config.Service.SPACE: "plane-local-space",
    plane_config.Service.PROXY: "plane-local-proxy",
}
# The tag of the owner's images, which every instance started without --image-tag runs.
DEFAULT_IMAGE_TAG: str = "current"
# Every service listens inside the network namespace of the instance. Only the proxy is published
# to the host, on the address and port the caller names.
SERVICE_PORTS: t.Dict[plane_config.Service, int] = {
    plane_config.Service.PROXY: 8080,
    plane_config.Service.API: 8000,
    plane_config.Service.LIVE: 3100,
    plane_config.Service.SPACE: 3003,
    plane_config.Service.POSTGRES: 5432,
    plane_config.Service.REDIS: 6379,
    plane_config.Service.MINIO: 9000,
}
# Tells a Python service that loaded its code to run; see apps/api/preload_and_wait.py.
START_SIGNAL: str = "SIGURG"


class DockerMetrics(t.TypedDict):
    calls: int
    wall_ms: float


class ContainerState(t.TypedDict, total=False):
    Running: bool
    Pid: int


class ContainerConfig(t.TypedDict):
    Labels: t.Dict[str, str]


class ContainerHostConfig(t.TypedDict):
    NetworkMode: str
    PortBindings: t.Dict[str, t.List[t.Dict[str, str]]]


class Container(t.TypedDict):
    Id: str
    Name: str
    Image: str
    State: ContainerState
    Config: ContainerConfig
    HostConfig: ContainerHostConfig


class ImageTag(t.TypedDict):
    ID: str
    Repository: str
    Tag: str


class Timings(t.TypedDict, total=False):
    host_setup_ms: float
    stop_ms: float
    archive_ms: float
    stream_ms: float
    stream_cpu_ms: float
    payload_bytes: int
    compressed_bytes: int
    stream_mb_per_s: float
    extract_stream_ms: float
    start_ms: float
    service_start_ms: t.Dict[plane_config.Service, float]
    service_ready_ms: t.Dict[plane_config.Service, float]
    service_stop_ms: t.Dict[plane_config.Service, float]
    total_ms: float
    controller_docker_calls: int
    controller_docker_wall_ms: float


Containers: t.TypeAlias = t.Dict[plane_config.Service, Container]
Jobs: t.TypeAlias = t.Mapping[plane_config.Service, t.Callable[[], None]]
DOCKER_METRICS: DockerMetrics = {"calls": 0, "wall_ms": 0.0}
DOCKER_METRICS_LOCK: threading.Lock = threading.Lock()


@dc.dataclass(frozen=True)
class BindAddress:
    host: ipaddress.IPv4Address
    port: int

    @classmethod
    def parse(cls, text: str) -> "BindAddress":
        # FOR_REVIEWER: IPv4 only. An IPv6 host needs brackets both in Docker's --publish and in
        # the URLs of the readiness probes; nothing asked for it.
        host: str
        port: str
        host, _, port = text.rpartition(":")
        try:
            address: BindAddress = cls(ipaddress.IPv4Address(host), int(port))
        except ValueError as error:
            raise argparse.ArgumentTypeError(
                f"Expected IPV4:PORT, such as 127.0.0.1:12001: {text!r}: {error}"
            )
        if not 0 < address.port < 65536:
            raise argparse.ArgumentTypeError(f"Port out of range: {text!r}")
        return address

    def get_host_for_local_clients(self) -> ipaddress.IPv4Address:
        return (
            ipaddress.IPv4Address("127.0.0.1")
            if self.host.is_unspecified
            else self.host
        )


def parse_image_tag(text: str) -> plane_config.ImageTag:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", text):
        raise argparse.ArgumentTypeError(
            f"Expected a Docker image tag: up to 128 letters, digits, '_', '.' and '-', not starting with '.' or '-': {text!r}"
        )
    if text == DEFAULT_IMAGE_TAG:
        raise argparse.ArgumentTypeError(
            f"{text!r} names the images of the instances started without --image-tag"
        )
    return plane_config.ImageTag(text)


def make_bind_mount_option(
    source: pl.Path, target: pl.Path, readonly: bool = False
) -> str:
    buffer: io.StringIO = io.StringIO()
    values: t.List[str] = ["type=bind", f"src={source}", f"dst={target}"]
    if readonly:
        values.append("readonly")
    csv.writer(buffer, lineterminator="").writerow(values)
    return buffer.getvalue()


def make_infrastructure_command_arguments(argv: t.Sequence[str]) -> t.List[str]:
    infrastructure_path: str = "/usr/lib/postgresql/18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    return ["-i", "PATH=" + infrastructure_path, *argv]


def get_host_environment() -> t.Dict[str, str]:
    return {"PATH": os.environ.get("PATH", os.defpath)}


def open_local_url(
    request: t.Union[str, urllib.request.Request], timeout: float
) -> http.client.HTTPResponse:
    response: http.client.HTTPResponse = urllib.request.build_opener(
        urllib.request.ProxyHandler({})
    ).open(request, timeout=timeout)
    return response


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run_command(
    argv: t.Sequence[str],
    capture: bool = False,
    input: t.Optional[bytes] = None,
    timeout: t.Optional[float] = None,
    pass_fds: t.Tuple[int, ...] = (),
) -> subprocess.CompletedProcess[bytes]:
    result: subprocess.CompletedProcess[bytes] = subprocess.run(
        list(argv),
        stdout=subprocess.PIPE if capture else sys.stderr,
        stderr=subprocess.PIPE if capture else sys.stderr,
        env=get_host_environment(),
        input=input,
        timeout=timeout,
        pass_fds=pass_fds,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {shlex.join(argv)}: "
            + (result.stderr.decode(errors="replace") if capture else "see stderr")
        )
    return result


def run_docker(
    argv: t.Sequence[str],
    capture: bool = False,
    input: t.Optional[bytes] = None,
    timeout: t.Optional[float] = None,
) -> subprocess.CompletedProcess[bytes]:
    start_time: float = time.monotonic()
    try:
        return run_command(
            ["docker", *argv], capture=capture, input=input, timeout=timeout
        )
    finally:
        with DOCKER_METRICS_LOCK:
            DOCKER_METRICS["calls"] += 1
            DOCKER_METRICS["wall_ms"] += (time.monotonic() - start_time) * 1000


def expand_home(path: pl.Path) -> pl.Path:
    if path.parts and path.parts[0] == "~":
        return pl.Path(pwd.getpwuid(os.getuid()).pw_dir).joinpath(*path.parts[1:])
    return path


def resolve_home(path: pl.Path) -> pl.Path:
    return expand_home(path).resolve()


def resolve_run_dir(run_dir: pl.Path) -> pl.Path:
    run_dir = expand_home(run_dir).absolute()
    if not run_dir.name or run_dir.name in (".", ".."):
        raise RuntimeError(f"Unsafe run directory: {run_dir}")
    run_dir = run_dir.parent.resolve() / run_dir.name
    if run_dir.is_symlink() or run_dir == pl.Path(pwd.getpwuid(os.getuid()).pw_dir):
        raise RuntimeError("Use a dedicated non-symlink run directory")
    return run_dir


def resolve_archive_path(archive_path: pl.Path, run_dir: pl.Path) -> pl.Path:
    archive_path = expand_home(archive_path).absolute()
    archive_path = archive_path.parent.resolve() / archive_path.name
    resolved_archive_path: pl.Path = archive_path.resolve()
    if resolved_archive_path == run_dir or run_dir in resolved_archive_path.parents:
        raise RuntimeError(
            "Archive must be outside run-dir; relocate it before import/export"
        )
    return archive_path


def get_image_tag(image_tag: t.Optional[plane_config.ImageTag]) -> str:
    return DEFAULT_IMAGE_TAG if image_tag is None else image_tag


def get_all_images(
    image_tag: t.Optional[plane_config.ImageTag],
) -> t.Dict[plane_config.Service, str]:
    tag: str = get_image_tag(image_tag)
    return {
        **{service: f"{name}:{tag}" for service, name in OUR_IMAGE_NAMES.items()},
        **EXTERNAL_DEPS,
    }


def build_our_images(
    plane_git_path: pl.Path, image_tag: t.Optional[plane_config.ImageTag]
) -> None:
    service: plane_config.Service
    for service in (
        plane_config.Service.API,
        plane_config.Service.LIVE,
        plane_config.Service.SPACE,
        plane_config.Service.PROXY,
    ):
        args: t.List[str] = [
            "buildx",
            "build",
            "--load",
            "--network",
            "host",
            "-t",
            get_all_images(image_tag)[service],
            "-f",
            str(
                plane_git_path
                / "scripts/runtime"
                / (
                    "api.Dockerfile"
                    if service == plane_config.Service.API
                    else "clients.Dockerfile"
                )
            ),
        ]
        if service != plane_config.Service.API:
            args += ["--target", service.value]
        run_docker([*args, str(plane_git_path)])


def get_docker_image_ids_by_tag(tags: t.Sequence[str]) -> t.Dict[str, str]:
    output: str = run_docker(
        ["image", "ls", "--no-trunc", "--format", "{{json .}}"], capture=True
    ).stdout.decode()
    image_ids_by_tag: t.Dict[str, str] = {}
    line: str
    for line in output.splitlines():
        image: ImageTag = json.loads(line)
        tag: str = image["Repository"] + ":" + image["Tag"]
        if tag in tags:
            image_ids_by_tag[tag] = image["ID"]
    return image_ids_by_tag


def pull_and_resolve_external_images() -> t.Dict[plane_config.Service, str]:
    image_ids_by_tag: t.Dict[str, str] = get_docker_image_ids_by_tag(
        list(EXTERNAL_DEPS.values())
    )
    missing_image_tags: t.List[str] = [
        tag for tag in EXTERNAL_DEPS.values() if tag not in image_ids_by_tag
    ]
    tag: str
    for tag in missing_image_tags:
        run_docker(["pull", tag])
    if missing_image_tags:
        image_ids_by_tag = get_docker_image_ids_by_tag(list(EXTERNAL_DEPS.values()))
    return {service: image_ids_by_tag[tag] for service, tag in EXTERNAL_DEPS.items()}


def run_jobs_in_parallel(jobs: Jobs) -> None:
    error: Exception
    errors: t.List[str] = []
    executor: concurrent.futures.ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        futures: t.Dict[concurrent.futures.Future[None], plane_config.Service] = {
            executor.submit(operation): service for service, operation in jobs.items()
        }
        service: plane_config.Service
        future: concurrent.futures.Future[None]
        for future, service in futures.items():
            try:
                future.result()
            except Exception as error:
                errors.append(f"{service}: {error}")
    if errors:
        raise RuntimeError("; ".join(errors))


def sync_filesystem(path: pl.Path) -> None:
    descriptor: int = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        library: ctypes.CDLL = ctypes.CDLL(None, use_errno=True)
        if library.syncfs(descriptor) != 0:
            error: int = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
    finally:
        os.close(descriptor)


class DockerFs:
    def __init__(self) -> None:
        self.user_namespace: t.Optional[t.BinaryIO] = None

    def get_fs_cmd(self, argv: t.Sequence[str]) -> t.List[str]:
        if self.user_namespace is None:
            endpoint: str = (
                run_docker(
                    ["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
                    capture=True,
                )
                .stdout.decode()
                .strip()
            )
            if not endpoint.startswith("unix:///"):
                raise RuntimeError(
                    "Rootless docker_fs access requires a local Docker Unix socket"
                )
            connection: socket.socket
            with socket.socket(socket.AF_UNIX) as connection:
                connection.connect(endpoint.removeprefix("unix://"))
                pid: int
                uid: int
                peer_gid: int
                pid, uid, peer_gid = struct.unpack(
                    "3i",
                    connection.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                    ),
                )
            if uid != os.getuid():
                raise RuntimeError("Docker socket is not owned by the invoking user")
            namespace: t.BinaryIO = pl.Path(f"/proc/{pid}/ns/user").open("rb")
            try:
                mapping: t.List[str] = (
                    pl.Path(f"/proc/{pid}/uid_map").read_text().splitlines()[0].split()
                )
                if list(map(int, mapping)) != [0, os.getuid(), 1]:
                    raise RuntimeError(
                        "Docker socket peer is not in the invoking user's rootless namespace"
                    )
            except BaseException:
                namespace.close()
                raise
            self.user_namespace = namespace
        return [
            "nsenter",
            "--user=/proc/self/fd/" + str(self.user_namespace.fileno()),
            "--setuid=0",
            "--setgid=0",
            *argv,
        ]

    def get_fs_desc(self) -> t.Tuple[int, ...]:
        return (self.user_namespace.fileno(),) if self.user_namespace else ()

    def close(self) -> None:
        if self.user_namespace is not None:
            self.user_namespace.close()

    def __enter__(self) -> "DockerFs":
        return self

    def __exit__(
        self,
        exception_type: t.Optional[t.Type[BaseException]],
        exception: t.Optional[BaseException],
        traceback: t.Optional[types.TracebackType],
    ) -> None:
        self.close()

    def run_fs_cmd_in_docker_ns(
        self, argv: t.Sequence[str], capture: bool = False
    ) -> subprocess.CompletedProcess[bytes]:
        return run_command(
            self.get_fs_cmd(argv),
            capture=capture,
            pass_fds=self.get_fs_desc(),
        )


def get_container_name_prefix(run_dir: pl.Path) -> str:
    instance_key: str = hashlib.sha256(str(run_dir).encode()).hexdigest()[:20]
    return "plane-" + instance_key


def get_container_name(run_dir: pl.Path, service: plane_config.Service) -> str:
    return get_container_name_prefix(run_dir) + "-" + service.value


def require_instance_config(run_dir: pl.Path) -> plane_config.InstanceConfig:
    config: t.Optional[plane_config.InstanceConfig] = (
        plane_config.InstanceConfig.read_existing(run_dir)
    )
    if config is None:
        raise RuntimeError("Plane instance is not initialized; start it first")
    return config


def require_same_image_tag_as_instance(
    config: t.Optional[plane_config.InstanceConfig],
    image_tag: t.Optional[plane_config.ImageTag],
) -> None:
    """The API image an instance runs applies its migrations to the instance's data, and the
    owner's instance holds real tasks. Pointed at the owner's run dir, a session's images would
    migrate that data with code under development; a session that leaves out its --image-tag
    would check the owner's images rather than its own code. Refuses images other than those of
    the instance's first start."""
    if config is not None and config.image_tag != image_tag:
        recorded_option: str = (
            "no --image-tag"
            if config.image_tag is None
            else f"--image-tag {config.image_tag}"
        )
        raise RuntimeError(
            f"The instance runs the images plane-local-*:{get_image_tag(config.image_tag)}, and this command names "
            f"plane-local-*:{get_image_tag(image_tag)}: pass {recorded_option}, or another --run-dir"
        )


def require_separate_source_and_run_directory(
    plane_git_path: pl.Path, run_dir: pl.Path
) -> None:
    if (
        run_dir == plane_git_path
        or run_dir in plane_git_path.parents
        or plane_git_path in run_dir.parents
    ):
        raise RuntimeError("Run directory must be outside the Plane checkout")


def get_containers(
    run_dir: pl.Path,
    services: t.Sequence[plane_config.Service] = tuple(plane_config.Service),
) -> Containers:
    container_name_prefix: str = get_container_name_prefix(run_dir)
    expected: t.Dict[str, plane_config.Service] = {
        get_container_name(run_dir, service): service for service in services
    }
    value: str = run_docker(
        [
            "ps",
            "--all",
            "--filter",
            "name=" + container_name_prefix + "-",
            "--format",
            "{{.ID}} {{.Names}}",
        ],
        capture=True,
    ).stdout.decode()
    identifiers: t.List[str] = []
    row: str
    for row in value.splitlines():
        name: str
        identifier: str
        identifier, name = row.split()
        if name in expected:
            identifiers.append(identifier)
    if not identifiers:
        return {}
    value = run_docker(["inspect", *identifiers], capture=True).stdout.decode()
    found: Containers = {}
    containers: t.List[Container] = json.loads(value)
    container: Container
    for container in containers:
        name = container["Name"].removeprefix("/")
        labels: t.Dict[str, str] = container["Config"].get("Labels") or {}
        service: t.Optional[plane_config.Service] = expected.get(name)
        if (
            service is None
            or labels.get("org.plane.local.target") != str(run_dir)
            or labels.get("org.plane.local.service") != service
        ):
            raise RuntimeError("Container name belongs to another instance")
        found[service] = container
    return found


def get_plane_origin(port: int) -> str:
    """The origin Plane writes into the absolute URLs it makes. A browser may reach the instance by
    another address, so the proxy turns redirects to this origin into relative ones (see
    write_caddy_config()); links in emails and notifications keep it."""
    return f"http://localhost:{port}"


def get_plane_environment(
    port: int, service_secrets: plane_config.ServiceSecrets
) -> t.Dict[str, str]:
    origin: str = get_plane_origin(port)
    redis_port: int = SERVICE_PORTS[plane_config.Service.REDIS]
    return {
        "DJANGO_SETTINGS_MODULE": "plane.settings.production",
        "DEBUG": "0",
        "SECRET_KEY": service_secrets[plane_config.SecretName.DJANGO],
        "DATABASE_URL": f"postgresql://plane:{service_secrets[plane_config.SecretName.POSTGRES]}@127.0.0.1:{SERVICE_PORTS[plane_config.Service.POSTGRES]}/plane",
        "REDIS_URL": f"redis://127.0.0.1:{redis_port}/0",
        "AMQP_URL": f"redis://127.0.0.1:{redis_port}/1",
        "WEB_URL": origin,
        "APP_BASE_URL": origin,
        "ADMIN_BASE_URL": origin,
        "SPACE_BASE_URL": origin,
        "CORS_ALLOWED_ORIGINS": origin,
        "LIVE_BASE_URL": f"http://127.0.0.1:{SERVICE_PORTS[plane_config.Service.LIVE]}",
        "API_BASE_URL": f"http://127.0.0.1:{SERVICE_PORTS[plane_config.Service.API]}",
        "LIVE_SERVER_SECRET_KEY": service_secrets[plane_config.SecretName.LIVE],
        "AWS_ACCESS_KEY_ID": "plane",
        "AWS_SECRET_ACCESS_KEY": service_secrets[plane_config.SecretName.MINIO],
        "AWS_S3_BUCKET_NAME": "uploads",
        "AWS_REGION": "us-east-1",
        "AWS_S3_ENDPOINT_URL": f"http://127.0.0.1:{SERVICE_PORTS[plane_config.Service.MINIO]}",
        "USE_MINIO": "1",
        "MINIO_ENDPOINT_SSL": "0",
        "ENABLE_SIGNUP": "1",
        "ENABLE_EMAIL_PASSWORD": "1",
        "ENABLE_MAGIC_LINK_LOGIN": "1",
        "API_KEY_RATE_LIMIT": "1000000/minute",
        "EMAIL_HOST": "localhost",
        "SKIP_ENV_VAR": "1",
        "REDIS_HOST": "127.0.0.1",
        "REDIS_PORT": str(redis_port),
        "LIVE_BASE_PATH": "/live",
        "HOST": "127.0.0.1",
    }


def create_instance_directories(run_dir: pl.Path) -> None:
    directory_name: str
    for directory_name in (*PERSISTENT_DIR_NAMES, "logs", "runtime"):
        (run_dir / directory_name).mkdir(parents=True, exist_ok=True)


def write_minio_config(run_dir: pl.Path, root_password: str) -> None:
    minio_config: plane_config.JSONObject = {
        "version": "v1",
        "rootUser": "plane",
        "rootPassword": root_password,
        "pools": [["/data"]],
    }
    (run_dir / "runtime/minio.json").write_text(json.dumps(minio_config, indent=2))


def write_postgres_auth_config(run_dir: pl.Path) -> None:
    postgres_auth_config: pl.Path = run_dir / "runtime/postgres-hba.conf"
    postgres_auth_config.write_text(
        "local all all trust\nhost all all 0.0.0.0/0 scram-sha-256\nhost all all ::/0 scram-sha-256\n"
    )
    postgres_auth_config.chmod(0o644)


def write_caddy_config(run_dir: pl.Path, plane_origin: str) -> None:
    ports: t.Dict[plane_config.Service, int] = SERVICE_PORTS
    origin_pattern: str = re.escape(plane_origin)
    caddy_config: str = f"""{{
    admin off
    auto_https off
    persist_config off
    grace_period 120s
}}
# The API closes a connection that has been idle for a moment. A proxy that keeps the connection for its next
# request can send a save down it just as the API closes it, and must then answer 502: a save is not sent twice.
# So each request to the API gets a connection of its own.
# The API redirects to Plane's own origin, which is not the address a browser used when it came through another
# interface of the host or a tunnel. Such a redirect is made relative, so the browser stays at the address it used.
# The origin followed by "//" is left alone: made relative, it would name another host.
(api) {{
    reverse_proxy 127.0.0.1:{ports[plane_config.Service.API]} {{
        transport http {{
            keepalive off
        }}
        header_down Location "^{origin_pattern}(/[^/]|/$)" "$1"
        header_down Location "^{origin_pattern}([?#]|$)" "/$1"
    }}
}}
:{ports[plane_config.Service.PROXY]} {{
    bind 0.0.0.0
    handle /api/* {{
        import api
    }}
    handle /auth/* {{
        import api
    }}
    handle /static/* {{
        import api
    }}
    handle /live/* {{
        reverse_proxy 127.0.0.1:{ports[plane_config.Service.LIVE]}
    }}
    handle /uploads* {{
        reverse_proxy 127.0.0.1:{ports[plane_config.Service.MINIO]}
    }}
    redir /spaces /spaces/
    handle /spaces/* {{
        reverse_proxy 127.0.0.1:{ports[plane_config.Service.SPACE]}
    }}
    redir /god-mode /god-mode/
    handle_path /god-mode/* {{
        root * /srv/admin
        try_files {{path}} /index.html
        file_server
    }}
    handle {{
        root * /srv/web
        try_files {{path}} /index.html
        file_server
    }}
}}
"""
    (run_dir / "runtime/Caddyfile").write_text(caddy_config)


def run_api_command(
    image: str,
    argv: t.Sequence[str],
    network_mode: str,
    plane_environment: t.Dict[str, str],
) -> None:
    arguments: t.List[str] = ["run", "--rm", "--network", network_mode]
    key: str
    value: str
    for key, value in plane_environment.items():
        arguments += ["-e", f"{key}={value}"]
    run_docker([*arguments, image, *argv])


def wait_for_service_readiness(
    run_dir: pl.Path,
    service: plane_config.Service,
    marker: str,
    probe: t.Optional[t.Callable[[float], object]] = None,
) -> None:
    deadline: float = time.monotonic() + START_TIMEOUT
    container_name: str = get_container_name(run_dir, service)
    clients: t.List[subprocess.Popen[bytes]] = []
    output: bytes = b""
    try:
        logs: subprocess.Popen[bytes] = subprocess.Popen(
            ["docker", "logs", "--follow", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=get_host_environment(),
        )
        clients.append(logs)
        monitor: subprocess.Popen[bytes] = subprocess.Popen(
            ["docker", "wait", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=get_host_environment(),
        )
        clients.append(monitor)
        selection: selectors.DefaultSelector
        with selectors.DefaultSelector() as selection:
            assert logs.stdout is not None
            assert monitor.stdout is not None
            selection.register(logs.stdout, selectors.EVENT_READ, "logs")
            selection.register(monitor.stdout, selectors.EVENT_READ, "exit")
            while True:
                remaining: float = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(f"Service readiness timed out: {service}")
                events: t.List[t.Tuple[selectors.SelectorKey, int]] = selection.select(
                    remaining
                )
                if not events:
                    raise RuntimeError(f"Service readiness timed out: {service}")
                key: selectors.SelectorKey
                event_mask: int
                for key, event_mask in events:
                    if key.data == "exit":
                        details: str = os.read(key.fd, 65536).decode(errors="replace")
                        raise RuntimeError(
                            f"Service exited during startup: {service}: {details}: {output.decode(errors='replace')}"
                        )
                for key, event_mask in events:
                    data: bytes = os.read(key.fd, 65536)
                    if not data:
                        raise RuntimeError(
                            f"Service log stream closed during startup: {service}: {output.decode(errors='replace')}"
                        )
                    output += data
                if marker.encode() in output:
                    if probe is not None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise RuntimeError(
                                f"Service readiness timed out: {service}"
                            )
                        probe(remaining)
                    return
    finally:
        process: subprocess.Popen[bytes]
        for process in clients:
            process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()


def check_http_service(bind: BindAddress, path: str, timeout: float = 3) -> None:
    url: str = f"http://{bind.get_host_for_local_clients()}:{bind.port}{path}"
    response: http.client.HTTPResponse
    with open_local_url(url, timeout=min(3, timeout)) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Service readiness failed: {url}: HTTP {response.status}"
            )
        response.read(256)


def initialize_postgres(
    run_dir: pl.Path,
    postgres_password: str,
    postgres_image_id: str,
    docker_fs: DockerFs,
) -> None:
    directory: pl.Path = run_dir / plane_config.Service.POSTGRES.value
    if docker_fs.run_fs_cmd_in_docker_ns(
        ["find", str(directory), "-maxdepth", "1", "-name", "PG_VERSION"], capture=True
    ).stdout:
        return
    docker_fs.run_fs_cmd_in_docker_ns(
        ["install", "-d", "-m", "700", "-o", "999", "-g", "999", str(directory)]
    )
    run_docker(
        [
            "run",
            "--rm",
            "--interactive",
            "--network",
            "none",
            "--user",
            "postgres",
            "--mount",
            make_bind_mount_option(directory, pl.Path("/data")),
            "--entrypoint",
            "/usr/bin/env",
            postgres_image_id,
            *make_infrastructure_command_arguments(
                [
                    "initdb",
                    "-D",
                    "/data",
                    "--username=plane",
                    "--pwfile=/dev/stdin",
                    "--data-checksums",
                    "--locale=en_US.utf8",
                    "--auth-local=trust",
                    "--auth-host=scram-sha-256",
                    # PostgreSQL keeps a few write-ahead log files for reuse, full size each.
                    # With its usual sizes they would be most of a small instance's backup.
                    "--wal-segsize=1",
                    "--set=min_wal_size=4MB",
                ]
            ),
        ],
        input=postgres_password.encode(),
    )


def record_duration(
    durations_ms: t.Dict[plane_config.Service, float],
    service: plane_config.Service,
    operation: t.Callable[[], None],
) -> None:
    start_time: float = time.monotonic()
    operation()
    durations_ms[service] = round((time.monotonic() - start_time) * 1000, 3)


def signal_container_and_wait(
    run_dir: pl.Path,
    service: plane_config.Service,
    timings: Timings,
    signal_name: str = "SIGTERM",
    allowed_exit_codes: t.Sequence[int] = (0,),
) -> None:
    start_time: float = time.monotonic()
    container_name: str = get_container_name(run_dir, service)
    run_docker(["kill", "--signal", signal_name, container_name])
    code: int = int(
        run_docker(["wait", container_name], capture=True, timeout=STOP_TIMEOUT)
        .stdout.decode()
        .strip()
    )
    if code not in allowed_exit_codes:
        raise RuntimeError(f"Writer did not stop successfully: {service}: exit: {code}")
    timings.setdefault("service_stop_ms", {})[service] = round(
        (time.monotonic() - start_time) * 1000, 3
    )


def extract_archive(
    archive: pl.Path, run_dir: pl.Path, docker_fs: DockerFs, timings: Timings
) -> None:
    start_time: float = time.monotonic()
    process: subprocess.Popen[bytes] = subprocess.Popen(
        ["zstd", "-d", "-c", str(archive)],
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        env=get_host_environment(),
    )
    assert process.stdout is not None
    extractor: t.Optional[subprocess.Popen[bytes]] = None
    try:
        extractor = subprocess.Popen(
            docker_fs.get_fs_cmd(
                [
                    "tar",
                    "--extract",
                    "--file=-",
                    "--ignore-zeros",
                    "--keep-old-files",
                    "--numeric-owner",
                    "--same-owner",
                    "-C",
                    str(run_dir),
                ]
            ),
            stdin=process.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=get_host_environment(),
            pass_fds=docker_fs.get_fs_desc(),
        )
        process.stdout.close()
        errors: str = extractor.communicate()[1].decode(errors="replace")
        decoder_code: int = process.wait()
        if extractor.returncode or decoder_code:
            raise RuntimeError(
                f"Archive extraction failed: tar: {extractor.returncode}, zstd: {decoder_code}: {errors}"
            )
        sync_filesystem(run_dir)
        timings["extract_stream_ms"] = round((time.monotonic() - start_time) * 1000, 3)
    finally:
        process.stdout.close()
        child: t.Optional[subprocess.Popen[bytes]]
        for child in (extractor, process):
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait()


def read_instance_config_from_archive(archive: pl.Path) -> plane_config.InstanceConfig:
    """Reads the configuration, which is the first thing in an archive, without the rest."""
    decoder: subprocess.Popen[bytes] = subprocess.Popen(
        ["zstd", "-d", "-c", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=get_host_environment(),
    )
    try:
        extractor: subprocess.CompletedProcess[bytes] = subprocess.run(
            [
                "tar",
                "--extract",
                "--file=-",
                "--to-stdout",
                "--occurrence=1",
                "config/instance.json",
            ],
            stdin=decoder.stdout,
            capture_output=True,
            env=get_host_environment(),
        )
    finally:
        decoder.kill()
        decoder.wait()
        assert decoder.stdout is not None
        decoder.stdout.close()
    if extractor.returncode:
        raise RuntimeError(
            f"Archive has no readable config/instance.json: {archive}: {extractor.stderr.decode(errors='replace')}"
        )
    return plane_config.InstanceConfig.parse(extractor.stdout.decode())


def remove_containers(run_dir: pl.Path) -> None:
    containers: Containers = get_containers(run_dir)
    running: t.List[str] = [
        container["Id"]
        for container in containers.values()
        if container["State"]["Running"]
    ]
    if running:
        run_docker(["kill", "--signal", "SIGKILL", *running])
        run_docker(["wait", *running], capture=True, timeout=STOP_TIMEOUT)
    if containers:
        children: t.List[str] = [
            container["Id"]
            for name, container in containers.items()
            if name != plane_config.Service.NETWORK
        ]
        if children:
            run_docker(["rm", *children])
        if plane_config.Service.NETWORK in containers:
            run_docker(["rm", containers[plane_config.Service.NETWORK]["Id"]])


def get_status(run_dir: pl.Path) -> t.Dict[plane_config.Service, ContainerState]:
    containers: Containers = get_containers(run_dir)
    states: t.Dict[plane_config.Service, ContainerState] = {}
    service: plane_config.Service
    for service in tuple(plane_config.Service):
        container: t.Optional[Container] = containers.get(service)
        states[service] = container["State"] if container is not None else {}
    return states


def start_container(
    run_dir: pl.Path,
    service: plane_config.Service,
    image: str,
    argv: t.Sequence[str],
    network_mode: str,
    existing_container: t.Optional[Container],
    published_port: t.Optional[str] = None,
    env: t.Optional[t.Dict[str, str]] = None,
    mounts: t.Sequence[t.Tuple[pl.Path, pl.Path]] = (),
    readonly_mounts: t.Sequence[t.Tuple[pl.Path, pl.Path]] = (),
    entrypoint: t.Optional[str] = None,
    user: t.Optional[str] = None,
) -> None:
    if existing_container:
        if existing_container["State"]["Running"]:
            return
        run_docker(["rm", existing_container["Id"]])
    args: t.List[str] = [
        "run",
        "-d",
        "--network",
        network_mode,
        "--restart",
        "no",
        "--name",
        get_container_name(run_dir, service),
        "--label",
        f"org.plane.local.target={run_dir}",
        "--label",
        f"org.plane.local.service={service}",
    ]
    if published_port is not None:
        args += ["--publish", published_port]
    value: str
    key: str
    for key, value in (env or {}).items():
        args += ["-e", f"{key}={value}"]
    if entrypoint is not None:
        args += ["--entrypoint", entrypoint]
    if user is not None:
        args += ["--user", user]
    target: pl.Path
    source: pl.Path
    for source, target in mounts:
        args += ["--mount", make_bind_mount_option(source, target)]
    for source, target in readonly_mounts:
        args += ["--mount", make_bind_mount_option(source, target, readonly=True)]
    run_docker([*args, image, *argv])


def run_infrastructure_tool(
    run_dir: pl.Path,
    service: plane_config.Service,
    argv: t.Sequence[str],
    capture: bool = False,
    timeout: t.Optional[float] = None,
) -> subprocess.CompletedProcess[bytes]:
    return run_docker(
        [
            "exec",
            get_container_name(run_dir, service),
            "/usr/bin/env",
            *make_infrastructure_command_arguments(argv),
        ],
        capture=capture,
        timeout=timeout,
    )


def run_postgres_tool(
    run_dir: pl.Path,
    tool: str,
    arguments: t.Sequence[str],
    capture: bool = False,
    timeout: t.Optional[float] = None,
) -> subprocess.CompletedProcess[bytes]:
    return run_infrastructure_tool(
        run_dir,
        plane_config.Service.POSTGRES,
        [
            tool,
            "--no-password",
            "-h",
            "/var/run/postgresql",
            "-p",
            str(SERVICE_PORTS[plane_config.Service.POSTGRES]),
            "-U",
            "plane",
            *arguments,
        ],
        capture=capture,
        timeout=timeout,
    )


def start_postgres(
    run_dir: pl.Path,
    postgres_password: str,
    initialized: bool,
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
    docker_fs: DockerFs,
) -> None:
    if not initialized:
        initialize_postgres(run_dir, postgres_password, image_id, docker_fs)
    start_container(
        run_dir,
        plane_config.Service.POSTGRES,
        image_id,
        make_infrastructure_command_arguments(
            [
                "postgres",
                "-D",
                "/data",
                "-p",
                str(SERVICE_PORTS[plane_config.Service.POSTGRES]),
                "-c",
                "listen_addresses=127.0.0.1",
                "-c",
                "hba_file=/run/plane-postgres-hba.conf",
                "-c",
                "max_connections=100",
                "-c",
                "recovery_init_sync_method=syncfs",
                "-c",
                "unix_socket_directories=/var/run/postgresql",
            ]
        ),
        entrypoint="/usr/bin/env",
        user="postgres",
        mounts=[(run_dir / plane_config.Service.POSTGRES.value, pl.Path("/data"))],
        readonly_mounts=[
            (
                run_dir / "runtime/postgres-hba.conf",
                pl.Path("/run/plane-postgres-hba.conf"),
            )
        ],
        network_mode=network_mode,
        existing_container=existing_container,
    )
    wait_for_service_readiness(
        run_dir,
        plane_config.Service.POSTGRES,
        "database system is ready to accept connections",
        probe=lambda remaining: run_postgres_tool(
            run_dir,
            "psql",
            ["-X", "-d", "postgres", "-c", "SELECT 1"],
            capture=True,
            timeout=remaining,
        ),
    )
    if (
        not initialized
        and not run_postgres_tool(
            run_dir,
            "psql",
            [
                "-X",
                "-d",
                "postgres",
                "-tAc",
                "SELECT 1 FROM pg_database WHERE datname='plane'",
            ],
            capture=True,
        ).stdout.strip()
    ):
        run_postgres_tool(run_dir, "createdb", ["--maintenance-db=postgres", "plane"])


def start_redis(
    run_dir: pl.Path,
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    redis_modules: t.Tuple[str, ...] = (
        "redisbloom.so",
        "redisearch.so",
        "redistimeseries.so",
        "rejson.so",
    )
    start_container(
        run_dir,
        plane_config.Service.REDIS,
        image_id,
        make_infrastructure_command_arguments(
            [
                "redis-server",
                "--bind",
                "127.0.0.1",
                "--port",
                str(SERVICE_PORTS[plane_config.Service.REDIS]),
                "--dir",
                "/data",
                "--appendonly",
                "yes",
                "--appendfsync",
                "always",
                "--save",
                "",
                "--hz",
                "100",
                "--auto-aof-rewrite-min-size",
                "1mb",
                "--maxmemory-policy",
                "noeviction",
                *[
                    argument
                    for name in redis_modules
                    for argument in (
                        "--loadmodule",
                        "/usr/local/lib/redis/modules/" + name,
                    )
                ],
            ]
        ),
        entrypoint="/usr/bin/env",
        user="0",
        mounts=[(run_dir / plane_config.Service.REDIS.value, pl.Path("/data"))],
        network_mode=network_mode,
        existing_container=existing_container,
    )
    wait_for_service_readiness(
        run_dir,
        plane_config.Service.REDIS,
        "Ready to accept connections tcp",
        probe=lambda remaining: run_infrastructure_tool(
            run_dir,
            plane_config.Service.REDIS,
            [
                "redis-cli",
                "-e",
                "-p",
                str(SERVICE_PORTS[plane_config.Service.REDIS]),
                "ping",
            ],
            capture=True,
            timeout=remaining,
        ),
    )


def start_minio(
    run_dir: pl.Path,
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    address: str = f"127.0.0.1:{SERVICE_PORTS[plane_config.Service.MINIO]}"
    start_container(
        run_dir,
        plane_config.Service.MINIO,
        image_id,
        make_infrastructure_command_arguments(
            [
                "silo",
                "server",
                "--config",
                "/run/plane-minio.json",
                "--address",
                address,
            ]
        ),
        entrypoint="/usr/bin/env",
        mounts=[(run_dir / "uploads", pl.Path("/data"))],
        readonly_mounts=[
            (run_dir / "runtime/minio.json", pl.Path("/run/plane-minio.json"))
        ],
        network_mode=network_mode,
        existing_container=existing_container,
    )
    wait_for_service_readiness(
        run_dir,
        plane_config.Service.MINIO,
        "API:",
        probe=lambda remaining: run_infrastructure_tool(
            run_dir,
            plane_config.Service.MINIO,
            ["curl", "--silent", "--fail", f"http://{address}/minio/health/ready"],
            capture=True,
            timeout=remaining,
        ),
    )


def start_proxy(
    run_dir: pl.Path,
    bind: BindAddress,
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    start_container(
        run_dir,
        plane_config.Service.PROXY,
        image_id,
        make_infrastructure_command_arguments(
            [
                "caddy",
                "run",
                "--config",
                "/etc/caddy/Caddyfile",
                "--adapter",
                "caddyfile",
            ]
        ),
        entrypoint="/usr/bin/env",
        mounts=[(run_dir / "runtime/Caddyfile", pl.Path("/etc/caddy/Caddyfile"))],
        network_mode=network_mode,
        existing_container=existing_container,
    )
    wait_for_service_readiness(
        run_dir,
        plane_config.Service.PROXY,
        "serving initial configuration",
        probe=lambda remaining: check_http_service(bind, "/", timeout=remaining),
    )
    check_http_service(bind, "/god-mode/")


def get_python_service_commands(
    run_dir: pl.Path,
) -> t.Dict[plane_config.Service, t.List[str]]:
    return {
        plane_config.Service.API: [
            "gunicorn",
            "plane.wsgi:application",
            "--config",
            "python:plane.gunicorn_conf",
            "--bind",
            f"127.0.0.1:{SERVICE_PORTS[plane_config.Service.API]}",
            "--workers",
            "2",
            "--worker-class",
            "gthread",
            "--threads",
            "8",
            "--timeout",
            "120",
            "--graceful-timeout",
            "120",
            "--access-logfile",
            "-",
        ],
        plane_config.Service.WORKER: [
            "celery",
            "-A",
            "plane",
            "worker",
            "-l",
            "info",
            "--pool=solo",
            "--concurrency=1",
            "--prefetch-multiplier=1",
            "--without-mingle",
            "--without-gossip",
            "--hostname",
            get_container_name_prefix(run_dir) + "@%h",
        ],
        plane_config.Service.BEAT: [
            "celery",
            "-A",
            "plane",
            "beat",
            "-l",
            "info",
            "--scheduler",
            "django_celery_beat.schedulers:DatabaseScheduler",
        ],
    }


def start_python_service(
    run_dir: pl.Path,
    service: plane_config.Service,
    command: t.Sequence[str],
    plane_environment: t.Dict[str, str],
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    start_container(
        run_dir,
        service,
        image_id,
        ["python", "preload_and_wait.py", *command],
        env=plane_environment,
        mounts=[(run_dir / "logs", pl.Path("/code/plane/logs"))],
        network_mode=network_mode,
        existing_container=existing_container,
    )


def start_python_service_and_wait_for_loaded_code(
    run_dir: pl.Path,
    service: plane_config.Service,
    command: t.Sequence[str],
    plane_environment: t.Dict[str, str],
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    start_python_service(
        run_dir,
        service,
        command,
        plane_environment,
        image_id,
        network_mode,
        existing_container,
    )
    wait_for_service_readiness(run_dir, service, "Plane code loaded:")


def start_live(
    run_dir: pl.Path,
    plane_environment: t.Dict[str, str],
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    start_container(
        run_dir,
        plane_config.Service.LIVE,
        image_id,
        ["node", "apps/live/dist/start.bundle.mjs"],
        env={
            **plane_environment,
            "PORT": str(SERVICE_PORTS[plane_config.Service.LIVE]),
        },
        network_mode=network_mode,
        existing_container=existing_container,
    )
    wait_for_service_readiness(
        run_dir,
        plane_config.Service.LIVE,
        "SERVER: Express server has started at port",
    )


def start_space(
    run_dir: pl.Path,
    plane_environment: t.Dict[str, str],
    image_id: str,
    network_mode: str,
    existing_container: t.Optional[Container],
) -> None:
    start_container(
        run_dir,
        plane_config.Service.SPACE,
        image_id,
        ["./node_modules/.bin/react-router-serve", "./build/server/index.bundle.js"],
        env={
            **plane_environment,
            "PORT": str(SERVICE_PORTS[plane_config.Service.SPACE]),
        },
        network_mode=network_mode,
        existing_container=existing_container,
    )
    wait_for_service_readiness(
        run_dir,
        plane_config.Service.SPACE,
        "[react-router-serve] http://localhost:",
    )


def start_network_container(
    run_dir: pl.Path,
    bind: BindAddress,
    image_id: str,
    existing_container: t.Optional[Container],
) -> None:
    start_container(
        run_dir,
        plane_config.Service.NETWORK,
        image_id,
        make_infrastructure_command_arguments(["sleep", "infinity"]),
        entrypoint="/usr/bin/env",
        network_mode="bridge",
        existing_container=existing_container,
        published_port=f"{bind.host}:{bind.port}:{SERVICE_PORTS[plane_config.Service.PROXY]}",
    )


def start_plane_services(
    run_dir: pl.Path,
    config: plane_config.InstanceConfig,
    bind: BindAddress,
    image_ids: t.Dict[plane_config.Service, str],
    docker_fs: DockerFs,
    timings: Timings,
) -> None:
    start_time: float = time.monotonic()
    containers: Containers = get_containers(run_dir)
    running: Containers = {
        name: container
        for name, container in containers.items()
        if container["State"]["Running"]
    }
    network_container: t.Optional[Container] = running.get(plane_config.Service.NETWORK)
    proxy_port: int = SERVICE_PORTS[plane_config.Service.PROXY]
    image_services: t.Dict[plane_config.Service, plane_config.Service] = {
        plane_config.Service.NETWORK: plane_config.Service.POSTGRES,
        plane_config.Service.WORKER: plane_config.Service.API,
        plane_config.Service.BEAT: plane_config.Service.API,
    }
    # What already runs is kept only if it is this instance as asked for: the images just built,
    # the requested bind address, every service in the namespace of the running network container.
    if running and (
        network_container is None
        or network_container["HostConfig"]["PortBindings"]
        != {
            f"{proxy_port}/tcp": [
                {"HostIp": str(bind.host), "HostPort": str(bind.port)}
            ]
        }
        or any(
            container["Image"] != image_ids[image_services.get(name, name)]
            or (
                name != plane_config.Service.NETWORK
                and container["HostConfig"]["NetworkMode"]
                != "container:" + network_container["Id"]
            )
            for name, container in running.items()
        )
    ):
        stop_plane_containers(run_dir, timings).result()
        containers = get_containers(run_dir)
    service_secrets: plane_config.ServiceSecrets = config.secrets
    create_instance_directories(run_dir)
    config.write(run_dir)
    write_minio_config(run_dir, service_secrets[plane_config.SecretName.MINIO])
    write_postgres_auth_config(run_dir)
    write_caddy_config(run_dir, get_plane_origin(bind.port))
    start_network_container(
        run_dir,
        bind,
        image_ids[plane_config.Service.POSTGRES],
        containers.get(plane_config.Service.NETWORK),
    )
    network_mode: str = "container:" + get_container_name(
        run_dir, plane_config.Service.NETWORK
    )
    initialized: bool = config.initialized
    api_image_id: str = image_ids[plane_config.Service.API]
    plane_environment: t.Dict[str, str] = get_plane_environment(
        bind.port, service_secrets
    )
    python_service_commands: t.Dict[plane_config.Service, t.List[str]] = (
        get_python_service_commands(run_dir)
    )

    start_durations_ms: t.Dict[plane_config.Service, float] = timings.setdefault(
        "service_start_ms", {}
    )

    def start_redis_then_live() -> None:
        # The live server gives up when Redis does not answer at its start.
        record_duration(
            start_durations_ms,
            plane_config.Service.REDIS,
            functools.partial(
                start_redis,
                run_dir,
                image_ids[plane_config.Service.REDIS],
                network_mode,
                containers.get(plane_config.Service.REDIS),
            ),
        )
        record_duration(
            start_durations_ms,
            plane_config.Service.LIVE,
            functools.partial(
                start_live,
                run_dir,
                plane_environment,
                image_ids[plane_config.Service.LIVE],
                network_mode,
                containers.get(plane_config.Service.LIVE),
            ),
        )

    # Everything starts at once. The stores recover their data while the applications load their
    # code, which takes longer; the three Python services then wait for START_SIGNAL, because they
    # would connect to a store that is not ready yet.
    independent_jobs: Jobs = {
        plane_config.Service.POSTGRES: functools.partial(
            start_postgres,
            run_dir,
            service_secrets[plane_config.SecretName.POSTGRES],
            initialized,
            image_ids[plane_config.Service.POSTGRES],
            network_mode,
            containers.get(plane_config.Service.POSTGRES),
            docker_fs,
        ),
        plane_config.Service.MINIO: functools.partial(
            start_minio,
            run_dir,
            image_ids[plane_config.Service.MINIO],
            network_mode,
            containers.get(plane_config.Service.MINIO),
        ),
        plane_config.Service.PROXY: functools.partial(
            start_proxy,
            run_dir,
            bind,
            image_ids[plane_config.Service.PROXY],
            network_mode,
            containers.get(plane_config.Service.PROXY),
        ),
        plane_config.Service.SPACE: functools.partial(
            start_space,
            run_dir,
            plane_environment,
            image_ids[plane_config.Service.SPACE],
            network_mode,
            containers.get(plane_config.Service.SPACE),
        ),
        **{
            service: functools.partial(
                start_python_service_and_wait_for_loaded_code,
                run_dir,
                service,
                command,
                plane_environment,
                api_image_id,
                network_mode,
                containers.get(service),
            )
            for service, command in python_service_commands.items()
        },
    }
    run_jobs_in_parallel(
        {
            plane_config.Service.REDIS: start_redis_then_live,
            **{
                service: functools.partial(
                    record_duration, start_durations_ms, service, operation
                )
                for service, operation in independent_jobs.items()
            },
        }
    )
    if not initialized or config.last_api_image != api_image_id:
        run_api_command(
            api_image_id,
            ["python", "manage.py", "migrate", "--noinput"],
            network_mode,
            plane_environment,
        )
    if not initialized:
        management_command: t.List[str]
        for management_command in (
            ["register_instance", config.instance_id],
            ["configure_instance"],
            ["create_bucket"],
        ):
            run_api_command(
                api_image_id,
                ["python", "manage.py", *management_command],
                network_mode,
                plane_environment,
            )
        config.initialized = True
        config.write(run_dir)
    run_docker(
        [
            "kill",
            "--signal",
            START_SIGNAL,
            *[
                get_container_name(run_dir, service)
                for service in python_service_commands
            ],
        ]
    )
    ready_durations_ms: t.Dict[plane_config.Service, float] = timings.setdefault(
        "service_ready_ms", {}
    )
    # The applications are asked through the proxy, the way a browser reaches them.
    ready_jobs: Jobs = {
        plane_config.Service.API: functools.partial(
            wait_for_service_readiness,
            run_dir,
            plane_config.Service.API,
            "Plane API worker ready:",
            probe=lambda remaining: check_http_service(
                bind, "/api/instances/", timeout=remaining
            ),
        ),
        plane_config.Service.WORKER: functools.partial(
            wait_for_service_readiness,
            run_dir,
            plane_config.Service.WORKER,
            "Plane worker ready:",
        ),
        plane_config.Service.BEAT: functools.partial(
            wait_for_service_readiness,
            run_dir,
            plane_config.Service.BEAT,
            "Plane beat ready:",
        ),
        plane_config.Service.LIVE: functools.partial(
            check_http_service, bind, "/live/health/"
        ),
        plane_config.Service.SPACE: functools.partial(
            check_http_service, bind, "/spaces/"
        ),
    }
    run_jobs_in_parallel(
        {
            service: functools.partial(
                record_duration, ready_durations_ms, service, operation
            )
            for service, operation in ready_jobs.items()
        }
    )
    if config.last_api_image != api_image_id:
        config.last_api_image = api_image_id
        config.write(run_dir)
    timings["start_ms"] = round((time.monotonic() - start_time) * 1000, 3)


def signal_processes_and_wait_for_exit(
    signals_by_service: t.Mapping[plane_config.Service, t.Tuple[int, signal.Signals]],
    timings: Timings,
) -> None:
    """Sends a signal to the main process of each container and returns when all have exited.

    Docker needs many times longer to kill a container than its processes need to die, because
    it also takes the container apart and records the stop. The main process of a container
    exits only after every other process of the container is gone, so its exit means that
    nothing writes to the container's files any more.
    """
    start_time: float = time.monotonic()
    selection: selectors.DefaultSelector
    with selectors.DefaultSelector() as selection:
        service: plane_config.Service
        pid: int
        signal_number: signal.Signals
        for service, (pid, signal_number) in signals_by_service.items():
            try:
                process: int = os.pidfd_open(pid)
            except ProcessLookupError:
                continue
            signal.pidfd_send_signal(process, signal_number)
            selection.register(process, selectors.EVENT_READ, service)
        deadline: float = start_time + STOP_TIMEOUT
        while selection.get_map():
            exited: t.List[t.Tuple[selectors.SelectorKey, int]] = selection.select(
                deadline - time.monotonic()
            )
            if not exited:
                raise RuntimeError(
                    f"Processes did not exit: {[key.data for key in selection.get_map().values()]}"
                )
            key: selectors.SelectorKey
            event_mask: int
            for key, event_mask in exited:
                selection.unregister(key.fd)
                os.close(key.fd)
                timings.setdefault("service_stop_ms", {})[key.data] = round(
                    (time.monotonic() - start_time) * 1000, 3
                )


def wait_until_docker_has_recorded_stops(
    network_container_stop: concurrent.futures.Future[None],
    container_names: t.Sequence[str],
) -> None:
    network_container_stop.result()
    if container_names:
        run_docker(["wait", *container_names], capture=True, timeout=STOP_TIMEOUT)


def stop_plane_containers(
    run_dir: pl.Path, timings: Timings
) -> concurrent.futures.Future[None]:
    """Stops every service and returns what Docker still has to finish.

    When this returns, no service writes data any more. Still in progress are the stop of the
    network container, where Docker needs longer to remove the network than everything else
    here takes, and Docker's own record that the other containers have stopped. A caller with
    other work to do, such as writing the archive, does it before it waits for the returned
    future; a command must not end before that, or the next one would see containers as running.
    """
    start_time: float = time.monotonic()
    running: Containers = {
        name: container
        for name, container in get_containers(run_dir).items()
        if container["State"]["Running"]
    }
    # Their main processes get a signal directly, see signal_processes_and_wait_for_exit().
    # MinIO is asked to stop; the others are killed, which PostgreSQL and Redis recover from.
    signals_by_service: t.Dict[plane_config.Service, t.Tuple[int, signal.Signals]] = {
        name: (
            running[name]["State"]["Pid"],
            signal.SIGTERM if name == plane_config.Service.MINIO else signal.SIGKILL,
        )
        for name in (
            plane_config.Service.BEAT,
            plane_config.Service.API,
            plane_config.Service.SPACE,
            plane_config.Service.PROXY,
            plane_config.Service.POSTGRES,
            plane_config.Service.REDIS,
            plane_config.Service.MINIO,
        )
        if name in running
    }
    # The network container goes first because its stop takes longest. The services keep reaching
    # each other, since they talk inside the namespace that outlives its container, but from here
    # on nothing reaches the instance and it reaches nothing outside.
    executor: concurrent.futures.ThreadPoolExecutor = (
        concurrent.futures.ThreadPoolExecutor(max_workers=2)
    )
    try:
        network_container_stop: concurrent.futures.Future[None]
        if plane_config.Service.NETWORK in running:
            network_container_stop = executor.submit(
                signal_container_and_wait,
                run_dir,
                plane_config.Service.NETWORK,
                timings,
                signal_name="SIGKILL",
                allowed_exit_codes=(0, 137),
            )
        else:
            network_container_stop = concurrent.futures.Future()
            network_container_stop.set_result(None)
        # These two hold work that is not yet in a store: a background task that is running, page
        # edits waiting for the debounced save. They finish it while the API and the stores run.
        graceful_jobs: Jobs = {
            name: functools.partial(signal_container_and_wait, run_dir, name, timings)
            for name in (plane_config.Service.WORKER, plane_config.Service.LIVE)
            if name in running
        }
        if graceful_jobs:
            run_jobs_in_parallel(graceful_jobs)
        signal_processes_and_wait_for_exit(signals_by_service, timings)
        timings["stop_ms"] = round((time.monotonic() - start_time) * 1000, 3)
        return executor.submit(
            wait_until_docker_has_recorded_stops,
            network_container_stop,
            [get_container_name(run_dir, name) for name in signals_by_service],
        )
    finally:
        executor.shutdown(wait=False)


def write_archive(
    run_dir: pl.Path,
    output: pl.Path,
    docker_fs: DockerFs,
    timings: Timings,
    zstd_threads: int,
    zstd_level: int,
) -> None:
    temporary: pl.Path = output.parent / (
        "." + output.name + ".writing-" + secrets.token_hex(8)
    )
    producer: t.Optional[subprocess.Popen[bytes]] = None
    compressor: t.Optional[subprocess.Popen[bytes]] = None
    try:
        start_time: float = time.monotonic()
        usage_before: resource.struct_rusage = resource.getrusage(
            resource.RUSAGE_CHILDREN
        )
        file: t.BinaryIO
        with temporary.open("wb") as file:
            compressor = subprocess.Popen(
                [
                    "zstd",
                    "--check",
                    "--ultra",
                    "--fast=" + str(-zstd_level)
                    if zstd_level < 0
                    else "-" + str(zstd_level),
                    "-T" + str(zstd_threads),
                    "-c",
                ],
                stdin=subprocess.PIPE,
                stdout=file,
                stderr=sys.stderr,
                env=get_host_environment(),
            )
            producer = subprocess.Popen(
                docker_fs.get_fs_cmd(
                    [
                        "tar",
                        "--format=posix",
                        "--numeric-owner",
                        "--hard-dereference",
                        "--totals",
                        "-c",
                        "-C",
                        str(run_dir),
                        *PERSISTENT_DIR_NAMES,
                    ]
                ),
                stdout=compressor.stdin,
                stderr=subprocess.PIPE,
                env=get_host_environment(),
                pass_fds=docker_fs.get_fs_desc(),
            )
            assert compressor.stdin is not None
            compressor.stdin.close()
            errors: str = producer.communicate()[1].decode(errors="replace")
            compressor_code: int = compressor.wait()
            if producer.returncode or compressor_code:
                raise RuntimeError(
                    f"Archive pipeline failed: tar: {producer.returncode}, zstd: {compressor_code}: {errors}"
                )
            match: t.Optional[re.Match[str]] = re.search(
                "Total bytes written: (\\d+)", errors
            )
            payload_bytes: int = int(match.group(1)) if match else 0
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, output)
        plane_config.fsync_dir(output.parent)
        elapsed: float = time.monotonic() - start_time
        usage_after: resource.struct_rusage = resource.getrusage(
            resource.RUSAGE_CHILDREN
        )
        timings.update(
            {
                "archive_ms": round(elapsed * 1000, 3),
                "stream_ms": round(elapsed * 1000, 3),
                "stream_cpu_ms": round(
                    (
                        usage_after.ru_utime
                        + usage_after.ru_stime
                        - (usage_before.ru_utime + usage_before.ru_stime)
                    )
                    * 1000,
                    3,
                ),
                "payload_bytes": payload_bytes,
                "compressed_bytes": output.stat().st_size,
                "stream_mb_per_s": round(
                    payload_bytes / max(elapsed, 1e-06) / 1000000.0, 3
                ),
            }
        )
    finally:
        process: t.Optional[subprocess.Popen[bytes]]
        for process in (producer, compressor):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def require_archive_output_file(output: pl.Path) -> None:
    if output.is_symlink():
        raise RuntimeError("Archive output must not be a symlink")
    if output.exists() and (not output.is_file()):
        raise RuntimeError("Archive output must be a regular file")


def build_or_pull_missing_images_and_get_ids(
    plane_git_path: pl.Path, image_tag: t.Optional[plane_config.ImageTag]
) -> t.Dict[plane_config.Service, str]:
    all_images: t.Dict[plane_config.Service, str] = get_all_images(image_tag)
    image_ids_by_tag: t.Dict[str, str] = get_docker_image_ids_by_tag(
        list(all_images.values())
    )
    if any(tag not in image_ids_by_tag for tag in all_images.values()):
        if any(
            tag not in image_ids_by_tag
            for service, tag in all_images.items()
            if service not in EXTERNAL_DEPS
        ):
            build_our_images(plane_git_path, image_tag)
        pull_and_resolve_external_images()
        image_ids_by_tag = get_docker_image_ids_by_tag(list(all_images.values()))
    return {service: image_ids_by_tag[tag] for service, tag in all_images.items()}


def start_network_container_and_python_services(
    image_lookup: concurrent.futures.Future[t.Dict[plane_config.Service, str]],
    run_dir: pl.Path,
    bind: BindAddress,
    service_secrets: plane_config.ServiceSecrets,
) -> t.Dict[plane_config.Service, str]:
    """Starts what needs only the instance configuration, so that it can run beside the
    extraction of a backup: the network container, and the Python services, which begin to load
    their code."""
    # By its tag, so that it need not wait for the image lookup: Docker pulls this image itself
    # when it is missing, which it cannot do for the images built from the checkout.
    start_network_container(
        run_dir, bind, EXTERNAL_DEPS[plane_config.Service.POSTGRES], None
    )
    image_ids: t.Dict[plane_config.Service, str] = image_lookup.result()
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    network_mode: str = "container:" + get_container_name(
        run_dir, plane_config.Service.NETWORK
    )
    plane_environment: t.Dict[str, str] = get_plane_environment(
        bind.port, service_secrets
    )
    run_jobs_in_parallel(
        {
            service: functools.partial(
                start_python_service,
                run_dir,
                service,
                command,
                plane_environment,
                image_ids[plane_config.Service.API],
                network_mode,
                None,
            )
            for service, command in get_python_service_commands(run_dir).items()
        }
    )
    return image_ids


def make_lifecycle_timings(start_time: float) -> Timings:
    return {"host_setup_ms": round((time.monotonic() - start_time) * 1000, 3)}


def print_lifecycle_result(
    run_dir: pl.Path, action: str, timings: Timings, start_time: float
) -> None:
    timings["total_ms"] = round((time.monotonic() - start_time) * 1000, 3)
    timings["controller_docker_calls"] = DOCKER_METRICS["calls"]
    timings["controller_docker_wall_ms"] = round(DOCKER_METRICS["wall_ms"], 3)
    print(
        json.dumps(
            {"action": action, "ok": True, "timings": timings, "run_dir": str(run_dir)}
        )
    )


class Command(abc.ABC):
    @abc.abstractmethod
    def run(self) -> None: ...


@dc.dataclass(frozen=True)
class PrepareCommand(Command):
    plane_git_path: pl.Path
    image_tag: t.Optional[plane_config.ImageTag]

    def run(self) -> None:
        plane_git_path: pl.Path = resolve_home(self.plane_git_path)
        build_our_images(plane_git_path, self.image_tag)
        pull_and_resolve_external_images()
        print(
            json.dumps(
                {
                    "ok": True,
                    "action": "prepare",
                    "images": list(get_all_images(self.image_tag).values()),
                }
            )
        )


@dc.dataclass(frozen=True)
class StartCommand(Command):
    run_dir: pl.Path
    plane_git_path: pl.Path
    bind: BindAddress
    image_tag: t.Optional[plane_config.ImageTag]

    def run(self) -> None:
        start_time: float = time.monotonic()
        run_dir: pl.Path = resolve_run_dir(self.run_dir)
        plane_git_path: pl.Path = resolve_home(self.plane_git_path)
        require_separate_source_and_run_directory(plane_git_path, run_dir)
        timings: Timings = make_lifecycle_timings(start_time)
        config: t.Optional[plane_config.InstanceConfig] = (
            plane_config.InstanceConfig.read_existing(run_dir)
        )
        require_same_image_tag_as_instance(config, self.image_tag)
        docker_fs: DockerFs
        with DockerFs() as docker_fs:
            image_ids: t.Dict[plane_config.Service, str] = (
                build_or_pull_missing_images_and_get_ids(plane_git_path, self.image_tag)
            )
            if config is None:
                config = plane_config.InstanceConfig.make()
                config.image_tag = self.image_tag
            start_plane_services(
                run_dir, config, self.bind, image_ids, docker_fs, timings
            )
        print_lifecycle_result(run_dir, "start", timings, start_time)


@dc.dataclass(frozen=True)
class StopCommand(Command):
    run_dir: pl.Path

    def run(self) -> None:
        start_time: float = time.monotonic()
        run_dir: pl.Path = resolve_run_dir(self.run_dir)
        timings: Timings = make_lifecycle_timings(start_time)
        stop_plane_containers(run_dir, timings).result()
        print_lifecycle_result(run_dir, "stop", timings, start_time)


@dc.dataclass(frozen=True)
class StatusCommand(Command):
    run_dir: pl.Path

    def run(self) -> None:
        run_dir: pl.Path = resolve_run_dir(self.run_dir)
        print(json.dumps({"services": get_status(run_dir)}))


@dc.dataclass(frozen=True)
class ExportCommand(Command):
    run_dir: pl.Path
    output: pl.Path
    zstd_threads: int
    zstd_level: int

    def run(self) -> None:
        start_time: float = time.monotonic()
        run_dir: pl.Path = resolve_run_dir(self.run_dir)
        output: pl.Path = resolve_archive_path(self.output, run_dir)
        require_archive_output_file(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        config: plane_config.InstanceConfig = require_instance_config(run_dir)
        if not config.initialized:
            raise RuntimeError(
                "Export requires an initialized instance; start it first"
            )
        timings: Timings = make_lifecycle_timings(start_time)
        network_container_stop: concurrent.futures.Future[None] = stop_plane_containers(
            run_dir, timings
        )
        docker_fs: DockerFs
        with DockerFs() as docker_fs:
            write_archive(
                run_dir, output, docker_fs, timings, self.zstd_threads, self.zstd_level
            )
        network_container_stop.result()
        print_lifecycle_result(run_dir, "export", timings, start_time)


@dc.dataclass(frozen=True)
class ImportCommand(Command):
    run_dir: pl.Path
    input: pl.Path
    plane_git_path: pl.Path
    bind: BindAddress
    image_tag: t.Optional[plane_config.ImageTag]

    def run(self) -> None:
        start_time: float = time.monotonic()
        run_dir: pl.Path = resolve_run_dir(self.run_dir)
        plane_git_path: pl.Path = resolve_home(self.plane_git_path)
        require_separate_source_and_run_directory(plane_git_path, run_dir)
        input: pl.Path = (
            self.input
            if self.input == pl.Path("/dev/null")
            else resolve_archive_path(self.input, run_dir)
        )
        # FOR_REVIEWER: a failed import may leave the configuration of the archive, and with it the image
        # tag of the exported instance; a retry with another tag is then refused, and the message names
        # the tag to pass.
        require_same_image_tag_as_instance(
            plane_config.InstanceConfig.read_existing(run_dir), self.image_tag
        )
        timings: Timings = make_lifecycle_timings(start_time)
        docker_fs: DockerFs
        executor: concurrent.futures.ThreadPoolExecutor
        with (
            DockerFs() as docker_fs,
            concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor,
        ):
            image_lookup: concurrent.futures.Future[
                t.Dict[plane_config.Service, str]
            ] = executor.submit(
                build_or_pull_missing_images_and_get_ids,
                plane_git_path,
                self.image_tag,
            )
            remove_containers(run_dir)
            docker_fs.run_fs_cmd_in_docker_ns(["rm", "-rf", "--", str(run_dir)])
            run_dir.mkdir(parents=True, exist_ok=True)
            config: plane_config.InstanceConfig = (
                plane_config.InstanceConfig.make()
                if input == pl.Path("/dev/null")
                else read_instance_config_from_archive(input)
            )
            # An archive keeps the image tag of the instance that was exported; the owner imports a
            # session's export without one.
            config.image_tag = self.image_tag
            # The Python services need only the configuration to load their code, which takes
            # longer than extracting a backup, so they start before the extraction.
            early_start: concurrent.futures.Future[
                t.Dict[plane_config.Service, str]
            ] = executor.submit(
                start_network_container_and_python_services,
                image_lookup,
                run_dir,
                self.bind,
                config.secrets,
            )
            if input == pl.Path("/dev/null"):
                name: str
                for name in PERSISTENT_DIR_NAMES:
                    (run_dir / name).mkdir()
            else:
                extract_archive(input, run_dir, docker_fs, timings)
            image_ids: t.Dict[plane_config.Service, str] = early_start.result()
            config.write(run_dir)
            start_plane_services(
                run_dir, config, self.bind, image_ids, docker_fs, timings
            )
        print_lifecycle_result(run_dir, "import", timings, start_time)


# Run by the API's own Python with Plane loaded: makes the account with this address an administrator of the
# instance, or keeps it one, with this password hash, marks the instance set up and gives the account's API token.
# bootstrap-user runs it on its own; the checks' account maker (claude/checks/instance.py), which has Plane loaded
# already, runs it as it starts.
BOOTSTRAP_ADMINISTRATOR: str = textwrap.dedent("""\
    def bootstrap_administrator(email: str, password_hash: str) -> dict:
        import django.core.cache as django_cache
        import plane.db.models as db_models
        import plane.license.models as license_models

        user: db_models.User
        _: bool
        user, _ = db_models.User.objects.get_or_create(email=email, defaults={"username": email})
        user.password = password_hash
        user.is_superuser = True
        user.is_staff = True
        user.is_email_verified = True
        user.save()
        instance: license_models.Instance = license_models.Instance.objects.get()
        instance.is_setup_done = True
        instance.save()
        # The API serves the instance state from its cache.
        django_cache.cache.delete("/api/instances/")
        license_models.InstanceAdmin.objects.update_or_create(
            instance=instance, user=user, defaults={"role": 20, "is_verified": True}
        )
        api_token: db_models.APIToken
        api_token, _ = db_models.APIToken.objects.get_or_create(user=user, label="local-mcp")
        return {"api_key": api_token.token, "user_id": str(user.id), "email": user.email}
""")


@dc.dataclass(frozen=True)
class BootstrapUserCommand(Command):
    run_dir: pl.Path
    email: str
    password: str

    def run(self) -> None:
        code: str = (
            textwrap.dedent("""\
                import json
                import sys
                import django
                django.setup()
                import django.contrib.auth.hashers as hashers
            """)
            + BOOTSTRAP_ADMINISTRATOR
            + textwrap.dedent("""\
                email: str
                password: str
                email, password = sys.argv[1:3]
                print(json.dumps(bootstrap_administrator(email, hashers.make_password(password))))
            """)
        )
        run_dir: pl.Path = resolve_run_dir(self.run_dir)
        credentials: str = (
            run_docker(
                [
                    "exec",
                    get_container_name(run_dir, plane_config.Service.API),
                    "python",
                    "-c",
                    code,
                    self.email,
                    self.password,
                ],
                capture=True,
            )
            .stdout.decode()
            .strip()
            .splitlines()[-1]
        )
        print(credentials)


def parse_cli_command(argv: t.Sequence[str]) -> Command:
    # FOR_REVIEWER: claude/README.md deletes a session's images with two docker commands, the first
    # removing the containers of an instance by its run directory. A subcommand that removes every
    # container on the images of a tag (docker ps --filter ancestor=...) and then the images would
    # be harder to get wrong; not added, since it was not asked for.
    plane_git_path: pl.Path = pl.Path(__file__).resolve().parents[1]
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog=pl.Path(__file__).name,
        description="Create Docker images, start, stop, inspect, back up, and restore a local Plane installation.",
    )
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser] = (
        parser.add_subparsers(
            dest="subparser_name",
            required=True,
            help="Choose a command. Run COMMAND --help to see its arguments.",
        )
    )
    prepare_parser: argparse.ArgumentParser = subparsers.add_parser(
        "prepare",
        help="Create Plane Docker images for later starts and restores.",
        description="Build the current Plane images directly from this checkout using Docker layer caching. Replace the current image tags after source changes; the next start or import uses them.",
    )
    prepare_parser.add_argument(
        "--plane-git-path",
        default=str(plane_git_path),
        metavar="PATH",
        help="Plane checkout containing application sources, packages and Dockerfiles. Default: the checkout containing this script.",
    )
    prepare_parser.add_argument(
        "--image-tag",
        type=parse_image_tag,
        metavar="TAG",
        help="Build the images as plane-local-*:TAG rather than plane-local-*:current, which every instance started without --image-tag runs.",
    )
    start_parser: argparse.ArgumentParser = subparsers.add_parser(
        "start",
        help="Start Plane using the data in --run-dir.",
        description="Start Plane containers and wait until each service is ready. Initialize databases if --run-dir is empty. Use the current Docker image tags; run prepare after source changes.",
    )
    start_parser.add_argument(
        "--plane-git-path",
        default=str(plane_git_path),
        metavar="PATH",
        help="Plane Git checkout used to create missing application images; default: the checkout containing this script. Run prepare after editing sources.",
    )
    start_parser.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Directory containing the databases, uploads, and settings for this instance.",
    )
    start_parser.add_argument(
        "--bind",
        type=BindAddress.parse,
        required=True,
        metavar="IPV4:PORT",
        help="Host address and port the browser reaches Plane on: 127.0.0.1:PORT for this host only, 0.0.0.0:PORT for every interface. It is the only port of the instance open on the host. A browser may reach it by any address of the host or through a tunnel; links in the emails and notifications Plane sends name http://localhost:PORT.",
    )
    start_parser.add_argument(
        "--image-tag",
        type=parse_image_tag,
        metavar="TAG",
        help="Run the images plane-local-*:TAG rather than plane-local-*:current, which every instance started without --image-tag runs, building them first if they are missing. An instance runs only the images of its first start.",
    )
    stop_parser: argparse.ArgumentParser = subparsers.add_parser(
        "stop",
        help="Finish the current background job, save page edits, and stop Plane.",
        description="Finish the current background job, save page edits already received by the server, and stop all containers. Queued jobs remain saved for the next start.",
    )
    stop_parser.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Directory containing the Plane instance to stop.",
    )
    status_parser: argparse.ArgumentParser = subparsers.add_parser(
        "status",
        help="Show whether each Plane container is running or stopped.",
        description="Print container states as JSON. This command does not change files or start services.",
    )
    status_parser.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Directory identifying the Plane instance to inspect.",
    )
    export_parser: argparse.ArgumentParser = subparsers.add_parser(
        "export",
        help="Stop Plane and save a compressed backup.",
        description="Stop Plane, then compress its database files, uploads, queued jobs, and settings into --output. Plane remains stopped after the backup.",
    )
    export_parser.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Directory containing the Plane instance to stop and back up.",
    )
    export_parser.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Backup file outside --run-dir. Replace an existing file only after the complete backup is written and saved to disk.",
    )
    export_parser.add_argument(
        "--zstd-threads",
        type=int,
        default=0,
        help="Number of zstd compression threads for the backup; default: %(default)s. Zero uses all available CPUs.",
    )
    export_parser.add_argument(
        "--zstd-level",
        type=int,
        default=4,
        metavar="LEVEL",
        help="Compression level passed to zstd; default: %(default)s. Higher levels usually make smaller backups and take more time.",
    )
    import_parser: argparse.ArgumentParser = subparsers.add_parser(
        "import",
        help="Replace Plane data from a backup, then start Plane.",
        description="Replace the data in --run-dir with the backup from --input, then start Plane. Use --input /dev/null to delete the previous instance and create an empty one.",
    )
    import_parser.add_argument(
        "--plane-git-path",
        default=str(plane_git_path),
        metavar="PATH",
        help="Plane Git checkout used to create missing application images; default: the checkout containing this script. Run prepare after editing sources.",
    )
    import_parser.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Directory whose previous Plane data will be replaced.",
    )
    import_parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Backup file outside --run-dir, or /dev/null to delete the previous data and create an empty instance.",
    )
    import_parser.add_argument(
        "--bind",
        type=BindAddress.parse,
        required=True,
        metavar="IPV4:PORT",
        help="Host address and port the browser reaches the restored Plane on: 127.0.0.1:PORT for this host only, 0.0.0.0:PORT for every interface. It is the only port of the instance open on the host. A browser may reach it by any address of the host or through a tunnel; links in the emails and notifications Plane sends name http://localhost:PORT.",
    )
    import_parser.add_argument(
        "--image-tag",
        type=parse_image_tag,
        metavar="TAG",
        help="Run the images plane-local-*:TAG rather than plane-local-*:current, which every instance started without --image-tag runs, building them first if they are missing. An instance runs only the images of its first start. The tag recorded in the backup does not count.",
    )
    bootstrap_user_parser: argparse.ArgumentParser = subparsers.add_parser(
        "bootstrap-user",
        help="Create or update an administrator and print its API token.",
        description="Create or update the administrator account with this email and password, and print its API token as JSON. The token is what an MCP client needs as PLANE_API_KEY. The Plane API container must be running.",
    )
    bootstrap_user_parser.add_argument(
        "--run-dir",
        required=True,
        metavar="PATH",
        help="Directory containing the running Plane instance to update.",
    )
    bootstrap_user_parser.add_argument(
        "--email",
        required=True,
        help="Email address of the administrator to create or update.",
    )
    bootstrap_user_parser.add_argument(
        "--password", required=True, help="Password to set for the administrator."
    )
    args: argparse.Namespace = parser.parse_args(argv)
    if args.subparser_name == "prepare":
        return PrepareCommand(
            plane_git_path=pl.Path(args.plane_git_path), image_tag=args.image_tag
        )
    elif args.subparser_name == "start":
        return StartCommand(
            run_dir=pl.Path(args.run_dir),
            plane_git_path=pl.Path(args.plane_git_path),
            bind=args.bind,
            image_tag=args.image_tag,
        )
    elif args.subparser_name == "stop":
        return StopCommand(run_dir=pl.Path(args.run_dir))
    elif args.subparser_name == "status":
        return StatusCommand(run_dir=pl.Path(args.run_dir))
    elif args.subparser_name == "export":
        return ExportCommand(
            run_dir=pl.Path(args.run_dir),
            output=pl.Path(args.output),
            zstd_threads=args.zstd_threads,
            zstd_level=args.zstd_level,
        )
    elif args.subparser_name == "import":
        return ImportCommand(
            run_dir=pl.Path(args.run_dir),
            input=pl.Path(args.input),
            plane_git_path=pl.Path(args.plane_git_path),
            bind=args.bind,
            image_tag=args.image_tag,
        )
    elif args.subparser_name == "bootstrap-user":
        return BootstrapUserCommand(
            run_dir=pl.Path(args.run_dir), email=args.email, password=args.password
        )
    raise RuntimeError(f"Unhandled subcommand: {args.subparser_name}")


def run_cli(argv: t.Sequence[str]) -> int:
    error: Exception
    command: Command = parse_cli_command(argv)
    try:
        command.run()
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        log(str(error))
        return 1
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(run_cli(sys.argv[1:]))
