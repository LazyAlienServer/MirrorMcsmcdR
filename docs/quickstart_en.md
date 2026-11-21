# Quick Start

## Configuring the First Mirror Server

In the default configuration file, the content under the initial `"!!mirror"` is the configuration file for your first mirror server. In the game, you can use commands starting with `!!mirror` to control this mirror server.

It includes the following commands:

`!!mirror` Displays command help

`!!mirror help` Displays command help

`!!mirror status` Gets the running status of the mirror server instance, with states such as unknown/stopped/stopping/starting/running/server stopped, MCDR still running

`!!mirror start` Starts the mirror server instance

`!!mirror stop` Stops the mirror server instance

`!!mirror kill` Terminates the mirror server instance

`!!mirror kill -f` or `!!mirror kill --force` Forcefully terminates the mirror server instance (terminal proxies)

`!!mirror sync` Performs file synchronization

`!!mirror confirm` Confirms the operation of a certain command

`!!mirror reload` Hot reloads the configuration file for the corresponding mirror server

`!!mirror input <command>` Sends a command through the subprocess proxy

`!!mirror log` View the enabled/disabled status of console log output.

`!!mirror log enable|disable|<count>` Enable or disable console log output, or output only the next `<count>` lines of console logs.

**The following content will guide you through the configuration of this mirror server**

## Composition of the Configuration File

The configuration file is mainly composed as follows:

```yaml
!!mirror:
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

### Brief Explanation

`root_path` and `is_mcdr` tell where the mirror server is and what it is; `mcsm` and `terminal` are used to control the mirror server, such as obtaining status, starting, and stopping the mirror server.

`sync` is for synchronizing saves; it takes effect when using the `!!mirror sync` command to synchronize the survival server to the mirror server (i.e., controlling the logic of synchronizing saves from the source server to the target server).

`command` controls command permissions and the behavior when commands are executed.

`display` controls the display settings for command feedback.

## Start Configuring

Here is an overview of the configuration, which aims to give you a general understanding of the configuration items that need to be set. At the end of each step, there will also be a link to guide you to the next configuration step.

First, configure the directory of the mirror server, jump to [Mirror Server Directory](#mirror-server-directory).

If you have used the [MCSManager](https://github.com/MCSManager/MCSManager) panel, please jump to [Configuring the Mirror Server through MCSM](#configuring-the-mirror-server-through-mcsm).

If you have not used the panel, please jump to [Controlling the Mirror Server through the Terminal](#controlling-the-mirror-server-through-the-terminal).

Then, you need to configure the save synchronization, jump to [Save Synchronization](#save-synchronization).

Finally, you can optionally configure command permissions, behavior, and display settings, jump to [Command and Display Suggestions](#command-and-display-suggestions) to view some reminders and suggestions.

### Mirror Server Directory

```yaml
root_path: ./Mirror
is_mcdr: true
```

Assuming this is your directory structure:
```
mcdr_root
 ├─ config
 ├─ logs
 ├─ plugins
 ├─ server
 └─ Mirror
     ├─ config.yml
     └─ server
```

`root_path` should be the root directory of your mirror server. In the example, the mirror server is located in `mcdr_root/Mirror`, so `root_path` is `./Mirror`, where `./` represents the MCDR server root directory where the plugin is located. Of course, you can also use absolute paths. Note that the path separator in the path should be `/` or `\\`, not a single `\`.

`is_mcdr` defaults to `true`, meaning the mirror server is run by MCDReforged; `root_path` is then the directory of the mirror MCDR's `config.yml`. For a plain server without MCDR, set it to `false`; `root_path` is then the server's own directory (where `server.properties` is).

The plugin starts and looks for the mirror server in `root_path`, and derives the sync target from it, so the sync target usually needs no setting of its own.

### Configuring the Mirror Server through MCSM

If you have any questions about this configuration section, you can refer to the [MCSManager Official Documentation](https://docs.mcsmanager.com/#/zh-cn/apis/readme) and compare

```yaml
mcsm:
    enable: false
    url: http://127.0.0.1:23333/
    uuid:
    remote_uuid:
    apikey:
```

Note that after enabling MCSM, the terminal (`terminal`) configuration items will be disabled.

`url` is the access address of the MCSManager panel, that is, the address for requesting the API.

`uuid` is the ID of the server instance, that is, the UID displayed by the instance. `remote_uuid` is the ID of the remote node, that is, the GID displayed by the instance. You can find these two configurations by opening MCSM and the corresponding instance.

`apikey` is the key required to call the API interface, which can usually be viewed in the user interface.

After completing these four configurations, you need to set `enable` to `true` to truly enable MCSM control.

Jump to [Save Synchronization](#save-synchronization) for the next step.

### Controlling the Mirror Server through the Terminal

> [!NOTE]
> `screen` is required when `proxy_type` is `linux` (or left as `null` on Linux); `windows` creates a new command prompt; and `subprocess` starts the mirror server as a child process inside MCDR. The Linux/Windows proxies control the server through screen or system processes, while the subprocess proxy uses standard input and output.
```yaml
terminal:
    enable: false
    launch_command: python -m mcdreforged
    port:
    terminal_name: Mirror
    proxy_type:
    console_log: false
```

The plugin will run the `launch_command` startup command in the `root_path` directory. In the example of [Mirror Server Directory](#mirror-server-directory), the mirror server is started by `MCDReforged`, so `launch_command` is `python -m mcdreforged`.

`port` is the port of the mirror server, that is, the `server-port` item in the `server.properties` file of the mirror server. It should be an integer and does not need to be wrapped in `"xxx"`.

When `proxy_type` is `linux`, the plugin creates a screen session; when it is `windows`, it creates a new command prompt; and when it is `subprocess`, it starts the mirror server as a child process inside MCDR. `terminal_name` is the title of the command prompt, the name of the screen, or the prefix used for subprocess log output.

`proxy_type` generally does not need to be modified. When it is `null`, the plugin automatically selects `linux` or `windows` based on the operating system. When set to `subprocess`, the mirror server runs as an MCDR child process, and `console_log` controls whether its console logs are output by default. See [README-Configuring the Mirror Server Terminal through the Command Line](../README_en.md#terminal-configuration-for-starting-the-mirror-server-terminal-through-the-command-line) for details.

> [!NOTE]
> When using the `subprocess` proxy to start another MCDR instance, set `advanced_console: false` in the mirror server MCDR's `config.yml`.

Similarly, after the configuration is completed, you need to set `enable` to `true` to truly enable terminal control.

> [!IMPORTANT]
> The plugin tracks the mirror server processes it started itself. Start the mirror server with `!!mirror start`, and let `launch_command` run it in the foreground; do not detach it with `nohup ... &`, `start` or the like. A mirror server the plugin did not start, such as one started by hand, can be adopted with `!!mirror recover`. See [README - Mirror server status](../README_en.md#mirror-server-status) and [README - Adopting a mirror server](../README_en.md#adopting-a-mirror-server).

Jump to [Save Synchronization](#save-synchronization) for the next step.

### Save Synchronization

```yaml
sync:
    world:
        - world
    source: ''
    target: []
    ignore_inexistent_target_path: false
    concurrency: 4
    ignore_files:
        - session.lock
```

Assuming this is your directory structure:
```
mcdr_root
 ├─ config
 ├─ logs
 ├─ plugins
 ├─ server
 |   └─ world
 └─ Mirror
     └─ server
         └─ world
```

Similarly, in the example, the mirror server is located in `mcdr_root/Mirror`. The `./` represents the MCDR server root directory where the plugin is located.

The plugin will synchronize each world folder contained in each `world` in the `source` directory to the corresponding world folder in the `target` directory. By default, it will synchronize the files in `mcdr_root/server/world` to `mcdr_root/Mirror/server/world`.

In general, there is no need to change `world`, `source` or `target`:
- An empty `source` means the working directory of this MCDR (`working_directory`, `server` by default);
- An empty `target` is derived from `root_path`: with `is_mcdr` set to `true`, the working directory of the mirror server's MCDR, `./Mirror/server` in the example; with `is_mcdr` set to `false`, `root_path` itself. Set `target` for an unusual directory layout, or to sync into several directories. A simple check is that the `target` directory is the directory where `server.properties` is located.

`ignore_files` are files that are not synchronized, and generally, there is no need to change them. If the `carpet` module is loaded, you can add `carpet.conf`. If the `Plusls-Carpet-Addition(PCA)` module is loaded, you can add `pca.conf`.

During synchronization, the plugin will also compare the hash values of the files. `concurrency` is the number of threads used by the plugin for comparison and synchronization. Generally, there is no need to change it. `ignore_inexistent_target_path` means that if a target directory does not exist, when set to `false`, it will skip synchronization for that directory and give a prompt. When set to `true`, it will create the directory and continue synchronization. Similarly, there is generally no need to change it.

### Command and Display Suggestions

For detailed information on the command part, please refer to [Command Configuration](../README_en.md#command-command-configuration). We suggest you adjust the `auto_server_restart` option to `true` as needed. When this option is `true`, if the mirror server is `running` during synchronization, the synchronization will be performed after trying to automatically stop the mirror server, and the mirror server will be automatically restarted after the synchronization is completed. This can reduce the complexity of operations to some extent, but it may also cause the mirror server to be synchronized suddenly when there are still players playing in the mirror server. It does not apply while the mirror server is `server stopped, MCDR still running`: only with `auto_mcdr_stop` set to `true` is MCDR made to exit before the sync, and nothing is restarted afterwards.

The `server_name` configuration item in the display part `display` is the name of the mirror server in the command feedback (i.e., the feedback information of the command) after executing the command. For example, you can customize it to `Mirror Server` `MyMirrorServer`, etc.

## Configuring Multiple Mirror Servers

To configure multiple mirror servers, for example, if you want to control the second mirror server with commands starting with `!!mirror2`, you only need to add `"!!mirror2"` after `"!!mirror"` and write the changed values in the configuration file.

**Example**

Mirror server 1 is `!!mirror`, which is also the default configuration file for other mirror servers, then put `!!mirror` first in the configuration file.

Control mirror server 2 through `!!mirror2`, and set the instance id of `!!mirror2` to `abc123`, change the server name of `!!mirror2` to `Mirror2`
```yaml
"!!mirror":
    # Configuration file for the first mirror server
"!!mirror2":
    # Configuration file for the second mirror server, only write the changed values
    root_path: ./Mirror2
    mcsm:
        uuid: abc123
    display:
        server_name: Mirror2
"!!mirror3":
    # Configuration file for the third mirror server, only write the changed values
```

Later mirror servers inherit `root_path` from the first one, so every mirror server needs its own `root_path`.

See [Multi-mirror Server Configuration File Example](../README_en.md#example-of-multi-mirror-server-configuration-file) for details.
