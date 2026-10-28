import argparse
import concurrent.futures
import dataclasses as dc
import errno
import io
import ipaddress
import json
import os
import pathlib as pl
import sys
import tempfile
import time
import typing as t
import unittest
import unittest.mock as mock

sys.path.insert(0, str(pl.Path(__file__).resolve().parents[1]))
import plane_config
import plane_runtime as runtime


class CallerDockerFs(runtime.DockerFs):
    def get_fs_cmd(self, argv: t.Sequence[str]) -> t.List[str]:
        # Tests have no rootless Docker namespace: they run the same commands as the caller,
        # who cannot restore the owners recorded in an archive.
        return [argument for argument in argv if argument != "--same-owner"]


class PipeProcess:
    def __init__(self, output: bytes) -> None:
        reader: int
        writer: int
        reader, writer = os.pipe()
        os.write(writer, output)
        self.writer: int = writer
        self.stdout: t.BinaryIO = os.fdopen(reader, "rb", buffering=0)

    def kill(self) -> None:
        os.close(self.writer)

    def wait(self) -> int:
        return 0


def make_initialized_instance(run_dir: pl.Path) -> plane_config.InstanceConfig:
    config: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
    config.initialized = True
    contents: t.Dict[str, bytes] = {
        "postgres/PG_VERSION": b"18\n",
        "postgres/pg_wal/wal": b"wal",
        "redis/appendonlydir/segment.aof": b"queue",
        "uploads/.minio.sys/format.json": b"{}",
    }
    name: str
    content: bytes
    for name, content in contents.items():
        path: pl.Path = run_dir / name
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
    (run_dir / "postgres/pg_twophase").mkdir()
    config.write(run_dir)
    return config


def read_tree(run_dir: pl.Path) -> t.Dict[str, t.Optional[bytes]]:
    return {
        str(path.relative_to(run_dir)): path.read_bytes() if path.is_file() else None
        for path in run_dir.rglob("*")
    }


class ArchiveTests(unittest.TestCase):
    def test_extracted_archive_equals_exported_persistent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary) / "original"
            make_initialized_instance(run_dir)
            (run_dir / "logs").mkdir()
            (run_dir / "logs/api.log").write_text("not part of a backup")
            archive: pl.Path = pl.Path(temporary) / "backup.zstd"
            restored_run_dir: pl.Path = pl.Path(temporary) / "restored"
            restored_run_dir.mkdir()
            with CallerDockerFs() as docker_fs:
                runtime.write_archive(run_dir, archive, docker_fs, {}, 0, 5)
                runtime.extract_archive(archive, restored_run_dir, docker_fs, {})
            expected: t.Dict[str, t.Optional[bytes]] = {
                name: content
                for name, content in read_tree(run_dir).items()
                if not name.startswith("logs")
            }
            actual: t.Dict[str, t.Optional[bytes]] = read_tree(restored_run_dir)
            self.assertEqual(actual, expected)

    def test_failed_archive_pipeline_keeps_previous_archive(self) -> None:
        failing_tool: str
        for failing_tool in ("tar", "zstd"):
            with (
                self.subTest(failing_tool=failing_tool),
                tempfile.TemporaryDirectory() as temporary,
            ):
                run_dir: pl.Path = pl.Path(temporary) / "original"
                make_initialized_instance(run_dir)
                archive: pl.Path = pl.Path(temporary) / "backup.zstd"
                archive.write_bytes(b"previous backup")
                bin_dir: pl.Path = pl.Path(temporary) / "bin"
                bin_dir.mkdir()
                (bin_dir / failing_tool).write_text("#!/bin/sh\nexit 97\n")
                (bin_dir / failing_tool).chmod(0o755)
                with (
                    mock.patch.dict(
                        os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
                    ),
                    CallerDockerFs() as docker_fs,
                    self.assertRaisesRegex(RuntimeError, "Archive pipeline failed"),
                ):
                    runtime.write_archive(run_dir, archive, docker_fs, {}, 0, 5)
                actual: t.Dict[str, t.Optional[bytes]] = read_tree(archive.parent)
                self.assertEqual(actual["backup.zstd"], b"previous backup")
                self.assertEqual(
                    [name for name in actual if name.startswith(".backup.zstd")], []
                )


class ImportTests(unittest.TestCase):
    def run_import(
        self,
        run_dir: pl.Path,
        input: pl.Path,
        image_tag: t.Optional[plane_config.ImageTag] = None,
    ) -> None:
        with (
            mock.patch.object(runtime, "DockerFs", CallerDockerFs),
            mock.patch.object(runtime, "remove_containers"),
            mock.patch.object(
                runtime, "build_or_pull_missing_images_and_get_ids", return_value={}
            ),
            mock.patch.object(
                runtime,
                "start_network_container_and_python_services",
                return_value={},
            ),
            mock.patch.object(runtime, "start_plane_services"),
            mock.patch("sys.stdout"),
        ):
            runtime.ImportCommand(
                run_dir,
                input,
                pl.Path(run_dir.parent / "plane-git"),
                runtime.BindAddress.parse("127.0.0.1:18080"),
                image_tag,
            ).run()

    def test_import_replaces_everything_a_failed_import_left_in_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original_run_dir: pl.Path = pl.Path(temporary) / "original"
            make_initialized_instance(original_run_dir)
            archive: pl.Path = pl.Path(temporary) / "backup.zstd"
            with CallerDockerFs() as docker_fs:
                runtime.write_archive(original_run_dir, archive, docker_fs, {}, 0, 5)
            run_dir: pl.Path = pl.Path(temporary) / "target"
            (run_dir / "postgres/base").mkdir(parents=True)
            (run_dir / "postgres/base/partially-restored").write_bytes(b"stale")
            (run_dir / "runtime").mkdir()
            (run_dir / "runtime/minio.json").write_text("stale")
            self.run_import(run_dir, archive)
            actual: t.Dict[str, t.Optional[bytes]] = read_tree(run_dir)
            expected: t.Dict[str, t.Optional[bytes]] = read_tree(original_run_dir)
            self.assertEqual(actual, expected)

    def test_import_from_dev_null_leaves_only_empty_directories_and_new_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary) / "target"
            previous_config: plane_config.InstanceConfig = make_initialized_instance(
                run_dir
            )
            self.run_import(run_dir, pl.Path("/dev/null"))
            actual: t.List[str] = sorted(read_tree(run_dir))
            expected: t.List[str] = [
                "config",
                "config/instance.json",
                "postgres",
                "redis",
                "uploads",
            ]
            self.assertEqual(actual, expected)
            config: plane_config.InstanceConfig = runtime.require_instance_config(
                run_dir
            )
            self.assertFalse(config.initialized)
            self.assertNotEqual(config.secrets, previous_config.secrets)

    def test_import_records_its_own_image_tag_over_the_archive_s(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original_run_dir: pl.Path = pl.Path(temporary) / "original"
            exported: plane_config.InstanceConfig = make_initialized_instance(
                original_run_dir
            )
            exported.image_tag = plane_config.ImageTag("plane-47")
            exported.write(original_run_dir)
            archive: pl.Path = pl.Path(temporary) / "backup.zstd"
            with CallerDockerFs() as docker_fs:
                runtime.write_archive(original_run_dir, archive, docker_fs, {}, 0, 5)
            run_dir: pl.Path = pl.Path(temporary) / "target"
            self.run_import(run_dir, archive, None)
            actual: plane_config.InstanceConfig = runtime.require_instance_config(
                run_dir
            )
            expected: plane_config.InstanceConfig = dc.replace(exported, image_tag=None)
            self.assertEqual(actual, expected)

    def test_import_refuses_another_image_tag_and_keeps_the_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary) / "target"
            make_initialized_instance(run_dir)
            expected: t.Dict[str, t.Optional[bytes]] = read_tree(run_dir)
            with self.assertRaisesRegex(RuntimeError, "plane-local-\\*:current"):
                self.run_import(
                    run_dir, pl.Path("/dev/null"), plane_config.ImageTag("plane-47")
                )
            actual: t.Dict[str, t.Optional[bytes]] = read_tree(run_dir)
            self.assertEqual(actual, expected)


class StartTests(unittest.TestCase):
    def run_start(
        self, run_dir: pl.Path, image_tag: t.Optional[plane_config.ImageTag]
    ) -> mock.MagicMock:
        def write_config(
            run_dir: pl.Path, config: plane_config.InstanceConfig, *_: t.Any
        ) -> None:
            config.write(run_dir)

        with (
            mock.patch.object(runtime, "DockerFs", CallerDockerFs),
            mock.patch.object(
                runtime, "build_or_pull_missing_images_and_get_ids", return_value={}
            ) as build,
            mock.patch.object(
                runtime, "start_plane_services", side_effect=write_config
            ),
            mock.patch("sys.stdout"),
        ):
            runtime.StartCommand(
                run_dir,
                pl.Path(run_dir.parent / "plane-git"),
                runtime.BindAddress.parse("127.0.0.1:18080"),
                image_tag,
            ).run()
        return build

    def test_start_of_a_new_instance_records_its_image_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary) / "new"
            self.run_start(run_dir, plane_config.ImageTag("plane-47"))
            actual: t.Optional[plane_config.ImageTag] = runtime.require_instance_config(
                run_dir
            ).image_tag
            self.assertEqual(actual, "plane-47")

    def test_start_refuses_another_image_tag_before_building_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary) / "instance"
            config: plane_config.InstanceConfig = make_initialized_instance(run_dir)
            config.image_tag = plane_config.ImageTag("plane-47")
            config.write(run_dir)
            with (
                mock.patch.object(
                    runtime, "build_or_pull_missing_images_and_get_ids"
                ) as build,
                self.assertRaisesRegex(RuntimeError, "plane-local-\\*:plane-47"),
            ):
                runtime.StartCommand(
                    run_dir,
                    pl.Path(temporary) / "plane-git",
                    runtime.BindAddress.parse("127.0.0.1:18080"),
                    None,
                ).run()
            self.assertEqual(build.call_count, 0)


class PrepareAndRestartTests(unittest.TestCase):
    def test_builds_only_for_a_start_that_would_be_accepted_and_restarts_only_after_the_build(
        self,
    ) -> None:
        class Tc(t.NamedTuple):
            name: str
            image_tag_of_instance: str
            bind_of_persisted: t.Optional[str]
            build_error: t.Optional[str]
            expected: t.Tuple[t.List[str], t.Optional[str]]

        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary).resolve() / "instance"
            plane_git_path: pl.Path = pl.Path(temporary).resolve() / "plane-git"
            start: runtime.StartCommand = runtime.StartCommand(
                run_dir,
                plane_git_path,
                runtime.BindAddress.parse("0.0.0.0:12001"),
                plane_config.ImageTag("plane-47"),
            )
            tcs: t.List[Tc] = [
                Tc(
                    "an instance of this image tag",
                    "plane-47",
                    None,
                    None,
                    (["build", "pull", "start"], None),
                ),
                Tc(
                    "an instance of another image tag",
                    "plane-48",
                    None,
                    None,
                    (
                        [],
                        "The instance runs the images plane-local-*:plane-48, and this command names "
                        "plane-local-*:plane-47: pass --image-tag plane-48, or another --run-dir",
                    ),
                ),
                Tc(
                    "a failed build",
                    "plane-47",
                    None,
                    "Command failed (1): docker buildx build: see stderr",
                    (["build"], "Command failed (1): docker buildx build: see stderr"),
                ),
                Tc(
                    "the instance of the persist-auto unit, with its arguments",
                    "plane-47",
                    "0.0.0.0:12001",
                    None,
                    (["build", "pull", "start"], None),
                ),
                Tc(
                    "the instance of the persist-auto unit, with another address",
                    "plane-47",
                    "127.0.0.1:12001",
                    None,
                    (
                        [],
                        f"{runtime.PERSIST_AUTO_UNIT_NAME} starts {run_dir} with --bind 127.0.0.1:12001 and "
                        f"--image-tag plane-47, from the checkout {plane_git_path}: pass the same, change what it "
                        "starts with start --persist-auto systemd, or stop starting it at boot with start "
                        "--persist-auto none",
                    ),
                ),
            ]
            i: int
            tc: Tc
            for i, tc in enumerate(tcs):
                config: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
                config.image_tag = plane_config.ImageTag(tc.image_tag_of_instance)
                config.write(run_dir)
                steps: t.List[str] = []

                def build(*_: t.Any) -> None:
                    steps.append("build")
                    if tc.build_error is not None:
                        raise RuntimeError(tc.build_error)

                error: t.Optional[str] = None
                with (
                    mock.patch.object(
                        runtime,
                        "get_persist_auto_start_of",
                        return_value=None
                        if tc.bind_of_persisted is None
                        else dc.replace(
                            start,
                            bind=runtime.BindAddress.parse(tc.bind_of_persisted),
                        ),
                    ),
                    mock.patch.object(runtime, "build_our_images", side_effect=build),
                    mock.patch.object(
                        runtime,
                        "pull_and_resolve_external_images",
                        side_effect=lambda: steps.append("pull"),
                    ),
                    mock.patch.object(
                        runtime.StartCommand,
                        "run",
                        side_effect=lambda: steps.append("start"),
                    ),
                ):
                    try:
                        runtime.PrepareAndRestartCommand(start).run()
                    except RuntimeError as raised:
                        error = str(raised)
                actual: t.Tuple[t.List[str], t.Optional[str]] = (steps, error)
                self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")


class PlaneEnvironmentTests(unittest.TestCase):
    def test_instances_on_one_host_name_their_cookies_apart_and_a_restored_backup_keeps_them(
        self,
    ) -> None:
        def get_cookie_names(
            config: plane_config.InstanceConfig, port: int
        ) -> t.Tuple[str, str, str]:
            environment: t.Dict[str, str] = runtime.get_plane_environment(port, config)
            return (
                environment["SESSION_COOKIE_NAME"],
                environment["ADMIN_SESSION_COOKIE_NAME"],
                environment["CSRF_COOKIE_NAME"],
            )

        exported: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
        other: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
        with tempfile.TemporaryDirectory() as temporary:
            # an archive carries the configuration as it is written in the run directory
            exported.write(pl.Path(temporary))
            imported: plane_config.InstanceConfig = runtime.require_instance_config(
                pl.Path(temporary)
            )
        names: t.Tuple[str, str, str] = get_cookie_names(exported, 18080)
        cases: t.List[t.Tuple[str, bool]] = [
            (
                "a copy imported from the export, on another port, names them otherwise",
                set(get_cookie_names(imported, 18081)).isdisjoint(names),
            ),
            (
                "another instance on the same port of another machine names them otherwise",
                set(get_cookie_names(other, 18080)).isdisjoint(names),
            ),
            (
                "the backup restored on the same port keeps them",
                get_cookie_names(imported, 18080) == names,
            ),
            (
                "the names that Plane and Django give them unless told otherwise are not taken",
                set(names).isdisjoint({"session-id", "admin-session-id", "csrftoken"}),
            ),
        ]
        actual: t.List[t.Tuple[str, bool]] = cases
        expected: t.List[t.Tuple[str, bool]] = [(rule, True) for rule, _ in cases]
        self.assertEqual(actual, expected)


class InstanceConfigTests(unittest.TestCase):
    def test_written_config_reads_back_equal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary)
            expected: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
            expected.initialized = True
            expected.last_api_image = "sha256:image"
            expected.image_tag = plane_config.ImageTag("plane-47")
            expected.write(run_dir)
            actual: plane_config.InstanceConfig = runtime.require_instance_config(
                run_dir
            )
            self.assertEqual(actual, expected)
            self.assertEqual(
                {type(name) for name in actual.secrets}, {plane_config.SecretName}
            )

    def test_config_written_before_image_tags_runs_without_one(self) -> None:
        text: str = json.dumps(
            {
                "secrets": {name.value: "secret" for name in plane_config.SecretName},
                "instance_id": "instance",
                "initialized": True,
                "last_api_image": "sha256:image",
            }
        )
        actual: plane_config.InstanceConfig = plane_config.InstanceConfig.parse(text)
        expected: plane_config.InstanceConfig = plane_config.InstanceConfig(
            secrets={name: "secret" for name in plane_config.SecretName},
            instance_id="instance",
            initialized=True,
            last_api_image="sha256:image",
            image_tag=None,
        )
        self.assertEqual(actual, expected)

    def test_interrupted_config_write_keeps_previous_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary)
            expected: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
            expected.write(run_dir)

            def write_partial_config_then_fail(
                value: plane_config.JSONObject, file: t.TextIO, indent: int
            ) -> None:
                file.write('{"secrets":')
                raise OSError(errno.ENOSPC, "No space left on device")

            with (
                mock.patch(
                    "plane_config.json.dump",
                    side_effect=write_partial_config_then_fail,
                ),
                self.assertRaises(OSError),
            ):
                plane_config.InstanceConfig.make().write(run_dir)
            actual: plane_config.InstanceConfig = runtime.require_instance_config(
                run_dir
            )
            self.assertEqual(actual, expected)


class ServiceReadinessTests(unittest.TestCase):
    def wait_for_readiness(
        self, logs: bytes, exit_status: bytes, probe: t.Callable[[float], object]
    ) -> None:
        processes: t.List[PipeProcess] = [PipeProcess(logs), PipeProcess(exit_status)]
        try:
            with (
                mock.patch("plane_runtime.subprocess.Popen", side_effect=processes),
                mock.patch.object(runtime, "START_TIMEOUT", 0.2),
            ):
                runtime.wait_for_service_readiness(
                    pl.Path("/run-dir"),
                    plane_config.Service.POSTGRES,
                    "service ready",
                    probe,
                )
        finally:
            process: PipeProcess
            for process in processes:
                process.stdout.close()

    def test_ready_marker_is_followed_by_one_protocol_probe(self) -> None:
        probe: mock.Mock = mock.Mock()
        self.wait_for_readiness(b"loading\nservice ready\n", b"", probe)
        self.assertEqual(probe.call_count, 1)

    def test_container_exit_fails_startup_even_with_a_ready_marker(self) -> None:
        probe: mock.Mock = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "exited during startup: postgres: 1"):
            self.wait_for_readiness(b"service ready\n", b"1\n", probe)
        self.assertEqual(probe.call_count, 0)

    def test_missing_ready_marker_fails_at_the_startup_deadline(self) -> None:
        probe: mock.Mock = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "readiness timed out: postgres"):
            self.wait_for_readiness(b"still loading\n", b"", probe)
        self.assertEqual(probe.call_count, 0)

    def test_failed_protocol_probe_fails_startup(self) -> None:
        probe: mock.Mock = mock.Mock(side_effect=RuntimeError("probe refused"))
        with self.assertRaisesRegex(RuntimeError, "probe refused"):
            self.wait_for_readiness(b"service ready\n", b"", probe)


class RunningInstanceTests(unittest.TestCase):
    def test_start_replaces_the_services_not_as_asked_and_every_one_for_a_store_the_network_or_another_script(
        self,
    ) -> None:
        bind: runtime.BindAddress = runtime.BindAddress.parse("127.0.0.1:12141")
        image_ids: t.Dict[plane_config.Service, str] = {
            service: "sha256:built" for service in plane_config.Service
        }

        def make_container(
            service: plane_config.Service,
            image: str = "sha256:built",
            network_mode: str = "container:network-id",
            port: int = 12141,
            labels: t.Optional[t.Dict[str, str]] = None,
        ) -> runtime.Container:
            is_network: bool = service == plane_config.Service.NETWORK
            return {
                "Id": "network-id" if is_network else f"{service.value}-id",
                "Name": f"/plane-x-{service.value}",
                "Image": image,
                "State": {"Running": True},
                "Config": {
                    "Labels": {"org.plane.local.script": runtime.RUNTIME_SCRIPT_DIGEST}
                    if labels is None
                    else labels,
                    "Cmd": ["serve"],
                },
                "HostConfig": {
                    "NetworkMode": "bridge" if is_network else network_mode,
                    "PortBindings": {
                        "8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]
                    }
                    if is_network
                    else {},
                },
            }

        def make_running(**changed: runtime.Container) -> runtime.Containers:
            running: runtime.Containers = {
                service: make_container(service) for service in plane_config.Service
            }
            name: str
            container: runtime.Container
            for name, container in changed.items():
                running[plane_config.Service(name)] = container
            return running

        class Tc(t.NamedTuple):
            name: str
            running: runtime.Containers
            expected: t.Set[plane_config.Service]

        api: plane_config.Service = plane_config.Service.API
        every_service: t.Set[plane_config.Service] = set(plane_config.Service)
        tcs: t.List[Tc] = [
            Tc("every service as this script starts it", make_running(), set()),
            Tc(
                "a service on an image other than the one just built",
                make_running(api=make_container(api, image="sha256:older")),
                {api},
            ),
            Tc(
                "the clients on images other than those just built, after a change of the web app",
                make_running(
                    live=make_container(
                        plane_config.Service.LIVE, image="sha256:older"
                    ),
                    space=make_container(
                        plane_config.Service.SPACE, image="sha256:older"
                    ),
                    proxy=make_container(
                        plane_config.Service.PROXY, image="sha256:older"
                    ),
                ),
                {
                    plane_config.Service.LIVE,
                    plane_config.Service.SPACE,
                    plane_config.Service.PROXY,
                },
            ),
            Tc(
                "a service outside the namespace of the network container",
                make_running(api=make_container(api, network_mode="bridge")),
                {api},
            ),
            Tc(
                "a service that another version of this script made",
                make_running(
                    api=make_container(
                        api, labels={"org.plane.local.script": "sha256 of another"}
                    )
                ),
                every_service,
            ),
            Tc(
                "a service made before containers were labelled with their script",
                make_running(
                    postgres=make_container(plane_config.Service.POSTGRES, labels={})
                ),
                every_service,
            ),
            Tc(
                "a store on an image other than the one this script names",
                make_running(
                    redis=make_container(
                        plane_config.Service.REDIS, image="sha256:older"
                    )
                ),
                every_service,
            ),
            Tc(
                "the network container on another port",
                make_running(
                    network=make_container(plane_config.Service.NETWORK, port=12142)
                ),
                every_service,
            ),
            Tc(
                "no network container",
                {
                    service: container
                    for service, container in make_running().items()
                    if service != plane_config.Service.NETWORK
                },
                every_service - {plane_config.Service.NETWORK},
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: t.Set[plane_config.Service] = (
                runtime.get_running_services_to_replace(tc.running, bind, image_ids)
            )
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")


class BindAddressTests(unittest.TestCase):
    def test_parse_accepts_only_ipv4_and_port_in_range(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            text: str
            expected: t.Optional[runtime.BindAddress]

        tcs: t.List[Tc] = [
            Tc(
                "loopback",
                "127.0.0.1:12001",
                runtime.BindAddress(ipaddress.IPv4Address("127.0.0.1"), 12001),
            ),
            Tc(
                "every interface",
                "0.0.0.0:12001",
                runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 12001),
            ),
            Tc(
                "highest port",
                "10.11.13.3:65535",
                runtime.BindAddress(ipaddress.IPv4Address("10.11.13.3"), 65535),
            ),
            Tc("port alone", "12001", None),
            Tc("host name", "localhost:12001", None),
            Tc("ipv6", "[::1]:12001", None),
            Tc("no port", "127.0.0.1:", None),
            Tc("port zero", "127.0.0.1:0", None),
            Tc("port above range", "127.0.0.1:65536", None),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: t.Optional[runtime.BindAddress]
            try:
                actual = runtime.BindAddress.parse(tc.text)
            except argparse.ArgumentTypeError:
                actual = None
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_local_clients_reach_every_interface_through_loopback(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            text: str
            expected: ipaddress.IPv4Address

        tcs: t.List[Tc] = [
            Tc("every interface", "0.0.0.0:12001", ipaddress.IPv4Address("127.0.0.1")),
            Tc("loopback", "127.0.0.1:12001", ipaddress.IPv4Address("127.0.0.1")),
            Tc(
                "one interface", "10.11.13.3:12001", ipaddress.IPv4Address("10.11.13.3")
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: ipaddress.IPv4Address = runtime.BindAddress.parse(
                tc.text
            ).get_host_for_local_clients()
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")


class ImageTagTests(unittest.TestCase):
    def test_parse_accepts_only_docker_tags_other_than_the_owner_s(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            text: str
            expected: t.Optional[plane_config.ImageTag]

        tcs: t.List[Tc] = [
            Tc("task", "plane-47", plane_config.ImageTag("plane-47")),
            Tc("underscore first", "_a.b-c", plane_config.ImageTag("_a.b-c")),
            Tc("longest", "a" * 128, plane_config.ImageTag("a" * 128)),
            Tc(
                "other case than the owner's",
                "Current",
                plane_config.ImageTag("Current"),
            ),
            Tc("the owner's", "current", None),
            Tc("empty", "", None),
            Tc("too long", "a" * 129, None),
            Tc("dash first", "-a", None),
            Tc("dot first", ".a", None),
            Tc("slash", "a/b", None),
            Tc("colon", "a:b", None),
            Tc("space", "a b", None),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: t.Optional[plane_config.ImageTag]
            try:
                actual = runtime.parse_image_tag(tc.text)
            except argparse.ArgumentTypeError:
                actual = None
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_image_tag_applies_to_our_images_and_leaves_external_ones(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            image_tag: t.Optional[plane_config.ImageTag]
            expected: t.Dict[plane_config.Service, str]

        tcs: t.List[Tc] = [
            Tc(
                "no tag",
                None,
                {
                    plane_config.Service.API: "plane-local-api:current",
                    plane_config.Service.LIVE: "plane-local-live:current",
                    plane_config.Service.SPACE: "plane-local-space:current",
                    plane_config.Service.PROXY: "plane-local-proxy:current",
                    **runtime.EXTERNAL_DEPS,
                },
            ),
            Tc(
                "a tag of its own",
                plane_config.ImageTag("plane-47"),
                {
                    plane_config.Service.API: "plane-local-api:plane-47",
                    plane_config.Service.LIVE: "plane-local-live:plane-47",
                    plane_config.Service.SPACE: "plane-local-space:plane-47",
                    plane_config.Service.PROXY: "plane-local-proxy:plane-47",
                    **runtime.EXTERNAL_DEPS,
                },
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: t.Dict[plane_config.Service, str] = runtime.get_all_images(
                tc.image_tag
            )
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_instance_accepts_only_the_image_tag_of_its_first_start(self) -> None:
        def make_config(
            image_tag: t.Optional[plane_config.ImageTag],
        ) -> plane_config.InstanceConfig:
            config: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
            config.image_tag = image_tag
            return config

        class Tc(t.NamedTuple):
            name: str
            config: t.Optional[plane_config.InstanceConfig]
            image_tag: t.Optional[plane_config.ImageTag]
            expected_is_accepted: bool

        tag: plane_config.ImageTag = plane_config.ImageTag("plane-47")
        tcs: t.List[Tc] = [
            Tc("new instance, without tag", None, None, True),
            Tc("new instance, with tag", None, tag, True),
            Tc("without tag, again without", make_config(None), None, True),
            Tc("without tag, now with one", make_config(None), tag, False),
            Tc("with tag, again the same", make_config(tag), tag, True),
            Tc("with tag, now without", make_config(tag), None, False),
            Tc(
                "with tag, now another",
                make_config(tag),
                plane_config.ImageTag("plane-48"),
                False,
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: bool
            try:
                runtime.require_same_image_tag_as_instance(tc.config, tc.image_tag)
                actual = True
            except RuntimeError:
                actual = False
            self.assertEqual(
                actual, tc.expected_is_accepted, f"Testcase #{i + 1} {tc.name}"
            )


def make_start(
    run_dir: str, bind: str, image_tag: t.Optional[str] = None
) -> runtime.StartCommand:
    return runtime.StartCommand(
        pl.Path(run_dir),
        pl.Path("/opt/plane"),
        runtime.BindAddress.parse(bind),
        None if image_tag is None else plane_config.ImageTag(image_tag),
    )


EXPORT_ON_SHUTDOWN: runtime.ExportOnShutdown = runtime.ExportOnShutdown(
    "plane-dev-export", pl.Path("/opt")
)


def make_persist_auto_unit(
    start: runtime.StartCommand,
    export_on_shutdown: runtime.ExportOnShutdown = EXPORT_ON_SHUTDOWN,
) -> str:
    return runtime.make_persist_auto_unit(
        dc.replace(start, export_on_shutdown=export_on_shutdown),
        pl.Path("/usr/bin/python3"),
        pl.Path("/opt/plane/scripts/plane_runtime.py"),
    )


class PersistAutoTests(unittest.TestCase):
    def test_unit_starts_and_stops_the_instance_with_the_persisted_arguments(
        self,
    ) -> None:
        class Tc(t.NamedTuple):
            name: str
            start: runtime.StartCommand
            export_on_shutdown: runtime.ExportOnShutdown
            expected: str

        script: str = "/usr/bin/python3 /opt/plane/scripts/plane_runtime.py"
        tcs: t.List[Tc] = [
            Tc(
                "the owner's instance, on every interface, exported beside the checkout",
                make_start("/home/owner/plane-dev", "0.0.0.0:12001"),
                runtime.ExportOnShutdown("plane-dev-export", pl.Path("/opt")),
                "# Written by plane_runtime.py start --persist-auto systemd, which rewrites it; --persist-auto none removes it.\n"
                "[Unit]\n"
                "Description=Plane of /home/owner/plane-dev on 0.0.0.0:12001, started at boot and exported on shutdown (plane_runtime.py --persist-auto)\n"
                "Requires=docker.service\n"
                "After=docker.service\n"
                "\n"
                "[Service]\n"
                "Type=oneshot\n"
                "RemainAfterExit=yes\n"
                f"ExecStart={script} start --run-dir /home/owner/plane-dev --plane-git-path /opt/plane --bind 0.0.0.0:12001\n"
                f"ExecReload={script} start --run-dir /home/owner/plane-dev --plane-git-path /opt/plane --bind 0.0.0.0:12001\n"
                f"ExecStop={script} stop --run-dir /home/owner/plane-dev --export-basename plane-dev-export --export-dir /opt\n"
                "TimeoutStopSec=infinity\n"
                "\n"
                "[Install]\n"
                "WantedBy=default.target\n",
            ),
            Tc(
                "an instance with images of its own tag, exported to a directory of its own",
                make_start("/srv/checks-1", "127.0.0.1:12141", "plane-67"),
                runtime.ExportOnShutdown("checks-1", pl.Path("/srv/exports/checks")),
                "# Written by plane_runtime.py start --persist-auto systemd, which rewrites it; --persist-auto none removes it.\n"
                "[Unit]\n"
                "Description=Plane of /srv/checks-1 on 127.0.0.1:12141, started at boot and exported on shutdown (plane_runtime.py --persist-auto)\n"
                "Requires=docker.service\n"
                "After=docker.service\n"
                "\n"
                "[Service]\n"
                "Type=oneshot\n"
                "RemainAfterExit=yes\n"
                f"ExecStart={script} start --run-dir /srv/checks-1 --plane-git-path /opt/plane --bind 127.0.0.1:12141 --image-tag plane-67\n"
                f"ExecReload={script} start --run-dir /srv/checks-1 --plane-git-path /opt/plane --bind 127.0.0.1:12141 --image-tag plane-67\n"
                f"ExecStop={script} stop --run-dir /srv/checks-1 --export-basename checks-1 --export-dir /srv/exports/checks\n"
                "TimeoutStopSec=infinity\n"
                "\n"
                "[Install]\n"
                "WantedBy=default.target\n",
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: str = make_persist_auto_unit(tc.start, tc.export_on_shutdown)
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_unit_refuses_an_argument_that_systemd_would_change(self) -> None:
        start: runtime.StartCommand = make_start("/srv/a", "0.0.0.0:12001")
        starts: t.List[t.Tuple[runtime.StartCommand, runtime.ExportOnShutdown]] = [
            *(
                (make_start(run_dir, "0.0.0.0:12001"), EXPORT_ON_SHUTDOWN)
                for run_dir in (
                    "/srv/plane dev",
                    "/srv/plane%h",
                    "/srv/plane$HOME",
                    '/srv/"plane"',
                )
            ),
            (start, runtime.ExportOnShutdown("plane %Y", pl.Path("/opt"))),
            (start, runtime.ExportOnShutdown("plane", pl.Path("/srv/my exports"))),
        ]
        export_on_shutdown: runtime.ExportOnShutdown
        for start, export_on_shutdown in starts:
            with (
                self.subTest(start=start, export_on_shutdown=export_on_shutdown),
                self.assertRaisesRegex(RuntimeError, "Cannot persist"),
            ):
                make_persist_auto_unit(start, export_on_shutdown)

    def test_unit_refuses_an_export_dir_in_the_run_dir(self) -> None:
        export_dir: str
        for export_dir in ("/srv/a", "/srv/a/exports", "/srv/a/../a/exports"):
            with (
                self.subTest(export_dir=export_dir),
                self.assertRaisesRegex(RuntimeError, "outside run-dir"),
            ):
                make_persist_auto_unit(
                    make_start("/srv/a", "0.0.0.0:12001"),
                    runtime.ExportOnShutdown("plane-dev-export", pl.Path(export_dir)),
                )

    def test_unit_reads_back_as_the_start_it_was_made_from_without_the_export(
        self,
    ) -> None:
        start: runtime.StartCommand
        for start in (
            make_start("/home/owner/plane-dev", "0.0.0.0:12001"),
            make_start("/srv/checks-1", "127.0.0.1:12141", "plane-67"),
        ):
            with self.subTest(start=start):
                actual: runtime.StartCommand = runtime.parse_persist_auto_unit(
                    make_persist_auto_unit(start)
                )
                self.assertEqual(actual, start)

    def test_steps_turn_the_persisted_unit_into_the_wanted_one(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            persisted_unit: t.Optional[str]
            wanted_unit: t.Optional[str]
            expected: t.List[runtime.PersistAutoStep]

        unit: str = runtime.PERSIST_AUTO_UNIT_NAME
        first: str = make_persist_auto_unit(make_start("/srv/a", "0.0.0.0:12001"))
        second: str = make_persist_auto_unit(make_start("/srv/b", "0.0.0.0:12002"))
        tcs: t.List[Tc] = [
            Tc(
                "first persisted",
                None,
                first,
                [
                    ("write-unit",),
                    ("systemctl", "daemon-reload"),
                    ("systemctl", "enable", unit),
                    ("systemctl", "start", unit),
                ],
            ),
            Tc(
                "persisted again with the same arguments",
                first,
                first,
                [
                    ("systemctl", "enable", unit),
                    ("systemctl", "reload-or-restart", unit),
                ],
            ),
            Tc(
                "moved to another run directory and address",
                first,
                second,
                [
                    ("systemctl", "stop", unit),
                    ("write-unit",),
                    ("systemctl", "daemon-reload"),
                    ("systemctl", "enable", unit),
                    ("systemctl", "start", unit),
                ],
            ),
            Tc(
                "undone",
                first,
                None,
                [
                    ("systemctl", "stop", unit),
                    ("systemctl", "disable", unit),
                    ("remove-unit",),
                    ("systemctl", "daemon-reload"),
                ],
            ),
            Tc("undone with nothing persisted", None, None, []),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: t.List[runtime.PersistAutoStep] = runtime.get_persist_auto_steps(
                tc.persisted_unit, tc.wanted_unit
            )
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_only_a_hand_run_command_on_the_persisted_run_dir_goes_through_the_unit(
        self,
    ) -> None:
        class Tc(t.NamedTuple):
            name: str
            persisted_unit: t.Optional[str]
            is_in_unit: bool
            run_dir: pl.Path
            expected: t.Optional[runtime.StartCommand]

        persisted: runtime.StartCommand = make_start("/srv/a", "0.0.0.0:12001")
        tcs: t.List[Tc] = [
            Tc("nothing persisted", None, False, pl.Path("/srv/a"), None),
            Tc(
                "the persisted run directory, by hand",
                make_persist_auto_unit(persisted),
                False,
                pl.Path("/srv/a"),
                persisted,
            ),
            Tc(
                "another run directory",
                make_persist_auto_unit(persisted),
                False,
                pl.Path("/srv/b"),
                None,
            ),
            Tc(
                "the persisted run directory, from the unit itself",
                make_persist_auto_unit(persisted),
                True,
                pl.Path("/srv/a"),
                None,
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            with (
                mock.patch.object(
                    runtime, "read_persist_auto_unit", return_value=tc.persisted_unit
                ),
                mock.patch.object(
                    runtime,
                    "is_running_in_persist_auto_unit",
                    return_value=tc.is_in_unit,
                ),
            ):
                actual: t.Optional[runtime.StartCommand] = (
                    runtime.get_persist_auto_start_of(tc.run_dir)
                )
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_hand_run_start_of_the_persisted_run_dir_needs_its_arguments(
        self,
    ) -> None:
        persisted: runtime.StartCommand = make_start("/srv/a", "0.0.0.0:12001")
        runtime.require_same_start_as_persisted(
            make_start("/srv/./a", "0.0.0.0:12001"), persisted
        )
        start: runtime.StartCommand
        for start in (
            make_start("/srv/a", "127.0.0.1:12001"),
            make_start("/srv/a", "0.0.0.0:12001", "plane-67"),
        ):
            with (
                self.subTest(start=start),
                self.assertRaisesRegex(RuntimeError, "--persist-auto systemd"),
            ):
                runtime.require_same_start_as_persisted(start, persisted)

    def test_start_with_persist_auto_writes_the_unit_and_starts_it_through_systemd(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            unit_path: pl.Path = pl.Path(temporary) / runtime.PERSIST_AUTO_UNIT_NAME
            start: runtime.StartCommand = dc.replace(
                make_start("/srv/a", "0.0.0.0:12001"),
                persist_auto=runtime.PersistAuto.SYSTEMD,
                export_on_shutdown=EXPORT_ON_SHUTDOWN,
            )
            with (
                mock.patch.object(
                    runtime, "get_persist_auto_unit_path", return_value=unit_path
                ),
                mock.patch.object(runtime, "require_lingering_user"),
                mock.patch.object(runtime, "run_systemctl_for_user") as systemctl,
                mock.patch("sys.stdout"),
            ):
                start.run()
            actual: t.Tuple[t.Dict[str, t.Optional[bytes]], t.List[t.List[str]]] = (
                read_tree(pl.Path(temporary)),
                [list(call.args[0]) for call in systemctl.call_args_list],
            )
        expected: t.Tuple[t.Dict[str, t.Optional[bytes]], t.List[t.List[str]]] = (
            {
                runtime.PERSIST_AUTO_UNIT_NAME: runtime.make_persist_auto_unit(
                    start, pl.Path(sys.executable), runtime.PLANE_RUNTIME_SCRIPT
                ).encode(),
                "docker-.scope.d": None,
                "docker-.scope.d/plane-persist-auto.conf": (
                    "# Written by plane_runtime.py start --persist-auto systemd with plane-persist-auto.service; --persist-auto none removes it.\n"
                    "[Unit]\n"
                    "Before=plane-persist-auto.service\n"
                ).encode(),
            },
            [
                ["daemon-reload"],
                ["enable", runtime.PERSIST_AUTO_UNIT_NAME],
                ["start", runtime.PERSIST_AUTO_UNIT_NAME],
            ],
        )
        self.assertEqual(actual, expected)

    def test_start_with_persist_auto_none_removes_the_unit_and_the_order_of_the_containers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            unit_path: pl.Path = pl.Path(temporary) / runtime.PERSIST_AUTO_UNIT_NAME
            persisted: runtime.StartCommand = dc.replace(
                make_start("/srv/a", "0.0.0.0:12001"),
                persist_auto=runtime.PersistAuto.SYSTEMD,
                export_on_shutdown=EXPORT_ON_SHUTDOWN,
            )
            with (
                mock.patch.object(
                    runtime, "get_persist_auto_unit_path", return_value=unit_path
                ),
                mock.patch.object(runtime, "require_lingering_user"),
                mock.patch.object(runtime, "run_systemctl_for_user"),
                mock.patch.object(runtime.StartCommand, "run", autospec=True) as run,
                mock.patch("sys.stdout"),
            ):
                runtime.StartCommand.persist_and_start(persisted)
                runtime.StartCommand.persist_and_start(
                    dc.replace(
                        persisted,
                        persist_auto=runtime.PersistAuto.NONE,
                        export_on_shutdown=None,
                    )
                )
            actual: t.Tuple[t.Dict[str, t.Optional[bytes]], t.List[t.Any]] = (
                read_tree(pl.Path(temporary)),
                [call.args[0] for call in run.call_args_list],
            )
        self.assertEqual(actual, ({}, [make_start("/srv/a", "0.0.0.0:12001")]))

    def test_hand_run_stop_of_the_persisted_run_dir_stops_the_unit(self) -> None:
        with (
            mock.patch.object(
                runtime,
                "get_persist_auto_start_of",
                return_value=make_start("/srv/a", "0.0.0.0:12001"),
            ),
            mock.patch.object(runtime, "run_systemctl_for_user") as systemctl,
            mock.patch.object(runtime, "stop_plane_containers") as stop,
            mock.patch("sys.stdout"),
        ):
            runtime.StopCommand(pl.Path("/srv/a")).run()
        actual: t.Tuple[t.List[t.List[str]], int] = (
            [list(call.args[0]) for call in systemctl.call_args_list],
            stop.call_count,
        )
        self.assertEqual(actual, ([["stop", runtime.PERSIST_AUTO_UNIT_NAME]], 0))


# What prepare-and-restart did: "build", "pull", then the start it ran, or nothing after its error.
PrepareAndRestartSteps = t.List[t.Union[str, runtime.StartCommand]]


class PrepareAndRestartArgumentsTests(unittest.TestCase):
    def run_prepare_and_restart(
        self, argv: t.List[str], persisted: t.Optional[runtime.StartCommand]
    ) -> t.Tuple[PrepareAndRestartSteps, t.Optional[str]]:
        """Runs prepare-and-restart from its command line by hand, with the persist-auto unit of persisted (None: no
        unit), and records what it builds and the start it would run."""
        steps: PrepareAndRestartSteps = []
        error: t.Optional[str] = None
        stderr: io.StringIO = io.StringIO()
        with (
            mock.patch.object(
                runtime,
                "read_persist_auto_unit",
                return_value=None
                if persisted is None
                else make_persist_auto_unit(persisted),
            ),
            mock.patch.object(
                runtime, "is_running_in_persist_auto_unit", return_value=False
            ),
            mock.patch.object(
                runtime,
                "build_our_images",
                side_effect=lambda *_: steps.append("build"),
            ),
            mock.patch.object(
                runtime,
                "pull_and_resolve_external_images",
                side_effect=lambda: steps.append("pull"),
            ),
            mock.patch.object(
                runtime.StartCommand, "run", autospec=True, side_effect=steps.append
            ),
            mock.patch("sys.stderr", stderr),
        ):
            try:
                runtime.parse_cli_command(["prepare-and-restart", *argv]).run()
            except RuntimeError as raised:
                error = str(raised)
            except SystemExit:
                error = stderr.getvalue().splitlines()[-1]
        return steps, error

    def test_takes_run_dir_bind_and_image_tag_from_the_persist_auto_unit_only_when_both_are_left_out(
        self,
    ) -> None:
        class Tc(t.NamedTuple):
            name: str
            argv: t.List[str]
            persisted: t.Optional[runtime.StartCommand]
            expected: t.Tuple[PrepareAndRestartSteps, t.Optional[str]]

        checkout: pl.Path = pl.Path(runtime.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary).resolve() / "plane-dev"
            other_run_dir: pl.Path = pl.Path(temporary).resolve() / "checks-1"
            persisted: runtime.StartCommand = runtime.StartCommand(
                run_dir, checkout, runtime.BindAddress.parse("0.0.0.0:12001"), None
            )
            persisted_with_tag: runtime.StartCommand = dc.replace(
                persisted, image_tag=plane_config.ImageTag("plane-67")
            )
            given: t.List[str] = [
                "--run-dir",
                str(other_run_dir),
                "--bind",
                "127.0.0.1:12141",
                "--image-tag",
                "plane-47",
            ]
            start_of_given: runtime.StartCommand = runtime.StartCommand(
                other_run_dir,
                checkout,
                runtime.BindAddress.parse("127.0.0.1:12141"),
                plane_config.ImageTag("plane-47"),
            )
            together: str = (
                "plane_runtime.py prepare-and-restart: error: --run-dir and --bind go together: pass both, or "
                f"neither for the instance that {runtime.PERSIST_AUTO_UNIT_NAME} starts"
            )
            tcs: t.List[Tc] = [
                Tc(
                    "both given, no unit",
                    given,
                    None,
                    (["build", "pull", start_of_given], None),
                ),
                Tc(
                    "both given, of another instance than the unit's",
                    given,
                    persisted,
                    (["build", "pull", start_of_given], None),
                ),
                Tc(
                    "both left out, the unit's instance",
                    [],
                    persisted,
                    (["build", "pull", persisted], None),
                ),
                Tc(
                    "both left out, the unit's instance on images of its own tag",
                    [],
                    persisted_with_tag,
                    (["build", "pull", persisted_with_tag], None),
                ),
                Tc(
                    "both left out, no unit",
                    [],
                    None,
                    (
                        [],
                        f"Pass --run-dir and --bind: there is no {runtime.get_persist_auto_unit_path()} "
                        "(start --persist-auto systemd) to take them from",
                    ),
                ),
                Tc(
                    "only --run-dir, the unit's",
                    ["--run-dir", str(run_dir)],
                    persisted,
                    ([], together),
                ),
                Tc(
                    "only --bind, the unit's",
                    ["--bind", "0.0.0.0:12001"],
                    persisted,
                    ([], together),
                ),
            ]
            i: int
            tc: Tc
            for i, tc in enumerate(tcs):
                actual: t.Tuple[PrepareAndRestartSteps, t.Optional[str]] = (
                    self.run_prepare_and_restart(tc.argv, tc.persisted)
                )
                self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_without_run_dir_and_bind_refuses_another_checkout_or_image_tag_than_the_unit_s_before_building(
        self,
    ) -> None:
        class Tc(t.NamedTuple):
            name: str
            argv: t.List[str]
            persisted: runtime.StartCommand
            expected: t.Tuple[PrepareAndRestartSteps, t.Optional[str]]

        checkout: pl.Path = pl.Path(runtime.__file__).resolve().parents[1]
        other_checkout: pl.Path = pl.Path("/opt/plane")
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary).resolve() / "plane-dev"
            persisted_with_tag: runtime.StartCommand = runtime.StartCommand(
                run_dir,
                checkout,
                runtime.BindAddress.parse("0.0.0.0:12001"),
                plane_config.ImageTag("plane-67"),
            )
            persisted_of_other_checkout: runtime.StartCommand = dc.replace(
                persisted_with_tag, plane_git_path=other_checkout
            )
            tcs: t.List[Tc] = [
                Tc(
                    "run from another checkout than the unit's",
                    [],
                    persisted_of_other_checkout,
                    (
                        [],
                        f"{runtime.PERSIST_AUTO_UNIT_NAME} starts {run_dir} with --bind 0.0.0.0:12001 and "
                        f"--image-tag plane-67, from the checkout {other_checkout}: pass the same, change what it "
                        "starts with start --persist-auto systemd, or stop starting it at boot with start "
                        "--persist-auto none",
                    ),
                ),
                Tc(
                    "run from another checkout, with the unit's as --plane-git-path",
                    ["--plane-git-path", str(other_checkout)],
                    persisted_of_other_checkout,
                    (["build", "pull", persisted_of_other_checkout], None),
                ),
                Tc(
                    "another --image-tag than the unit's",
                    ["--image-tag", "plane-48"],
                    persisted_with_tag,
                    (
                        [],
                        f"{runtime.PERSIST_AUTO_UNIT_NAME} starts {run_dir} with --bind 0.0.0.0:12001 and "
                        f"--image-tag plane-67, from the checkout {checkout}: pass the same, change what it "
                        "starts with start --persist-auto systemd, or stop starting it at boot with start "
                        "--persist-auto none",
                    ),
                ),
                Tc(
                    "the unit's --image-tag",
                    ["--image-tag", "plane-67"],
                    persisted_with_tag,
                    (["build", "pull", persisted_with_tag], None),
                ),
            ]
            i: int
            tc: Tc
            for i, tc in enumerate(tcs):
                actual: t.Tuple[PrepareAndRestartSteps, t.Optional[str]] = (
                    self.run_prepare_and_restart(tc.argv, tc.persisted)
                )
                self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")


class ExportOnShutdownTests(unittest.TestCase):
    def test_output_is_named_by_the_local_time_of_the_export(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            export_on_shutdown: runtime.ExportOnShutdown
            now: time.struct_time
            expected: pl.Path

        tcs: t.List[Tc] = [
            Tc(
                "beside the checkout",
                runtime.ExportOnShutdown(
                    "plane-dev-export", pl.Path("/home/owner/devel")
                ),
                time.struct_time((2026, 10, 23, 18, 5, 9, 4, 296, 0)),
                pl.Path(
                    "/home/owner/devel/plane-dev-export---2026-10-23---18-05-09.zstd"
                ),
            ),
            Tc(
                "a month, day, hour, minute and second of one digit",
                runtime.ExportOnShutdown("plane-dev-export", pl.Path("/srv/exports")),
                time.struct_time((2027, 1, 2, 3, 4, 5, 5, 2, 0)),
                pl.Path("/srv/exports/plane-dev-export---2027-01-02---03-04-05.zstd"),
            ),
            Tc(
                "the last second of a year",
                runtime.ExportOnShutdown("checks-1", pl.Path("/srv/exports")),
                time.struct_time((2026, 12, 31, 23, 59, 59, 3, 365, 0)),
                pl.Path("/srv/exports/checks-1---2026-12-31---23-59-59.zstd"),
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: pl.Path = runtime.get_export_on_shutdown_output(
                tc.export_on_shutdown, tc.now
            )
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_stop_exports_only_when_the_user_s_systemd_is_stopping(self) -> None:
        class Tc(t.NamedTuple):
            name: str
            export_on_shutdown: t.Optional[runtime.ExportOnShutdown]
            is_user_systemd_stopping: bool
            expected: t.Tuple[t.List[runtime.ExportCommand], int]

        now: time.struct_time = time.struct_time((2026, 10, 23, 18, 5, 9, 4, 296, 0))
        tcs: t.List[Tc] = [
            Tc(
                "the shutdown of the user's systemd",
                EXPORT_ON_SHUTDOWN,
                True,
                (
                    [
                        runtime.ExportCommand(
                            pl.Path("/srv/a"),
                            pl.Path(
                                "/opt/plane-dev-export---2026-10-23---18-05-09.zstd"
                            ),
                            0,
                            runtime.EXPORT_ON_SHUTDOWN_ZSTD_LEVEL,
                        )
                    ],
                    0,
                ),
            ),
            Tc(
                "a stop or restart of the unit",
                EXPORT_ON_SHUTDOWN,
                False,
                ([], 1),
            ),
            Tc(
                "the shutdown of the user's systemd, without --export-basename",
                None,
                True,
                ([], 1),
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            with (
                mock.patch.object(
                    runtime, "get_persist_auto_start_of", return_value=None
                ),
                mock.patch.object(
                    runtime,
                    "is_user_systemd_stopping",
                    return_value=tc.is_user_systemd_stopping,
                ),
                mock.patch("time.localtime", return_value=now),
                mock.patch.object(
                    runtime.ExportCommand, "run", autospec=True
                ) as export,
                mock.patch.object(runtime, "stop_plane_containers") as stop,
                mock.patch("sys.stdout"),
            ):
                runtime.StopCommand(pl.Path("/srv/a"), tc.export_on_shutdown).run()
            actual: t.Tuple[t.List[runtime.ExportCommand], int] = (
                [call.args[0] for call in export.call_args_list],
                stop.call_count,
            )
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_export_creates_missing_directories_and_replaces_a_backup_of_the_same_name(
        self,
    ) -> None:
        class Tc(t.NamedTuple):
            name: str
            existing: t.Dict[str, t.Optional[bytes]]

        # a zstd frame begins with these bytes
        zstd_magic_number: bytes = bytes.fromhex("28b52ffd")
        tcs: t.List[Tc] = [
            Tc("two levels of directories missing", {}),
            Tc("the directories there", {"a": None, "a/b": None}),
            Tc(
                "a backup of the same name there",
                {"a": None, "a/b": None, "a/b/backup.zstd": b"previous backup"},
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            with tempfile.TemporaryDirectory() as temporary:
                run_dir: pl.Path = pl.Path(temporary) / "run"
                make_initialized_instance(run_dir)
                exports: pl.Path = pl.Path(temporary) / "exports"
                exports.mkdir()
                name: str
                content: t.Optional[bytes]
                for name, content in tc.existing.items():
                    if content is None:
                        (exports / name).mkdir()
                    else:
                        (exports / name).write_bytes(content)
                stopped: concurrent.futures.Future[None] = concurrent.futures.Future()
                stopped.set_result(None)
                with (
                    mock.patch.object(runtime, "DockerFs", CallerDockerFs),
                    mock.patch.object(
                        runtime, "read_persist_auto_unit", return_value=None
                    ),
                    mock.patch.object(
                        runtime, "stop_plane_containers", return_value=stopped
                    ),
                    mock.patch("sys.stdout"),
                ):
                    runtime.ExportCommand(
                        run_dir, exports / "a/b/backup.zstd", 0, 1
                    ).run()
                actual: t.Dict[str, t.Optional[bytes]] = {
                    name: None if content is None else content[:4]
                    for name, content in read_tree(exports).items()
                }
            self.assertEqual(
                actual,
                {"a": None, "a/b": None, "a/b/backup.zstd": zstd_magic_number},
                f"Testcase #{i + 1} {tc.name}",
            )


class CommandLineTests(unittest.TestCase):
    def test_each_subcommand_parses_to_its_command(self) -> None:
        class Tc(t.NamedTuple):
            argv: t.List[str]
            expected: runtime.Command

        plane_git_path: pl.Path = pl.Path(runtime.__file__).resolve().parents[1]
        tcs: t.List[Tc] = [
            Tc(["prepare"], runtime.PrepareCommand(plane_git_path, None)),
            Tc(
                ["prepare", "--image-tag", "plane-47"],
                runtime.PrepareCommand(
                    plane_git_path, plane_config.ImageTag("plane-47")
                ),
            ),
            Tc(
                ["start", "--run-dir", "run", "--bind", "127.0.0.1:18580"],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("127.0.0.1"), 18580),
                    None,
                ),
            ),
            Tc(
                [
                    "start",
                    "--run-dir",
                    "run",
                    "--bind",
                    "127.0.0.1:18580",
                    "--image-tag",
                    "plane-47",
                ],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("127.0.0.1"), 18580),
                    plane_config.ImageTag("plane-47"),
                ),
            ),
            Tc(
                [
                    "start",
                    "--run-dir",
                    "run",
                    "--bind",
                    "0.0.0.0:12001",
                    "--persist-auto",
                    "systemd",
                    "--export-basename",
                    "plane-dev-export",
                ],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 12001),
                    None,
                    runtime.PersistAuto.SYSTEMD,
                    runtime.ExportOnShutdown("plane-dev-export", plane_git_path.parent),
                ),
            ),
            Tc(
                [
                    "start",
                    "--run-dir",
                    "run",
                    "--bind",
                    "0.0.0.0:12001",
                    "--persist-auto",
                    "systemd",
                    "--export-basename",
                    "plane-dev-export",
                    "--export-dir",
                    "exports",
                ],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 12001),
                    None,
                    runtime.PersistAuto.SYSTEMD,
                    runtime.ExportOnShutdown("plane-dev-export", pl.Path("exports")),
                ),
            ),
            Tc(
                [
                    "start",
                    "--run-dir",
                    "run",
                    "--bind",
                    "0.0.0.0:12001",
                    "--persist-auto",
                    "none",
                ],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 12001),
                    None,
                    runtime.PersistAuto.NONE,
                ),
            ),
            Tc(["stop", "--run-dir", "run"], runtime.StopCommand(pl.Path("run"))),
            Tc(
                ["stop", "--run-dir", "run", "--export-basename", "plane-dev-export"],
                runtime.StopCommand(
                    pl.Path("run"),
                    runtime.ExportOnShutdown("plane-dev-export", plane_git_path.parent),
                ),
            ),
            Tc(
                [
                    "stop",
                    "--run-dir",
                    "run",
                    "--export-basename",
                    "plane-dev-export",
                    "--export-dir",
                    "/srv/exports",
                ],
                runtime.StopCommand(
                    pl.Path("run"),
                    runtime.ExportOnShutdown(
                        "plane-dev-export", pl.Path("/srv/exports")
                    ),
                ),
            ),
            Tc(["status", "--run-dir", "run"], runtime.StatusCommand(pl.Path("run"))),
            Tc(
                [
                    "export",
                    "--run-dir",
                    "run",
                    "--output",
                    "backup.zstd",
                    "--zstd-threads",
                    "2",
                    "--zstd-level",
                    "19",
                ],
                runtime.ExportCommand(pl.Path("run"), pl.Path("backup.zstd"), 2, 19),
            ),
            Tc(
                [
                    "import",
                    "--run-dir",
                    "run",
                    "--input",
                    "/dev/null",
                    "--bind",
                    "0.0.0.0:18080",
                ],
                runtime.ImportCommand(
                    pl.Path("run"),
                    pl.Path("/dev/null"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 18080),
                    None,
                ),
            ),
            Tc(
                [
                    "import",
                    "--run-dir",
                    "run",
                    "--input",
                    "backup.zstd",
                    "--plane-git-path",
                    "plane",
                    "--bind",
                    "127.0.0.1:18580",
                    "--image-tag",
                    "plane-47",
                ],
                runtime.ImportCommand(
                    pl.Path("run"),
                    pl.Path("backup.zstd"),
                    pl.Path("plane"),
                    runtime.BindAddress(ipaddress.IPv4Address("127.0.0.1"), 18580),
                    plane_config.ImageTag("plane-47"),
                ),
            ),
            Tc(
                [
                    "prepare-and-restart",
                    "--run-dir",
                    "run",
                    "--bind",
                    "0.0.0.0:12001",
                    "--image-tag",
                    "plane-47",
                ],
                runtime.PrepareAndRestartCommand(
                    runtime.StartCommand(
                        pl.Path("run"),
                        plane_git_path,
                        runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 12001),
                        plane_config.ImageTag("plane-47"),
                    )
                ),
            ),
            Tc(
                ["prepare-and-restart"],
                runtime.PrepareAndRestartPersistedCommand(plane_git_path, None),
            ),
            Tc(
                [
                    "bootstrap-user",
                    "--run-dir",
                    "run",
                    "--email",
                    "me@example.internal",
                    "--password",
                    "secret",
                ],
                runtime.BootstrapUserCommand(
                    pl.Path("run"), "me@example.internal", "secret"
                ),
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: runtime.Command = runtime.parse_cli_command(tc.argv)
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.argv}")

    def test_start_and_import_need_a_bind_address(self) -> None:
        argv: t.List[str]
        for argv in (
            ["start", "--run-dir", "run"],
            ["import", "--run-dir", "run", "--input", "/dev/null"],
        ):
            with (
                self.subTest(argv=argv),
                mock.patch("sys.stderr"),
                self.assertRaises(SystemExit),
            ):
                runtime.parse_cli_command(argv)

    def test_export_options_need_persist_auto_systemd_and_a_basename(self) -> None:
        start: t.List[str] = ["start", "--run-dir", "run", "--bind", "0.0.0.0:12001"]
        argv: t.List[str]
        for argv in (
            [*start, "--persist-auto", "systemd"],
            [*start, "--persist-auto", "systemd", "--export-dir", "exports"],
            [*start, "--export-basename", "plane-dev-export"],
            [*start, "--export-dir", "exports"],
            [*start, "--persist-auto", "none", "--export-basename", "plane-dev-export"],
            [*start, "--persist-auto", "systemd", "--export-basename", "exports/plane"],
            [*start, "--persist-auto", "systemd", "--export-basename", ".."],
            ["stop", "--run-dir", "run", "--export-dir", "exports"],
        ):
            with (
                self.subTest(argv=argv),
                mock.patch("sys.stderr"),
                self.assertRaises(SystemExit),
            ):
                runtime.parse_cli_command(argv)

    def test_failed_command_exits_nonzero_and_prints_the_error_as_json(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch("sys.stdout") as stdout,
            mock.patch("sys.stderr"),
        ):
            actual: int = runtime.run_cli(
                ["export", "--run-dir", temporary + "/absent", "--output", "/dev/null"]
            )
        self.assertEqual(actual, 1)
        self.assertEqual(
            json.loads(stdout.write.call_args_list[0].args[0]),
            {"ok": False, "error": "Archive output must be a regular file"},
        )


if __name__ == "__main__":
    unittest.main()
