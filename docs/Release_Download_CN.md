# 下载 MATRiX v1.0.13

[中文主页](README_CN.md) | [English](Release_Download.md)

提供两种下载方式：

- [GitHub Release v1.0.13](https://github.com/zsibot/matrix/releases/tag/v1.0.13)：分片压缩包和校验文件；
- [百度网盘 Linux 运行包](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)：完整包，提取码 `118g`。

GitHub Release 单文件需要低于 2 GB，因此 Linux 运行包拆成 3 个分片。需要下载：

```text
MATRiX_v1.0.13.tar.gz.part-001
MATRiX_v1.0.13.tar.gz.part-002
MATRiX_v1.0.13.tar.gz.part-003
SHA256SUMS
```

全部分片必须放在同一目录并保留原文件名。

## 校验并直接解压

```bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
```

该方式不会额外生成一个完整压缩包。

## 先恢复完整压缩包

```bash
cat MATRiX_v1.0.13.tar.gz.part-* > MATRiX_v1.0.13.tar.gz
sha256sum MATRiX_v1.0.13.tar.gz
tar -xzf MATRiX_v1.0.13.tar.gz
```

完整压缩包 SHA-256：

```text
92f17600a188ec92373847cb4bfb1df2c5a932ebfc2a49b276658e88d7f32539
```

| 分片 | 字节数 | SHA-256 |
|---|---:|---|
| `part-001` | 1,992,294,400 | `e1ae537d820c85ab844271a03ecb589f263bfaac4ae2e4b2513745312321277c` |
| `part-002` | 1,992,294,400 | `d0a50d66fde1b8d6add86244e60dfeb81eec3c63b9b8c6e6c73a49627d300af9` |
| `part-003` | 266,886,524 | `69d7e82deb1278700b1c96cee3fc325ddbe93d96b56deed049336d54a3a51453` |

任一分片缺失、损坏、重命名或顺序错误都会导致解压失败。
