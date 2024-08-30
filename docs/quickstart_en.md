# Quick Start

*This document is still under manual checking, which is initially translated by Kimi AI*

## Configuring the First Mirror Server

In the default configuration file, the content under the initial `"!!mirror"` is the configuration file for your first mirror server. In the game, you can use commands starting with `!!mirror` to control this mirror server.

It includes the following commands:

`!!mirror` Displays command help

`!!mirror help` Displays command help

`!!mirror status` Gets the running status of the mirror server instance, with states such as unknown/stopped/stopping/starting/running

`!!mirror start` Starts the mirror server instance

`!!mirror stop` Stops the mirror server instance

`!!mirror kill` Forcefully terminates the mirror server instance

`!!mirror sync` Performs file synchronization

`!!mirror confirm` Confirms the operation of a certain command

`!!mirror reload` Hot reloads the configuration file for the corresponding mirror server

**The following content will guide you through the configuration of this mirror server**

## Composition of the Configuration File

The configuration file is mainly composed as follows:

```json
{
    "!!mirror": {
        "mcsm": {/* MCSManager configuration */},
        "terminal": {/* Configuration for starting the mirror server terminal through the command line */},
        "rcon": {/* RCON configuration */},
        "sync": {/* Save synchronization configuration */},
        "command": {
            "permission": {/* Command permission configuration */},
            "action": {/* Command behavior configuration */}
        },
        "display": {/* Display configuration */}
    }
}
```

### Brief Explanation

`mcsm`, `terminal`, and `rcon` are used to control the mirror server, such as obtaining status, starting, and stopping the mirror server.

`sync` is for synchronizing saves; it takes effect when using the `!!mirror sync` command to synchronize the survival server to the mirror server (i.e., controlling the logic of synchronizing saves from the source server to the target server).

`command` controls command permissions and the behavior when commands are executed.

`display` controls the display settings for command feedback.

## Start Configuring

Here is an overview of the configuration, which aims to give you a general understanding of the configuration items that need to be set. At the end of each step, there will also be a link to guide you to the next configuration step.

If you have used the [MCSManager](https://github.com/MCSManager/MCSManager) panel, please jump to [Configuring the Mirror Server through MCSM](#configuring-the-mirror-server-through-mcsm).

If you have not used the panel, please jump to [Controlling the Mirror Server through the Terminal](#controlling-the-mirror-server-through-the-terminal).

Then, you need to configure the save synchronization, jump to [Save Synchronization](#save-synchronization).

Finally, you can optionally configure command permissions, behavior, and display settings, jump to [Command and Display Suggestions](#command-and-display-suggestions) to view some reminders and suggestions.

### Configuring the Mirror Server through MCSM

If you have any questions about this configuration section, you can refer to the [MCSManager Official Documentation](https://docs.mcsmanager.com/#/zh-cn/apis/readme) and compare

```json
"mcsm": {
    "enable": false,
    "url": "http://127.0.0.1:23333/", 
    "uuid": null,
    "remote_uuid": null,
    "apikey": null
}
```

Note that after enabling MCSM, the terminal (`terminal`) and RCON (`rcon`) configuration items will be disabled.

`url` is the access address of the MCSManager panel, that is, the address for requesting the API.

`uuid` is the ID of the server instance, that is, the UID displayed by the instance. `remote_uuid` is the ID of the remote node, that is, the GID displayed by the instance. You can find these two configurations by opening MCSM and the corresponding instance.

`apikey` is the key required to call the API interface, which can usually be viewed in the user interface.

After completing these four configurations, you need to set `enable` to `true` to truly enable MCSM control.

Jump to [Save Synchronization](#save-synchronization) for the next step.

### Controlling the Mirror Server through the Terminal

**Note**: If you are a Linux user, you only need to configure `terminal`, and `rcon` is not a required option. If you are a Windows user, you need to configure both `terminal` and `rcon`. If you do not configure `rcon`, you will not be able to use the `!!mirror stop` command.

```json
"terminal": {
    "enable": false,
    "launch_path": "./Mirror",
    "launch_command": "python -m mcdreforged",
    "port": null,
    "terminal_name": "Mirror",
    "regex_strict": false,
    "system": null
}
```

Assuming this is your directory structure:
```
mcdr_root
 ├─ config
 ├─ logs
 ├─ plugins
 ├─ server
 └─ Mirror
     └─ server
```

The plugin will run the `launch_command` startup command in the `launch_path` directory, and `launch_path` should be the root directory of your mirror server.

In the example, the mirror server is located in `mcdr_root/Mirror` and is started by `MCDReforged`, then `launch_path` is `./Mirror`, `launch_command` is `python -m mcdreforged`, where `./` represents the MCDR server root directory where the plugin is located. Of course, you can also use absolute paths. Note that the path separator in the path should be `/` or `\\`, not a single `\`.

`port` is the port of the mirror server, that is, the `server-port` item in the `server.properties` file of the mirror server. It should be an integer and does not need to be wrapped in `"xxx"`.

Unlike other mirror server plugins, this plugin creates a new terminal (Windows) or screen (Linux) when starting the mirror server. `terminal_name` is the title of this terminal or the name of this screen, which is convenient for operation and maintenance. For implementation, see [README-Configuring the Mirror Server Terminal through the Command Line](../README_en.md#terminal-configuration-for-starting-the-mirror-server-terminal-through-the-command-line)

`regex_strict` and `system` generally do not need to be modified. `system` is set to `null` by default, and the plugin will automatically obtain the operating system. Manual configuration is only needed when the plugin fails to obtain the operating system. For more information about `regex_strict`, see [README-Configuring the Mirror Server Terminal through the Command Line](../README_en.md#terminal-configuration-for-starting-the-mirror-server-terminal-through-the-command-line).

So far, **for Linux users**, you can jump to [Save Synchronization](#save-synchronization) for the next step, or optionally continue to view the `rcon` configuration. **For Windows users**, please continue to configure `rcon`.

Similarly, after the configuration is completed, you need to set `enable` to `true` to truly enable terminal control.

```json
"rcon": {
    "enable": false,
    "address": null,
    "port": null,
    "password": null
}
```

First, you need to configure RCON in the `server.properties` of the mirror server, set `rcon.port` to a custom RCON port, set `rcon.password` to a custom RCON password, and set `enable-rcon` to `true` to enable RCON.

Then configure the configuration file of this plugin. `address` is the connection address for RCON, and generally, writing the local machine address `127.0.0.1` is sufficient. `port` is the port for RCON, which is the `rcon.port` item in the `server.properties` file of the mirror server. Similarly to the `port` in `terminal`, it should be an integer and does not need to be wrapped in `"xxx"`. `password` is the password for RCON, which is the `rcon.password` item in the `server.properties` file of the mirror server.

Note: After configuring RCON, the plugin will execute the `stop` command and obtain the status of the mirror server through RCON (both Windows and Linux). If both `rcon` and `terminal` are enabled, the plugin will first check the status of RCON to obtain the status of the mirror server. If RCON is not connected, it will check the status through the port. If the status of RCON does not match the status of the port, a prompt will be given. This mismatch is usually due to incorrect `rcon` configuration or incorrect port configuration for `terminal`.

Jump to [Save Synchronization](#save-synchronization) for the next step.

### Save Synchronization

```json
"sync": {
    "world": [
        "world"
    ],
    "source": "./server",
    "target": [
        "./Mirror/server"
    ],
    "ignore_inexistent_target_path": false,
    "concurrency": 4,
    "ignore_files": [
        "session.lock"
    ]
}
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

In general, there is no need to change `world` and `source`. `target` is the target directory, and if the mirror server is started by MCDR, it should be the working directory of the mirror server's MCDR, usually the `server` directory of the mirror server. In the example, it is `./Mirror/server`. A simple way to find it is that the `target` directory is the directory where `server.properties` is located.

`ignore_files` are files that are not synchronized, and generally, there is no need to change them. If the `carpet` module is loaded, you can add `carpet.conf`. If the `Plusls-Carpet-Addition(PCA)` module is loaded, you can add `pca.conf`.

During synchronization, the plugin will also compare the hash values of the files. `concurrency` is the number of threads used by the plugin for comparison and synchronization. Generally, there is no need to change it. `ignore_inexistent_target_path` means that if a target directory does not exist, when set to `false`, it will skip synchronization for that directory and give a prompt. When set to `true`, it will create the directory and continue synchronization. Similarly, there is generally no need to change it.

### Command and Display Suggestions

For detailed information on the command part, please refer to [Command Configuration](../README_en.md#command-command-configuration). We suggest you adjust the `auto_server_restart` option to `true` as needed. When this option is `true`, if the mirror server is not stopped during synchronization, the synchronization will be performed after trying to automatically stop the mirror server, and the mirror server will be automatically restarted after the synchronization is completed. This can reduce the complexity of operations to some extent, but it may also cause the mirror server to be synchronized suddenly when there are still players playing in the mirror server.

The `server_name` configuration item in the display part `display` is the name of the mirror server in the command feedback (i.e., the feedback information of the command) after executing the command. For example, you can customize it to `Mirror Server` `MyMirrorServer`, etc.

## Configuring Multiple Mirror Servers

To configure multiple mirror servers, for example, if you want to control the second mirror server with commands starting with `!!mirror2`, you only need to add `"!!mirror2"` after `"!!mirror"` and write the changed values in the configuration file.

**Example**

Mirror server 1 is `!!mirror`, which is also the default configuration file for other mirror servers, then put `!!mirror` first in the configuration file.

Control mirror server 2 through `!!mirror2`, and set the instance id of `!!mirror2` to `abc123`, change the server name of `!!mirror2` to `Mirror2`
```json
{
    "!!mirror": {
        // Configuration file for the first mirror server
    },
    "!!mirror2": {
        // Configuration file for the second mirror server, only write the changed values
        "mcsm": {
            "uuid": "abc123"
        },
        "display": {
            "server_name": "Mirror2"
        }
    },
    "!!mirror3": {
        // Configuration file for the third mirror server, only write the changed values
    }
}
```

See [Multi-mirror Server Configuration File Example](../README_en.md#example-of-multi-mirror-server-configuration-file) for details.