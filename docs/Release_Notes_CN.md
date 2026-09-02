# MATRiX v1.0.13 发布与升级说明

[返回中文主页](README_CN.md)

> 文档审计基线：源码分支 `crossplatform` 提交 `b666c0d9`（关节限位优化），核对日期 2026-09-02。运行命令、目录、默认配置和 Python 参数同时按本发布目录实物复核。

## 开源发布结构

v1.0.13 参考 v1.0.7 的简洁目录形式，以新打包版本为运行主体：

```text
MATRiX_v1.0.13/
├── UeSim.sh
├── UeSim/
├── Engine/
├── Tools/
├── docs/
├── demo_gif/
├── README.md
└── README_CN.md
```

发布包不包含独立 `robot_mc`。默认 `inside_mc=true`，用户直接启动 UeSim 即可使用内置运控。独立运控仅在文档中提供开源项目下载和配置方法。

## v1.0.13 重点更新

- Linux 运行包按 GitHub 单文件限制拆成 3 个分片，并提供 `SHA256SUMS`；
- 控制目标会按 MuJoCo 关节范围和执行器控制范围进行安全约束，接近限位时阻止继续向外施力；
- 地图选择界面支持按钮更新 `MapDataTable.json`，并从地图卡片下方自动下载对应 DLC；基础包使用合法的空地图目录；
- 传感器方案界面和默认传感器配置更新；
- 新增 LiDAR 到相机图像投影工具，并修正同步配对、相机模型和配置路径；
- 内置运控仍为开源发布默认模式，独立运控不随包分发。

分片下载、校验和解压命令见[下载与校验](Release_Download_CN.md)。

## 从 v1.0.7 迁移到 v1.0.13

- 使用 v1.0.13 新打包的 UeSim、Engine、模型和插件；
- 内置运控继续作为默认模式；
- 可选独立运控通过手动修改 `inside_mc` 切换；
- 模型路径修正为可移动的 `model/xgb/xgb.xml`；
- 工具和文档依据当前源码更新；
- 不沿用 v1.0.7 的旧下载链接、旧绝对路径或过时能力清单；
- 不把独立运控二进制、模型和依赖包放入开源发布目录。

## 迁移配置

不要整体覆盖 v1.0.13 的 `UeSim/Content/model/config/`。建议只迁移经过核对的传感器字段、外参和 topic，并保留：

```json
"mujoco_model": "model/xgb/xgb.xml",
"inside_mc": true
```

自定义模型放入 `UeSim/Content/model/<name>/`；地图 `.pak` 放入 `UeSim/Saved/DLCs/`。基础包地图目录为空，按 [地图目录与 DLC](Map_DLC_CN.md) 更新目录。首次启动应先使用默认内置运控验证模型。
