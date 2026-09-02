# MATRiX v1.0.13 map catalog and DLCs

[Back to README](../README.md) | [中文](Map_DLC_CN.md)

The v1.0.13 map-selection screen can update its catalog dynamically and detects maps already present in the base package or mounted from DLCs. The open base package does not distribute external map `.pak` files; use only assets you are authorized to install.

## Initial catalog

The catalog is stored at:

```text
UeSim/Content/model/MapDataTable.json
```

The base release intentionally ships a valid catalog with an empty `rows` array. Seeing no map cards on the first visit is therefore expected and does not mean the package is damaged.

## Update the catalog and download automatically

Select **UPDATE LIST** in the map-selection screen. It downloads the catalog from the address configured by the release, validates it, replaces the fixed `MapDataTable.json`, and refreshes the cards and installed-map state. The default download limit is 256 MB.

Keep the release directory writable while updating. Invalid or unreachable content is rejected instead of replacing the catalog; use the on-screen error to check the network and retry.

After the catalog is refreshed, every map that is not installed shows a **DOWNLOAD** button below its card. Select it to download the matching DLC automatically. The UI reports progress and marks the map ready after the download and mount complete. Do not exit UeSim or move the release directory while a download is running.

Recommended sequence:

1. Start UeSim and open map selection.
2. Select **UPDATE LIST** to retrieve the latest catalog.
3. Select **DOWNLOAD** below the required map.
4. Wait until the map is marked ready, then enter it.

## Manual download and installation

If automatic download is unavailable, download the map DLC manually from Baidu Netdisk:

[MATRiX map DLCs on Baidu Netdisk (access code: 6sth)](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F)

Choose a DLC matching v1.0.13 and the required map. If it is an archive, extract the `.pak`, then place it in the recommended user-content directory:

Place an authorized v1.0.13-compatible `.pak` in the recommended user-content directory:

```bash
mkdir -p UeSim/Saved/DLCs
cp /path/to/MapBundle.pak UeSim/Saved/DLCs/
```

UeSim also scans `UeSim/Content/DLCs/`, but `UeSim/Saved/DLCs/` is preferred for user-installed content. Restart UeSim to mount installed DLCs. A matching catalog card then changes from download state to ready.

A `.pak` may not appear when the catalog has no matching entry. Run **UPDATE LIST** first, or obtain the matching catalog from the map distributor. Do not mix catalogs and DLCs from different releases.

## Offline catalog update

When online update is unavailable, obtain a matching `MapDataTable.json` from the map distributor, close UeSim, and replace `UeSim/Content/model/MapDataTable.json`. Preserve the `format_version` and `rows` structure and back up the old file first. Restart UeSim and verify the catalog and installed state.

## Troubleshooting

- No cards: the base catalog is intentionally empty; select **UPDATE LIST**.
- Automatic download fails: verify network access, free disk space, and write permission, or use the manual Baidu Netdisk download.
- Still shown as not installed: verify the `.pak` path, catalog match, and release compatibility, then restart UeSim.
- Catalog update fails: verify write access, server reachability, valid JSON, and map images in each row.
- Map travel fails: inspect `UeSim/Saved/Logs/UeSim.log` for pak-mount and map-loading errors.
