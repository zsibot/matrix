# MATRiX v1.0.13 地图目录与 DLC

[返回中文主页](README_CN.md) | [English](Map_DLC.md)

v1.0.13 的地图选择界面支持动态更新目录，并自动识别基础包已有地图和已挂载的 DLC 地图。开源基础包不分发外部地图 `.pak`，只使用已获授权的地图资源。

## 初始目录

基础包中的地图目录文件是：

```text
UeSim/Content/model/MapDataTable.json
```

发布时该文件包含合法但为空的 `rows` 数组。因此第一次打开地图选择界面时没有地图卡片是正常现象，不代表程序或文件损坏。

## 在线更新目录并自动下载

在地图选择界面点击 **UPDATE LIST**。界面会从发布版本配置的目录地址下载新 JSON，先校验内容，再替换固定的 `MapDataTable.json`，随后刷新地图卡片和安装状态。下载上限默认为 256 MB。

更新期间应保持发布目录可写。若服务器不可达或返回内容无效，原目录不会被无效数据替换；按界面错误信息检查网络后重试。

目录更新完成后，每个尚未安装的地图卡片下方会显示 **DOWNLOAD** 按钮。点击该按钮即可自动下载对应的 DLC 包；界面会显示下载进度，下载和挂载完成后地图状态变为可进入。不要在下载过程中退出 UeSim 或移动发布目录。

推荐使用顺序：

1. 启动 UeSim 并进入地图选择界面；
2. 点击 **UPDATE LIST** 获取最新地图列表；
3. 在目标地图下方点击 **DOWNLOAD**；
4. 等待下载完成并显示可进入状态，然后选择地图。

## 手动下载和安装 DLC

自动下载不可用时，也可以从百度网盘手动下载：

[MATRiX 地图 DLC 百度网盘（提取码：6sth）](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F)

下载与 v1.0.13 及目标地图匹配的 DLC 包；若下载的是压缩包，先解压得到 `.pak`。将 `.pak` 放入推荐目录：

将获得授权且与 v1.0.13 匹配的 `.pak` 放入推荐目录：

```bash
mkdir -p UeSim/Saved/DLCs
cp /path/to/MapBundle.pak UeSim/Saved/DLCs/
```

UeSim 也扫描 `UeSim/Content/DLCs/`，但 `UeSim/Saved/DLCs/` 更适合用户安装内容。重启 UeSim 后，程序会挂载已安装 DLC；地图目录中对应卡片会从下载状态变为可进入状态。

只有 `.pak` 而目录 JSON 中没有对应条目时，界面可能不会显示卡片。此时先执行 **UPDATE LIST**，或从地图发布方获取与该 `.pak` 匹配的目录文件。不要把其他版本的目录和 DLC 混用。

## 离线更新

无法使用在线更新时，可以从地图发布方取得匹配的 `MapDataTable.json`，关闭 UeSim 后替换：

```text
UeSim/Content/model/MapDataTable.json
```

保留 JSON 的 `format_version` 和 `rows` 结构，并在替换前自行备份旧文件。重新启动 UeSim 后检查地图卡片和 DLC 安装状态。

## 排查

- 没有地图卡片：基础包空目录属于正常状态，先点击 **UPDATE LIST**。
- 自动下载失败：检查网络、磁盘空间和发布目录写权限，也可改用百度网盘手动下载。
- 下载后仍显示未安装：检查 `.pak` 是否位于 DLC 扫描目录、是否与当前版本和地图列表匹配，然后重启 UeSim。
- 更新失败：确认目录可写、服务器可访问，且 JSON 格式有效、条目包含地图图像。
- 地图无法进入：查看 `UeSim/Saved/Logs/UeSim.log` 中的 pak 挂载和地图加载错误。
