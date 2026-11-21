# 快速开始

## 配置第一个镜像服

在默认配置文件中，最开始的`"!!mirror"`下所包含的内容就是你的第一个镜像服的配置文件。在游戏中，你可以使用以`!!mirror`开头的命令来控制这一个镜像服。

它包含了以下指令：

`!!mirror` 显示指令帮助

`!!mirror help` 显示指令帮助

`!!mirror status` 获取镜像服实例运行状态，状态未知/已停止/正在停止/正在启动/正在运行/服务端已停止, MCDR仍在运行

`!!mirror start` 启动镜像服实例

`!!mirror stop` 停止镜像服实例

`!!mirror kill` 终止镜像服实例

`!!mirror kill -f` 或 `!!mirror kill --force` 强制终止镜像服实例（terminal 代理）

`!!mirror sync` 进行文件同步

`!!mirror confirm` 确认某指令的操作

`!!mirror reload` 热重载对应镜像服的配置文件

`!!mirror input <command>` 向subprocess代理中的镜像服发送指令

`!!mirror log` 查看控制台日志输出启用/禁用状态

`!!mirror log enable|disable|<count>` 启用/禁用控制台日志输出，或仅输出接下来`<count>`行控制台日志

**接下来的内容将引导你完成对这一镜像服的配置**

## 配置文件的组成

配置文件主要是这样构成的：

```yaml
!!mirror:
  root_path: # 镜像服目录
  is_mcdr: # 镜像服是否由MCDR运行
  mcsm: # MCSManager配置
  terminal: # 通过命令行启动镜像服终端的配置
  sync: # 存档同步配置
  command:
    permission: # 指令权限配置
    action: # 指令行为配置
  display: # 显示配置
```

### 简要说明

其中，`root_path`和`is_mcdr`说明镜像服在哪里、是什么，`mcsm` `terminal`用于控制镜像服，例如获取状态、开启和关闭镜像服。

而`sync`用于同步存档，当使用`!!mirror sync`指令将生存服同步到镜像服时，它将发挥作用（即控制由源服务端同步存档至目标服务端存档的逻辑）。

`command` 控制指令权限和指令执行时的行为。

`display` 控制指令回显的显示设置。

## 开始配置

这里是一个配置概要，目的是让你大致了解有哪些配置项需要配置。在每一步的末尾，同样会附有跳转以引导你进行下一项的配置。

首先，配置镜像服的目录，跳至[镜像服目录](#镜像服目录)。

如果你使用了[MCSManager](https://github.com/MCSManager/MCSManager)面板，那么请跳至[通过MCSM配置镜像服](#通过mcsm配置镜像服)。

如果你没有使用面板，那么请跳至[通过终端控制镜像服](#通过终端控制镜像服)。

然后，你需要对存档同步进行配置，跳至[存档同步](#存档同步)。

最后，你可以选择性的配置指令权限、行为与显示配置，跳至[指令与显示建议]()以查看一些提醒与建议。

### 镜像服目录

```yaml
root_path: ./Mirror
is_mcdr: true
```

假设这是你的目录结构：
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
`root_path`应当是你的镜像服的根目录。在示例中，镜像服位于`mcdr_root/Mirror`，则`root_path`为`./Mirror`，其中`./`所代表的目录就是插件所在的MCDR服务端根目录。当然，你也可以使用绝对路径。注意路径中的路径分隔符应为`/`或`\\`，而不是单独的`\`。

`is_mcdr`默认为`true`，表示镜像服由MCDReforged运行，此时`root_path`就是镜像服MCDR的`config.yml`所在的目录。镜像服是不带MCDR的普通服务端时，请设为`false`，`root_path`则为服务端自己的目录（`server.properties`所在的目录）。

插件通过`root_path`启动和查找镜像服，并由它推导出同步的目标目录，因此一般不需要再单独填写同步目标。

### 通过MCSM配置镜像服

此配置部分若有疑问，你可以查看[MCSManager官方文档](https://docs.mcsmanager.com/#/zh-cn/apis/readme)并对照
```yaml
mcsm:
  enable: false
  url: http://127.0.0.1:23333/
  uuid:
  remote_uuid:
  apikey:
```
需要注意的是，启用MCSM后，终端（`terminal`）配置项会弃用。

`url`为MCSManager面板的访问地址，即请求api的地址。

`uuid`为服务端实例的id，即实例显示的UID。`remote_uuid`为远程节点的id，即实例显示的GID。这两项配置你可以在打开MCSM并打开对应实例后找到。

`apikey`为调用API接口必需的密钥，通常在用户界面可以查看。

配置完成这四项后，你需要将`enable`设置为`true`，以真正地启用MCSM控制。

跳至[存档同步](#存档同步)来进行下一步

### 通过终端控制镜像服

> [!NOTE]
> `proxy_type`为`linux`（或在Linux系统保持为`null`）时需要安装`screen`；为`windows`时会创建新的命令行终端；为`subprocess`时会在MCDR进程内启动镜像服子进程。Linux/Windows代理的`stop`和`kill`分别通过screen或系统进程控制，subprocess代理通过标准输入输出控制。

```yaml
terminal:
  enable: false
  launch_command: python -m mcdreforged
  port:
  terminal_name: Mirror
  proxy_type:
  console_log: false
```

插件将在`root_path`目录下运行`launch_command`启动命令。在[镜像服目录](#镜像服目录)的示例中，镜像服通过`MCDReforged`启动，则`launch_command`为`python -m mcdreforged`。

`port`为镜像服的端口，即镜像服的`server.properties`文件中的`server-port`项。它应当是一个整数，无需用`"xxx"`包裹。

当`proxy_type`为`linux`时，插件会创建screen；为`windows`时会创建新的命令行终端；为`subprocess`时会在MCDR进程内启动镜像服子进程。`terminal_name`即为命令行终端的标题、screen的名称，或subprocess日志输出的前缀。

`proxy_type`一般无需修改。默认为`null`时，插件会根据操作系统自动选择`linux`或`windows`。设置为`subprocess`时，镜像服会作为MCDR子进程启动，并可通过`console_log`配置是否默认输出控制台日志。有关这些配置的详细信息参见[README-通过命令行启动镜像服终端](../README.md#terminal-通过命令行启动镜像服终端的配置)。

> [!NOTE]
> 使用 `subprocess` 代理启动镜像服 MCDR 实例时，请在镜像服 MCDR 的 `config.yml` 中将 `advanced_console` 设置为 `false`。

同样的，配置完成后，你需要将`enable`设置为`true`，以真正地启用终端控制。

> [!IMPORTANT]
> 插件跟踪的是自己启动的镜像服进程。请通过`!!mirror start`启动镜像服，并让`launch_command`在前台运行镜像服，不要用`nohup ... &`、`start`之类的写法让它脱离。不是插件启动的镜像服（例如手动启动的）可以用`!!mirror recover`接管。详见[README-镜像服状态](../README.md#镜像服状态)和[README-接管镜像服](../README.md#接管镜像服)。

跳至[存档同步](#存档同步)来进行下一步

### 存档同步

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

通常情况下，`world`、`source`和`target`都无需更改：
- `source`留空时，使用本MCDR的工作目录（`working_directory`，默认为`server`）；
- `target`留空时，由`root_path`推导：`is_mcdr`为`true`时，是镜像服MCDR的工作目录，在示例中就是`./Mirror/server`；`is_mcdr`为`false`时，就是`root_path`本身。目录结构特殊，或要同步到多个目录时，再填写`target`。一个简单的检查方法是，`target`目标目录就是`server.properties`所在的目录。

`ignore_files`为不进行同步的文件，一般无需更改。若加载了`carpet`模组，可以添加`carpet.conf`。若加载了`Plusls-Carpet-Addition(PCA)`模组，可以添加`pca.conf`。

在同步时，插件将同时比对文件的哈希值。`concurrency`即为插件比对和同步时使用的线程数。一般无需更改。`ignore_inexistent_target_path`表示若某个目标目录不存在，当设置为`false`时，将会跳过对该目录的同步，并进行提示。当设置为`true`时，将会新建该目录并继续同步。同样一般无需更改。

### 指令与显示建议

指令部分的详细信息请参见[指令配置](../README.md#command-指令配置)。我们建议你按需将`auto_server_restart`选项调整为`true`。当此选项为`true`时, 如果同步时镜像服`正在运行`, 那么将在尝试自动停止镜像服后进行同步, 并在同步完成后自动重启镜像服。这可以一定程度上降低操作复杂度，但是也可能产生仍有玩家在镜像服游玩时，镜像服突然被同步的情况。镜像服为`服务端已停止, MCDR仍在运行`时，此选项不起作用，需要将`auto_mcdr_stop`设为`true`才会让MCDR退出后同步，同步后也不会重启。

显示部分`display`中`server_name`配置项为执行指令后，指令回显（即指令的反馈信息）中镜像服的名称。例如你可以将它自定义为`镜像服` `MyMirrorServer`等。

## 配置多个镜像服

要配置多个镜像服，例如想要通过以`!!mirror2`开头的指令控制镜像服2，你只需要在`"!!mirror"`后面添加`"!!mirror2"`，并书写配置文件中变化的值即可。

**例**

镜像服1为`!!mirror`，同时也是其他镜像服的默认配置文件，那么将`!!mirror`放在配置文件中的第一个

通过`!!mirror2`控制镜像服2，并设置`!!mirror2`的实例id为`abc123`，将`!!mirror2`的服务端名称改为`Mirror2`
```yaml
"!!mirror":
  # 第一个镜像服的配置文件
"!!mirror2":
  # 第二个镜像服的配置文件，只书写变化的值
  root_path: ./Mirror2
  mcsm:
    uuid: abc123
  display:
    server_name: Mirror2
"!!mirror3":
  # 第三个镜像服的配置文件，只书写变化的值
```
后续镜像服会继承第一个镜像服的`root_path`，因此每个镜像服都要填写自己的`root_path`。

详见[多镜像服配置文件示例](../README.md#多镜像服配置文件示例)
