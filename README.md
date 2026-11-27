# MirrorMcsmcdR

[![MCDR](https://img.shields.io/badge/MCDR-%E2%89%A52.16.0-blue)](https://github.com/Fallen-Breath/MCDReforged) [![许可证](https://img.shields.io/github/license/LazyAlienServer/MirrorMcsmcdR)](./LICENSE) [![下载量](https://img.shields.io/github/downloads/LazyAlienServer/MirrorMcsmcdR/total)](https://github.com/LazyAlienServer/MirrorMcsmcdR/releases)

中文 · [English](./README_en.md)

> 最全面的 [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) 镜像服控制插件！通过多种方式控制镜像服，并使用基于哈希的增删同步。

## 特性

- **多种方式控制与启停**：
  - 支持通过[MCSManager](https://github.com/MCSManager/MCSManager)控制镜像服（`MCSM-v9.9.0` `MCSM-v10.2.1+`）
  - 支持直接通过终端启动与停止镜像服（`Linux` `Windows`），并且新终端与父MCDR进程互不干扰，便于运维管理
    - Linux 通过`screen`控制镜像服
    - Windows 通过新命令行终端控制镜像服
  - 支持通过`subprocess`在MCDR进程内启动镜像服子进程，并通过标准输入输出控制镜像服
  - 支持通过`!!mirror input <command>`向镜像服发送指令
  - 支持多种控制方式的组合使用，例如：
    - 通过 MCDR 启动与停止镜像服，当镜像服进程异常时，通过 Linux 强制终止镜像服
- **完善的控制功能**：完善的**多镜像服**控制操作，获取运行状态/启动/停止/强制终止/同步操作
- **基于哈希的文件同步**：基于哈希的文件同步，只同步镜像服与源服务端不同的文件，提升速度并减少磁盘IO
- **同步前备份**：可选在每次同步前用镜像服自己的 PrimeBackup 备份镜像服世界，没有成功的备份就不同步
- **高度可自定义的配置文件**：使用YAML格式，提供高可自定义的、配置友好配置文件，多个镜像服配置时只需要书写变化的值

> [!NOTE]
> 本插件不提供服务端创建/管理功能，请在镜像服创建完成并创建对应的MCSManager实例后再使用本插件。镜像服启动完成后插件会广播`已启动`，但不提供停止完成的提示信息，需要时建议搭配vchat等插件使用。

## 依赖

| 依赖                | 说明                                                                                      |
|---------------------|-------------------------------------------------------------------------------------------|
| Python              | `>=3.10`                                                                                  |
| Python 包           | `xxhash>=3`                                                                               |
| Linux terminal 代理 | `proxy_type` 为 `linux` 或 `null` 时需要 [`screen`](https://www.gnu.org/software/screen/) |
| PrimeBackup         | 镜像服 MCDR 中需要 `>=1.13.0`，仅在启用[同步前备份](#syncbackup-同步前备份)时需要                    |

## 从v1.8.0及更早版本升级

新版本要求MCDReforged`>=2.16.0`，请注意升级。

旧版本启动的镜像服不在新版本的记录中（见[镜像服状态](#镜像服状态)）。升级时镜像服可以保持运行：插件加载时会自动接管它（见[接管镜像服](#接管镜像服)）。无法自动接管时，插件会在控制台和游戏内提示，此时请用`!!mirror recover`手动接管，或手动停止镜像服。`is_mcdr`为`false`时，插件只提示、不自动接管，请用`!!mirror recover`手动接管。镜像服不在screen或命令行窗口中运行时（例如用`nohup`启动的），接管后没有控制台，只能用`!!mirror kill -f`结束。

升级后请检查配置文件：
- `rcon`配置已删除，旧配置中的`rcon`会被忽略。需要跨主机控制镜像服时，请使用MCSManager；
- `terminal.regex_strict`已删除。配置的端口被任何插件未跟踪的进程占用时，状态都显示为`状态未知`；
- `subprocess`代理现在也必须配置`terminal.port`，未配置时terminal代理不可用；
- `command.action.sync.max_attempt_times`已删除。同步自动停服后，最多等待`command.action.stop.timeout`秒（默认60秒，以前默认15秒）；
- `command.action.sync.check_status_interval`移到了`command.action.check_status_interval`。旧位置的值会被忽略，恢复为默认值`5`；
- `!!mirror execute`改名为`!!mirror input`，旧指令不再可用。权限配置`command.permission.execute`随之改为`command.permission.input`，旧的`execute`会被忽略，恢复为默认值`console`；
- `terminal.launch_path`改为顶层的[`root_path`](#root_path--is_mcdr-镜像服目录与类型)，`terminal.is_mcdr`改为顶层的`is_mcdr`，`sync.backup.mcdr_path`已删除（备份改用`root_path`）。旧的项会被忽略，`root_path`恢复为默认值`./Mirror`，`is_mcdr`恢复为默认值`true`，请**手动修改**。以前设置了`terminal.is_mcdr: false`的普通服务端镜像服，要重新设置`is_mcdr: false`（后续镜像服会继承第一个镜像服的值）。`is_mcdr`为`false`时不支持同步前备份，启用`sync.backup.enable`时所有同步都会被拒绝；
- 镜像服MCDR用`--config`指定其他配置文件启动时，请填写`sync.target`，这种情况下不支持同步前备份，见[`root_path`](#root_path--is_mcdr-镜像服目录与类型)；
- `command.permission.abort`和`command.action.abort`已删除，它们从未对应任何指令；
- 同时启用`mcsm`和`terminal`时，现在只使用MCSM，`terminal`配置不再生效（只有subprocess代理提供的`log`、`input`也不可用）。这样做是为了避免`kill -f`和接管镜像服误操作本机上与MCSM实例无关的进程；
- Windows上的`subprocess`代理改为按UTF-8读取镜像服的输出，以前按系统代码页读取。镜像服MCDR的输出是UTF-8，`log`中的中文不再乱码；普通服务端（`is_mcdr`为`false`）的输出不是UTF-8时，`log`中会出现乱码；
- `sync.source`和`sync.target`可以留空，分别使用本MCDR的`working_directory`和由`root_path`推导出的目录。原有的值仍然有效；
- `sync.world`现在是[gitignore规则](#sync-文件同步相关的配置文件)。直接写目录名的含义不变，但区分大小写，Windows上也一样：以前写`World`也能同步`world`，现在要写成实际的名字，否则同步被拒绝。同步时，只存在于镜像服世界中的空目录现在也会被删除；
- `sync.ignore_files`已删除，改为`sync.ignore_patterns`和`sync.retain_patterns`，旧的值不会迁移，请**手动修改**。以前`ignore_files`中的文件（如`carpet.conf`、`pca.conf`）会保留镜像服中原有的那份，对应现在的`retain_patterns`；`session.lock`默认在`ignore_patterns`中，镜像服中的会被删除；
- `sync.ignore_inexistent_target_path`已删除，改为[`sync.missing`](#sync-文件同步相关的配置文件)，旧的值不会迁移。旧的`true`对应`missing.target: create`（现在只创建最后一级目录）；旧的`false`会跳过不存在的目标目录，对应`missing.target: skip`，而新的默认值`refuse`会拒绝同步。

插件加载配置时，会从配置文件中删除它不认识的项（包括上面已删除的项和拼错的项），并在控制台逐项列出路径和值，同时在游戏内提示一次。删除前，原配置文件会备份为同目录下的`config.yml.<时间>-<内容哈希>.bak`。

## 指令

默认指令前缀为 `!!mirror`。

| 指令                                    | 说明                                |
|-----------------------------------------|-------------------------------------|
| `!!mirror` / `!!mirror help`            | 显示指令帮助                        |
| `!!mirror status`                       | 查看镜像服状态，详情只发给执行者    |
| `!!mirror start`                        | 启动镜像服                          |
| `!!mirror stop`                         | 停止镜像服                          |
| `!!mirror kill`                         | 终止镜像服                          |
| `!!mirror kill -f`                      | 强制终止镜像服（terminal 代理） |
| `!!mirror recover [pid]`                | 接管未跟踪的镜像服（terminal 代理） |
| `!!mirror sync`                         | 同步文件                            |
| `!!mirror confirm`                      | 确认待执行操作                      |
| `!!mirror reload`                       | 热重载镜像服配置                    |
| `!!mirror history`                      | 查看同步历史                        |
| `!!mirror input <command>`              | 通过 subprocess 代理发送指令        |
| `!!mirror log`                          | 查看 subprocess 控制台日志状态      |
| `!!mirror log enable\|disable\|<count>` | 启用、禁用或限制控制台日志输出      |

## 配置文件

> [!TIP]
> 配置文件较长，建议先阅读[快速开始](./docs/quickstart.md)，再将下文作为配置参考。

配置文件支持热重载和自动补全。新版本增加配置项时，插件会自动为旧配置补充默认值。

```yaml
"!!mirror":
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

### 镜像服条目与继承

第一个镜像服条目是基础配置。后续条目会继承它的值，只需填写需要覆盖的配置。

**示例**

通过`!!mirror2`控制镜像服2，并设置`!!mirror2`的实例id为`abc123`，将`!!mirror2`的服务端名称改为`Mirror2`
```yaml
"!!mirror":
  # ...
"!!mirror2":
  mcsm:
    uuid: abc123
  display:
    server_name: Mirror2
```
你也可以借助YAML的特性来简化配置，例如：
```yaml
"!!mirror":
  # ...
"!!mirror2":
  mcsm.uuid: abc123
  display.server_name: Mirror2
```
其中，在`!!mirror2`中未设置的参数将会自动地从第一个设置的`!!mirror`中继承，例如`!!mirror2`中并未设置`mcsm`的`url`，那么它将继承自`!!mirror`中的`mcsm`的`url`，即`"http://127.0.0.1:23333/"`

完整的示例详见[多镜像服配置文件示例](#多镜像服配置文件示例)

<br>

### root_path / is_mcdr: 镜像服目录与类型
```yaml
root_path: "./Mirror"
is_mcdr: true
```

**root_path** `str`
- 镜像服所在的目录，相对于本服务端的MCDR根目录，也可以使用绝对路径，不能为空。
  - terminal代理在此目录下执行`launch_command`，`!!mirror recover`在此目录中查找镜像服；
  - `is_mcdr`为`true`时，它是镜像服MCDR的目录（其`config.yml`所在目录）。`sync.target`留空时，同步目标为此目录下镜像服MCDR的`working_directory`；同步前备份在此目录中查找镜像服的PrimeBackup；
    - 推导同步目标和查找PrimeBackup时，插件只读取此目录下的`config.yml`。如果镜像服MCDR是用其他配置文件启动的（例如`launch_command`为`python -m mcdreforged start --config custom.yml`），请填写`sync.target`；同步前备份可能找错PrimeBackup，这种情况下不支持同步前备份；
  - `is_mcdr`为`false`时，它是服务端自己的目录。`sync.target`留空时，同步目标就是它本身。

**is_mcdr** `bool`
- 镜像服是否由MCDReforged运行，默认为`true`，普通服务端请设为`false`。设为`false`时，不支持[同步前备份](#syncbackup-同步前备份)，插件也不会在加载时自动接管未跟踪的服务端。
- 它还决定terminal代理如何停止和终止镜像服：Linux代理设置为`true`时，`stop`会向screen输入`!!MCDR server stop_exit`，`kill`在端口已开放时输入`!!MCDR server kill`，否则关闭screen；设置为`false`时，`stop`会输入Minecraft的`stop`命令，`kill`会直接执行强制终止。Windows代理设置为`true`时，`stop`会向命令提示符窗口输入`!!MCDR server stop_exit`，设置为`false`时会输入Minecraft的`stop`命令，`kill`始终强制终止监听端口的进程；镜像服仍在启动、端口尚未开放时，则终止插件启动的全部进程。subprocess代理设置为`true`时，`stop`会发送`!!MCDR server stop_exit`，设置为`false`时会发送Minecraft的`stop`命令，`kill`会直接终止子进程。

<br>

### mcsm: MCSManager配置
此配置部分若有疑问，请参见[MCSManager官方文档](https://docs.mcsmanager.com/#/zh-cn/apis/readme)
```yaml
mcsm:
  enable: false,
  url: "http://127.0.0.1:23333/"
  uuid: 
  remote_uuid: 
  apikey: 
```
启用MCSM后，终端配置会弃用。

**enable** `bool`
- 是否启用MCSM，你需要在配置完成此部分后将此选项设置为`true`。

**url** `str`
- MCSManager面板的访问地址，即请求api的地址。

**uuid** `str`
- 服务端实例的id，即实例显示的UID。

**remote_uuid** `str`
- 远程节点的id，即实例显示的GID。

**apikey** `str`
- 调用API接口必需的密钥，通常在用户界面可以查看。

<br>

### terminal: 通过命令行启动镜像服终端的配置
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
当`proxy_type`为`linux`时，插件会创建一个新的screen；为`windows`时，会创建一个新的命令行终端；为`subprocess`时，会在MCDR进程内启动镜像服子进程。镜像服停止后，Linux/Windows代理创建的screen/终端会自动关闭。

> [!NOTE]
> 如果你无法通过此命令启动镜像服，尝试按以下步骤检查。其中`terminal_name` `launch_command`都为配置文件中对应key的值
> 1. 在`root_path`下执行`launch_command`，并确认能够使镜像服正常启动
> 2. Linux用户检查是否安装了`screen`，Windows用户检查终端中输入`python`是否能正常启动Python
> 3. 若以上两项都不能解决，则在当前服务端的MCDR根目录下执行Linux或Windows代理对应的完整命令，并检查命令回显
>   - Linux `cd "{root_path}"&&screen -dmS {terminal_name}&&screen -x -S {terminal_name} -p 0 -X stuff "{launch_command}&&exit\n"`
>   - Windows `cd /d "{root_path}"&&start cmd.exe /S /C "title {terminal_name}&&{launch_command}"`

其中，`linux`代理通过screen控制镜像服；`windows`代理的`stop`会向监听镜像服端口的进程所在的命令提示符窗口输入停止命令，`kill`会强制终止该进程；`subprocess`代理通过子进程标准输入输出进行控制。所有代理都需要正确配置`port`。MCSM仍可作为替代控制方式。

> [!WARNING]
> Windows代理下的 stop 命令为实验性功能，请自行承担使用风险。

**enable** `bool`
- 是否启用终端，当MCSM未启用且此选项为`true`时将通过终端启动镜像服。

**launch_command** `str`
- 需要执行的启动命令，若简单的启动命令无法满足需求，你可以创建一个`.bat`（或`.sh`）文件，并将启动命令写在该文件中，然后执行该文件。Linux代理下命令过长（约700字节以上）时会被拒绝，同样请改用脚本文件。

**port** `int`
- 镜像服运行的端口，所有代理都必须配置。插件通过此端口检查镜像服状态；Linux/Windows代理还通过它控制进程。未配置时终端代理不可用，帮助信息中的`terminal`会显示为配置错误。

**terminal_name** `str`
- 新命令行终端的标题、新screen的名称，或subprocess代理日志输出使用的前缀。作为screen名称时不能超过64字节，也不能包含控制字符。

> [!IMPORTANT]
> `!!mirror kill -f`和`!!mirror kill --force`适用于所有terminal代理。它会强制终止插件启动并记录的全部进程（Linux代理随后关闭screen）；状态未知时，还会终止占用配置端口、但插件未跟踪的进程。执行前会向执行者列出这些进程，之后只终止列出的进程：执行时（包括确认后）若出现了未列出的进程，则不终止任何进程，需要重新执行查看。若端口被无法读取PID的进程（例如其他用户的进程）占用，则不终止任何进程。请确认`port`配置正确，避免终止其他服务。
>
> 插件只能读取当前用户有权查看的进程。占用端口的进程属于其他用户时，插件可能读不到它的PID，`kill -f`将不终止任何进程。

**proxy_type** `str | null`
- 终端代理类型，替代旧版的`system`配置项。可选值为`linux`、`windows`和`subprocess`。设置为`null`时，将根据当前操作系统自动选择`linux`或`windows`。`subprocess`会在MCDR进程内启动镜像服子进程，并支持通过`!!mirror input`发送指令。

> [!NOTE]
> 使用 `subprocess` 代理启动镜像服 MCDR 实例时，请在镜像服 MCDR 的配置文件中将 `advanced_console` 设置为 `false`。
>
> subprocess代理启动的镜像服是本MCDR的子进程。执行`!!mirror reload`、重载或卸载本插件时，插件会强制终止这样的镜像服。[接管](#接管镜像服)的镜像服不是插件启动的，不会被终止。

**console_log** `bool`
- 是否默认将`subprocess`代理的镜像服控制台日志输出到MCDR控制台。此配置仅对`subprocess`代理生效。

**auto_recover** `bool`
- 插件加载时，如果记录中没有运行的进程，而`root_path`中有未跟踪的MCDR，是否自动接管它，默认为`true`。只有恰好找到一个、且配置的端口空闲或由它及其子进程监听时，插件才会接管，并在控制台列出进程、在游戏内提示一次。其他情况下，以及设置为`false`时，插件只提示，可以用`!!mirror recover`手动接管。`is_mcdr`为`false`时，插件从不自动接管。见[接管镜像服](#接管镜像服)。

**java_name** `str`
- `is_mcdr`为`false`时，插件在`root_path`中查找未跟踪的服务端，只看进程名与此正则表达式匹配的进程，不区分大小写。默认值匹配`java`、`javaw`、`java17`、`java21.exe`等。把Java可执行文件改成了其他名字时，请相应修改。

#### 镜像服状态

插件只根据**记录中的进程**（插件启动或接管的进程）和配置的`port`判断镜像服状态。每次通过terminal代理启动镜像服时，插件都会记录启动的进程，并在之后每次查询状态时把它们新启动的子进程加入记录。记录保存在`config/mirror_mcsmcdr/<指令前缀>/process.json`，重载插件后仍然有效。

> [!IMPORTANT]
> `launch_command`必须在前台运行镜像服，直到镜像服退出才结束。不要在命令或脚本中让镜像服脱离启动它的进程，例如`nohup ... &`、`setsid`、`start`或`screen -dm`。脱离的进程不在记录中，插件无法判断和控制它们。

记录中的进程分为以下几类：
- **MCDR**：`is_mcdr`为`true`时，以`python -m mcdreforged`、`mcdreforged`命令或`python MCDReforged.py`运行的Python进程；
- **服务端**：MCDR启动的进程中，监听`port`的那一个；在端口打开之前，与镜像服MCDR配置文件中`start_command`和`working_directory`一致的那一个也会被认定为服务端；
- **子进程**：MCDR启动、但还没有认定是否为服务端的进程，全部按服务端处理；
- **其他进程**：除此之外的进程，例如MCDR插件启动的进程。

`!!mirror status`会向所有人广播状态，并只向执行者发送详情：MCDR、服务端（或子进程）、其他进程的数量、端口，以及状态的说明和可用的操作。

| 状态 | 含义 | 可用的操作 |
|------|------|------------|
| 已停止 | 记录中的进程都已退出，端口未被占用 | `start`、`sync` |
| 正在启动 | 已发送启动指令，或服务端进程在运行但端口尚未打开，且插件没有见过它打开端口 | `kill`、`kill -f` |
| 正在运行 | 端口由记录中的进程监听 | `stop`、`kill`、`kill -f`；开启`auto_server_restart`时可`sync` |
| 正在停止 | 已发送关闭指令，或服务端关闭了插件见过它打开的端口（例如在镜像服自己的控制台中停服），正在等待进程退出 | `kill`、`kill -f` |
| 服务端已停止, MCDR仍在运行 | 服务端已退出，MCDR空闲或正在退出 | `start`、`stop`、`kill`、`kill -f`；开启`auto_mcdr_stop`时可`sync` |
| 状态未知 | 端口被插件未跟踪的进程占用 | `kill -f` |
| 状态未知 | `root_path`中有未跟踪的MCDR（`is_mcdr`为`false`时为Java进程）在运行（见下文） | `recover` |

`服务端已停止, MCDR仍在运行`时，`start`和`stop`不会再启动一个镜像服，而是向仍在运行的MCDR的控制台输入指令：`start`输入`!!MCDR server start`，在这个MCDR中启动服务端；`stop`输入`!!MCDR server exit`，让MCDR退出。MCDR正在退出时会拒绝启动服务端，此时状态会变为`已停止`。

插件向镜像服控制台输入指令（`start`、`stop`，以及Linux下的`kill`）之前，会再确认一次MCDR（`is_mcdr`为`false`时为服务端）仍在运行，避免指令被启动失败后残留的终端执行。如果状态在此期间发生了变化，回复会说明现在的状态。

状态后还可能附带以下异常：
- **已失去控制台**：记录中的进程仍在运行，但插件已无法向它们发送命令（screen或命令提示符窗口已关闭，或重载插件后subprocess代理失去了子进程）。只能使用`kill -f`；
- **未找到MCDR进程**：`is_mcdr`为`true`，服务端在运行，但记录中没有MCDR进程。可以使用`kill`或`kill -f`；
- **已分离**：启动命令已结束，但screen或终端仍在。可以使用`kill`或`kill -f`。

服务端进程在运行、端口却一直没有打开时，状态会停在`正在启动`。请检查`port`是否与镜像服的`server-port`一致。插件没有见过它打开端口的服务端（例如关闭端口后才被接管的）也可能正在退出，详情中会说明。

> [!WARNING]
> 不是本插件启动的镜像服（例如手动启动的，或旧版本插件启动的）不在记录中：
> - 端口被占用时，状态为`状态未知`，只能用`!!mirror kill -f`终止；
> - 端口未被占用时（镜像服正在启动、正在停止，或服务端已在MCDR内停止），平时的状态检查看不到它。因此`!!mirror status`、`start`和`sync`判断为`已停止`后，会在本机所有进程中查找工作目录为`root_path`的MCDR（`is_mcdr`为`false`时查找Java进程）。找到时状态为`状态未知`，`start`和`sync`会被拒绝。只查找与插件属于同一用户、且能读取到信息的进程。
>
> 这样的镜像服可以用`!!mirror recover`接管，见下文。

#### 接管镜像服

`!!mirror recover`在本机所有进程中查找工作目录为`root_path`、不在记录中的MCDR，把它和它启动的进程写入记录。接管之后，插件像对待自己启动的镜像服一样判断状态、执行`stop`、`kill`和同步。

`is_mcdr`为`false`时，插件查找的是工作目录为`root_path`的Java进程，进程名由[`java_name`](#terminal-通过命令行启动镜像服终端的配置)决定。只监听配置端口、工作目录不是`root_path`的进程不会被接管：端口配置错误时，它可能是别的服务端。这样的镜像服不会在加载时自动接管。

- 只找到一个时，插件会列出它，并要求`!!mirror confirm`确认，确认后只接管列出的这个进程，它已退出时不接管任何进程；找到多个时，插件会列出它们，请用`!!mirror recover <pid>`指定其中一个。指定的PID必须在列出的进程之中，指定PID时不需要确认；
- 配置的端口被这个MCDR及其子进程以外的进程占用时，不会接管；
- 记录中仍有运行的进程时，或同步进行期间，不会接管；
- 插件会找到这个MCDR所在的控制台，之后向其中输入指令：
  - `windows`代理：MCDR所在的控制台窗口；
  - `linux`代理：MCDR所在的screen会话和窗口，可以是用户自己的、有多个窗口的会话；
  - `subprocess`代理，或MCDR不在控制台或screen中：没有控制台，接管后状态带有`已失去控制台`，只能用`kill -f`结束。
- 控制台不属于插件：`kill`和`kill -f`只结束MCDR及其子进程，不关闭用户的命令行窗口或screen会话。

插件加载时也会查找一次，并按[`auto_recover`](#terminal-通过命令行启动镜像服终端的配置)自动接管或只提示。

`recover`默认需要权限等级3，可通过`command.permission.recover`修改。MCSManager不提供此指令。

<br>

### sync: 文件同步相关的配置文件
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
在`sync`中，`./`即指服务端所在的`MCDReforged`根目录，一个可能的目录结构如下：

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

`world`、`extra_patterns`、`ignore_patterns`、`retain_patterns`中的每一项都是一条[gitignore](https://git-scm.com/docs/gitignore)规则，写法与镜像服PrimeBackup中同名（或对应）的设置相同。规则区分大小写，Windows上也一样。以`!`开头的规则用来排除，它自己不选中任何内容。

**world** `list`
- 要同步的世界，与PrimeBackup的`backup.targets`一样，只与源服务端目录第一层条目的名字匹配。直接写目录名即可，如`world`、`world_nether`；也可以写`world*`，或者用`!world_the_end`排除。
- 规则末尾不要加`/`：只匹配名字，`world/`选不中任何目录。
- 只选中目录。被匹配到的第一层文件不会同步，控制台会提示；文件请用`extra_patterns`同步。
- 同步后，目标中的世界与源一致：只存在于目标世界中的文件和目录会被删除（`retain_patterns`匹配到的除外）。
- 一条规则没有选中任何目录时，按`missing.source_world`处理。

**extra_patterns** `list`
- 世界以外要同步的文件或目录，如`config/carpet.conf`、`config/`。路径相对于服务端目录，规则在任意层级匹配；世界内部的匹配不算，世界只由`world`决定。
- 选中的目录与世界一样整体同步，其中的内容不再单独匹配；选中的文件在内容不同时覆盖。只存在于目标中的路径保持原样。目标中缺少的上级目录会自动创建。
- 同一个路径在源服务端是文件、在目标中是目录（或者反过来）时，同步在停止镜像服之前被拒绝。
- 留空时，插件不会遍历世界以外的内容。
- 一条规则没有匹配到任何内容时，按`missing.extra_pattern`处理。

> [!WARNING]
> 不要用`extra_patterns`选中`server.properties`：镜像服的端口等设置会被主服的覆盖。

**source** `str`
- 源服务端目录。留空时使用本MCDR的[工作目录](https://mcdreforged.readthedocs.io/zh-cn/latest/configuration.html#working-directory)（`working_directory`，默认为`server`，每次同步时读取，本MCDR重载配置后也随之变化），通常无需填写。文件由`source/world` 同步至==> `target/world`

**target** `str, list`
- 目标服务端目录, 只有一个目录时可只写字符串, 多个目录需为列表。将会为每个目标目录都同步一份源目录的文件。
- 留空时由[`root_path`](#root_path--is_mcdr-镜像服目录与类型)推导：`is_mcdr`为`true`时，是`root_path`下镜像服MCDR的`working_directory`（每次同步时读取镜像服的`config.yml`，读取失败时同步被拒绝）；`is_mcdr`为`false`时，就是`root_path`。默认配置下为`./Mirror/server`。

**missing**
- 同步设置中写到、但实际不存在的内容如何处理，都在停止镜像服之前判断：
  - `refuse`：拒绝同步，同步记为失败；
  - `skip`：跳过这一项，其余照常同步。游戏内只提示跳过的数量，路径输出到控制台。
- 所有内容都被跳过时，同步被拒绝，不会显示为“文件完全相同”。

| 项 | 情况 | 可选值 | 默认值 |
|---|---|---|---|
| `source_world` | `world`中的一条规则在源服务端没有选中任何目录 | `refuse`；`skip`：目标中同名的世界保持原样 | `refuse` |
| `target` | 目标目录不存在 | `refuse`；`skip`；`create`：只创建最后一级目录，上级目录也不存在时拒绝同步 | `refuse` |
| `target_world` | 目标目录存在，但其中没有要同步的世界 | `create`；`refuse` | `create` |
| `extra_pattern` | `extra_patterns`中的一条规则没有匹配到任何内容 | `skip`；`refuse` | `skip` |

- 目标路径是一个文件时，同步总是被拒绝。
- 源服务端目录、选中的世界和目录，或`extra_patterns`需要遍历的目录无法读取（例如没有权限）时，同步在停止镜像服之前被拒绝，路径和原因输出到控制台。插件只检查选中的世界和目录的第一层；更深层的目录无法读取时，同步在停止镜像服之后出错，镜像服中的内容可能不完整。
- 复制每一项之前，插件会再次确认它在源服务端还存在。停止镜像服之后才消失的，同步中止并记为失败，目标中对应的内容不会被清空；已经复制的内容保留，镜像服中的内容可能不完整。

**concurrency** `int`
- 同步时进行哈希计算的线程数

**ignore_patterns** `list`
- 不同步、并在目标中删除的路径，对应PrimeBackup的`backup.ignore_patterns`。路径相对于服务端目录，只在被同步的世界和`extra_patterns`选中的内容中起作用。默认为`session.lock`。

**retain_patterns** `list`
- 不同步、并保留目标中原有内容的路径，对应PrimeBackup的`backup.retain_patterns`。适合放镜像服自己的设置文件，例如`carpet`模组和`plus-carpet-addition(PCA)`模组的`"carpet.conf"` `"pca.conf"`（规则中不含`/`时在任意层级匹配）。
- 一个路径同时被`ignore_patterns`和`retain_patterns`匹配时，按`retain_patterns`处理。

**backup** 同步前备份，见下文 [sync.backup](#syncbackup-同步前备份)

<br>

### sync.backup: 同步前备份

```yaml
sync:
  backup:
    enable: false
    timeout: 600
    confirm_on_warning: true
```

同步会覆盖镜像服的世界，并删除只存在于镜像服中的文件，而且无法撤销。设置 `backup.enable: true` 后，每次 `!!mirror sync` 都会先通过 PrimeBackup 的命令行工具，用**镜像服自己的** [PrimeBackup](https://github.com/TISUnion/PrimeBackup) 做一次备份：用它的插件文件、它的存储和它的设置，设置完全按镜像服管理员的配置。

有两条规则：
- **没有备份就不同步。** 备份做不了或者失败时，同步被拒绝，不复制任何文件。想不备份就同步，请把 `enable` 改为 `false` 并执行 `!!mirror reload`。
- **备份有多完整，取决于镜像服 PrimeBackup 的设置。** 它应当与同步设置等价。不一致时，插件会给出警告，默认要求确认（见 `confirm_on_warning`），然后按现有设置备份。确认的人即接受：同步覆盖的内容中有一部分不在备份里。

**enable** `bool`
- 每次同步前是否先备份。默认关闭；为 `false` 时插件不会读取镜像服 PrimeBackup 的任何文件，同步行为与没有此功能时相同。
- 镜像服的PrimeBackup在[`root_path`](#root_path--is_mcdr-镜像服目录与类型)中查找。从镜像服文件中读取的路径（`plugin_directories`、`working_directory`，以及 PrimeBackup 的 `storage_root` 和 `source_root`）都相对于 `root_path`，与镜像服 MCDR 自己的解析方式一致。
- `is_mcdr` 为 `false` 时不支持同步前备份：普通服务端没有MCDR，也就没有自己的PrimeBackup。此时开启 `enable` 会让所有同步被拒绝，加载时控制台也会警告，请关闭 `enable`。

**timeout** `int`
- 备份最多可用的秒数。超时的备份会被终止，同步被拒绝。

**confirm_on_warning** `bool`
- 出现下文的警告时，是否必须确认后才同步，即使 `command.action.sync.require_confirm` 为 `false`。默认为 `true`。设为 `false` 时警告仍会显示，是否需要确认只由 `require_confirm` 决定。

**前提条件**
- 镜像服运行在 MCDR 下，且其某个 `plugin_directories` 中装有 `>=1.13.0` 的 PrimeBackup。PrimeBackup 必须恰好只有一个（打包的 `.pyz`/`.mcdr`、目录插件或链接目录插件均可；`.disabled` 的不计入）。
- 镜像服的 PrimeBackup 至少被加载过一次，因此其配置文件 `config/prime_backup/config.json` 和 `storage_root` 中的数据库 `prime_backup.db` 已经存在。
- 命令行工具使用运行本 MCDR 的 Python 解释器启动，因此该解释器必须装有 PrimeBackup 的 Python 依赖（见其 `requirements.txt`）。

**警告**

输入 `!!mirror sync` 时，插件会把镜像服的 PrimeBackup 配置与同步配置做比对。游戏内只显示有几项不一致；详情包含路径，只写入 MCDR 控制台。

| PrimeBackup 设置 | 出现警告的情况 |
|---|---|
| `backup.source_root`；`backup.source_root_use_mcdr_working_directory` 为 `true` 时则是镜像服的 `working_directory` | 它不是已存在的 `sync.target`，或者除它之外还有别的已存在的 `sync.target` 目录 |
| `backup.targets` | `sync.world` 选中的世界和 `sync.extra_patterns` 选中的路径中，有一项的第一层名字没有被它匹配到 |
| `backup.ignore_patterns`、`backup.ignored_files` | 其中有一条规则不在 `sync.ignore_patterns` 或 `sync.retain_patterns` 中 |
| `backup.retain_patterns` | 其中有一条规则不在 `sync.ignore_patterns` 或 `sync.retain_patterns` 中 |
| `backup.reuse_stat_unchanged_file` | 为 `true`：大小和修改时间未变的文件不会被读取 |
| `backup.creation_skip_missing_file` | 为 `true`：备份过程中消失的文件会被跳过 |
| `storage_root` | 位于被同步的路径里面：同步会删除只存在于镜像服中的文件，备份也在其中 |

两个插件都使用默认配置时，不会出现警告。规则按字符串本身比较：写法不同但效果相同的规则（如 `session.lock` 与 `/session.lock`）也会警告。

**启用备份后，一次同步的过程**
1. 输入 `!!mirror sync` 时，先定位镜像服的 PrimeBackup：插件、配置和数据库。缺少任何一项，同步立即被拒绝。接着检查上面的警告；有警告且 `confirm_on_warning` 为 `true` 时，必须确认后才同步。
2. 镜像服必须已停止，镜像服的 MCDR 也必须已经退出（`auto_server_restart`和`auto_mcdr_stop`可以自动停止它，并等到 MCDR 退出）。
3. 由 PrimeBackup 的 `make` 按镜像服的设置做备份，备注为 `MirrorMcsmcdR pre-sync by <操作者>`。
4. `make` 的退出码为 0 且报告了备份编号，备份才算成功。否则拒绝同步，把 PrimeBackup 输出的最后几行写入 MCDR 控制台，并把这次同步记为失败。
5. 广播备份编号，然后保存主服世界。`ensure_server_closed` 为 `true` 时，开始复制前的一刻镜像服必须仍处于停止状态；否则备份已不是最新的，同步被拒绝。
6. `!!mirror history` 会显示每次同步的备份编号，备份之后失败的同步也会显示。

备份和警告只针对同步会覆盖的内容：已存在的目标目录，以及要同步到其中的世界和路径。`missing.target: create` 新建的目标目录不需要备份。如果这些目标目录中都还没有要同步的内容，就没有可丢失的内容：跳过备份，直接同步。

游戏内的消息不包含路径。同步被拒绝时，涉及的路径见 MCDR 控制台。

插件加载和执行 `!!mirror reload` 时，会定位镜像服的 PrimeBackup、运行命令行工具的 `--version` 并检查警告，结果写入控制台。这只用于诊断，不会阻止任何操作，每次同步时都会重新检查。

**恢复**
- 同步前备份是镜像服 PrimeBackup 中的普通备份，没有标签，创建者为 `prime_backup:cli`，只能通过备注识别。
- 恢复时使用镜像服的 PrimeBackup，编号见同步消息或 `!!mirror history`：在镜像服中执行 `!!pb back <编号>`。若配置了 `restore.destination_root`，会恢复到该目录，否则恢复到其备份源目录。
- 旧的同步前备份由镜像服 PrimeBackup 的 prune 设置清理，本插件不会删除任何备份。

**已知限制**
- `ensure_server_closed` 为 `false` 时，插件不检查镜像服是否在运行，命令行工具和镜像服的 PrimeBackup 插件可能同时操作同一份存储。不是本插件启动的镜像服可能被误判为已停止，后果相同（见[镜像服状态](#镜像服状态)）。
- 警告在输入指令时检查。从那时到确认之间配置发生的变化，不会再次警告。
- 内容完全相同的同步也会创建一个备份（PrimeBackup 会去重，但备份列表中会多一项）。
- 每次同步约多花 1 秒；插件加载或重载时，每个启用备份的镜像服约多花 1 秒（`--version`）。
- 插件只采信 `make` 报告的结果，不验证备份能否成功恢复（命令行工具没有校验命令）。
- `--version` 不一定会导入 PrimeBackup 的所有依赖；这种缺失会在第一次 `make` 时暴露，届时同步会被拒绝。
- 因超时而被终止的 `make` 可能在 PrimeBackup 的存储中留下孤立文件，插件不会清理它们。

<br>

### command: 指令配置
```yaml
command:
  permission: # 指令权限配置
  action: # 指令行为配置
```
<br>

### permission: 指令权限配置
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
`int | str`
- 执行各指令所需的最低MCDR权限等级，或设置为`console`以限制只允许控制台执行
<br>

### action: 指令行为配置
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
    require_confirm: true
    ensure_server_closed: true
    auto_server_restart: false
    auto_mcdr_stop: false
    save_world:
      # 保存世界配置
      # ...
  history:
    require_confirm: false
    max_history_count: 5
  confirm:
    timeout: 30
    cancel_anymsg: true
```


### 通用配置

**require_confirm** `bool`
- 当此选项为`true`时, 执行该指令后需要输入`!!mirror confirm`以确认操作
- `start`、`stop`、`kill`和`kill -f`在要求确认之前会先检查镜像服状态, 当前状态下无法执行时直接回复原因, 不再要求确认。确认后执行前会再检查一次

### start / stop配置
**timeout** `int`
- 启动(停止)指令发出后, 镜像服最多需要多少秒完成启动(停止)。在此期间状态显示为`正在启动`(`正在停止`), 超过此时间后插件将重新只根据端口、进程等实际情况判断状态。镜像服启动较慢时请调大`start.timeout`
- 镜像服`正在启动`时无法重载配置文件, 可等待启动完成, 或先执行`!!mirror kill`
- 启用MCSM时状态由MCSM提供, 此选项不影响状态显示
- 同步自动停服(`auto_server_restart`、`auto_mcdr_stop`)后, 最多等待`stop.timeout`秒, 超时则输出`自动关闭失败`及镜像服当前状态, 并向执行者说明仍在等待什么
- 每次启动(包括`!!mirror start`、同步后的重启和`服务端已停止, MCDR仍在运行`时的启动)后, 插件会在后台等待镜像服进入`正在运行`, 然后广播`已启动`。如果在此之前镜像服变为`已停止`、`状态未知`或出现异常, 或超过`start.timeout`秒仍未进入`正在运行`, 则广播`启动未完成`及当前状态, 并向执行者说明详情。使用MCSManager时, 面板报告的`已停止`和`状态未知`(实例忙碌)可能只是暂时的, 插件会继续等待到超时; 同步自动停服时, 面板报告的`状态未知`同样会继续等待

### check_status_interval
**check_status_interval** `int`
- 等待镜像服状态变化(例如同步前等待其停止, 启动后等待其运行)时, 两次完整检查状态之间的最长间隔(秒)。记录中的进程一退出, 或开始、停止监听配置的端口(每秒查看一次), 插件就会立即检查, 不必等满这个间隔; 新启动的服务端进程要到下一次完整检查才会被看到。启用MCSM时按此间隔查询MCSM

### sync配置
同步进行期间（从自动停服、等待、备份、复制到同步后的重启），`!!mirror start`会被拒绝，以免镜像服在复制过程中启动。`stop`、`kill`和`kill -f`不受影响。

**ensure_server_closed** `bool`
- 当此选项为`true`时, 同步时将会检查镜像服是否已停止。镜像服必须为`已停止`才能同步。`服务端已停止, MCDR仍在运行`时, 未开启`auto_mcdr_stop`则拒绝同步，需等待MCDR退出，或使用`!!mirror stop`让MCDR退出、使用`!!mirror kill`终止MCDR。当此选项为`false`时, 无论镜像服是否停止, 都将直接进行同步。

**auto_server_restart** `bool`
- 此选项仅在`ensure_server_closed`为`true`时生效。当此选项为`true`时, 如果同步时镜像服`正在运行`, 那么将在尝试自动停止镜像服、等待MCDR也退出后进行同步, 并在同步完成后自动重启镜像服。等待时间见`stop.timeout`

**auto_mcdr_stop** `bool`
- 此选项仅在`ensure_server_closed`为`true`时生效。当此选项为`true`时, 如果同步时镜像服为`服务端已停止, MCDR仍在运行`, 那么将让MCDR退出后进行同步。同步完成后不会重启, 因为同步前服务端本来就没有运行。等待时间见`stop.timeout`

**save_world** 保存世界配置 *一般无需更改*
```yaml
save_world:
  turn_off_auto_save: true
  commands:
    save_all_worlds: save-all flush
    auto_save_off: save-off
    auto_save_on: save-on
  saved_world_regex: '^Saved the game$'
  save_world_max_wait_sec: 60
```
**turn_off_auto_save** `bool`
- 保存世界时关闭自动保存

**commands** 相关指令
- **save_all_worlds** `str`
  + 保存世界的指令
- **auto_save_off** `str`
  + 关闭自动保存的指令
- **auto_save_on** `str`
  + 开启自动保存的指令

**saved_world_regex** `str`
- 匹配服务端"世界保存完成"日志的正则表达式

**save_world_max_wait_sec** `int`
- 保存世界的最大等待时间(秒)，超时将会跳过世界保存并进行同步

### history配置

**max_history_count** `int`
- 最多保存多少条同步历史。设置为`-1`以不限制最大数量，设置为`0`以禁用同步历史功能。默认最多保存`5`条

### confirm配置
玩家只能确认自己执行的指令

**timeout** `int`
- 需确认的指令经过多少秒后超时取消。若执行某指令后超过`timeout`秒后, 该玩家未进行任何操作, 则此指令超时，自动取消

**cancel_anymsg** `bool`
- 若玩家执行某指令后发送了除`confirm`指令外的消息, 则此指令操作自动取消。除此之外, 若玩家执行了某指令后又执行了对应镜像服的其他指令, 则先前执行的指令自动取消

<br>

### display: 显示配置
```yaml
display:
  server_name: Mirror
  protected_process_info: []
```
**server_name** `str`
- "镜像服"的名称，用以在显示时区分不同的镜像服

**protected_process_info** `list`
- 游戏内消息中不显示的进程信息，可选`name`（进程名）和`pid`，默认为空。它影响`kill -f`列出的进程和`status`提到的进程。两项都填写时只显示进程数量。控制台始终显示进程名、PID和命令行；命令行和路径在任何情况下都不会出现在游戏内消息中。

<br>

### 多镜像服配置文件示例


```yaml
'!!mirror':
  root_path: ./Mirror
  is_mcdr: true

  mcsm:
    enable: true
    url: http://127.0.0.1:23333/
    uuid: 71154??????????0a1a2f4dd90695609
    remote_uuid: 6e927??????????999f0e66bc404071b
    apikey: b8f???????????????????????????ade

  terminal:
    enable: false
    launch_command: python -m mcdreforged
    port:
    terminal_name: Mirror
    proxy_type:
    console_log: false
    auto_recover: true
    java_name: '^javaw?\d*(\.exe)?$'

  sync:
    world:
    - world
    extra_patterns: []
    source: ''
    target: []
    missing:
      source_world: refuse
      target: refuse
      target_world: create
      extra_pattern: skip
    concurrency: 4
    ignore_patterns:
    - session.lock
    retain_patterns: []

  command:
    permission:
      status: 0
      start: 0
      stop: 2
      kill: 3
      sync: 2
      history: 0
      confirm: 0
      log: console
      input: console
      recover: 3
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
        require_confirm: true
        ensure_server_closed: true
        auto_server_restart: true
        auto_mcdr_stop: false
        save_world:
          turn_off_auto_save: true
          commands:
            save_all_worlds: save-all flush
            auto_save_off: save-off
            auto_save_on: save-on
          saved_world_regex: ^Saved the game$
          save_world_max_wait_sec: 60
      history:
        require_confirm: false
        max_history_count: 5
      confirm:
        timeout: 30
        cancel_anymsg: true

  display:
    server_name: Mirror

'!!mirror2':
  root_path: ./Mirror2
  mcsm:
    uuid: 83011??????????49c1133fc08a41b80
  display:
    server_name: Mirror2

'!!mirror3':
  root_path: ./Mirror3
  mcsm.enable: false
  terminal:
    enable: true
    port: 30002
    terminal_name: Mirror3
  display.server_name: Mirror3
```

后续条目会继承第一个条目的`root_path`，因此每个镜像服都要填写自己的`root_path`。

## 致谢

- 哈希比对思路 / [better_backup](https://github.com/z0z0r4/better_backup)
- 配置文件权限配置思路 / [PrimeBackup](https://github.com/TISUnion/PrimeBackup)
- 保存世界思路 / [QuickBackupM](https://github.com/TISUnion/QuickBackupM)

## ToDo

- [x] 指令执行确认
- [ ] 指令执行延迟
- [ ] 禁止同步`!!mirror sync enable/disable reason`
- [x] lang语言文件
- [ ] 指令禁用
- [x] 无MCSM下通过命令行启动服务端
- [x] Linux/Windows通过终端执行`kill`指令
- [x] 历史同步记录显示
