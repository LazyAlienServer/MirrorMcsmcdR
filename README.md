# MirrorMcsmcdR

[![MCDR](https://img.shields.io/badge/MCDR-%E2%89%A52.6.0-blue)](https://github.com/Fallen-Breath/MCDReforged) [![许可证](https://img.shields.io/github/license/LazyAlienServer/MirrorMcsmcdR)](./LICENSE) [![下载量](https://img.shields.io/github/downloads/LazyAlienServer/MirrorMcsmcdR/total)](https://github.com/LazyAlienServer/MirrorMcsmcdR/releases)

中文 · [English](./README_en.md)

> 最全面的 [MCDReforged](https://github.com/Fallen-Breath/MCDReforged) 镜像服控制插件！通过多种方式控制镜像服，并使用基于哈希的增删同步。

## 特性

- **多种方式控制与启停**：
  - 支持通过[MCSManager](https://github.com/MCSManager/MCSManager)控制镜像服（`MCSM-v9.9.0` `MCSM-v10.2.1+`）
  - 支持直接通过终端启动与停止镜像服（`Linux` `Windows`），并且新终端与父MCDR进程互不干扰，便于运维管理
    - Linux 通过`screen`控制镜像服
    - Windows 通过新命令行终端控制镜像服
  - 支持通过`subprocess`在MCDR进程内启动镜像服子进程，并通过标准输入输出控制镜像服
  - 支持通过`!!mirror execute <command>`向镜像服发送指令
  - 支持多种控制方式的组合使用，例如：
    - 通过 MCDR 启动与停止镜像服，当镜像服进程异常时，通过 Linux 强制终止镜像服
- **完善的控制功能**：完善的**多镜像服**控制操作，获取运行状态/启动/停止/强制终止/同步操作
- **基于哈希的文件同步**：基于哈希的文件同步，只同步镜像服与源服务端不同的文件，提升速度并减少磁盘IO
- **同步前备份**：可选在每次同步前用镜像服自己的 PrimeBackup 备份镜像服世界，没有成功的备份就不同步
- **高度可自定义的配置文件**：使用YAML格式，提供高可自定义的、配置友好配置文件，多个镜像服配置时只需要书写变化的值

> [!NOTE]
> 本插件不提供服务端创建/管理功能，请在镜像服创建完成并创建对应的MCSManager实例后再使用本插件。同样，本插件不提供镜像服启动/关闭成功的提示信息，建议搭配vchat等插件使用。

## 依赖

| 依赖                | 说明                                                                                      |
|---------------------|-------------------------------------------------------------------------------------------|
| Python              | `>=3.10`                                                                                  |
| Python 包           | `xxhash>=3`                                                                               |
| Linux terminal 代理 | `proxy_type` 为 `linux` 或 `null` 时需要 [`screen`](https://www.gnu.org/software/screen/) |
| PrimeBackup         | 镜像服 MCDR 中需要 `>=1.13.0`，仅在启用[同步前备份](#syncbackup-同步前备份)时需要                    |

## 从v1.8.0及更早版本升级

升级前请先手动停止镜像服。新版本只认识自己启动并记录的进程，旧版本启动的镜像服不在记录中（见[镜像服状态](#镜像服状态)）。

升级后请检查配置文件：
- `rcon`配置已删除，旧配置中的`rcon`会被忽略。需要跨主机控制镜像服时，请使用MCSManager；
- `terminal.regex_strict`已删除。配置的端口被任何不是插件启动的进程占用时，状态都显示为`状态未知`；
- `subprocess`代理现在也必须配置`terminal.port`，未配置时terminal代理不可用。

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
| `!!mirror sync`                         | 同步文件                            |
| `!!mirror confirm`                      | 确认待执行操作                      |
| `!!mirror reload`                       | 热重载镜像服配置                    |
| `!!mirror history`                      | 查看同步历史                        |
| `!!mirror execute <command>`            | 通过 subprocess 代理发送指令        |
| `!!mirror log`                          | 查看 subprocess 控制台日志状态      |
| `!!mirror log enable\|disable\|<count>` | 启用、禁用或限制控制台日志输出      |

## 配置文件

> [!TIP]
> 配置文件较长，建议先阅读[快速开始](./docs/quickstart.md)，再将下文作为配置参考。

配置文件支持热重载和自动补全。新版本增加配置项时，插件会自动为旧配置补充默认值。

```yaml
"!!mirror":
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
  launch_path: "./Mirror"
  launch_command: "python -m mcdreforged"
  port: 
  terminal_name: "Mirror"
  is_mcdr: true
  proxy_type: 
  console_log: false
```
当`proxy_type`为`linux`时，插件会创建一个新的screen；为`windows`时，会创建一个新的命令行终端；为`subprocess`时，会在MCDR进程内启动镜像服子进程。镜像服停止后，Linux/Windows代理创建的screen/终端会自动关闭。

> [!NOTE]
> 如果你无法通过此命令启动镜像服，尝试按以下步骤检查。其中`terminal_name` `launch_command`都为配置文件中对应key的值
> 1. 在`launch_path`下执行`launch_command`，并确认能够使镜像服正常启动
> 2. Linux用户检查是否安装了`screen`，Windows用户检查终端中输入`python`是否能正常启动Python
> 3. 若以上两项都不能解决，则在当前服务端的MCDR根目录下执行Linux或Windows代理对应的完整命令，并检查命令回显
>   - Linux `cd "{launch_path}"&&screen -dmS {terminal_name}&&screen -x -S {terminal_name} -p 0 -X stuff "{launch_command}&&exit\n"`
>   - Windows `cd /d "{launch_path}"&&start cmd.exe /S /C "title {terminal_name}&&{launch_command}"`

其中，`linux`代理通过screen控制镜像服；`windows`代理的`stop`会向监听镜像服端口的进程所在的命令提示符窗口输入停止命令，`kill`会强制终止该进程；`subprocess`代理通过子进程标准输入输出进行控制。所有代理都需要正确配置`port`。MCSM仍可作为替代控制方式。

> [!WARNING]
> Windows代理下的 stop 命令为实验性功能，请自行承担使用风险。

**enable** `bool`
- 是否启用终端，当MCSM未启用且此选项为`true`时将通过终端启动镜像服。

**launch_path** `str`
- 执行启动命令的路径，通常为镜像服所在的目录。

**launch_command** `str`
- 需要执行的启动命令，若简单的启动命令无法满足需求，你可以创建一个`.bat`（或`.sh`）文件，并将启动命令写在该文件中，然后执行该文件。Linux代理下命令过长（约700字节以上）时会被拒绝，同样请改用脚本文件。

**port** `int`
- 镜像服运行的端口，所有代理都必须配置。插件通过此端口检查镜像服状态；Linux/Windows代理还通过它控制进程。未配置时终端代理不可用，帮助信息中的`terminal`会显示为配置错误。

**terminal_name** `str`
- 新命令行终端的标题、新screen的名称，或subprocess代理日志输出使用的前缀。作为screen名称时不能超过64字节，也不能包含控制字符。

**is_mcdr** `bool`
- 是否通过MCDReforged启动镜像服，默认为`true`。Linux代理设置为`true`时，`stop`会向screen输入`!!MCDR server stop_exit`，`kill`在端口已开放时输入`!!MCDR server kill`，否则关闭screen；设置为`false`时，`stop`会输入Minecraft的`stop`命令，`kill`会直接执行强制终止。Windows代理设置为`true`时，`stop`会向命令提示符窗口输入`!!MCDR server stop_exit`，设置为`false`时会输入Minecraft的`stop`命令，`kill`始终强制终止监听端口的进程；镜像服仍在启动、端口尚未开放时，则终止插件启动的全部进程。subprocess代理设置为`true`时，`stop`会发送`!!MCDR server stop_exit`，设置为`false`时会发送Minecraft的`stop`命令，`kill`会直接终止子进程。

> [!IMPORTANT]
> `!!mirror kill -f`和`!!mirror kill --force`适用于所有terminal代理。它会强制终止插件启动并记录的全部进程（Linux代理随后关闭screen）；状态未知时，还会终止占用配置端口、但不是插件启动的进程。执行前会向执行者列出这些进程。若端口被无法读取PID的进程（例如其他用户的进程）占用，则不终止任何进程。请确认`port`配置正确，避免终止其他服务。
>
> 插件只能读取当前用户有权查看的进程。占用端口的进程属于其他用户时，插件可能读不到它的PID，`kill -f`将不终止任何进程。

**proxy_type** `str | null`
- 终端代理类型，替代旧版的`system`配置项。可选值为`linux`、`windows`和`subprocess`。设置为`null`时，将根据当前操作系统自动选择`linux`或`windows`。`subprocess`会在MCDR进程内启动镜像服子进程，并支持通过`!!mirror execute`发送指令。

> [!NOTE]
> 使用 `subprocess` 代理启动镜像服 MCDR 实例时，请在镜像服 MCDR 的配置文件中将 `advanced_console` 设置为 `false`。
>
> subprocess代理启动的镜像服是本MCDR的子进程。执行`!!mirror reload`、重载或卸载本插件时，插件会强制终止这样的镜像服。

**console_log** `bool`
- 是否默认将`subprocess`代理的镜像服控制台日志输出到MCDR控制台。此配置仅对`subprocess`代理生效。

#### 镜像服状态

插件只根据**自己启动的进程**和配置的`port`判断镜像服状态。每次通过terminal代理启动镜像服时，插件都会记录启动的进程，并在之后每次查询状态时把它们新启动的子进程加入记录。记录保存在`config/mirror_mcsmcdr/<指令前缀>/process.json`，重载插件后仍然有效。

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
| 正在启动 | 已发送启动指令，或服务端进程在运行但端口尚未打开 | `kill`、`kill -f` |
| 正在运行 | 端口由记录中的进程监听 | `stop`、`kill`、`kill -f`；开启`auto_server_restart`时可`sync` |
| 正在停止 | 已发送关闭指令，正在等待进程退出 | `kill`、`kill -f` |
| 服务端已停止, MCDR仍在运行 | 服务端已退出，MCDR空闲或正在退出 | `start`、`stop`、`kill`、`kill -f` |
| 状态未知 | 端口被不是插件启动的进程占用 | `kill -f` |

`服务端已停止, MCDR仍在运行`时，`start`和`stop`不会再启动一个镜像服，而是向仍在运行的MCDR的控制台输入指令：`start`输入`!!MCDR server start`，在这个MCDR中启动服务端；`stop`输入`!!MCDR server exit`，让MCDR退出。MCDR正在退出时会拒绝启动服务端，此时状态会变为`已停止`。

插件向镜像服控制台输入指令（`start`、`stop`，以及Linux下的`kill`）之前，会再确认一次MCDR（`is_mcdr`为`false`时为服务端）仍在运行，避免指令被启动失败后残留的终端执行。如果状态在此期间发生了变化，回复会说明现在的状态。

状态后还可能附带以下异常：
- **已失去控制台**：记录中的进程仍在运行，但插件已无法向它们发送命令（screen或命令提示符窗口已关闭，或重载插件后subprocess代理失去了子进程）。只能使用`kill -f`；
- **未找到MCDR进程**：`is_mcdr`为`true`，服务端在运行，但记录中没有MCDR进程。可以使用`kill`或`kill -f`；
- **已分离**：启动命令已结束，但screen或终端仍在。可以使用`kill`或`kill -f`。

服务端进程在运行、端口却一直没有打开时，状态会停在`正在启动`。请检查`port`是否与镜像服的`server-port`一致。

> [!WARNING]
> 不是本插件启动的镜像服（例如手动启动的，或旧版本插件启动的）不在记录中：
> - 端口被占用时，状态为`状态未知`，只能用`!!mirror kill -f`终止；
> - 端口未被占用时（镜像服正在启动、正在停止，或服务端已在MCDR内停止），状态会显示为`已停止`。此时`start`会再启动一个镜像服，`sync`会直接写入正在使用的世界。
>
> 因此，请只通过本插件启动镜像服。

<br>

### sync: 文件同步相关的配置文件
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

**world** `list`
- 需要同步的目录，当存档有多个世界文件时需要添加

**source** `str`
- 源服务端目录，通常应为MCDR的[工作目录](https://mcdreforged.readthedocs.io/zh-cn/latest/configuration.html#working-directory)，即默认情况下的`server`目录。文件由`source/world` 同步至==> `target/world`

**target** `str, list`
- 目标服务端目录, 只有一个目录时可只写字符串, 多个目录需为列表。将会为每个目标目录都同步一份源目录的文件。默认情况下镜像服的MCDR工作目录位于当前MCDR的根目录下的`Mirror`目录。

**ignore_inexistent_target_path** `bool`
- 若某个目标服务端目录不存在，当设置为`false`时，将会跳过对该目录的同步。当设置为`true`时，将会新建该目录并继续同步

**concurrency** `int`
- 同步时进行哈希计算的线程数

**ignore_files** `list`
- 不进行同步的文件，若使用`carpet`模组和`plus-carpet-addition(PCA)`模组，建议添加`"carpet.conf"` `"pca.conf"`

**backup** 同步前备份，见下文 [sync.backup](#syncbackup-同步前备份)

<br>

### sync.backup: 同步前备份

```yaml
sync:
  backup:
    enable: false
    mcdr_path: ""
    timeout: 600
    confirm_on_warning: true
```

同步会覆盖镜像服的世界，并删除只存在于镜像服中的文件，而且无法撤销。设置 `backup.enable: true` 后，每次 `!!mirror sync` 都会先通过 PrimeBackup 的命令行工具，用**镜像服自己的** [PrimeBackup](https://github.com/TISUnion/PrimeBackup) 做一次备份：用它的插件文件、它的存储和它的设置，设置完全按镜像服管理员的配置。

有两条规则：
- **没有备份就不同步。** 备份做不了或者失败时，同步被拒绝，不复制任何文件。想不备份就同步，请把 `enable` 改为 `false` 并执行 `!!mirror reload`。
- **备份有多完整，取决于镜像服 PrimeBackup 的设置。** 它应当与同步设置等价。不一致时，插件会给出警告并要求确认，然后按现有设置备份。确认的人即接受：同步覆盖的内容中有一部分不在备份里。

**enable** `bool`
- 每次同步前是否先备份。默认关闭；为 `false` 时插件不会读取镜像服的任何文件，同步行为与没有此功能时相同。

**mcdr_path** `str`
- 镜像服 MCDR 的目录，即其 `config.yml` 所在的目录。与 `sync.target` 一样，相对于本服务端的 MCDR 根目录。留空时，若 `terminal.enable` 为 `true` 则使用 `terminal.launch_path`，否则必须填写。
- 从镜像服文件中读取的路径（`plugin_directories`、`working_directory`，以及 PrimeBackup 的 `storage_root` 和 `source_root`）都相对于 `mcdr_path`，与镜像服 MCDR 自己的解析方式一致。

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
| `backup.source_root`；`backup.source_root_use_mcdr_working_directory` 为 `true` 时则是镜像服的 `working_directory` | 它不是 `sync.target`，或者除它之外还有别的 `sync.target` 目录 |
| `backup.targets` | `sync.world` 中有一项没有被它匹配到 |
| `backup.ignore_patterns`、`backup.ignored_files` | 其中有 `sync.ignore_files` 里没有的规则 |
| `backup.retain_patterns` | 不为空 |
| `backup.reuse_stat_unchanged_file` | 为 `true`：大小和修改时间未变的文件不会被读取 |
| `backup.creation_skip_missing_file` | 为 `true`：备份过程中消失的文件会被跳过 |
| `storage_root` | 位于被同步的世界目录里面：同步会删除只存在于镜像服中的文件，备份也在其中 |

两个插件都使用默认配置时，不会出现警告。

**启用备份后，一次同步的过程**
1. 输入 `!!mirror sync` 时，先定位镜像服的 PrimeBackup：插件、配置和数据库。缺少任何一项，同步立即被拒绝。接着检查上面的警告，有警告时必须确认后才同步。
2. 镜像服必须已停止，与以前相同（`auto_server_restart` 可以自动停止它）。
3. 由 PrimeBackup 的 `make` 按镜像服的设置做备份，备注为 `MirrorMcsmcdR pre-sync by <操作者>`。
4. `make` 的退出码为 0 且报告了备份编号，备份才算成功。否则拒绝同步，把 PrimeBackup 输出的最后几行写入 MCDR 控制台，并把这次同步记为失败。
5. 广播备份编号，然后保存主服世界。`ensure_server_closed` 为 `true` 时，开始复制前的一刻镜像服必须仍处于停止状态；否则备份已不是最新的，同步被拒绝。
6. `!!mirror history` 会显示每次同步的备份编号，备份之后失败的同步也会显示。

如果所有目标目录中都还没有要同步的世界，就没有可丢失的内容：跳过备份，直接同步。

游戏内的消息不包含路径。同步被拒绝时，涉及的路径见 MCDR 控制台。

插件加载和执行 `!!mirror reload` 时，会定位镜像服的 PrimeBackup、运行命令行工具的 `--version` 并检查警告，结果写入控制台。这只用于诊断，不会阻止任何操作，每次同步时都会重新检查。

**恢复**
- 同步前备份是镜像服 PrimeBackup 中的普通备份，没有标签，创建者为 `prime_backup:cli`，只能通过备注识别。
- 恢复时使用镜像服的 PrimeBackup，编号见同步消息或 `!!mirror history`：在镜像服中执行 `!!pb back <编号>`。若配置了 `restore.destination_root`，会恢复到该目录，否则恢复到其备份源目录。
- 旧的同步前备份由镜像服 PrimeBackup 的 prune 设置清理，本插件不会删除任何备份。

**已知限制**
- 自动停服（`auto_server_restart`）后会立刻开始备份。如果镜像服的 MCDR 还在退出、它的 PrimeBackup 仍占用着数据库，`make` 会失败，同步被拒绝，镜像服照常被重新启动。请重新执行同步，或者先停止镜像服再同步。
- 插件不检查镜像服的 MCDR 是否在运行。`ensure_server_closed` 为 `false`，或者镜像服的服务端停止后 MCDR 仍在运行时，命令行工具和镜像服的 PrimeBackup 插件可能同时操作同一份存储。
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
  abort: 0
  log: "console"
  execute: "console"
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
  kill:
    require_confirm: true
  sync:
    require_confirm: true
    ensure_server_closed: true
    auto_server_restart: false
    check_status_interval: 5
    max_attempt_times: 3
    save_world:
      # 保存世界配置
      # ...
  history:
    require_confirm: false
    max_history_count: 5
  confirm:
    timeout: 30
    cancel_anymsg: true
  abort:
    operator: everyone
```


### 通用配置

**require_confirm** `bool`
- 当此选项为`true`时, 执行该指令后需要输入`!!mirror confirm`以确认操作

### start / stop配置
**timeout** `int`
- 启动(停止)指令发出后, 镜像服最多需要多少秒完成启动(停止)。在此期间状态显示为`正在启动`(`正在停止`), 超过此时间后插件将重新只根据端口、进程等实际情况判断状态。镜像服启动较慢时请调大`start.timeout`
- 镜像服`正在启动`时无法重载配置文件, 可等待启动完成, 或先执行`!!mirror kill`
- 启用MCSM时状态由MCSM提供, 此选项不影响状态显示

### sync配置
**ensure_server_closed** `bool`
- 当此选项为`true`时, 同步时将会检查镜像服是否已停止。镜像服必须为`已停止`才能同步，`服务端已停止, MCDR仍在运行`时也会拒绝同步，需等待MCDR退出，或使用`!!mirror stop`让MCDR退出、使用`!!mirror kill`终止MCDR。当此选项为`false`时, 无论镜像服是否停止, 都将直接进行同步。

**auto_server_restart** `bool`
- 此选项仅在`ensure_server_closed`为`true`时生效。当此选项为`true`时, 如果同步时镜像服`正在运行`, 那么将在尝试自动停止镜像服、等待MCDR也退出后进行同步, 并在同步完成后自动重启镜像服

**check_status_interval** `int`
- 此选项仅在`auto_server_restart`生效时生效。同步时停止镜像服后, 插件需确认镜像服是否已停止。此选项为检查镜像服状态的时间间隔

**max_attempt_times** `int`
- 此选项仅在`auto_server_restart`生效时生效。检查镜像服状态的尝试次数, 超过此尝试次数后将不再尝试检查镜像服状态, 并输出`自动关闭失败`及镜像服当前状态信息, 同时向执行者说明仍在等待什么。等效于超时时间 `timeout = check_status_interval * max_attempt_times`

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

### abort配置
~此功能仍在开发~

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
  mcsm:
    enable: true
    url: http://127.0.0.1:23333/
    uuid: 71154??????????0a1a2f4dd90695609
    remote_uuid: 6e927??????????999f0e66bc404071b
    apikey: b8f???????????????????????????ade

  terminal:
    enable: false
    launch_path: ./Mirror
    launch_command: python -m mcdreforged
    port:
    terminal_name: Mirror
    is_mcdr: true
    proxy_type:
    console_log: false

  sync:
    world:
    - world
    source: ./server
    target:
    - ./Mirror/server
    ignore_inexistent_target_path: false
    concurrency: 4
    ignore_files:
    - session.lock

  command:
    permission:
      status: 0
      start: 0
      stop: 2
      kill: 3
      sync: 2
      history: 0
      confirm: 0
      abort: 0
      log: console
      execute: console
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
        check_status_interval: 5
        max_attempt_times: 3
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
      abort:
        operator: everyone

  display:
    server_name: Mirror

'!!mirror2':
  mcsm:
    uuid: 83011??????????49c1133fc08a41b80
  sync:
    target:
    - ./Mirror2/server
  display:
    server_name: Mirror2

'!!mirror3':
  mcsm.enable: false
  sync.target:
    - ./Mirror3/server
  terminal:
    enable: true
    launch_path: ./Mirror3
    port: 30002
    terminal_name: Mirror3
  display.server_name: Mirror3
```

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
