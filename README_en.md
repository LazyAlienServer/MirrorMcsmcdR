# MirrorMcsmcdR

[![MCDR](https://img.shields.io/badge/MCDR-%E2%89%A52.16.0-blue)](https://github.com/Fallen-Breath/MCDReforged) [![License](https://img.shields.io/github/license/LazyAlienServer/MirrorMcsmcdR)](./LICENSE) [![Downloads](https://img.shields.io/github/downloads/LazyAlienServer/MirrorMcsmcdR/total)](https://github.com/LazyAlienServer/MirrorMcsmcdR/releases)

[中文](./README.md) · English

> The most comprehensive [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) mirror server control plugin! Control mirror servers through multiple methods and synchronize additions and deletions based on hashes.

## Features

- **Multiple control and lifecycle methods**:
  - Control mirror servers through [MCSManager](https://github.com/MCSManager/MCSManager) (`MCSM-v9.9.0` `MCSM-v10.2.1+`)
  - Start and stop mirror servers directly through terminal proxies (`Linux` `Windows`), with the new terminal independent from the parent MCDR process
    - Linux uses `screen` to control the mirror server
    - Windows uses a new command prompt to control the mirror server
  - Start mirror servers as child processes inside MCDR through `subprocess`, controlled through standard input and output
  - Send commands through `!!mirror input <command>`
  - Combine multiple control methods, for example:
    - Start and stop through MCDR, then force-terminate through Linux when the mirror process fails
- **Comprehensive control features**: manage multiple mirror servers, inspect status, start, stop, force-terminate, and synchronize
- **Hash-based file synchronization**: synchronize only files that differ from the source server, improving speed and reducing disk I/O
- **Pre-sync backup**: optionally back up the mirror world with the mirror's own PrimeBackup before every sync; without a successful backup, nothing is synced
- **Highly customizable configuration**: use YAML and write only changed values when configuring multiple mirror servers

> [!NOTE]
> This plugin does not provide server creation or management functionality. Please use it after creating the mirror server and its MCSManager instance. It broadcasts `has started` once the mirror server is up, but gives no notice when it has stopped; consider a companion plugin such as vchat for that.

## Dependencies

| Dependency           | Description                                                                             |
|----------------------|-----------------------------------------------------------------------------------------|
| Python               | `>=3.10`                                                                                |
| Python package       | `xxhash>=3`                                                                             |
| Linux terminal proxy | [`screen`](https://www.gnu.org/software/screen/) when `proxy_type` is `linux` or `null` |
| PrimeBackup          | `>=1.13.0` in the mirror's MCDR, only with [pre-sync backup](#syncbackup-pre-sync-backup) enabled |

## Upgrading from v1.8.0 or earlier

The new version requires MCDReforged `>=2.16.0`; upgrade it if needed.

A mirror server started by an older version is not in the new version's record (see [Mirror server status](#mirror-server-status)). It can keep running through the upgrade: the plugin adopts it when it loads (see [Adopting a mirror server](#adopting-a-mirror-server)). When it cannot be adopted automatically, the plugin says so in the console and in the game; adopt it with `!!mirror recover` then, or stop it by hand. With `is_mcdr` set to `false` the plugin only reports it and never adopts it automatically; adopt it with `!!mirror recover`. A mirror server that does not run in a screen or a console window (such as one started with `nohup`) has no console once adopted, and only `!!mirror kill -f` ends it.

After upgrading, check the configuration file:
- The `rcon` section is removed, and an old `rcon` section is ignored. Use MCSManager to control a mirror server on another host;
- `terminal.regex_strict` is removed. Whenever the configured port is held by any process the plugin does not track, the status is `status unknown`;
- The `subprocess` proxy now requires `terminal.port` as well; without it the terminal proxy is unavailable;
- `command.action.sync.max_attempt_times` is removed. After an automatic stop for a sync, the plugin waits up to `command.action.stop.timeout` seconds (60 by default; 15 before);
- `command.action.sync.check_status_interval` moved to `command.action.check_status_interval`. A value at the old place is ignored, and the default `5` applies;
- `!!mirror execute` is renamed `!!mirror input`; the old command no longer exists. The permission key `command.permission.execute` becomes `command.permission.input`; an old `execute` key is ignored, and the default `console` applies;
- `terminal.launch_path` becomes the top-level [`root_path`](#root_path--is_mcdr-mirror-server-directory-and-kind), `terminal.is_mcdr` becomes the top-level `is_mcdr`, and `sync.backup.mcdr_path` is removed (the backup uses `root_path`). The old keys are ignored, `root_path` falls back to its default `./Mirror` and `is_mcdr` to its default `true`; **set them by hand**. A plain-server mirror that had `terminal.is_mcdr: false` needs `is_mcdr: false` again (later mirror entries inherit the value of the first one). With `is_mcdr` set to `false` there is no pre-sync backup: with `sync.backup.enable` on, every sync is refused;
- When the mirror's MCDR is started with another config file through `--config`, set `sync.target`; the pre-sync backup is not supported then, see [`root_path`](#root_path--is_mcdr-mirror-server-directory-and-kind);
- `command.permission.abort` and `command.action.abort` are removed; no command ever used them;
- With both `mcsm` and `terminal` enabled, only MCSM is used now and the `terminal` section has no effect (`log` and `input`, which only the subprocess proxy offers, are unavailable as well). This keeps `kill -f` and adopting a mirror server from acting on local processes that have nothing to do with the MCSM instance;
- On Windows the `subprocess` proxy now reads the mirror server's output as UTF-8 instead of the system code page. The mirror's MCDR writes UTF-8, so `log` shows non-ASCII text correctly now; a plain server (`is_mcdr` set to `false`) whose output is not UTF-8 shows garbled text in `log`;
- `sync.source` and `sync.target` may be left empty; they then use this MCDR's `working_directory` and the directory derived from `root_path`. Values already set keep working;
- `sync.world` now holds [gitignore patterns](#sync-configuration-file-related-to-file-synchronization). A plain directory name keeps its meaning, but matching is case-sensitive, also on Windows: `World` used to sync `world` as well, now it must be spelt as the directory is, or the sync is refused. A sync now also deletes empty directories that only the mirror's world has;
- `sync.ignore_files` is removed in favour of `sync.ignore_patterns` and `sync.retain_patterns`; the old value is not migrated, **set them by hand**. The files in the old `ignore_files` (such as `carpet.conf` and `pca.conf`) kept the mirror's own copy, which is what `retain_patterns` does now; `session.lock` is in `ignore_patterns` by default, so the mirror's copy is deleted;
- `sync.ignore_inexistent_target_path` is removed in favour of [`sync.missing`](#sync-configuration-file-related-to-file-synchronization); the old value is not migrated. The old `true` corresponds to `missing.target: create` (which now makes the last component only); the old `false` skipped a missing target directory, which is `missing.target: skip`, while the new default `refuse` refuses the sync.

When the plugin loads its configuration, it removes the keys it does not know from the configuration file (including the removed keys above and misspelt ones). It lists each of them with its path and value in the console and tells the game once. Before that, the original file is backed up as `config.yml.<time>-<content hash>.bak` in the same folder.

## Commands

The default command prefix is `!!mirror`.

| Command                                 | Description                                             |
|-----------------------------------------|---------------------------------------------------------|
| `!!mirror` / `!!mirror help`            | Display command help                                    |
| `!!mirror status`                       | Get the mirror server status; details go to the sender only |
| `!!mirror start`                        | Start the mirror server                                 |
| `!!mirror stop`                         | Stop the mirror server                                  |
| `!!mirror kill`                         | Terminate the mirror server                             |
| `!!mirror kill -f`                      | Force-terminate the mirror server (terminal proxies) |
| `!!mirror recover [pid]`                | Adopt an untracked mirror server (terminal proxies) |
| `!!mirror sync`                         | Synchronize files                                       |
| `!!mirror confirm`                      | Confirm a pending operation                             |
| `!!mirror reload`                       | Hot-reload the mirror configuration                     |
| `!!mirror history`                      | View synchronization history                            |
| `!!mirror input <command>`              | Send a command through the subprocess proxy             |
| `!!mirror log`                          | View subprocess console-log status                      |
| `!!mirror log enable\|disable\|<count>` | Enable, disable, or limit console-log output            |

## Configuration File

> [!TIP]
> This configuration file is long. We recommend reading the [Quick Start](./docs/quickstart_en.md) first, then using this document as a reference.

The configuration file supports hot reloading and automatic completion. When a new version adds an option, the plugin automatically fills in its default value in your old configuration file.


```yaml
"!!mirror":
    root_path: # Directory of the mirror server
    is_mcdr: # Whether the mirror server is run by MCDR
    mcsm: # MCSManager configuration
    terminal: # Configuration for starting the mirror server terminal through the command line
    sync: # Save synchronization configuration
    command:
        permission: # Command permission configuration
        action: # Command behavior configuration
    display: # Display configuration
```

### Mirror entries and inheritance

The first mirror entry is the base configuration. Later entries inherit its values and only need to contain overrides.

**Example**

Control mirror server 2 through `!!mirror2`, set its instance ID to `abc123`, and change its server name to `Mirror2`.
```yaml
"!!mirror":
    # ...
"!!mirror2":
    mcsm:
        uuid: "abc123"
    display:
        server_name: "Mirror2"
```

Alternatively, thanks to YAML, you can write it in a simpler form:
```yaml
"!!mirror":
    # ...
"!!mirror2":
    mcsm.uuid: "abc123"
    display.server_name: "Mirror2"
```

The parameters not set in `!!mirror2` automatically inherit from the first `!!mirror` entry. For example, an unset `mcsm.url` inherits `"http://127.0.0.1:23333/"` from `!!mirror`.

For a complete example, see [Multi-mirror Server Configuration File Example](#example-of-multi-mirror-server-configuration-file).

<br>

### root_path / is_mcdr: Mirror server directory and kind
```yaml
root_path: "./Mirror"
is_mcdr: true
```

**root_path** `str`
- The directory of the mirror server, relative to the MCDR root of this server, or absolute. It must not be empty.
  - The terminal proxies run `launch_command` in it, and `!!mirror recover` looks for the mirror server in it;
  - With `is_mcdr` set to `true`, it is the mirror's MCDR directory, the one that contains its `config.yml`. An empty `sync.target` then means the mirror MCDR's `working_directory` under it, and the pre-sync backup looks for the mirror's PrimeBackup in it;
    - To derive the sync target and to locate PrimeBackup, the plugin reads only the `config.yml` in it. If the mirror MCDR is started with another config file (e.g. `launch_command` is `python -m mcdreforged start --config custom.yml`), set `sync.target`; the pre-sync backup may locate the wrong PrimeBackup, so it is not supported in this case;
  - With `is_mcdr` set to `false`, it is the server's own directory, and an empty `sync.target` means this directory itself.

**is_mcdr** `bool`
- Whether the mirror server is run by MCDReforged. Defaults to `true`; set it to `false` for a plain server. With `false`, the [pre-sync backup](#syncbackup-pre-sync-backup) is not supported, and the plugin never adopts an untracked server when it loads.
- It also decides how the terminal proxies stop and kill the mirror server. For the Linux proxy, `true` makes `stop` send `!!MCDR server stop_exit` to screen, and `kill` send `!!MCDR server kill` while the port is open, or close the screen otherwise; `false` makes `stop` send Minecraft's `stop` command and `kill` perform a force kill. For the Windows proxy, `true` makes `stop` type `!!MCDR server stop_exit` into the command prompt window, while `false` types Minecraft's `stop` command; `kill` always forcefully terminates the process listening on the port; while the mirror server is still starting and the port is not open yet, it terminates every process the plugin started. For the subprocess proxy, `true` makes `stop` send `!!MCDR server stop_exit`, while `false` sends Minecraft's `stop` command; `kill` terminates the child process directly.

<br>

### mcsm: MCSManager Configuration
If you have any questions about this configuration section, please refer to the [MCSManager Documentation](https://docs.mcsmanager.com/#/zh-cn/apis/readme).
```yaml
mcsm:
    enable: false
    url: "http://127.0.0.1:23333/"
    uuid:
    remote_uuid:
    apikey:
```
After enabling MCSM, the terminal configuration will be disabled.


**enable** `bool`
- Whether to enable MCSM. You need to set this option to `true` after completing the configuration of this section.

**url** `str`
- The access address of the MCSManager panel, that is, the address for requesting the API.

**uuid** `str`
- The ID of the server instance, that is, the UID displayed by the instance.

**remote_uuid** `str`
- The ID of the remote node, that is, the GID displayed by the instance.

**apikey** `str`
- The key required to call the API interface, which can usually be viewed in the user interface.

<br>

### terminal: Configuration for starting the mirror server terminal through the command line
```yaml
terminal:
  enable: false
  launch_command: "python -m mcdreforged"
  port:
  terminal_name: "Mirror"
  proxy_type:
  console_log: false
  auto_recover: true
  java_name: '^javaw?\d*(\.exe)?$'
```
When `proxy_type` is `linux`, the plugin creates a new screen; when it is `windows`, it creates a new command prompt; and when it is `subprocess`, it starts the mirror server as a child process inside MCDR. The screen or terminal created by the Linux/Windows proxies is closed automatically after the mirror server stops.

> [!NOTE]
> If you cannot start the mirror server with this command, try the following steps. `terminal_name` and `launch_command` are the corresponding configuration values.
> 1. Execute `launch_command` under `root_path` and confirm that it starts the mirror server successfully.
> 2. Linux users should check whether `screen` is installed. Windows users should check whether the `python` command works in the terminal.
> 3. If neither suggestion resolves the problem, execute the complete command for the Linux or Windows proxy in the current MCDR server's root directory and inspect the output.
>    - Linux: `cd "{root_path}"&&screen -dmS {terminal_name}&&screen -x -S {terminal_name} -p 0 -X stuff "{launch_command}&&exit\n"`
>    - Windows: `cd /d "{root_path}"&&start cmd.exe /S /C "title {terminal_name}&&{launch_command}"`

Note: The `linux` proxy controls the mirror server through screen. With the `windows` proxy, `stop` types the stop command into the command prompt window of the process listening on the configured mirror port and `kill` forcefully terminates that process. The `subprocess` proxy controls the mirror server through the child process's standard input and output. Every proxy requires a correctly configured `port`. MCSM can still be used as an alternative control method.

> [!WARNING]
> The `stop` command under the Windows proxy is experimental; use it at your own risk.

**enable** `bool`
- Whether to enable the terminal. When MCSM is not enabled and this option is `true`, the mirror server will be started through the selected terminal proxy.

**launch_command** `str`
- The startup command that needs to be executed. If a simple startup command cannot meet your requirements, you can create a `.bat` (or `.sh`) file and write the startup command in it, then execute the file. The Linux proxy rejects a command that is too long (above roughly 700 bytes); use a script file in that case as well.

**port** `int`
- The mirror server port, required for every proxy. The plugin checks the mirror status through it; the Linux and Windows proxies also use it to control the process. Without it the terminal proxy is unavailable and the help message shows `terminal` as misconfigured.

**terminal_name** `str`
- The title of the new command prompt, the name of the new screen, or the prefix used for subprocess proxy log output. As a screen name it must not exceed 64 bytes or contain control characters.

> [!IMPORTANT]
> `!!mirror kill -f` and `!!mirror kill --force` are available for every terminal proxy. They forcefully terminate every process the plugin started and recorded (the Linux proxy then closes the screen); when the status is unknown, they also terminate untracked processes holding the configured port. The processes are listed to the command source first, and only listed processes are terminated: if a process that was not listed turns up when the kill runs (after confirmation, too), nothing is terminated and the command has to be run again to review them. If the port is held by a process whose PID cannot be read (such as a process of another user), nothing is terminated. Confirm that `port` is correct to avoid terminating other services.
>
> The plugin can only read processes the current user is allowed to inspect. When the port is held by a process of another user, the plugin may be unable to read its PID, and `kill -f` then terminates nothing.

**proxy_type** `str | null`
- The terminal proxy type, replacing the legacy `system` option. Valid values are `linux`, `windows`, and `subprocess`. When set to `null`, the plugin automatically selects `linux` or `windows` based on the current operating system. `subprocess` starts the mirror server as a child process inside MCDR and supports sending commands through `!!mirror input`.

> [!NOTE]
> When using the `subprocess` proxy to start another MCDR instance, set `advanced_console` to `false` in the mirror server MCDR's configuration file.
>
> A mirror server started by the subprocess proxy is a child process of this MCDR. `!!mirror reload`, and reloading or unloading this plugin, forcefully terminate it. An [adopted](#adopting-a-mirror-server) mirror server was not started by the plugin and keeps running.

**console_log** `bool`
- Whether to output the subprocess proxy's mirror server console logs to the MCDR console by default. This option only applies to the `subprocess` proxy.

**auto_recover** `bool`
- Whether the plugin, when it loads with no running process in its record, adopts an untracked MCDR that runs in `root_path`. Defaults to `true`. It adopts only when it finds exactly one, and the configured port is free or listened on by that MCDR and its children; it then lists the adopted MCDR process in the console (the server process joins the record at the next status check) and tells the game once. Otherwise, and with `false`, it only reports what it found; `!!mirror recover` adopts it by hand. With `is_mcdr` set to `false`, nothing is ever adopted automatically. See [Adopting a mirror server](#adopting-a-mirror-server).

**java_name** `str`
- With `is_mcdr` set to `false`, the plugin looks for an untracked server in `root_path` among the processes whose name matches this regular expression, case-insensitively. The default matches `java`, `javaw`, `java17`, `java21.exe` and the like. Change it if the Java executable goes by another name.

#### Mirror server status

The plugin judges the status of the mirror server only from **the processes in its record** (those it started or adopted) and the configured `port`. Each time a terminal proxy starts the mirror server, the plugin records the processes it started, and on every later status check it adds the processes they have started since. The record is kept in `config/mirror_mcsmcdr/<command prefix>/process.json` and survives plugin reloads.

> [!IMPORTANT]
> `launch_command` must run the mirror server in the foreground and end only when the mirror server exits. Do not let the mirror server detach from the process that started it, for example with `nohup ... &`, `setsid`, `start` or `screen -dm`. Detached processes are not in the record, and the plugin can neither judge nor control them.

The recorded processes fall into these groups:
- **MCDR**: with `is_mcdr` set to `true`, a Python process running `python -m mcdreforged`, the `mcdreforged` command or `python MCDReforged.py`;
- **Server**: among the processes MCDR started, the one listening on `port`. Before the port opens, the one matching `start_command` and `working_directory` in the mirror MCDR's configuration file is taken as the server too;
- **Child processes**: processes MCDR started while the server is not told apart from them yet; all of them are treated as the server;
- **Other processes**: everything else, such as processes started by MCDR plugins.

`!!mirror status` broadcasts the status, and sends the details to the sender only: MCDR, the server (or the child processes), the number of other processes, the port, and what the status means and what can be done.

| Status | Meaning | Available actions |
|--------|---------|-------------------|
| stopped | Every recorded process has exited, and the port is free | `start`, `sync` |
| starting | The start command was sent, or the server process is running but the port is not open, and the plugin has not seen it open | `kill`, `kill -f` |
| running | The port is held by a recorded process | `stop`, `kill`, `kill -f`; `sync` with `auto_server_restart` |
| stopping | The stop command was sent, or the server closed the port the plugin had seen it open (for example, it was stopped from the mirror's own console); waiting for the processes to exit | `kill`, `kill -f` |
| server stopped, MCDR still running | The server has exited; MCDR is idle or exiting | `start`, `stop`, `kill`, `kill -f`; `sync` with `auto_mcdr_stop` |
| status unknown | The port is held by an untracked process | `kill -f` |
| status unknown | An untracked MCDR (a Java process with `is_mcdr` set to `false`) is running in `root_path` (see below) | `recover` |

In `server stopped, MCDR still running`, `start` and `stop` do not launch another mirror server; they type a command into the console of the MCDR that is still running: `start` types `!!MCDR server start`, which starts the server in that MCDR, and `stop` types `!!MCDR server exit`, which makes MCDR exit. An MCDR that is exiting refuses to start the server; the status then becomes `stopped`.

Before the plugin types a command into the mirror's console (`start`, `stop`, and `kill` on Linux), it checks once more that MCDR (the server, with `is_mcdr` set to `false`) is still running, so that a terminal left behind by a failed launch does not run the command. If the status has changed in the meantime, the reply tells the status as it is now.

One of these anomalies may follow the status:
- **Console lost**: recorded processes are still running, but the plugin can no longer send them commands (the screen or command prompt window is closed, or the subprocess proxy lost its child process after a plugin reload). Only `kill -f` is available;
- **MCDR process not found**: `is_mcdr` is `true` and the server is running, but there is no MCDR process in the record. `kill` and `kill -f` are available;
- **Detached**: the launch command has ended, but the screen or terminal is left. `kill` and `kill -f` are available.

When the server process is running but the port never opens, the status stays at `starting`. Check that `port` matches the mirror server's `server-port`. A server whose port the plugin has never seen open, such as one adopted after it closed the port, may also be exiting; the details say so.

> [!WARNING]
> A mirror server this plugin did not start (started by hand, or by an older version of the plugin) is not in the record:
> - While its port is held, the status is `status unknown`, and only `!!mirror kill -f` can end it;
> - While its port is free (the mirror server is starting or stopping, or the server has stopped inside MCDR), the usual status check does not see it. So once `!!mirror status`, `start` or `sync` finds the status `stopped`, the plugin looks among all processes of the machine for an MCDR whose working directory is `root_path` (a Java process with `is_mcdr` set to `false`). If there is one, the status is `status unknown`, and `start` and `sync` are refused. Only processes of the plugin's own user whose details can be read are looked at.
>
> Such a mirror server can be adopted with `!!mirror recover`; see below.

#### Adopting a mirror server

`!!mirror recover` looks among all processes of the machine for an MCDR whose working directory is `root_path` and that is not in the record, and writes it and the processes it started into the record. From then on the plugin judges its status, and runs `stop`, `kill` and syncs on it, as it does for a mirror server it started itself.

With `is_mcdr` set to `false`, the plugin looks for a Java process whose working directory is `root_path` instead, with a name as [`java_name`](#terminal-configuration-for-starting-the-mirror-server-terminal-through-the-command-line) gives. A process that only listens on the configured port, with another working directory, is never adopted: with a wrong port, it may be another server. Such a mirror server is not adopted when the plugin loads.

- With exactly one found, the plugin lists it and asks for `!!mirror confirm`; once confirmed, only that listed process is adopted, and nothing is if it has exited. With several found, it lists them, and `!!mirror recover <pid>` picks one. The PID must be one of those listed; no confirmation is asked when a PID is given;
- Nothing is adopted while the configured port is held by a process outside this MCDR and its children;
- Nothing is adopted while the record still holds running processes, or while a sync is in progress;
- The plugin finds the console the MCDR runs in, and types commands into it from then on:
  - `windows` proxy: the console window of the MCDR;
  - `linux` proxy: the screen session and window of the MCDR, which may be the user's own session with several windows;
  - `subprocess` proxy, or an MCDR outside any console or screen: there is no console; after adopting, the status carries `Console lost`, and only `kill -f` can end it.
- The console does not belong to the plugin: `kill` and `kill -f` end only the MCDR and its children, and leave the user's command prompt window or screen session open.

The plugin also looks once when it loads, and adopts or only reports what it finds according to [`auto_recover`](#terminal-configuration-for-starting-the-mirror-server-terminal-through-the-command-line).

`recover` requires permission level 3 by default; change it with `command.permission.recover`. It is not offered with MCSManager.

<br>

### sync: Configuration file related to file synchronization
```yaml
sync:
    world:
        - "world"
    extra_patterns: []
    source: ""
    target: []
    missing:
        source_world: refuse
        target: refuse
        target_world: create
        extra_pattern: skip
    concurrency: 4
    ignore_patterns:
        - "session.lock"
    retain_patterns: []
    backup:
        enable: false
        timeout: 600
        confirm_on_warning: true
```

In `sync`, `./` refers to the `MCDReforged` root directory where the server is located.

```
mcdr_root (./)
 ├─ config
 ├─ logs
 ├─ plugins
 ├─ server (./server)
 |   └─ world
 └─ Mirror
     └─ server (./Mirror/server)
         └─ world
```

Each entry of `world`, `extra_patterns`, `ignore_patterns` and `retain_patterns` is a [gitignore](https://git-scm.com/docs/gitignore) pattern, written as in the same-named (or corresponding) setting of the mirror's PrimeBackup. Patterns are case-sensitive, also on Windows. A pattern starting with `!` excludes; it selects nothing by itself.

**world** `list`
- The worlds to synchronize. As PrimeBackup's `backup.targets`, the patterns are matched against the names of the source server directory's top-level entries only. Plain directory names such as `world` and `world_nether` do; `world*`, or an exclusion such as `!world_the_end`, work as well.
- Do not end a pattern with `/`: only the name is matched, so `world/` selects no directory.
- Only directories are selected. A top-level file a pattern matches is not synchronized, and the console says so; synchronize files through `extra_patterns`.
- After a sync, a world in the target is what it is in the source: files and directories only the target world has are deleted (except those `retain_patterns` matches).
- A pattern that selects no directory is handled by `missing.source_world`.

**extra_patterns** `list`
- Files or directories to synchronize outside the worlds, such as `config/carpet.conf` or `config/`. Paths are relative to the server directory, and a pattern is matched at any depth; matches inside a world do not count, as the worlds are up to `world`.
- A selected directory is synchronized as a whole, like a world, and what it holds is not matched again; a selected file is overwritten when its content differs. Paths only the target has stay as they are. Missing parent directories in the target are created.
- When a path is a file in the source server and a directory in a target (or the other way round), the sync is refused before the mirror is stopped.
- When empty, nothing outside the worlds is walked.
- A pattern that matches nothing is handled by `missing.extra_pattern`.

> [!WARNING]
> Do not select `server.properties` with `extra_patterns`: the mirror's port and other settings would be overwritten by those of the main server.

**source** `str`
- The source server directory. When empty, the [working directory](https://mcdreforged.readthedocs.io/en/latest/configuration.html#working-directory) of this MCDR (`working_directory`, `server` by default; read at every sync, so it follows a reload of this MCDR's config) is used; usually there is no need to set it. Files are synchronized from `source/world`  to `target/world`

**target** `str, list`
- The target server directory, you can only write a string if there is only one directory, and a list is needed for multiple directories. A copy of the source directory files will be synchronized for each target directory.
- When empty, it is derived from [`root_path`](#root_path--is_mcdr-mirror-server-directory-and-kind): with `is_mcdr` set to `true`, the mirror MCDR's `working_directory` under `root_path` (read from the mirror's `config.yml` at every sync; if it cannot be read, the sync is refused); with `is_mcdr` set to `false`, `root_path` itself. With the default config it is `./Mirror/server`.

**missing**
- What to do about what the sync config names but does not exist. All of it is judged before the mirror is stopped:
  - `refuse`: the sync is refused and recorded as failed;
  - `skip`: the entry is left out and the rest is synchronized. The game is told only how many were skipped; their paths go to the console.
- A sync that would skip everything is refused instead of being reported as identical.

| Key | When | Values | Default |
|---|---|---|---|
| `source_world` | A `world` pattern selects no directory in the source server | `refuse`; `skip`: the target's world of that name stays as it is | `refuse` |
| `target` | A target directory does not exist | `refuse`; `skip`; `create`: makes the last component only, and refuses when its parent does not exist either | `refuse` |
| `target_world` | A target directory exists but lacks a world to sync | `create`; `refuse` | `create` |
| `extra_pattern` | An `extra_patterns` pattern matches nothing | `skip`; `refuse` | `skip` |

- A target path that is a file always refuses the sync.
- When the source server directory, a selected world or directory, or a directory `extra_patterns` has to walk cannot be read (e.g. no permission), the sync is refused before the mirror is stopped; the paths and reasons go to the console. Only the top level of the selected worlds and directories is checked; a deeper directory that cannot be read makes the sync fail after the mirror is stopped, and the mirror may hold an incomplete copy.
- Right before each entry is copied, the plugin checks again that it still exists in the source server. If it disappeared after the mirror was stopped, the sync stops and is recorded as failed, and the target's copy is not emptied; what was copied already stays, so the mirror may hold an incomplete copy.

**concurrency** `int`
- The number of threads performing hash calculations during synchronization.

**ignore_patterns** `list`
- Paths that are not synchronized and are deleted in the target, as PrimeBackup's `backup.ignore_patterns`. Paths are relative to the server directory; the patterns apply inside the synchronized worlds and what `extra_patterns` selects. `session.lock` by default.

**retain_patterns** `list`
- Paths that are not synchronized, the target's own copy kept as it is, as PrimeBackup's `backup.retain_patterns`. Meant for the mirror's own settings files, such as `"carpet.conf"` and `"pca.conf"` of the `carpet` and `plus-carpet-addition(PCA)` mods (a pattern without `/` matches at any depth).
- A path matched by both `ignore_patterns` and `retain_patterns` is retained.

**backup** pre-sync backup, see [sync.backup](#syncbackup-pre-sync-backup) below

<br>

### sync.backup: Pre-sync backup

```yaml
sync:
    backup:
        enable: false
        timeout: 600
        confirm_on_warning: true
```

A sync overwrites the mirror world and deletes the files that only exist in the mirror; there is no undo. With `backup.enable: true`, every `!!mirror sync` first makes a backup with the **mirror's own** [PrimeBackup](https://github.com/TISUnion/PrimeBackup), through PrimeBackup's command line tool: its plugin file, its storage and its settings, exactly as the mirror admin configured them.

Two rules apply:
- **No backup, no sync.** If the backup cannot be made or fails, the sync is refused and nothing is copied. To sync without a backup, set `enable` to `false` and run `!!mirror reload`.
- **The backup is as complete as the mirror's PrimeBackup settings make it.** They are expected to be equivalent to the sync settings. Where they are not, the plugin warns and by default asks for confirmation (see `confirm_on_warning`), then backs up with the settings as they are. Whoever confirms accepts that part of what the sync overwrites is not in the backup.

**enable** `bool`
- Whether every sync is preceded by a backup. Off by default; while it is `false` nothing of the mirror's PrimeBackup is read and syncing works as without this feature.
- The mirror's PrimeBackup is looked for in [`root_path`](#root_path--is_mcdr-mirror-server-directory-and-kind). Paths read from the mirror's files (`plugin_directories`, `working_directory`, PrimeBackup's `storage_root` and `source_root`) are relative to `root_path`, as they are for the mirror's MCDR.
- With `is_mcdr` set to `false` there is no pre-sync backup: a plain server has no MCDR, so no PrimeBackup of its own. Turning `enable` on then refuses every sync and warns in the console on load; turn it off.

**timeout** `int`
- Seconds a backup may take. A backup that takes longer is killed and the sync is refused.

**confirm_on_warning** `bool`
- Whether a sync has to be confirmed when one of the warnings below applies, even if `command.action.sync.require_confirm` is `false`. Defaults to `true`. With `false` the warning is still shown, and whether the sync is confirmed follows `require_confirm` alone.

**Prerequisites**
- The mirror runs under MCDR, with PrimeBackup `>=1.13.0` in one of its `plugin_directories`. Exactly one PrimeBackup must be there (packed `.pyz`/`.mcdr`, directory or linked directory plugin; `.disabled` ones do not count).
- The mirror's PrimeBackup has been loaded at least once, so that its config `config/prime_backup/config.json` and its database `prime_backup.db` in `storage_root` exist.
- The command line tool is started with the Python interpreter that runs this MCDR, so PrimeBackup's Python dependencies (see its `requirements.txt`) must be installed for it.

**Warnings**

When `!!mirror sync` is entered, the mirror's PrimeBackup config is compared with the sync config. In game only the number of differences is shown; the details contain paths and are written to the MCDR console.

| PrimeBackup setting | Warning when |
|---|---|
| `backup.source_root`, or the mirror's `working_directory` when `backup.source_root_use_mcdr_working_directory` is `true` | It is not an existing `sync.target`, or there are further existing `sync.target` directories besides it |
| `backup.targets` | It does not match the top-level name of a world `sync.world` selects or of a path `sync.extra_patterns` selects |
| `backup.ignore_patterns`, `backup.ignored_files` | They contain a pattern that is in neither `sync.ignore_patterns` nor `sync.retain_patterns` |
| `backup.retain_patterns` | It contains a pattern that is in neither `sync.ignore_patterns` nor `sync.retain_patterns` |
| `backup.reuse_stat_unchanged_file` | It is `true`: files with unchanged size and time are not read |
| `backup.creation_skip_missing_file` | It is `true`: files that disappear during the backup are skipped |
| `storage_root` | It is inside a synchronized path: the sync deletes the files only the mirror has, the backup among them |

With the defaults of both plugins there is no warning. Patterns are compared as strings: patterns spelt differently that match the same (such as `session.lock` and `/session.lock`) are warned about as well.

**What a sync does with backup enabled**
1. When `!!mirror sync` is entered, the mirror's PrimeBackup is located: plugin, config and database. If one is missing, the sync is refused at once. Then the warnings above are checked; if there are any and `confirm_on_warning` is `true`, the sync has to be confirmed.
2. The mirror server must be stopped, and the mirror's MCDR must have exited too (`auto_server_restart` and `auto_mcdr_stop` may stop it and wait for MCDR to exit).
3. PrimeBackup's `make` makes the backup with the mirror's settings, with comment `MirrorMcsmcdR pre-sync by <operator>`.
4. The backup counts if `make` exits with code 0 and reports a backup id. Otherwise the sync is refused, the last lines of PrimeBackup's output are written to the MCDR console, and the sync is recorded as failed.
5. The backup id is broadcast and the main world is saved. With `ensure_server_closed: true`, the mirror must still be stopped right before copying; otherwise the sync is refused, because the backup would be stale.
6. `!!mirror history` shows the backup id of each sync, also of a sync that failed after its backup.

The backup and its warnings cover what the sync overwrites: the existing target directories, and the worlds and paths synchronized into them. A target directory that `missing.target: create` makes needs no backup. If none of those targets holds anything to be synchronized yet, there is nothing to lose: the backup is skipped and the sync runs.

Messages in game never contain paths. When a sync is refused, the paths involved are in the MCDR console.

When the plugin loads and on `!!mirror reload`, the mirror's PrimeBackup is located, `--version` of the command line tool is run and the warnings are checked; the results are written to the console. This is diagnostics only: it blocks nothing, and every sync checks again.

**Restoring**
- Pre-sync backups are regular backups of the mirror's PrimeBackup, without tags, with creator `prime_backup:cli`; only the comment identifies them.
- To restore one, use the mirror's PrimeBackup with the id from the sync message or `!!mirror history`: `!!pb back <id>` on the mirror. It restores into `restore.destination_root` when that is configured, otherwise into its source root.
- Old pre-sync backups are pruned by the mirror's PrimeBackup prune settings; this plugin deletes nothing.

**Known limits**
- With `ensure_server_closed: false` the plugin does not check whether the mirror is running, and the command line tool and the mirror's PrimeBackup plugin can work on the same storage at the same time. A mirror this plugin did not start may be taken for stopped, with the same result (see [Mirror server status](#mirror-server-status)).
- The warnings are checked when the command is entered. A config changed between that and the confirmation is not warned about again.
- A sync whose content is identical still creates a backup (deduplicated by PrimeBackup, but one more entry in its list).
- About 1 s more per sync, and about 1 s per backup-enabled mirror when the plugin loads or reloads (`--version`).
- The plugin trusts what `make` reported; it does not verify that the backup can be restored (the command line tool has no verify command).
- `--version` may not import every dependency of PrimeBackup; such a gap shows at the first `make`, which then refuses the sync.
- A `make` killed by the timeout may leave orphan files in PrimeBackup's storage; they are not cleaned up.

<br>

### command: Command Configuration

```yaml
command:
    permission: # Command permission configuration
    action: # Command behavior configuration
```

<br>

### permission: Command Permission Configuration
```yaml
permission:
    status: 0
    start: 0
    stop: 2
    kill: 3
    sync: 2
    confirm: 0
    log: "console"
    input: "console"
    recover: 3
```
`int`
- The minimum MCDR permission level required to execute each command, set to `console` for console available only.

<br>

### action: Command Behavior Configuration
```yaml
action:
    status:
        require_confirm: false
    start:
        require_confirm: false
        timeout: 120
    stop:
        require_confirm: true
        timeout: 60
    check_status_interval: 5
    kill:
        require_confirm: true
    sync:
        ensure_server_closed: true
        auto_server_restart: false
        auto_mcdr_stop: false
        save_world: # Save world configuration
        require_confirm: true
    history:
        require_confirm: false
        max_history_count: 5
    confirm:
        timeout: 30
        cancel_anymsg: true
```

### General Configuration

**require_confirm** `bool`
- When this option is `true`, the command `!!mirror confirm` needs to be entered to confirm the operation after executing the command
- `start`, `stop`, `kill` and `kill -f` check the status of the mirror server before they ask for confirmation. If the status does not allow the command, the reply says why at once, without asking for confirmation. After confirmation the status is checked again before the command runs

### start / stop Configuration
**timeout** `int`
- How many seconds the mirror server may take to start (stop) after the command was sent. Meanwhile its status is shown as `starting` (`stopping`); after that the plugin judges the status only by what it observes, such as the port and the process. Increase `start.timeout` if the mirror server starts slowly
- The config cannot be reloaded while the mirror server is `starting`. Wait for it, or run `!!mirror kill` first
- When MCSM is enabled the status comes from MCSM, and this option does not affect it. The plugin broadcasts `has started` as soon as the panel reports the instance running, which may be while the server is still loading its world
- After an automatic stop for a sync (`auto_server_restart`, `auto_mcdr_stop`), the plugin waits up to `stop.timeout` seconds; past that it outputs `automatic shutdown failed` with the current status of the mirror server and tells the sender what it is still waiting for
- After every start (`!!mirror start`, the restart after a sync, and the start in `server stopped, MCDR still running`), the plugin waits in the background for the mirror server to be `running` and then broadcasts `has started`. If it becomes `stopped` or `status unknown` or shows an anomaly first, or is still not `running` after `start.timeout` seconds, it broadcasts `start not completed` with the current status and tells the sender the details. With MCSManager, `stopped` and `status unknown` (a busy instance) reported by the panel may be temporary, so the plugin keeps waiting until the timeout; after an automatic stop for a sync, it likewise keeps waiting through a `status unknown` from the panel

### check_status_interval
**check_status_interval** `int`
- The longest gap in seconds between two full checks of the status while waiting for it to change (e.g. for the mirror server to stop before a sync, or to run after a start). As soon as a recorded process exits, or starts or stops listening on the configured port (looked at once a second), the plugin checks at once, without waiting for the interval; a newly started server process is only seen at the next full check. With MCSM, it is how often MCSM is asked

### sync Configuration
While a sync is in progress (from the automatic stop, the wait, the backup and the copy to the restart afterwards), `!!mirror start` is refused, so that the mirror server cannot start during the copy. `stop`, `kill` and `kill -f` are not affected.

**ensure_server_closed** `bool`
- When this option is `true`, synchronization will check whether the mirror server has stopped. The mirror server must be `stopped`. `server stopped, MCDR still running` is refused unless `auto_mcdr_stop` is on, until MCDR exits, is told to exit with `!!mirror stop`, or is ended with `!!mirror kill`. When this option is `false`, synchronization will be carried out directly regardless of whether the mirror server has stopped or not.

**auto_server_restart** `bool`
- This option only takes effect when `ensure_server_closed` is `true`. When this option is `true`, if the mirror server is `running` during synchronization, it will attempt to automatically stop the mirror server, wait for MCDR to exit as well, perform synchronization, and automatically restart the mirror server after the synchronization is completed. For how long it waits, see `stop.timeout`.

**auto_mcdr_stop** `bool`
- This option only takes effect when `ensure_server_closed` is `true`. When this option is `true`, if the mirror server is `server stopped, MCDR still running` during synchronization, MCDR is made to exit before the synchronization. Nothing is restarted afterwards, since the server was not running before. For how long it waits, see `stop.timeout`.

**save_world** Save world configuration *Generally no need to change*
```yaml
save_world:
    turn_off_auto_save: true
    commands:
        save_all_worlds: "save-all flush"
        auto_save_off: "save-off"
        auto_save_on: "save-on"
    saved_world_regex: "^Saved the game$"
    save_world_max_wait_sec: 60
```
**turn_off_auto_save** `bool`
- Turn off auto save when saving the world

**commands** Related commands
- **save_all_worlds** `str`
  + Command to save the world
- **auto_save_off** `str`
  + Command to turn off auto save
- **auto_save_on** `str`
  + Command to turn on auto save

**saved_world_regex** `str`
- Regular expression to match the server "world saved" log

**save_world_max_wait_sec** `int`
- The maximum waiting time (seconds) for saving the world. After the timeout it will skip saving the world and perform synchronization

### history Configuration

**max_history_count** `int`
- The maximum number of synchronization history records to save. Set it to `-1` to remove the limit, or `0` to disable synchronization history. The default is `5`.

### confirm Configuration
Players can only confirm the commands they have executed

**timeout** `int`
- Command that needs confirmation will be canceled after the number of seconds. If the player has not taken any action after executing a command, the command will be canceled automatically.

**cancel_anymsg** `bool`
- If the player sends a message other than the `confirm` command after executing a command, the command operation will be canceled automatically. In addition, if the player executes another command corresponding to the mirror server after executing a command, the previously executed command will be canceled too.

<br>

### display: Display Configuration
```yaml
display:
    server_name: "Mirror"
    protected_process_info: []
```
**server_name** `str`
- The name of the "mirror server", used to distinguish between different mirror servers in the display

**protected_process_info** `list`
- Process details left out of in-game messages: `name` (process name) and/or `pid`, empty by default. It applies to the processes `kill -f` lists and those `status` mentions. With both, only counts are shown. The console always shows the name, PID and command line; command lines and paths never appear in in-game messages.

<br>

### Example of Multi-mirror Server Configuration File

```yaml
"!!mirror":
    root_path: "./Mirror"
    is_mcdr: true
    mcsm:
        enable: true
        url: "http://127.0.0.1:23333/"
        uuid: "71154??????????0a1a2f4dd90695609"
        remote_uuid: "6e927??????????999f0e66bc404071b"
        apikey: "b8f???????????????????????????ade"
    terminal:
        enable: false
        launch_command: "python -m mcdreforged"
        port: null
        terminal_name: "Mirror"
        proxy_type: null
        console_log: false
        auto_recover: true
        java_name: '^javaw?\d*(\.exe)?$'
    sync:
        world:
            - "world"
        extra_patterns: []
        source: ""
        target: []
        missing:
            source_world: refuse
            target: refuse
            target_world: create
            extra_pattern: skip
        concurrency: 4
        ignore_patterns:
            - "session.lock"
        retain_patterns: []
    command:
        permission:
            status: 0
            start: 0
            stop: 2
            kill: 3
            sync: 2
            confirm: 0
        action:
            status:
                require_confirm: false
            start:
                require_confirm: false
            stop:
                require_confirm: true
            kill:
                require_confirm: true
            sync:
                ensure_server_closed: true
                auto_server_restart: true
                auto_mcdr_stop: false
                save_world:
                    turn_off_auto_save: true
                    commands:
                        save_all_worlds: "save-all flush"
                        auto_save_off: "save-off"
                        auto_save_on: "save-on"
                    saved_world_regex: "^Saved the game$"
                    save_world_max_wait_sec: 60
                require_confirm: true
            confirm:
                timeout: 30
                cancel_anymsg: true
    display:
        server_name: "Mirror"
"!!mirror2":
    root_path: "./Mirror2"
    mcsm:
        uuid: "83011??????????49c1133fc08a41b80"
    display:
        server_name: "Mirror2"
"!!mirror3":
    root_path: "./Mirror3"
    mcsm:
        enable: false
    terminal:
        enable: true
        port: 30002
        terminal_name: "Mirror3"
```

Later entries inherit `root_path` from the first one, so every mirror server needs its own `root_path`.

## Acknowledgements

- Hash comparison idea / [better_backup](https://github.com/z0z0r4/better_backup) 
- Configuration file permission configuration idea / [PrimeBackup](https://github.com/TISUnion/PrimeBackup) 
- Save world idea / [QuickBackupM](https://github.com/TISUnion/QuickBackupM) 

## ToDo

- [x] Command execution confirmation
- [ ] Command execution delay
- [ ] Prohibit synchronization `!!mirror sync enable/disable reason`
- [x] language file
- [ ] Command disable
- [x] Start server through command line without MCSM
- [x] Linux/Windows execute `kill` command through terminal
- [x] Display history synchronization records
