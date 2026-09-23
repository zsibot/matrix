# Downloading MATRiX v1.1.2

[README](../README.md) | [中文](Release_Download_CN.md)

## Download sources

- [Direct Linux download](http://39.96.31.125:18080/matrix/v1.1.2/Linux/MATRiX_v1.1.2.tar.gz): complete archive, resumable.
- [GitHub Release v1.1.2](https://github.com/zsibot/matrix/releases/tag/v1.1.2): download every `.part-*`, `SHA256SUMS`, and `EXTRACT.md`. Each part is at most 1,900,000,000 bytes, strictly below 2 GB.
- [Baidu Netdisk Linux package](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q), access code `118g`: **select the latest version**. This guide and its checksum list target v1.1.2; never mix parts from different versions.

## Complete archive

```bash
curl -fL -C - -o MATRiX_v1.1.2.tar.gz \
  'http://39.96.31.125:18080/matrix/v1.1.2/Linux/MATRiX_v1.1.2.tar.gz'
tar -xzf MATRiX_v1.1.2.tar.gz
cd MATRiX_v1.1.2
./UeSim.sh
```

For a Baidu download, start at the `tar` command. The direct link provides the complete archive and supports resumable downloads. Use the mirror's own checksum manifest if supplied; byte identity with the newly built GitHub archive has not been assumed.

## GitHub parts

Keep all parts and `SHA256SUMS` in a directory containing only this release, without renaming files. Parts cannot be extracted individually.

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.2.tar.gz.part-* | tar -xzf -
cd MATRiX_v1.1.2
./UeSim.sh
```

To reconstruct the complete archive first, also download `SHA256SUMS-full`:

```bash
sha256sum -c SHA256SUMS && \
  cat MATRiX_v1.1.2.tar.gz.part-* > MATRiX_v1.1.2.tar.gz
sha256sum -c SHA256SUMS-full && tar -xzf MATRiX_v1.1.2.tar.gz
```

`SHA256SUMS` checks parts; `SHA256SUMS-full` checks the reconstructed archive. Redownload damaged files if validation fails.


This delivery is the 2026-09-23 10:24 China Standard Time rebuild with versioned v1.1.2 filenames. Do not mix parts from earlier builds of the same version. Download all parts and checksum files from one release. `RELEASE_BUILD.json` identifies the binary and default configuration.


Mirrors synchronize independently; use GitHub Release if this version has not reached a mirror. File sizes and SHA-256 values are in the Release assets `release-manifest.json` and `SHA256SUMS`.

## GitHub Release assets

| File | Bytes | SHA-256 |
|---|---:|---|
| `MATRiX_v1.1.2.tar.gz.part-001` | 1,900,000,000 | `bacf28c84c528b66bb37ea0921243e2dd28560518bbbe5b2c920738790b21976` |
| `MATRiX_v1.1.2.tar.gz.part-002` | 1,900,000,000 | `f0773807dde2ae3f9b41aff30e8f4ad7f55d4aab0f67e87f26db23f30d0dc19c` |
| `MATRiX_v1.1.2.tar.gz.part-003` | 1,230,168,999 | `1ea4e7e26e77ed2d57ccbe7f5ffab4eea70ef2dd975cb74382843ba3fd213671` |

Complete archive: 5,030,168,999 bytes; SHA-256: `dd48005a7185d08d3dcdc700dd3f93716c95c5009a1a0ab6f8b1b5f1697da817`.

[Release JSON](releases/v1.1.2.json) · [Build identity](releases/v1.1.2-build.json)
