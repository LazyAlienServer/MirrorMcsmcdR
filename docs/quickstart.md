# 快速开始

## 配置第一个镜像服

在默认配置文件中，最开始的`"!!mirror"`下所包含的内容就是你的第一个镜像服的配置文件。在游戏中，你可以使用以`!!mirror`开头的命令来控制这一个镜像服。

它包含了以下指令：

`!!mirror` 显示指令帮助

`!!mirror help` 显示指令帮助

`!!mirror status` 获取镜像服实例运行状态，状态未知/已停止/正在停止/正在启动/正在运行

`!!mirror start` 启动镜像服实例

`!!mirror stop` 停止镜像服实例

`!!mirror kill` 强制终止镜像服实例

`!!mirror sync` 进行文件同步

`!!mirror confirm` 确认某指令的操作

`!!mirror reload` 热重载对应镜像服的配置文件

**接下来的内容将引导你完成对这一镜像服的配置**

## 配置文件的组成

配置文件主要是这样构成的：

```json
{
    "!!mirror": {
        "mcsm": {/* MCSManager配置 */},
        "terminal": {/* 通过命令行启动镜像服终端的配置 */},
        "rcon": {/* RCON配置 */},
        "sync": {/* 存档同步配置 */},
        "command": {
            "permission": {/* 指令权限配置 */},
            "action": {/* 指令行为配置 */}
        },
        "display": {/* 显示配置 */}
    }
}
```

### 简要说明

其中，`mcsm` `terminal` `rcon`用于控制镜像服，例如获取状态、开启和关闭镜像服。

而`sync`用于同步存档，当使用`!!mirror sync`指令将生存服同步到镜像服时，它将发挥作用（即控制由源服务端同步存档至目标服务端存档的逻辑）。

`command` 控制指令权限和指令执行时的行为。

`display` 控制指令回显的显示设置。

## 开始配置

这里是一个配置概要，目的是让你大致了解有哪些配置项需要配置。在每一步的末尾，同样会附有跳转以引导你进行下一项的配置。

如果你使用了[MCSManager](https://github.com/MCSManager/MCSManager)面板，那么请跳至[通过MCSM配置镜像服](#通过mcsm配置镜像服)。

如果你没有使用面板，那么请跳至[通过终端控制镜像服](#通过终端控制镜像服)。

然后，你需要对存档同步进行配置，跳至[存档同步](#存档同步)。

最后，你可以选择性的配置指令权限、行为与显示配置，跳至[指令与显示建议]()以查看一些提醒与建议。

### 通过MCSM配置镜像服

此配置部分若有疑问，你可以查看[MCSManager官方文档](https://docs.mcsmanager.com/#/zh-cn/apis/readme)并对照
```json
"mcsm": {
    "enable": false,
    "url": "http://127.0.0.1:23333/",
    "uuid": null,
    "remote_uuid": null,
    "apikey": null
}
```
需要注意的是，启用MCSM后，终端（`terminal`）与RCON（`rcon`）配置项都会弃用。

`url`为MCSManager面板的访问地址，即请求api的地址。

`uuid`为服务端实例的id，即实例显示的UID。`remote_uuid`为远程节点的id，即实例显示的GID。这两项配置你可以在打开MCSM并打开对应实例后找到。

`apikey`为调用API接口必需的密钥，通常在用户界面可以查看。

配置完成这四项后，你需要将`enable`设置为`true`，以真正地启用MCSM控制。

跳至[存档同步](#存档同步)来进行下一步

### 通过终端控制镜像服

**注意**：如果你是Linux用户，那么你只需要配置`terminal`，而`rcon`不是必选项。如果你是Windows用户，那么你需要同时配置`terminal`和`rcon`，若不配置`rcon`则无法使用`!!mirror stop`指令。

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

假设这是你的目录结构：
```
mcdr_root
 ├─ config
 ├─ logs
 ├─ plugins
 ├─ server
 └─ Mirror
     └─ server
```
那么，插件将在`launch_path`目录下运行`launch_command`启动命令，`launch_path`应当是你的镜像服的根目录。

在示例中，镜像服位于`mcdr_root/Mirror`，且通过`MCDReforged`启动，则`launch_path`为`./Mirror`，`launch_command`为`python -m mcdreforged`，其中`./`所代表的目录就是插件所在的MCDR服务端根目录。当然，你也可以使用绝对路径。注意路径中的路径分隔符应为`/`或`\\`，而不是单独的`\`。

`port`为镜像服的端口，即镜像服的`server.properties`文件中的`server-port`项。它应当是一个整数，无需用`"xxx"`包裹。

与其他镜像服插件不同的是，此插件在启动镜像服时，会创建一个新的终端（Windows）或screen（Linux）。`terminal_name`即为这一终端的标题或这一screen的名称，方便运维。实现方式参见[README-通过命令行启动镜像服终端](../README.md#terminal-通过命令行启动镜像服终端的配置)

`regex_strict`与`system`一般无需修改。`system`默认为`null`时，插件会自动获取操作系统。只有当插件获取操作系统出错时才需要认为配置。有关`regex_strict`的详细信息参见[README-通过命令行启动镜像服终端](../README.md#terminal-通过命令行启动镜像服终端的配置)。

至此，**对于Linux用户**，你可以跳至[存档同步](#存档同步)来进行下一步了，或选择性地继续查看`rcon`配置。**对于Windows用户**，请继续配置`rcon`。

同样的，配置完成后，你需要将`enable`设置为`true`，以真正地启用终端控制。

```json
"rcon": {
    "enable": false,
    "address": null,
    "port": null,
    "password": null
}
```

首先，你需要在镜像服的`server.properties`中配置RCON，设置`rcon.port`为自定义的RCON端口，设置`rcon.password`为自定义的RCON密码，并将`enable-rcon`设置为`true`以启用RCON。

然后配置此插件的配置文件。`address`为RCON的连接地址，一般情况下书写本机地址`127.0.0.1`即可。`port`为RCON的端口，即镜像服的`server.properties`文件中的`rcon.port`项。与`terminal`中的`port`同理，它应当是一个整数，无需用`"xxx"`包裹。`password`为RCON的密码，即镜像服的`server.properties`文件中的`rcon.password`项。

说明：当配置RCON后，插件将通过RCON执行`stop`指令和获取镜像服状态（Windows和Linux）。若同时启用了`rcon`和`terminal`，插件将优先通过检查RCON状态来获取镜像服状态，若RCON未连接，则将通过检查端口来获取状态。若RCON状态与端口状态不匹配将会提示，这种不匹配通常是由于`rcon`配置错误，或`terminal`的端口配置错误。

跳至[存档同步](#存档同步)来进行下一步

### 存档同步

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
假设这是你的目录结构：
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
和前文同理，在示例中，镜像服位于`mcdr_root/Mirror`。其中`./`所代表的目录就是插件所在的MCDR服务端根目录。

插件将把`source`源目录中的每个`world`中所包含的世界文件夹同步到`target`目标目录中的对应的世界文件夹。在默认配置下，它将把`mcdr_root/server/world`中的文件同步至`mcdr_root/Mirror/server/world`。

通常情况下，`world`与`source`无需更改。`target`为目标目录，如果镜像服是通过MCDR启动的，那么它应当是镜像服MCDR的工作目录，通常为镜像服的`server`目录。在示例中它就是`./Mirror/server`。一个简单的寻找方法是，`target`目标目录就是`server.properties`所在的目录。

`ignore_files`为不进行同步的文件，一般无需更改。若加载了`carpet`模组，可以添加`carpet.conf`。若加载了`Plusls-Carpet-Addition(PCA)`模组，可以添加`pca.conf`。

在同步时，插件将同时比对文件的哈希值。`concurrency`即为插件比对和同步时使用的线程数。一般无需更改。`ignore_inexistent_target_path`表示若某个目标目录不存在，当设置为`false`时，将会跳过对该目录的同步，并进行提示。当设置为`true`时，将会新建该目录并继续同步。同样一般无需更改。

### 指令与显示建议

指令部分的详细信息请参见[指令配置](../README.md#command-指令配置)。我们建议你按需将`auto_server_restart`选项调整为`true`。当此选项为`true`时, 如果同步时镜像服未停止, 那么将在尝试自动停止镜像服后进行同步, 并在同步完成后自动重启镜像服。这可以一定程度上降低操作复杂度，但是也可能产生仍有玩家在镜像服游玩时，镜像服突然被同步的情况。

显示部分`display`中`server_name`配置项为执行指令后，指令回显（即指令的反馈信息）中镜像服的名称。例如你可以将它自定义为`镜像服` `MyMirrorServer`等。

## 配置多个镜像服

要配置多个镜像服，例如想要通过以`!!mirror2`开头的指令控制镜像服2，你只需要在`"!!mirror"`后面添加`"!!mirror2"`，并书写配置文件中变化的值即可。

**例**

镜像服1为`!!mirror`，同时也是其他镜像服的默认配置文件，那么将`!!mirror`放在配置文件中的第一个

通过`!!mirror2`控制镜像服2，并设置`!!mirror2`的实例id为`abc123`，将`!!mirror2`的服务端名称改为`Mirror2`
```json
{
    "!!mirror": {
        // 第一个镜像服的配置文件
    },
    "!!mirror2": {
        // 第二个镜像服的配置文件，只书写变化的值
        "mcsm": {
            "uuid": "abc123"
        },
        "display": {
            "server_name": "Mirror2"
        }
    },
    "!!mirror3": {
        // 第三个镜像服的配置文件，只书写变化的值
    }
}
```
详见[多镜像服配置文件示例](../README.md#多镜像服配置文件示例)