import argparse
import dataclasses as dc
import errno
import ipaddress
import json
import os
import pathlib as pl
import sys
import tempfile
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


def make_persist_auto_unit(start: runtime.StartCommand) -> str:
    return runtime.make_persist_auto_unit(
        start,
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
            expected: str

        script: str = "/usr/bin/python3 /opt/plane/scripts/plane_runtime.py"
        tcs: t.List[Tc] = [
            Tc(
                "the owner's instance, on every interface",
                make_start("/home/owner/plane-dev", "0.0.0.0:12001"),
                "# Written by plane_runtime.py start --persist-auto systemd, which rewrites it; --persist-auto none removes it.\n"
                "[Unit]\n"
                "Description=Plane of /home/owner/plane-dev on 0.0.0.0:12001, started at boot (plane_runtime.py --persist-auto)\n"
                "Requires=docker.service\n"
                "After=docker.service\n"
                "\n"
                "[Service]\n"
                "Type=oneshot\n"
                "RemainAfterExit=yes\n"
                f"ExecStart={script} start --run-dir /home/owner/plane-dev --plane-git-path /opt/plane --bind 0.0.0.0:12001\n"
                f"ExecReload={script} start --run-dir /home/owner/plane-dev --plane-git-path /opt/plane --bind 0.0.0.0:12001\n"
                f"ExecStop={script} stop --run-dir /home/owner/plane-dev\n"
                f"TimeoutStopSec={2 * runtime.STOP_TIMEOUT + 30}\n"
                "\n"
                "[Install]\n"
                "WantedBy=default.target\n",
            ),
            Tc(
                "an instance with images of its own tag",
                make_start("/srv/checks-1", "127.0.0.1:12141", "plane-67"),
                "# Written by plane_runtime.py start --persist-auto systemd, which rewrites it; --persist-auto none removes it.\n"
                "[Unit]\n"
                "Description=Plane of /srv/checks-1 on 127.0.0.1:12141, started at boot (plane_runtime.py --persist-auto)\n"
                "Requires=docker.service\n"
                "After=docker.service\n"
                "\n"
                "[Service]\n"
                "Type=oneshot\n"
                "RemainAfterExit=yes\n"
                f"ExecStart={script} start --run-dir /srv/checks-1 --plane-git-path /opt/plane --bind 127.0.0.1:12141 --image-tag plane-67\n"
                f"ExecReload={script} start --run-dir /srv/checks-1 --plane-git-path /opt/plane --bind 127.0.0.1:12141 --image-tag plane-67\n"
                f"ExecStop={script} stop --run-dir /srv/checks-1\n"
                f"TimeoutStopSec={2 * runtime.STOP_TIMEOUT + 30}\n"
                "\n"
                "[Install]\n"
                "WantedBy=default.target\n",
            ),
        ]
        i: int
        tc: Tc
        for i, tc in enumerate(tcs):
            actual: str = make_persist_auto_unit(tc.start)
            self.assertEqual(actual, tc.expected, f"Testcase #{i + 1} {tc.name}")

    def test_unit_refuses_an_argument_that_systemd_would_change(self) -> None:
        run_dir: str
        for run_dir in (
            "/srv/plane dev",
            "/srv/plane%h",
            "/srv/plane$HOME",
            '/srv/"plane"',
        ):
            with (
                self.subTest(run_dir=run_dir),
                self.assertRaisesRegex(RuntimeError, "Cannot persist"),
            ):
                make_persist_auto_unit(make_start(run_dir, "0.0.0.0:12001"))

    def test_unit_reads_back_as_the_start_it_was_made_from(self) -> None:
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
            actual: t.Tuple[str, t.List[t.List[str]]] = (
                unit_path.read_text(),
                [list(call.args[0]) for call in systemctl.call_args_list],
            )
        expected: t.Tuple[str, t.List[t.List[str]]] = (
            runtime.make_persist_auto_unit(
                start, pl.Path(sys.executable), runtime.PLANE_RUNTIME_SCRIPT
            ),
            [
                ["daemon-reload"],
                ["enable", runtime.PERSIST_AUTO_UNIT_NAME],
                ["start", runtime.PERSIST_AUTO_UNIT_NAME],
            ],
        )
        self.assertEqual(actual, expected)

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
                ],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("0.0.0.0"), 12001),
                    None,
                    runtime.PersistAuto.SYSTEMD,
                ),
            ),
            Tc(["stop", "--run-dir", "run"], runtime.StopCommand(pl.Path("run"))),
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
