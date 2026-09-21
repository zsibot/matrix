# 下载 MATRiX v1.1.1

[中文主页](README_CN.md) | [English](Release_Download.md)

## 下载方式

- [Linux 直链下载](http://39.96.31.125:18080/matrix/v1.1.1/Linux/MATRiX_v1.1.1.tar.gz)：完整压缩包，支持断点续传。
- [GitHub Release v1.1.1](https://github.com/zsibot/matrix/releases/tag/v1.1.1)：下载全部 `.part-*`、`SHA256SUMS` 和 `EXTRACT.md`。分卷每个最多 1,900,000,000 字节，严格小于 2 GB。若该版本尚未上传，请检查百度网盘的最新构建，或等待直链恢复。
- [百度网盘 Linux 运行包](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)：提取码 `118g`。**请选择最新版本下载**；本文和校验清单对应 v1.1.1，不要混用其他版本的分卷。

## 直链或网盘完整包

```bash
curl -fL -C - -o MATRiX_v1.1.1.tar.gz \
  'http://39.96.31.125:18080/matrix/v1.1.1/Linux/MATRiX_v1.1.1.tar.gz'
tar -xzf MATRiX_v1.1.1.tar.gz
cd MATRiX_v1.1.1
./UeSim.sh
```

网盘下载完整包后从 `tar` 命令开始执行。直链提供完整压缩包，支持断点续传；服务器或网盘副本的校验值以其配套清单为准，未假定它们与本地新生成的 GitHub 压缩包逐字节相同。

## GitHub 分卷校验与解压

把本版本全部分卷和 `SHA256SUMS` 放入单独目录，保持原名。不要单独解压某一卷。

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.1.tar.gz.part-* | tar -xzf -
cd MATRiX_v1.1.1
./UeSim.sh
```

如需先恢复完整包，另下载 `SHA256SUMS-full`：

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.1.tar.gz.part-* > MATRiX_v1.1.1.tar.gz
sha256sum -c SHA256SUMS-full && tar -xzf MATRiX_v1.1.1.tar.gz
```

`SHA256SUMS` 校验分卷，`SHA256SUMS-full` 校验重建后的完整包。校验失败时重新下载对应文件，不要继续解压。


本次对应 2026-09-21 15:08（北京时间）重打包，仍使用 v1.1.1 文件名。不要混用先前同版本的分卷；全部分卷和校验文件必须来自同一次发布。`RELEASE_BUILD.json` 记录二进制与默认配置身份。

## 本次 GitHub Release 文件清单

本清单对应 2026-09-21 15:08 重打包，不能与此前同版本分卷混用。

Build ID: `20260921T070837079667Z-fd3f20ec`

| File | Bytes | SHA-256 |
|---|---:|---|
| `MATRiX_v1.1.1.tar.gz.part-001` | 1,900,000,000 | `8d1425cacc54c0fb950e8bd27a40c94e75c9576992e215e3e598c06bb2924c36` |
| `MATRiX_v1.1.1.tar.gz.part-002` | 1,900,000,000 | `2c21940df51b11b464607326bf6b1e674ff47ef6e2c1102d9973f0dae8006a2a` |
| `MATRiX_v1.1.1.tar.gz.part-003` | 1,220,891,465 | `4be76e5703a353c35656c2d93212aa2bb278b0dbf5a813edf3ae78b0b7948ad9` |

Complete archive / 完整包: 5,020,891,465 bytes

```text
39bc1e41a06c018571be2b6c47fa2548b597f81175e4baea9d348c28b0fb5301
```

[Release JSON](releases/v1.1.1.json) · [Runtime build identity](releases/v1.1.1-build.json)
