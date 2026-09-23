# 下载 MATRiX v1.1.2

[中文主页](README_CN.md) | [English](Release_Download.md)

## 下载方式

- [Linux 直链下载](http://39.96.31.125:18080/matrix/v1.1.2/Linux/MATRiX_v1.1.2.tar.gz)：完整压缩包，支持断点续传。
- [GitHub Release v1.1.2](https://github.com/zsibot/matrix/releases/tag/v1.1.2)：下载全部 `.part-*`、`SHA256SUMS` 和 `EXTRACT.md`。分卷每个最多 1,900,000,000 字节，严格小于 2 GB。
- [百度网盘 Linux 运行包](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)：提取码 `118g`。**请选择最新版本下载**；本文和校验清单对应 v1.1.2，不要混用其他版本的分卷。

## 直链或网盘完整包

```bash
curl -fL -C - -o MATRiX_v1.1.2.tar.gz \
  'http://39.96.31.125:18080/matrix/v1.1.2/Linux/MATRiX_v1.1.2.tar.gz'
tar -xzf MATRiX_v1.1.2.tar.gz
cd MATRiX_v1.1.2
./UeSim.sh
```

网盘下载完整包后从 `tar` 命令开始执行。直链提供完整压缩包，支持断点续传；服务器或网盘副本的校验值以其配套清单为准，未假定它们与本地新生成的 GitHub 压缩包逐字节相同。

## GitHub 分卷校验与解压

把本版本全部分卷和 `SHA256SUMS` 放入单独目录，保持原名。不要单独解压某一卷。

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.2.tar.gz.part-* | tar -xzf -
cd MATRiX_v1.1.2
./UeSim.sh
```

如需先恢复完整包，另下载 `SHA256SUMS-full`：

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.2.tar.gz.part-* > MATRiX_v1.1.2.tar.gz
sha256sum -c SHA256SUMS-full && tar -xzf MATRiX_v1.1.2.tar.gz
```

`SHA256SUMS` 校验分卷，`SHA256SUMS-full` 校验重建后的完整包。校验失败时重新下载对应文件，不要继续解压。


本次对应 2026-09-23 10:24（北京时间）重打包，使用 v1.1.2 文件名。不要混用先前同版本的分卷；全部分卷和校验文件必须来自同一次发布。`RELEASE_BUILD.json` 记录二进制与默认配置身份。


镜像独立同步，未同步本版本时请使用 GitHub Release。文件大小和 SHA-256 以 Release 附件 `release-manifest.json`、`SHA256SUMS` 为准。

## 本次 GitHub Release 文件清单

| File | Bytes | SHA-256 |
|---|---:|---|
| `MATRiX_v1.1.2.tar.gz.part-001` | 1,900,000,000 | `b23f641a5ba82eacaa80cc210e632cb8157b9db29ea14d9f6766e3b5701c5eb8` |
| `MATRiX_v1.1.2.tar.gz.part-002` | 1,900,000,000 | `7fdcdda8b7af7454330273d40ca90239ea081d107ebf684f96eb50d6904e3a98` |
| `MATRiX_v1.1.2.tar.gz.part-003` | 1,191,256,614 | `08aa1e2618b4b33d1db6cf1983f6e8b8bf4fd090b14f63247d076ec59a59a349` |

Complete archive: 4,991,256,614 bytes; SHA-256: `baaeaf01817e90baf20e3fd6f74ae2fe885ef69f7d862fa36f50222f69cfea81`.

[Release JSON](releases/v1.1.2.json) · [Build identity](releases/v1.1.2-build.json)
