# Running this Plane checkout: `scripts/plane_runtime.py`

One script starts, stops, backs up and restores a complete Plane installation on one Linux host.
It needs Python, rootless Docker with Buildx, GNU tar, zstd and `nsenter`; it uses only Python's
standard library and reads no environment variable except `PATH`, and `XDG_RUNTIME_DIR` to reach the
user's systemd. Every subcommand has `--help`.

```sh
./scripts/plane_runtime.py prepare                                                # build the images from this checkout
./scripts/plane_runtime.py import --run-dir RUN --bind IP:PORT --input /dev/null   # new empty instance, started
./scripts/plane_runtime.py bootstrap-user --run-dir RUN --email you@example.internal --password '...'
./scripts/plane_runtime.py export --run-dir RUN --output backup.zstd              # stop, then write the backup
./scripts/plane_runtime.py import --run-dir RUN --bind IP:PORT --input backup.zstd # replace everything, then start
./scripts/plane_runtime.py start --run-dir RUN --bind IP:PORT [--persist-auto systemd --export-basename NAME [--export-dir DIR]]
./scripts/plane_runtime.py prepare-and-restart [--run-dir RUN --bind IP:PORT]    # build while it runs, then restart what changed
./scripts/plane_runtime.py stop|status --run-dir RUN
```

Each command prints one JSON line on stdout (with timings for start, stop, export and import) and
diagnostics on stderr. A failed command exits non-zero with the failing external command and its
output in the message.

## The run directory

`config`, `postgres`, `redis` and `uploads` hold all state and are what a backup contains. `logs`
and `runtime` (generated service configuration) are recreated on every start.

`import` always begins by killing and removing the instance's containers and deleting the whole run
directory, so repeating an import after any failure starts from nothing. `import --input /dev/null`
is how an empty instance is created.

## How the instance runs

PostgreSQL, Redis, MinIO, the API, its worker and scheduler, the live server, Spaces and a Caddy
proxy each run in a container. They all share the network namespace of one more container that only
sleeps. Rootless Docker cannot give containers the host's network; the shared namespace lets every
service reach the others on `127.0.0.1` exactly as upstream's configuration expects.

The proxy is the only service the host can reach, on the address and port of `--bind`. `start` and
`import` always take `--bind`; it is not saved in the run directory or in a backup, and starting a
running instance with another address restarts it there. Instances in different run directories with
different ports run side by side.

A browser stays signed in to each of them, a copy imported from another's export too. It sends the cookies of a
host to every port of that host, so an instance names its cookies (its sessions and Django's token against forged
requests) after its port and its id, which an export keeps: a backup restored on the same port keeps the browser
signed in. A session is renewed while it is used and ends only when it was not used for as long as a browser keeps a
cookie.

Images are built from the checkout by `prepare` (or on first use when missing). After changing
sources run `prepare` again; the next `start` sees the new API image and runs Django migrations
before the applications come up. A `start` of a running instance stops and starts again only the
services whose images changed: after a change of the web app alone, the proxy, the live server and
Spaces, while the API keeps answering. Another address, another image of a store, or another version
of this script, which may give the services other arguments or settings, restarts every service.
`prepare-and-restart` is `prepare` and then that `start`: it builds while the instance still runs on
its old images, so the instance is down only while those services restart, and a failed build leaves
it running as it was.

Start waits for each service's own "ready" line in its log (and for the container not to exit),
then makes one protocol request to it: PostgreSQL, Redis and MinIO are asked inside their
containers with their own clients, and the API, the live server and Spaces through the proxy, the
way a browser reaches them. The API, the worker and the scheduler print the "ready" line from a
small hook, because their stock log output does not say when they can serve.

All containers start at once, because the applications need longer to load their code than the
stores need to recover their data. The API, the worker and the scheduler would connect to a store
that is not ready yet, so they start through `apps/api/preload_and_wait.py`: it loads the code,
then waits for a signal that the script sends once the stores answer. The live server starts as
soon as Redis answers. On import the three Python services start even before the backup is
extracted; they need only the configuration, which is the first thing in an archive.

The API listens on its address before it loads its code, and the proxy starts only then. A request
to the API made while the instance starts, a save too, waits in the kernel's queue until the API
accepts it, so a page opened then loads once the API answers, instead of saying that Plane did not
start. A start that fails before the API runs kills the API, so that such requests are answered 502.

## Stop, export and durability

Stop sends SIGTERM to the worker and the live server and waits for them: the worker finishes the
job it is running, and the live server writes every page edit it still holds to the database and
exits zero only if that succeeded. The remaining processes are killed outright. That is safe
because PostgreSQL's write-ahead log and Redis's append-only file (synced on every write) recover
a killed store on the next start. A killed scheduler loses only its record of periodic jobs sent
in the last few minutes, so one of them may run a second time.

Two things about Docker shape how this is done. Docker needs far longer to kill a container than
the container's processes need to die, so the processes get their signal directly and the script
waits for them to exit. And Docker needs longest of all to remove the network of the network
container, so that container is stopped first, alongside everything else. From that moment
nothing outside reaches the instance and the instance reaches nothing outside, while the
services still reach each other. A command ends only after Docker has recorded every stop.

Export stops the instance and streams the four state directories through tar and zstd into a
temporary file beside the output, which replaces the previous backup only after it is complete and
synced. The archive is written as soon as the services are down, while Docker finishes its part.
The instance stays stopped. A backup is a copy of the stopped database cluster, not a
logical dump, so restoring it costs no index rebuilds; it needs the same PostgreSQL major version.

PostgreSQL's files belong to a user id that exists only inside Docker's rootless user namespace.
tar, `rm` and the directory setup for a new cluster therefore run through `nsenter` in that
namespace; everything else runs as the caller.

## Starting at boot, exporting on shutdown

`start --persist-auto systemd --export-basename NAME` also writes
`~/.config/systemd/user/plane-persist-auto.service`, a unit of the user's systemd that runs this `start`,
with these arguments and from this checkout, at every boot, and this script's `stop` at shutdown. The
user's systemd starts at boot because the user lingers (`loginctl enable-linger`). There is one such
unit: running the command again with another run directory or address stops the old instance and moves
the unit. `systemctl --user start|stop|restart|status plane-persist-auto` work on it, and `start`,
`prepare-and-restart`, `stop`, `export` and `import` of that run directory go through it, so that
systemd always knows whether the instance runs. `start --persist-auto none` removes the unit and then
starts the instance once, as a plain `start` does.

`prepare-and-restart` without `--run-dir` and `--bind` brings that instance up to date: it takes them,
and `--image-tag` when it is not given, from the unit. Its `--plane-git-path`, by default the checkout
of the script, must be the one the unit starts, as with `--run-dir` and `--bind`: a run from another
checkout is refused before anything is built. With only one of the two, or without the unit, it says
that both are needed.

The unit's stop exports the instance when the user's systemd itself stops, which for a lingering user
is when the VM powers off or reboots: `crosvm powerbtn`, or `poweroff` or `reboot` inside the VM. The
export is written to `DIR/NAME---YYYY-mm-DD---HH-MM-SS.zstd`, with the local time of the export, at zstd
level 20, and replaces a file of that name. `DIR` is `--export-dir`, by default the directory that holds
this checkout, and is created when missing. A stop or restart of the unit, a restart of Docker and
running `start --persist-auto` again leave the user's systemd running, so they only stop the instance.
At shutdown the unit stops before rootless Docker, which the export reads the run directory through,
and the containers of every instance stop only after the unit
(`~/.config/systemd/user/docker-.scope.d/plane-persist-auto.conf`), so that the export stops the
services in its own order. Two settings of the VM, in `dockerfiles`, make this work: acpid turns the
power button into a poweroff (logind cannot see the button without udev), and the user's systemd may
take as long to stop as the export takes (Ubuntu gives it 5 s). A VM that is killed rather than shut
down exports nothing; the earlier exports stay.

## MCP

Agents use the unmodified upstream [plane-mcp-server](https://github.com/makeplane/plane-mcp-server)
against this instance's public API:

```json
{
  "mcpServers": {
    "plane": {
      "command": "uvx",
      "args": ["plane-mcp-server", "stdio"],
      "env": {
        "PLANE_BASE_URL": "http://localhost:<browser port>",
        "PLANE_API_KEY": "<api_key printed by bootstrap-user>",
        "PLANE_WORKSPACE_SLUG": "<workspace slug>"
      }
    }
  }
}
```

`bootstrap-user` creates (or updates) an administrator and prints its API token; it does not create
a workspace. Create one in the browser first. The instance sets the API key rate limit high enough
that agents are never throttled.
