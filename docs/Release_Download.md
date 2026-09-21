# Downloading MATRiX v1.1.1

[README](../README.md) | [中文](Release_Download_CN.md)

## Download sources

- [Direct Linux download](http://39.96.31.125:18080/matrix/v1.1.1/Linux/MATRiX_v1.1.1.tar.gz): complete archive, resumable.
- [GitHub Release v1.1.1](https://github.com/zsibot/matrix/releases/tag/v1.1.1): download every `.part-*`, `SHA256SUMS`, and `EXTRACT.md`. Each part is at most 1,900,000,000 bytes, strictly below 2 GB. If this tag is not published yet, check Baidu Netdisk for the latest build or wait for the direct endpoint to be restored.
- [Baidu Netdisk Linux package](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q), access code `118g`: **select the latest version**. This guide and its checksum list target v1.1.1; never mix parts from different versions.

## Complete archive

```bash
curl -fL -C - -o MATRiX_v1.1.1.tar.gz \
  'http://39.96.31.125:18080/matrix/v1.1.1/Linux/MATRiX_v1.1.1.tar.gz'
tar -xzf MATRiX_v1.1.1.tar.gz
cd MATRiX_v1.1.1
./UeSim.sh
```

For a Baidu download, start at the `tar` command. The direct link provides the complete archive and supports resumable downloads. Use the mirror's own checksum manifest if supplied; byte identity with the newly built GitHub archive has not been assumed.

## GitHub parts

Keep all parts and `SHA256SUMS` in a directory containing only this release, without renaming files. Parts cannot be extracted individually.

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.1.tar.gz.part-* | tar -xzf -
cd MATRiX_v1.1.1
./UeSim.sh
```

To reconstruct the complete archive first, also download `SHA256SUMS-full`:

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.1.tar.gz.part-* > MATRiX_v1.1.1.tar.gz
sha256sum -c SHA256SUMS-full && tar -xzf MATRiX_v1.1.1.tar.gz
```

`SHA256SUMS` checks parts; `SHA256SUMS-full` checks the reconstructed archive. Redownload damaged files if validation fails.


This delivery is the 2026-09-21 15:08 China Standard Time rebuild and retains the v1.1.1 filenames. Do not mix parts from earlier builds of the same version. Download all parts and checksum files from one release. `RELEASE_BUILD.json` identifies the binary and default configuration.

## Generated GitHub Release assets

This manifest identifies the 2026-09-21 15:08 CST rebuild. Do not mix these parts with earlier v1.1.1 builds.

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
