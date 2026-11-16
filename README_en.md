# MirrorMcsmcdR

[![MCDR](https://img.shields.io/badge/MCDR-%E2%89%A52.6.0-blue)](https://github.com/Fallen-Breath/MCDReforged) [![License](https://img.shields.io/github/license/LazyAlienServer/MirrorMcsmcdR)](./LICENSE) [![Downloads](https://img.shields.io/github/downloads/LazyAlienServer/MirrorMcsmcdR/total)](https://github.com/LazyAlienServer/MirrorMcsmcdR/releases)

[中文](./README.md) · English

> The most comprehensive [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) mirror server control plugin! Control mirror servers through multiple methods and synchronize additions and deletions based on hashes.

## Features

- **Multiple control and lifecycle methods**:
  - Control mirror servers through [MCSManager](https://github.com/MCSManager/MCSManager) (`MCSM-v9.9.0` `MCSM-v10.2.1+`)
  - Start and stop mirror servers directly through terminal proxies (`Linux` `Windows`), with the new terminal independent from the parent MCDR process
    - Linux uses `screen` to control the mirror server
    - Windows uses a new command prompt to control the mirror server
  - Start mirror servers as child processes inside MCDR through `subprocess`, controlled through standard input and output
  - Send commands through `!!mirror execute <command>`
  - Combine multiple control methods, for example:
    - Start and stop through MCDR, then force-terminate through Linux when the mirror process fails
- **Comprehensive control features**: manage multiple mirror servers, inspect status, start, stop, force-terminate, and synchronize
- **Hash-based file synchronization**: synchronize only files that differ from the source server, improving speed and reducing disk I/O
- **Pre-sync backup**: optionally back up the mirror world with the mirror's own PrimeBackup before every sync; without a successful backup, nothing is synced
- **Highly customizable configuration**: use YAML and write only changed values when configuring multiple mirror servers

> [!NOTE]
> This plugin does not provide server creation or management functionality. Please use it after creating the mirror server and its MCSManager instance. It also does not provide successful start/stop notifications; consider using a companion plugin such as vchat.

## Dependencies

| Dependency           | Description                                                                             |
|----------------------|-----------------------------------------------------------------------------------------|
| Python               | `>=3.10`                                                                                |
| Python package       | `xxhash>=3`                                                                             |
| Linux terminal proxy | [`screen`](https://www.gnu.org/software/screen/) when `proxy_type` is `linux` or `null` |
| PrimeBackup          | `>=1.13.0` in the mirror's MCDR, only with [pre-sync backup](#syncbackup-pre-sync-backup) enabled |

## Commands

The default command prefix is `!!mirror`.

| Command                                 | Description                                             |
|-----------------------------------------|---------------------------------------------------------|
| `!!mirror` / `!!mirror help`            | Display command help                                    |
| `!!mirror status`                       | Get the mirror server status                            |
| `!!mirror start`                        | Start the mirror server                                 |
| `!!mirror stop`                         | Stop the mirror server                                  |
| `!!mirror kill`                         | Terminate the mirror server                             |
| `!!mirror kill -f`                      | Force-terminate the mirror server (Linux terminal only) |
| `!!mirror sync`                         | Synchronize files                                       |
| `!!mirror confirm`                      | Confirm a pending operation                             |
| `!!mirror reload`                       | Hot-reload the mirror configuration                     |
| `!!mirror history`                      | View synchronization history                            |
| `!!mirror execute <command>`            | Send a command through the subprocess proxy             |
| `!!mirror log`                          | View subprocess console-log status                      |
| `!!mirror log enable\|disable\|<count>` | Enable, disable, or limit console-log output            |

## Configuration File

> [!TIP]
> This configuration file is long. We recommend reading the [Quick Start](./docs/quickstart_en.md) first, then using this document as a reference.

The configuration file supports hot reloading and automatic completion. When a new version adds an option, the plugin automatically fills in its default value in your old configuration file.


```yaml
"!!mirror":
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
  launch_path: "./Mirror"
  launch_command: "python -m mcdreforged"
  port:
  terminal_name: "Mirror"
  regex_strict: false
  is_mcdr: true
  proxy_type:
  console_log: false
```
When `proxy_type` is `linux`, the plugin creates a new screen; when it is `windows`, it creates a new command prompt; and when it is `subprocess`, it starts the mirror server as a child process inside MCDR. The screen or terminal created by the Linux/Windows proxies is closed automatically after the mirror server stops.

> [!NOTE]
> If you cannot start the mirror server with this command, try the following steps. `terminal_name` and `launch_command` are the corresponding configuration values.
> 1. Execute `launch_command` under `launch_path` and confirm that it starts the mirror server successfully.
> 2. Linux users should check whether `screen` is installed. Windows users should check whether the `python` command works in the terminal.
> 3. If neither suggestion resolves the problem, execute the complete command for the Linux or Windows proxy in the current MCDR server's root directory and inspect the output.
>    - Linux: `cd "{launch_path}"&&screen -dmS {terminal_name}&&screen -x -S {terminal_name} -p 0 -X stuff "{launch_command}&&exit\n"`
>    - Windows: `cd /d "{launch_path}"&&start cmd.exe /S /C "title {terminal_name}&&{launch_command}"`

Note: The `linux` proxy controls the mirror server through screen. With the `windows` proxy, `stop` types the stop command into the command prompt window of the process listening on the configured mirror port and `kill` forcefully terminates that process with `taskkill`. The `subprocess` proxy controls the mirror server through the child process's standard input and output. Every proxy requires a correctly configured `port`. MCSM can still be used as an alternative control method.

> [!WARNING]
> The `stop` command under the Windows proxy is experimental; use it at your own risk.

**enable** `bool`
- Whether to enable the terminal. When MCSM is not enabled and this option is `true`, the mirror server will be started through the selected terminal proxy.

**launch_path** `str`
- The path where the startup command is executed, usually the directory where the mirror server is located.

**launch_command** `str`
- The startup command that needs to be executed. If a simple startup command cannot meet your requirements, you can create a `.bat` (or `.sh`) file and write the startup command in it, then execute the file. The Linux proxy rejects a command that is too long (above roughly 700 bytes); use a script file in that case as well.

**port** `int`
- The mirror server port, required for every proxy. The plugin checks the mirror status through it; the Linux and Windows proxies also use it to control the process. Without it the terminal proxy is unavailable and the help message shows `terminal` as misconfigured.

**terminal_name** `str`
- The title of the new command prompt, the name of the new screen, or the prefix used for subprocess proxy log output. As a screen name it must not exceed 64 bytes or contain control characters.

**regex_strict** `bool`
- Whether the Linux or Windows proxies should continue to verify that the process name starts with `java` (such as `java`, `java.exe` or `javaw.exe`) after finding the configured port. Generally, there is no need to enable it.

**is_mcdr** `bool`
- Whether the mirror server is started by MCDReforged. Defaults to `true`. For the Linux proxy, `true` makes `stop` and `kill` send MCDR commands to screen; `false` makes `stop` send Minecraft's `stop` command and `kill` perform a force kill. For the Windows proxy, `true` makes `stop` type `!!MCDR server stop_exit` into the command prompt window, while `false` types Minecraft's `stop` command; `kill` always terminates the process listening on the port with `taskkill`; while the mirror server is still starting and the port is not open yet, it terminates the command prompt window the server was started in together with everything running in it. For the subprocess proxy, `true` makes `stop` send `!!MCDR server stop_exit`, while `false` sends Minecraft's `stop` command; `kill` terminates the child process directly.

> [!IMPORTANT]
> `!!mirror kill -f` and `!!mirror kill --force` are only available for the Linux proxy or Linux/Windows+MCDR. The Linux proxy kills every process inside the screen session (including anything you started in that screen by hand) and every process listening on the configured port, then closes the screen; confirm that `port` is correct before using them.
>
> The Linux and Windows proxies only recognize processes the current user is allowed to inspect. When the mirror server is started by another user, the port status is still detected, but `kill` may be unable to terminate it.

**proxy_type** `str | null`
- The terminal proxy type, replacing the legacy `system` option. Valid values are `linux`, `windows`, and `subprocess`. When set to `null`, the plugin automatically selects `linux` or `windows` based on the current operating system. `subprocess` starts the mirror server as a child process inside MCDR and supports sending commands through `!!mirror execute`.

> [!NOTE]
> When using the `subprocess` proxy to start another MCDR instance, set `advanced_console` to `false` in the mirror server MCDR's configuration file.

**console_log** `bool`
- Whether to output the subprocess proxy's mirror server console logs to the MCDR console by default. This option only applies to the `subprocess` proxy.

<br>

### sync: Configuration file related to file synchronization
```yaml
sync:
    world:
        - "world"
    source: "./server"
    target:
        - "./Mirror/server"
    ignore_inexistent_target_path: false
    concurrency: 4
    ignore_files:
        - "session.lock"
    backup:
        enable: false
        mcdr_path: ""
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

**world** `list`
- The directory that needs to be synchronized, it needs to be added when there are multiple world files in the archive.

**source** `str`
- The source server directory, which should usually be the [working directory](https://mcdreforged.readthedocs.io/en/latest/configuration.html#working-directory) of MCDR, that is, the default `server` directory. Files are synchronized from `source/world`  to `target/world`

**target** `str, list`
- The target server directory, you can only write a string if there is only one directory, and a list is needed for multiple directories. A copy of the source directory files will be synchronized for each target directory. By default, the MCDR working directory of the mirror server is located in the `Mirror` directory under the current MCDR root directory.

**ignore_inexistent_target_path** `bool`
- If a target server directory does not exist, it will be skipped when set to `false`. When set to `true`, the directory will be created and synchronization will continue.

**concurrency** `int`
- The number of threads performing hash calculations during synchronization.

**ignore_files** `list`
- Files that are not synchronized, if you use the `carpet` mod and the `plus-carpet-addition(PCA)` mod, it is recommended to add `"carpet.conf"` `"pca.conf"`

**backup** pre-sync backup, see [sync.backup](#syncbackup-pre-sync-backup) below

<br>

### sync.backup: Pre-sync backup

```yaml
sync:
    backup:
        enable: false
        mcdr_path: ""
        timeout: 600
        confirm_on_warning: true
```

A sync overwrites the mirror world and deletes the files that only exist in the mirror; there is no undo. With `backup.enable: true`, every `!!mirror sync` first makes a backup with the **mirror's own** [PrimeBackup](https://github.com/TISUnion/PrimeBackup), through PrimeBackup's command line tool: its plugin file, its storage and its settings, exactly as the mirror admin configured them.

Two rules apply:
- **No backup, no sync.** If the backup cannot be made or fails, the sync is refused and nothing is copied. To sync without a backup, set `enable` to `false` and run `!!mirror reload`.
- **The backup is as complete as the mirror's PrimeBackup settings make it.** They are expected to be equivalent to the sync settings. Where they are not, the plugin warns and asks for confirmation, then backs up with the settings as they are. Whoever confirms accepts that part of what the sync overwrites is not in the backup.

**enable** `bool`
- Whether every sync is preceded by a backup. Off by default; while it is `false` nothing of the mirror is read and syncing works as without this feature.

**mcdr_path** `str`
- Directory of the mirror's MCDR, the one that contains its `config.yml`. Like `sync.target`, it is relative to the MCDR root of this server. When empty, `terminal.launch_path` is used if `terminal.enable` is `true`; otherwise it must be set.
- Paths read from the mirror's files (`plugin_directories`, `working_directory`, PrimeBackup's `storage_root` and `source_root`) are relative to `mcdr_path`, as they are for the mirror's MCDR.

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
| `backup.source_root`, or the mirror's `working_directory` when `backup.source_root_use_mcdr_working_directory` is `true` | It is not a `sync.target`, or there are further `sync.target` directories besides it |
| `backup.targets` | A `sync.world` entry is not matched by it |
| `backup.ignore_patterns`, `backup.ignored_files` | They contain a pattern that is not in `sync.ignore_files` |
| `backup.retain_patterns` | It is not empty |
| `backup.reuse_stat_unchanged_file` | It is `true`: files with unchanged size and time are not read |
| `backup.creation_skip_missing_file` | It is `true`: files that disappear during the backup are skipped |
| `storage_root` | It is inside a synchronized world: the sync deletes the files only the mirror has, the backup among them |

With the defaults of both plugins there is no warning.

**What a sync does with backup enabled**
1. When `!!mirror sync` is entered, the mirror's PrimeBackup is located: plugin, config and database. If one is missing, the sync is refused at once. Then the warnings above are checked, and if there are any, the sync has to be confirmed.
2. The mirror server must be stopped, as before (`auto_server_restart` may stop it).
3. PrimeBackup's `make` makes the backup with the mirror's settings, with comment `MirrorMcsmcdR pre-sync by <operator>`.
4. The backup counts if `make` exits with code 0 and reports a backup id. Otherwise the sync is refused, the last lines of PrimeBackup's output are written to the MCDR console, and the sync is recorded as failed.
5. The backup id is broadcast and the main world is saved. With `ensure_server_closed: true`, the mirror must still be stopped right before copying; otherwise the sync is refused, because the backup would be stale.
6. `!!mirror history` shows the backup id of each sync, also of a sync that failed after its backup.

If no target holds any of the worlds yet, there is nothing to lose: the backup is skipped and the sync runs.

Messages in game never contain paths. When a sync is refused, the paths involved are in the MCDR console.

When the plugin loads and on `!!mirror reload`, the mirror's PrimeBackup is located, `--version` of the command line tool is run and the warnings are checked; the results are written to the console. This is diagnostics only: it blocks nothing, and every sync checks again.

**Restoring**
- Pre-sync backups are regular backups of the mirror's PrimeBackup, without tags, with creator `prime_backup:cli`; only the comment identifies them.
- To restore one, use the mirror's PrimeBackup with the id from the sync message or `!!mirror history`: `!!pb back <id>` on the mirror. It restores into `restore.destination_root` when that is configured, otherwise into its source root.
- Old pre-sync backups are pruned by the mirror's PrimeBackup prune settings; this plugin deletes nothing.

**Known limits**
- After an automatic stop (`auto_server_restart`) the backup starts at once. If the mirror's MCDR is still shutting down and its PrimeBackup still holds the database, `make` fails and the sync is refused; the mirror is restarted as usual. Run the sync again, or stop the mirror before syncing.
- The plugin does not check whether the mirror's MCDR is running. With `ensure_server_closed: false`, or with a mirror whose MCDR keeps running while its server is stopped, the command line tool and the mirror's PrimeBackup plugin can work on the same storage at the same time.
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
    abort: 0
    log: "console"
    execute: "console"
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
    kill:
        require_confirm: true
    sync:
        ensure_server_closed: true
        auto_server_restart: false
        check_status_interval: 5
        max_attempt_times: 3
        save_world: # Save world configuration
        require_confirm: true
    history:
        require_confirm: false
        max_history_count: 5
    confirm:
        timeout: 30
        cancel_anymsg: true
    abort:
        operator: "everyone"
```

### General Configuration

**require_confirm** `bool`
- When this option is `true`, the command `!!mirror confirm` needs to be entered to confirm the operation after executing the command

### start / stop Configuration
**timeout** `int`
- How many seconds the mirror server may take to start (stop) after the command was sent. Meanwhile its status is shown as `starting` (`stopping`); after that the plugin judges the status only by what it observes, such as the port and the process. Increase `start.timeout` if the mirror server starts slowly
- The config cannot be reloaded while the mirror server is `starting`. Wait for it, or run `!!mirror kill` first
- When MCSM is enabled the status comes from MCSM, and this option does not affect it

### sync Configuration
**ensure_server_closed** `bool`
- When this option is `true`, synchronization will check whether the mirror server has stopped. When this option is `false`, synchronization will be carried out directly regardless of whether the mirror server has stopped or not.

**auto_server_restart** `bool`
- This option only takes effect when `ensure_server_closed` is `true`. When this option is `true`, if the mirror server is not stopped during synchronization, it will attempt to automatically stop the mirror server, perform synchronization, and automatically restart the mirror server after the synchronization is completed.

**check_status_interval** `int`
- This option only takes effect when `auto_server_restart` is in effect. After stopping the mirror server during synchronization, the plugin needs to confirm whether the mirror server has stopped. This option is the time interval for checking the status of the mirror server.

**max_attempt_times** `int`
- This option only takes effect when `auto_server_restart` is in effect. The number of attempts to check the status of the mirror server, after exceeding this number of attempts, it will no longer attempt to check the status of the mirror server, and output `automatic shutdown failed` and the current status information of the mirror server. Equivalent to the timeout time `timeout = check_status_interval * max_attempt_times`

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

### abort Configuration
~This feature is still under development~

<br>

### display: Display Configuration
```yaml
display:
    server_name: "Mirror"
```
**server_name** `str`
- The name of the "mirror server", used to distinguish between different mirror servers in the display

<br>

### Example of Multi-mirror Server Configuration File

```yaml
"!!mirror":
    mcsm:
        enable: true
        url: "http://127.0.0.1:23333/"
        uuid: "71154??????????0a1a2f4dd90695609"
        remote_uuid: "6e927??????????999f0e66bc404071b"
        apikey: "b8f???????????????????????????ade"
    terminal:
        enable: false
        launch_path: "./Mirror"
        launch_command: "python -m mcdreforged"
        port: null
        terminal_name: "Mirror"
        regex_strict: false
        is_mcdr: true
        proxy_type: null
        console_log: false
    sync:
        world:
            - "world"
        source: "./server"
        target:
            - "./Mirror/server"
        ignore_inexistent_target_path: false
        concurrency: 4
        ignore_files:
            - "session.lock"
    command:
        permission:
            status: 0
            start: 0
            stop: 2
            kill: 3
            sync: 2
            confirm: 0
            abort: 0
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
                check_status_interval: 5
                max_attempt_times: 3
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
            abort:
                operator: "everyone"
    display:
        server_name: "Mirror"
"!!mirror2":
    mcsm:
        uuid: "83011??????????49c1133fc08a41b80"
    sync:
        target:
            - "./Mirror2/server"
    display:
        server_name: "Mirror2"
"!!mirror3":
    mcsm:
        enable: false
    sync:
        target:
            - "./Mirror3/server"
    terminal:
        enable: true
        launch_path: "./Mirror3"
        port: 30002
        terminal_name: "Mirror3"
```

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
