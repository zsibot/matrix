# MATRiX v1.1.2 发布说明

本版基于 2026-09-23 10:24（北京时间）的 Linux x86_64 打包产物；构建标识为 `20260923T022450476117Z-6596e3e1`。二进制和 PAK 与打包历史记录匹配。

## 本版配置与行为

- 默认模型为 `xgb`，模型路径为相对于 `UeSim/` 的 `Content/model/xgb/xgb.xml`。
- 默认开启内置运控：`inside_mc=true`；保留 `network_mode=standalone`、`sensor_sync_mode=true`。
- 初始 `robot.sensors` 为空。请在传感器设置中加载并应用方案，再进入仿真创建机器人；预设不会自动启用。
- XXG 在开源模式中隐藏，不作为本发布版的可选机器人。
- 保留 `config_default.json` 六传感器预设，以及 `config_semantic.json`、`config_rgb_semantic.json` 语义相机方案；语义输出为无损类别 ID PNG。
- 更新运行文件与机器人选择界面资源，修复重新打包生成的启动脚本，移除主配置中的开发机绝对路径。
- 同步中英文说明、公开配置示例、工具使用方式和可复用分卷打包脚本。

## 升级与启动

完整解压 v1.1.2 到新目录，保留运行程序、Engine、插件与模型的配套关系。备份旧配置后按字段迁移；不要将 v1.1.1 配置目录整体覆盖到新包。启动命令为 `./UeSim.sh`。

首次使用时通过地图界面的 **UPDATE LIST** 和 **DOWNLOAD** 安装匹配的地图 DLC。内置运控无需单独启动控制器；切换到外部 `robot_mc` 时需另行下载，并先关闭内置运控。

传感器验证可先选择 `config_default.json`；语义图验证选择 `config_rgb_semantic.json`。工具参数 `--sensor-config` 只选择工具读取的文件，不会替仿真器激活方案。

## 下载与校验

GitHub Release 附件按每卷小于 2 GB 分割。下载全部分卷与 `SHA256SUMS`，校验后合并解压；不能混用不同版本的分卷。百度网盘请选择最新版本。直链和网盘独立同步，以实际提供的版本及校验文件为准。

## 验证范围

发布前核对启动脚本、Python 工具、配置与文档链接，并校验压缩包及分卷完整性。当前发布流程不运行真实 GPU 场景，不将源码测试记录等同于本次交互验收。

本开源运行包不包含 `UeSim/Content/model/xxg` 模型目录。
