# MirrorMcsmcdR
一个**~超级完善的~**[MCDR](https://github.com/Fallen-Breath/MCDReforged)插件，基于[MCSM](https://github.com/MCSManager/MCSManager)对镜像服进行控制与进行文件同步

~CMD支持在写了, 所以都给我去用MCSM谢谢喵~

## 特性

- 插件的功能基于[MCSManager](https://github.com/MCSManager/MCSManager)
  + 测试基于mcsm9.9, 不保证完全支持mcsm10
- 完善的**多镜像服**控制操作，通过mcsm获取运行状态/启动/停止/强制终止/同步
- 基于哈希的文件同步，只同步镜像服与源服务端不同的文件
- 高可自定义的、配置友好配置文件，多个镜像服配置时只需要书写变化的值

**\[注意\]** 本插件不提供服务端创建/管理功能，请在镜像服创建完成并创建对应的MCSManager实例后再使用本插件。同样，本插件不提供镜像服启动/关闭成功的提示信息，建议搭配vchat等插件使用。

## 依赖

`xxhash>=3`

## 指令

指令前缀默认为`!!mirror`, 控制多个镜像服时将通过指令前缀区分, 详见[配置文件](#"!!mirror")

`!!mirror` 显示指令帮助

`!!mirror help` 显示指令帮助

`!!mirror status` 获取镜像服实例运行状态，状态未知/已停止/正在停止/正在启动/正在运行

`!!mirror start` 启动镜像服实例

`!!mirror stop` 停止镜像服实例

`!!mirror kill` 强制终止镜像服实例

`!!mirror sync` 进行文件同步

`!!mirror confirm` 确认某指令的操作

`!!mirror reload` 热重载对应镜像服的配置文件

## 配置文件

配置文件在`v1.1.0`支持了热重载, 同时添加了更完善的属性补全功能。当新版本的配置文件中新增了某一选项, 插件将会自动将默认值填写到你的旧配置文件中, 而不需要手动添加。

### 默认配置文件
```
{
    "!!mirror": {
        "mcsm": {
            "enable": true,
            "url": "http://127.0.0.1:23333/",
            "uuid": null,
            "remote_uuid": null,
            "apikey": null
        },
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
        },
        "command": {
            "permission": {
                "status": 0,
                "start": 0,
                "stop": 2,
                "kill": 3,
                "sync": 2
            },
            "action": {
                "start": {
                    "enable_cmd": false,
                    "path": "./Mirror",
                    "command": "python -m mcdreforged",
                    "require_confirm": false
                },
                "stop": {
                    "require_confirm": true
                },
                "kill": {
                    "require_confirm": true
                },
                "sync": {
                    "ensure_server_closed": true,
                    "auto_server_restart": false,
                    "check_status_interval": 5,
                    "max_attempt_times": 3,
                    "require_confirm": true
                },
                "confirm": {
                    "timeout": 30,
                    "cancel_anymsg": true
                },
                "abort": {
                    "operator": "everyone"
                }
            }
        },
        "display": {
            "server_name": "Mirror"
        },
        "server": {
            "turn_off_auto_save": true,
            "commands": {
                "save_all_worlds": "save-all flush",
                "auto_save_off": "save-off",
                "auto_save_on": "save-on"
            },
            "saved_world_regex": "^Saved the game$",
            "save_world_max_wait_sec": 60
        }
    }
}
```

### "!!mirror"
在此参数下配置该镜像服的所有配置，同时，此参数也是控制该镜像服的指令前缀。

要添加新的镜像服，如需要通过`!!mirror2`控制镜像服2，在配置文件中再添加一个`"!!mirror2"`即可。

配置文件中的第一个镜像服设置的参数将同时被设置为默认配置，在之后的镜像服的配置文件中，只需要写变化的参数值即可。

**例**

镜像服1为`!!mirror`，同时也是其他镜像服的默认配置文件，那么将`!!mirror`放在配置文件中的第一个

通过`!!mirror2`控制镜像服2，并设置`!!mirror2`的实例id为`abc123`，将`!!mirror2`的服务端名称改为`Mirror2`
```
{
    "!!mirror": {
        ...
    },
    "!!mirror2": {
        "mcsm": {
            "uuid": "abc123"
        },
        "display": {
            "server_name": "Mirror2"
        }
    }
}
```
其中，在`!!mirror2`中未设置的参数将会自动地从第一个设置的`!!mirror`中继承，例如`!!mirror2`中并未设置`mcsm`的`url`，那么它将继承自`!!mirror`中的`mcsm`的`url`，即`"http://127.0.0.1:23333/"`

完整的示例详见[多镜像服配置文件示例](#多镜像服配置文件示例)

<br>

### mcsm: MCSManager面板相关的配置文件
此配置部分若有疑问，请参见[MCSManager官方文档](https://docs.mcsmanager.com/#/zh-cn/apis/readme)
|参数|类型|解释|
|---|---|---|
| enable | bool | 启用MCSM-API，你需要在配置完成此部分后将此选项设置为`true` |
| url | str | MCSManager面板的访问地址，即请求api的地址 |
| uuid | str | 服务端实例的id，即实例显示的UID |
| remote_uuid | str | 远程节点的id，即实例显示的GID |
| apikey | str | 调用API接口必需的密钥，通常在用户界面可以查看 |

<br>

### sync: 文件同步相关的配置文件
|参数|类型|解释|
|---|---|---|
| world | list | 需要同步的目录，当存档有多个世界文件时需要添加 |
| source | str | 源服务端目录，source/world -> target/world |
| target | str/list | 目标服务端目录, 只有一个目录时可只写字符串, 多个目录需为列表。将会为每个目标目录都同步一份源目录的文件 |
| ignore_inexistent_target_path | bool | 若某个目标服务端目录不存在，当设置为`false`时，将会跳过对该目录的同步。当设置为`true`时，将会新建该目录并继续同步 |
| concurrency | int | 同步时进行哈希计算的线程数 |
| ignore_files | list | 不进行同步的文件 |

<br>

### command: 指令相关的配置文件
|参数|类型|解释|
|---|---|---|
| permission | dict | 各指令所需的最低的MCDR权限等级 |
| action || 控制指令执行时的部分行为 |

<br>

#### action: 控制指令执行时的部分行为

**通用设置**
|参数|类型|解释|
|---|---|---|
| require_confirm | bool | 当此选项为`true`时, 执行该指令后需要输入`!!mirror confirm`以确认操作 |

<br>

**sync设置**
|参数|类型|解释|
|---|---|---|
| ensure_server_closed | bool | 当此选项为`true`时, 同步时将会检查镜像服是否已停止。当此选项为`false`时, 无论镜像服是否停止, 都将直接进行同步。 |
| auto_server_restart | bool | 此选项仅在`ensure_server_closed`为`true`时生效。当此选项为`true`时, 如果同步时镜像服未停止, 那么将在尝试自动停止镜像服后进行同步, 并在同步完成后自动重启镜像服 |
| check_status_interval | int | 此选项仅在`auto_server_restart`生效时生效。同步时停止镜像服后, 插件需确认镜像服是否已停止。此选项为检查镜像服状态的时间间隔 |
| max_attempt_times | int | 此选项仅在`auto_server_restart`生效时生效。检查镜像服状态的尝试次数, 超过此尝试次数后将不再尝试检查镜像服状态, 并输出`自动关闭失败`及镜像服当前状态信息。等效于超时时间 `timeout = check_status_interval * max_attempt_times`|

<br>

**start设置**

~此功能仍在开发~

<br>

**confirm设置**
|参数|类型|解释|
|---|---|---|
| timeout | int | 执行某指令后超过`timeout`秒后, 该玩家未进行任何操作, 则此指令操作自动超时取消 |
| cancel_anymsg | bool | 若玩家执行某指令后发送了其他无关消息, 则此指令操作自动取消 |

除此之外, 若玩家执行了某指令后又执行了对应镜像服的其他指令, 则先前执行的指令自动取消

注意：每个玩家只能确认自己执行的指令

<br>

**abort设置**

~此功能仍在开发~
|参数|类型|解释|
|---|---|---|
| operator | str | 正在开发 |

<br>

### display: 显示相关的配置文件
|参数|类型|解释|
|---|---|---|
| server_name | str | "镜像服"的名称，用以在显示时区分不同的镜像服 |

<br>

### server: 与Minecraft服务端交互相关的配置文件
一般无需更改
|参数|类型|解释|
|---|---|---|
| turn_off_auto_save | bool | 保存世界时关闭自动保存 |
| commands |||
| save_all_worlds | str | 保存世界的指令 |
| auto_save_off | str | 关闭自动保存的指令 |
| auto_save_on | str | 开启自动保存的指令 |
| saved_world_regex | str | 匹配服务端"世界保存完成"日志的正则表达式 |
| save_world_max_wait_sec | int | 保存世界的最大等待时间(秒)，超时将会跳过世界保存并进行同步 |
<br>

### 多镜像服配置文件示例

```
{
    "!!mirror": {
        "mcsm": {
            "enable": true,
            "url": "http://127.0.0.1:23333/",
            "uuid": "71154?????8e4770a1a2f4dd90695609",
            "remote_uuid": "6e927?????5b4a6999f0e66bc404071b",
            "apikey": "b8f3e?????4449849743727539478ade"
        },
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
        },
        "command": {
            "permission": {
                "status": 0,
                "start": 0,
                "stop": 2,
                "kill": 3,
                "sync": 2
            },
            "action": {
                "start": {
                    "enable_cmd": false,
                    "path": "./Mirror",
                    "command": "python -m mcdreforged",
                    "require_confirm": false
                },
                "stop": {
                    "require_confirm": true
                },
                "kill": {
                    "require_confirm": true
                },
                "sync": {
                    "ensure_server_closed": true,
                    "auto_server_restart": false,
                    "check_status_interval": 5,
                    "max_attempt_times": 3,
                    "require_confirm": true
                },
                "confirm": {
                    "timeout": 30,
                    "cancel_anymsg": true
                },
                "abort": {
                    "operator": "everyone"
                }
            }
        },
        "display": {
            "server_name": "Mirror"
        },
        "server": {
            "turn_off_auto_save": true,
            "commands": {
                "save_all_worlds": "save-all flush",
                "auto_save_off": "save-off",
                "auto_save_on": "save-on"
            },
            "saved_world_regex": "^Saved the game$",
            "save_world_max_wait_sec": 60
        }
    },
    "!!mirror2": {
        "mcsm": {
            "uuid": "83011?????c443249c1133fc08a41b80"
        },
        "sync": {
            "target": [
                "./Mirror2/server"
            ]
        },
        "display": {
            "server_name": "Mirror2"
        }
    },
    "!!mirror3": {
        "mcsm": {
            "uuid": "dfb12?????82466cb864f840b8424226"
        },
        "sync": {
            "target": [
                "./Mirror3/server"
            ]
        },
        "display": {
            "server_name": "Mirror3"
        }
    }
}
```

## 致谢

- 哈希比对思路 / [better_backup](https://github.com/z0z0r4/better_backup)
- 配置文件权限配置思路 / [PrimeBackup](https://github.com/TISUnion/PrimeBackup)
- 保存世界思路 / [QuickBackupM](https://github.com/TISUnion/QuickBackupM)

## ToDo

- [x] 指令执行确认
- [ ] 指令执行延迟
- [ ] 禁止同步`!!mirror sync enable/disable reason`
- [ ] lang语言文件
- [ ] 指令禁用
- [ ] ~RCON支持~ Websocket连接支持更多功能
- [ ] 无MCSM下通过命令行启动服务端 *(win和Linux的API写好了 能独立命令窗口/screen启动)*
- [ ] 历史同步记录显示
