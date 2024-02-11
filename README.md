# MirrorMcsmcdR
一个MCDR插件，基于MCSM对镜像服进行控制与进行文件同步

---

## 说明

- 插件的功能基于[MCSManager](https://github.com/MCSManager/MCSManager)
- 完善的镜像服控制操作，获取运行状态/启动/停止/强制终止/同步
- 基于哈希的文件同步，只同步镜像服与源服务端不同的文件
- 高可自定义的配置文件

## 指令

*指令前缀默认为`!!mirror``*

`!!mirror` 显示指令帮助

`!!mirror help` 显示指令帮助

`!!mirror status` 获取镜像服实例运行状态，状态未知/已停止/正在停止/正在启动/正在运行

`!!mirror start` 启动镜像服实例

`!!mirror stop` 停止镜像服实例

`!!mirror kill` 强制终止镜像服实例

`!!mirror sync` 进行文件同步

## 配置文件

`MCSManager` 配置部分若有疑问，请参见[MCSManager官方文档](https://docs.mcsmanager.com/#/zh-cn/apis/readme)

```
{
    "MCSManager": {
        "url": "http://127.0.0.1:23333/", # MCSManager面板的地址，即请求api的地址
        "uuid": null,         # 应用实例的ID
        "remote_uuid": null,  # 远程节点ID
        "apikey": null        # 调用API接口必需的密钥
    },
    "command": {
        "prefix": "!!mirror", # 指令前缀，一般不需要更改
        "permission": {       # 各指令所需要的最低权限等级
            "status": 0,
            "start": 0,
            "stop": 2,
            "kill": 3,
            "sync": 2,
        }
    },
    "display": {
        "server_name": "Mirror"  # "镜像服"的名称
    },
    "sync": {
        "world": [                   # 需要同步的目录，当存档有多个世界文件时需要添加
            "world"
        ],
        "source": "./server",        # 源服务端目录，source/world -> target/world
        "target": "./Mirror/server", # 目标服务端目录
        "concurrency": 4,            # 同步时进行哈希计算的线程数
        "ignore_files": [            # 不进行同步的文件
            "session.lock"
        ]
    },
    "server": {
        "turn_off_auto_save": true,  # 保存世界时关闭自动保存
        "commands": {
            "save_all_worlds": "save-all flush",  # 保存世界的指令
            "auto_save_off": "save-off",          # 关闭自动保存的指令
            "auto_save_on": "save-on"             # 开启自动保存的指令
        },
        "saved_world_regex": "^Saved the game$",  # 匹配服务端"世界保存完成"日志的正则表达式
        "save_world_max_wait_sec": 60             # 保存世界的最大等待时间(秒)，超时将会跳过世界保存并进行同步
    }
}
```

## 致谢

- 哈希比对思路 / [better_backup](https://github.com/z0z0r4/better_backup)
- 配置文件权限配置思路 / [PrimeBackup](https://github.com/TISUnion/PrimeBackup)
- 保存世界思路 / [QuickBackupM](https://github.com/TISUnion/QuickBackupM)
