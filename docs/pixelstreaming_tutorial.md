# MATRiX v1.0.13 Pixel Streaming 2 Guide

[Getting Started](Getting_Started.md)

> Updated for the Pixel Streaming 2 plugin and server downloader included in the MATRiX v1.0.13 Linux runtime.

The old source-tree path `src/UeSim/.../PixelStreaming2/WebServers` does not apply to this runtime package. Use the packaged path documented below.

## 1. Components and ports

Pixel Streaming uses three processes/components:

```text
Browser <--HTTP/WebRTC--> Signalling Web Server <--WebSocket--> UeSim
```

Default server settings are normally:

| Purpose | Default |
|---|---|
| UeSim streamer WebSocket | TCP 8888 |
| Browser player page | TCP 80, or another port printed by the start script |
| WebRTC media | Negotiated ports; firewall/NAT rules depend on deployment |

Always use the ports printed by the signalling server. On Linux, some launch modes move the player page from privileged port 80 to 1025.

## 2. Prerequisites

- A working MATRiX v1.0.13 runtime and supported GPU driver;
- `curl`/`wget`, `tar`, Bash, Node.js and npm;
- internet access for the first infrastructure download;
- a graphical or off-screen rendering environment for UeSim.

Check tools:

```bash
node --version
npm --version
```

## 3. Download the matching server infrastructure

From the MATRiX root:

```bash
cd UeSim/Samples/PixelStreaming2/WebServers
chmod +x get_ps_servers.sh
./get_ps_servers.sh -v 5.7
```

The runtime currently contains the downloader, not the complete server tree. After a successful download, this directory should contain `SignallingWebServer/`, `Frontend/`, `Common/` and related infrastructure files.

Do not mix an arbitrary Pixel Streaming Infrastructure branch with this package. MATRiX v1.0.13 is built with UE 5.7 Pixel Streaming 2, so use the UE 5.7-compatible infrastructure.

## 4. Start the signalling and web server

Stay in `UeSim/Samples/PixelStreaming2/WebServers` and run:

```bash
./SignallingWebServer/platform_scripts/bash/start.sh
```

The first run may install npm dependencies and build the frontend. Keep this terminal open and note:

- the streamer WebSocket port;
- the browser/player URL;
- any npm, permission, or port-binding error.

For supported server arguments after installation:

```bash
cd SignallingWebServer
npm start -- --help
```

## 5. Start MATRiX as the streamer

Open a second terminal at the MATRiX root:

```bash
./UeSim.sh \
  -PixelStreamingConnectionURL=ws://127.0.0.1:8888 \
  -RenderOffScreen \
  -AudioMixer
```

`UeSim.sh` forwards these arguments to the UeSim binary. For Pixel Streaming 2 in the packaged UE version, `PixelStreamingConnectionURL` is the current connection argument. Replace the host and port if the signalling server runs elsewhere.

If interactive local rendering is required, omit `-RenderOffScreen`:

```bash
./UeSim.sh \
  -PixelStreamingConnectionURL=ws://127.0.0.1:8888 \
  -AudioMixer
```

The Pixel Streaming 2 plugin is enabled in the packaged application and auto-starts when a valid connection URL is supplied.

## 6. Open the player

Open the exact player URL printed by the signalling server, commonly one of:

```text
http://127.0.0.1/
http://127.0.0.1:1025/
```

For remote access, replace `127.0.0.1` with the signalling-server address. Do not expose the service directly to the public internet without TLS, authentication, TURN/NAT planning, and access controls.

## 7. Verification

Check UeSim for Pixel Streaming messages:

```bash
rg -i 'PixelStreaming|signalling|streamer|webrtc' \
  UeSim/Saved/Logs/UeSim.log
```

A healthy startup requires all of the following:

1. signalling server is listening;
2. UeSim connects to the streamer WebSocket port;
3. browser reaches the player page;
4. WebRTC negotiation succeeds;
5. the GPU encoder starts and frames arrive.

## 8. Troubleshooting

### `SignallingWebServer` does not exist

Only the downloader is included initially. Run `get_ps_servers.sh -v 5.7` and check its network/download errors.

### Permission denied on port 80

Use the non-privileged player port chosen by the platform script, or configure another port through the signalling server arguments. Do not run the whole stack as root only to bind port 80.

### UeSim never appears as a streamer

- confirm the WebSocket URL uses the streamer port, normally 8888;
- confirm the argument is `-PixelStreamingConnectionURL=...`;
- inspect both the signalling terminal and `UeSim.log`;
- verify local firewall and proxy rules.

### Browser page loads but video is black

- verify UeSim is rendering and has not failed GPU initialization;
- test without `-RenderOffScreen` to compare local rendering;
- inspect encoder and WebRTC errors in `UeSim.log`;
- check whether the GPU/driver supports the selected hardware codec.

### Works locally but not across machines

Opening only the HTTP player port is not sufficient for every topology. The browser, signalling server, streamer, ICE candidates, UDP media ports, and possibly a TURN server must all be reachable. Validate on a trusted LAN first.

## 9. Maintenance note

When MATRiX changes Unreal Engine versions, re-download the matching Pixel Streaming Infrastructure and re-check the connection argument, start script, default ports, and browser frontend. Do not copy this guide unchanged to a different UE release.
