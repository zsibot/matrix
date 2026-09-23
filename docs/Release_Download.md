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
| `MATRiX_v1.1.2.tar.gz.part-001` | 1,900,000,000 | `b23f641a5ba82eacaa80cc210e632cb8157b9db29ea14d9f6766e3b5701c5eb8` |
| `MATRiX_v1.1.2.tar.gz.part-002` | 1,900,000,000 | `7fdcdda8b7af7454330273d40ca90239ea081d107ebf684f96eb50d6904e3a98` |
| `MATRiX_v1.1.2.tar.gz.part-003` | 1,191,256,614 | `08aa1e2618b4b33d1db6cf1983f6e8b8bf4fd090b14f63247d076ec59a59a349` |

Complete archive: 4,991,256,614 bytes; SHA-256: `baaeaf01817e90baf20e3fd6f74ae2fe885ef69f7d862fa36f50222f69cfea81`.

[Release JSON](releases/v1.1.2.json) · [Build identity](releases/v1.1.2-build.json)
