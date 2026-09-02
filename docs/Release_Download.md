# Downloading MATRiX v1.0.13

[README](../README.md) | [中文](Release_Download_CN.md)

Two download sources are available:

- [GitHub Release v1.0.13](https://github.com/zsibot/matrix/releases/tag/v1.0.13): split archive with checksums.
- [Baidu Netdisk Linux package](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q): complete package, access code `118g`.

The Linux runtime archive on GitHub is split because each Release asset must remain below 2 GB. Download these files:

```text
MATRiX_v1.0.13.tar.gz.part-001
MATRiX_v1.0.13.tar.gz.part-002
MATRiX_v1.0.13.tar.gz.part-003
SHA256SUMS
```

Keep every part in one directory without renaming it.

## Verify and extract without a combined archive

```bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
```

## Rebuild the archive first

```bash
cat MATRiX_v1.0.13.tar.gz.part-* > MATRiX_v1.0.13.tar.gz
sha256sum MATRiX_v1.0.13.tar.gz
tar -xzf MATRiX_v1.0.13.tar.gz
```

Complete archive SHA-256:

```text
92f17600a188ec92373847cb4bfb1df2c5a932ebfc2a49b276658e88d7f32539
```

| Part | Size in bytes | SHA-256 |
|---|---:|---|
| `part-001` | 1,992,294,400 | `e1ae537d820c85ab844271a03ecb589f263bfaac4ae2e4b2513745312321277c` |
| `part-002` | 1,992,294,400 | `d0a50d66fde1b8d6add86244e60dfeb81eec3c63b9b8c6e6c73a49627d300af9` |
| `part-003` | 266,886,524 | `69d7e82deb1278700b1c96cee3fc325ddbe93d96b56deed049336d54a3a51453` |

Any missing, damaged, renamed, or reordered part causes extraction to fail.
