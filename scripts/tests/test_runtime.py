import argparse
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
    def run_import(self, run_dir: pl.Path, input: pl.Path) -> None:
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


class InstanceConfigTests(unittest.TestCase):
    def test_written_config_reads_back_equal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir: pl.Path = pl.Path(temporary)
            expected: plane_config.InstanceConfig = plane_config.InstanceConfig.make()
            expected.initialized = True
            expected.last_api_image = "sha256:image"
            expected.write(run_dir)
            actual: plane_config.InstanceConfig = runtime.require_instance_config(
                run_dir
            )
            self.assertEqual(actual, expected)
            self.assertEqual(
                {type(name) for name in actual.secrets}, {plane_config.SecretName}
            )

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


class CommandLineTests(unittest.TestCase):
    def test_each_subcommand_parses_to_its_command(self) -> None:
        class Tc(t.NamedTuple):
            argv: t.List[str]
            expected: runtime.Command

        plane_git_path: pl.Path = pl.Path(runtime.__file__).resolve().parents[1]
        tcs: t.List[Tc] = [
            Tc(["prepare"], runtime.PrepareCommand(plane_git_path)),
            Tc(
                ["start", "--run-dir", "run", "--bind", "127.0.0.1:18580"],
                runtime.StartCommand(
                    pl.Path("run"),
                    plane_git_path,
                    runtime.BindAddress(ipaddress.IPv4Address("127.0.0.1"), 18580),
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
                ],
                runtime.ImportCommand(
                    pl.Path("run"),
                    pl.Path("backup.zstd"),
                    pl.Path("plane"),
                    runtime.BindAddress(ipaddress.IPv4Address("127.0.0.1"), 18580),
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
