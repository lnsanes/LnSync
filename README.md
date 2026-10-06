# LnSync

**English** | [简体中文](README.zh-CN.md)

A generic file updater for Minecraft modpacks. The server hosts files from a content-addressed manifest; the client mod syncs by SHA-256 early in game launch. Forge, NeoForge, Fabric, and Quilt are supported. A universal client jar loads on all four.

Current release: **v0.1.4**  
Downloads: https://github.com/lnsanes/LnSync/releases

---

## What it does

| Piece | Path / artifact | Role |
|------|-----------------|------|
| Server | `server/` → `lnsync-server` / `lnsync-server.exe` | Pulls Client/Server zips from a GitHub Release, builds an object store and per-side manifests, serves HTTP API + admin UI |
| Client | `client/` → `lnsync*.jar` | Drop into the instance `mods/` folder; checks and fetches files at early launch |
| Overlay | `overlay_dir` (default `./private`) | Overrides official files of the same path; can be side-specific |
| Official-pack edits | `private/official-adjust.toml` | Exclude official files from the admin UI (search + categories) |

Protocol: manifest + sha256 objects + `client` / `server` sides + optional tokens (player sync / dedicated-server sync / admin UI).

---

## Use a Release (recommended)

Download assets from [Releases](https://github.com/lnsanes/LnSync/releases).

### 1. Deploy the server

**Windows**

1. Download `lnsync-server.exe` and `config.example.toml`
2. Copy the example to `config.toml` in the same folder; fill in repo, tag, tokens
3. From that folder:

```bat
lnsync-server.exe serve --config config.toml
```

**Linux (x86_64)**

This release does not ship a prebuilt Linux binary. Build on Linux (or in Docker):

```bash
cd server
cargo build --release
cp config.example.toml config.toml
./target/release/lnsync-server serve --config config.toml
```

After the first start, open the admin UI, set the pack source, and run **Rebuild** once to generate client/server manifests.

Default admin URL (local example):

```text
http://127.0.0.1:8765/admin/ifgfsgfbijuzoxzq
```

If `admin_token` is set, the admin UI asks for that password.

### 2. Install the client mod

1. Download a client jar (prefer the universal `lnsync.jar` or `lnsync-universal.jar`)
2. Put it in the instance `mods/` folder
3. Download `lnsync.toml.example`, copy it to the **instance root** (next to `mods/`), rename to `lnsync.toml`
4. Set `update_server` and `update_token` (see client config below)
5. Launch the game normally. Sync happens early in startup; logs go to `logs/lnsync.log`

Loader-specific jars (optional; only that loader’s entrypoint):

- `lnsync-forge.jar`
- `lnsync-neoforge.jar`
- `lnsync-fabric.jar`
- `lnsync-quilt.jar`

> There is no standalone double-click updater. Do not double-click the jar; load it as a mod.

### 3. Player flow

1. The update server must be running, with a rebuilt manifest
2. Launch the game → the mod checks → downloads/deletes hosted files if needed → otherwise continues into the game
3. If a mod jar itself changed and the update could not finish in the earliest stage, launch once more (the log says so)

---

## Build from source

Needs: Rust (server), JDK 17+ (client).

```bash
# Server
cd server
cp config.example.toml config.toml
cargo run --release -- serve --config config.toml

# Client
cd client
powershell -ExecutionPolicy Bypass -File .\build.ps1
# Output: dist/client/lnsync.jar and loader-specific jars
```

On Linux, `cargo build --release` in `server/` produces `target/release/lnsync-server`.

---

## Server config (`config.toml`)

Copy `server/config.example.toml` (or the Release `config.example.toml`) to `config.toml`.

Keys are matched as `key = value` lines. **Table nesting is ignored**; you can put a key anywhere. Bracket sections are only for reading.

### Listen and paths

| Key | Example | Meaning |
|-----|---------|---------|
| `listen` | `"127.0.0.1"` | Bind address. Use `127.0.0.1` for local-only; `0.0.0.0` for LAN/public |
| `port` | `8765` | HTTP port |
| `data_dir` | `"data"` | Cache, object store, manifests, unpacked repos |
| `public_url` | `"http://127.0.0.1:8765"` | Public base URL for clients. IDN hostnames are allowed; client v0.1.1+ converts them to punycode |
| `overlay_dir` | `"./private"` | Overlay root; actual files live under `files/` |

### Pack source (GitHub)

| Key | Example | Meaning |
|-----|---------|---------|
| `provider` | `"github"` | Source type (GitHub Release) |
| `repo` | `"Owner/PackName"` | `owner/repo` |
| `api` | `"https://api.github.com"` | GitHub API root; mirrors allowed |
| `tag` | `"v1.0.0"` | Release tag; `version` is an alias |
| `client_asset` | `"*Client*.zip"` | Glob against Release asset names |
| `server_asset` | `"*Server*.zip"` | Server zip glob |
| `loader` | `"auto"` | `auto` / `forge` / `neoforge` / `fabric` / `quilt` |

Legacy aliases (pick one of each pair):

- `github_repo` ↔ `repo`
- `github_api` ↔ `api`
- `version` ↔ `tag`

### `loader` behavior

- **`auto`**: inferred from asset names and pack markers (`fabric.mod.json`, `mods.toml`, NeoForge, `libraries/`, …). Result is logged and stored in `data/manifests/meta.json`
- **Pinned**: set a loader in config or the admin UI; rebuild uses that type

### Auth

| Key | Meaning |
|-----|---------|
| `access_token` | Player/client sync token. If set, clients must send it (`update_token` in `lnsync.toml`). Empty = no check (local debug only) |
| `server_access_token` | Dedicated-server sync token. If set, `side=server` must use this token, not `access_token` |
| `admin_token` | Admin UI password. Empty = admin UI only from `127.0.0.1`; non-empty requires login |
| `allow_anonymous` | If tokens are empty, anonymous sync is **denied** unless this is explicitly `true` |

### Example

```toml
listen = "0.0.0.0"
port = 8765
data_dir = "data"
public_url = "https://update.example.com"

provider = "github"
repo = "Owner/PackName"
api = "https://api.github.com"
tag = "v1.2.3"
client_asset = "*Client*.zip"
server_asset = "*Server*.zip"
loader = "auto"

access_token = "a long random string"
server_access_token = "a different string for dedicated servers"
admin_token = "admin password"

overlay_dir = "./private"
```

### Server command

```bash
# Foreground (dev / debug)
lnsync-server serve --config config.toml

# From source
cargo run --release -- serve --config config.toml
```

Rebuild from the admin UI: download the Release, unpack, split client/server files, merge overlay, write the object store.

### Overlay layout (short)

```text
private/
  files/           # files to overlay or add; paths relative to the pack root
  ...
```

Per-side rules (client-only / server-only / both) are edited in the admin UI. Overlay files are included in the next rebuild.

### Official-pack adjustments

The admin **Official pack** tab lists official manifest files by folder. Search, then exclude or restore. Rules are written to `overlay_dir/official-adjust.toml`:

```toml
[[exclude]]
path = "mods/SomeMod.jar"
side = "both"   # both / client / server
```

After save + rebuild, excluded files are not in the client/server repos or manifests. A same-path overlay file still wins.

---

## Client config (`lnsync.toml`)

Place this in the **instance root** (same level as `mods/`). The filename must be `lnsync.toml`.

| Key | Required | Meaning |
|-----|----------|---------|
| `update_server` | yes | Server root, e.g. `http://127.0.0.1:8765` or `https://your.domain`. IDN hostnames work on client v0.1.1+ (punycode) |
| `update_token` | if the server uses one | Must match server `access_token`. Leave empty if the server has no token |
| `instance_dir` | no | Directory to sync into. Defaults to the current instance; relative or absolute |

### Example

```toml
update_server = "https://update.example.com"
update_token = "same as server access_token"

# optional; usually leave unset
# instance_dir = "."
```

### Client behavior

- Sync runs via TransformationService (Forge/NeoForge) or `preLaunch` (Fabric/Quilt)
- The universal jar ships all four loader metadata files; only the current loader’s entry runs, and duplicate triggers are ignored
- State: `lnsync-state.json` in the instance root
- Log: `logs/lnsync.log`
- The mod jar itself (`mods/lnsync*.jar`) is never deleted by sync
- An empty or malformed remote `files` list, or a delete ratio that is too high, **fails closed** so the instance is not wiped
- `config/` and `defaultconfigs/` are overwritten only when the player has not changed them since the last synced hash

If the configured host is unreachable, the client tries localhost on the same port and, when a GUI is available, offers a retry.

---

## Admin UI

- Path prefix: `/admin/ifgfsgfbijuzoxzq`
- Full example: `http://PUBLIC-OR-LAN-IP:PORT/admin/ifgfsgfbijuzoxzq`
- Editable: repo, tag, asset globs, loader, bind/public URL, sync tokens
- Actions: rebuild, logs/progress, overlay files, official-pack excludes (categories/search), connection info
- The admin token is not echoed back. Responses keep CSP, X-Frame-Options, and similar headers

---

## API (for debugging)

| Path | Meaning |
|------|---------|
| `GET /api/status` | Server status and version fingerprint |
| `GET /api/manifest?side=client\|server` | Per-side file list |
| `GET /api/file/{sha256}` | Object by hash |
| `POST /api/pack` | Packed download (large packs) |

When tokens are enabled, clients send `X-LnSync-Token` (and side-related headers).

---

## Repository layout

```text
LnSync/
  server/                 # Rust server
    config.example.toml
    src/
    web/admin.html
  client/                 # Java client mod
    build.ps1
    lnsync.toml.example
    resources/loaders/    # forge / neoforge / fabric / quilt metadata
  dist/client/            # local build output (not required in git)
  README.md
  README.zh-CN.md
```

---

## FAQ

**Client says `unsupported URI` and the host is an IDN?**  
Use client **v0.1.1 or newer**, or write `update_server` as punycode (`xn--…`).

**Admin UI works locally, but remote clients cannot connect?**  
`listen` must be `0.0.0.0`, the firewall/security group must allow the port, and `public_url` must be a URL those clients can reach.

**401 / access token required?**  
The server has `access_token` set. Put the same string in the instance `lnsync.toml` as `update_token`.

**Dedicated-server sync vs player token?**  
Use `server_access_token` on dedicated-server instances. Do not reuse the player `access_token`.

**Double-clicking the jar does nothing / prints usage?**  
Expected. The client only runs as a loaded mod.

---

## License

[Apache License 2.0](LICENSE) (same as [ItemBan](https://github.com/lnsanes/itemban))
