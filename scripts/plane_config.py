import dataclasses as dc
import enum
import json
import os
import pathlib as pl
import secrets
import typing as t


class Service(enum.StrEnum):
    PROXY = "proxy"
    SPACE = "space"
    LIVE = "live"
    API = "api"
    WORKER = "worker"
    BEAT = "beat"
    MINIO = "minio"
    REDIS = "redis"
    POSTGRES = "postgres"
    NETWORK = "network"


class SecretName(enum.StrEnum):
    DJANGO = "django"
    POSTGRES = Service.POSTGRES
    MINIO = Service.MINIO
    LIVE = Service.LIVE


JSONObject: t.TypeAlias = t.Dict[str, t.Any]
ServiceSecrets: t.TypeAlias = t.Dict[SecretName, str]
# Tags the images that an instance runs, so that a session can build images of its own beside the owner's;
# see --image-tag in scripts/plane_runtime.py.
ImageTag = t.NewType("ImageTag", str)


def fsync_dir(path: pl.Path) -> None:
    fd: int = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@dc.dataclass
class InstanceConfig:
    secrets: ServiceSecrets
    instance_id: str
    initialized: bool = False
    last_api_image: t.Optional[str] = None
    image_tag: t.Optional[ImageTag] = None

    @staticmethod
    def get_path(run_dir: pl.Path) -> pl.Path:
        return run_dir / "config/instance.json"

    @classmethod
    def make(cls) -> "InstanceConfig":
        return cls(
            secrets={name: secrets.token_hex(32) for name in SecretName},
            instance_id=secrets.token_hex(16),
        )

    @classmethod
    def parse(cls, text: str) -> "InstanceConfig":
        fields: JSONObject = json.loads(text)
        return cls(
            secrets={
                SecretName(name): secret for name, secret in fields["secrets"].items()
            },
            instance_id=fields["instance_id"],
            initialized=fields.get("initialized", False),
            last_api_image=fields.get("last_api_image"),
            image_tag=fields.get("image_tag"),
        )

    @classmethod
    def read_existing(cls, run_dir: pl.Path) -> t.Optional["InstanceConfig"]:
        try:
            return cls.parse(cls.get_path(run_dir).read_text())
        except FileNotFoundError:
            return None

    def write(self, run_dir: pl.Path) -> None:
        path: pl.Path = self.get_path(run_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: pl.Path = path.with_name(path.name + ".writing")
        file: t.TextIO
        with temporary.open("w") as file:
            json.dump(dc.asdict(self), file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        fsync_dir(path.parent)
