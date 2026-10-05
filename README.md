# LnSync

面向 Minecraft 整合包的通用文件更新器：服务端按清单托管文件，客户端在游戏启动早期按文件哈希做增量同步。支持 Forge、NeoForge、Fabric、Quilt；也提供一份通用客户端模组，四种加载器都能加载。

当前版本：**v0.1.3**  
发布页：https://github.com/lnsanes/LnSync/releases

---

## 能做什么

| 组件 | 目录 / 产物 | 说明 |
|------|-------------|------|
| 服务端 | `server/` → `lnsync-server` / `lnsync-server.exe` | 从 GitHub Release 拉取 Client/Server 包，构建对象库与端侧清单，对外提供 HTTP API 与管理页 |
| 客户端 | `client/` → `lnsync*.jar` | 作为模组放入实例 `mods/`，启动早期自动检查并拉取文件 |
| 私货 | `overlay_dir`（默认 `./private`） | 覆盖官方同名文件，可按端侧区分 |
| 官方包调整 | `private/official-adjust.toml` | 管理页按分类排除官方文件，支持搜索 |

协议要点：清单（manifest）+ sha256 对象 + `client` / `server` 端侧 + 可选令牌（玩家同步 / 开服同步 / 管理页）。

---

## 从 Release 使用（推荐）

到 [Releases](https://github.com/lnsanes/LnSync/releases) 下载对应资源。

### 1. 部署服务端

**Windows**

1. 下载 `lnsync-server.exe` 与 `config.example.toml`
2. 将示例复制为同目录下的 `config.toml`，按下文填写仓库、标签、令牌等
3. 在资源管理器或终端中进入该目录，执行：

```bat
lnsync-server.exe serve --config config.toml
```

**Linux（x86_64）**

1. 下载 `lnsync-server-linux-x86_64` 与 `config.example.toml`
2. 复制并编辑 `config.toml`
3. 赋予执行权限后启动：

```bash
chmod +x lnsync-server-linux-x86_64
./lnsync-server-linux-x86_64 serve --config config.toml
```

首次启动后打开管理页，配置好源信息，执行一次「重新构建」，生成客户端/服务端清单。

管理页默认地址（本机示例）：

```text
http://127.0.0.1:8765/admin/ifgfsgfbijuzoxzq
```

若设置了 `admin_token`，打开管理页需要输入该口令。

### 2. 安装客户端模组

1. 下载客户端 jar（推荐通用版 `lnsync.jar` 或 `lnsync-universal.jar`）
2. 放入游戏实例的 `mods/` 目录
3. 下载 `lnsync.toml.example`，复制到实例根目录（与 `mods/` 同级），改名为 `lnsync.toml`
4. 填写 `update_server`、`update_token`（见下文客户端配置）
5. 用启动器正常开游戏；模组会在启动早期同步，日志写在实例 `logs/lnsync.log`

专用包（可选，只保留对应加载器入口）：

- `lnsync-forge.jar`
- `lnsync-neoforge.jar`
- `lnsync-fabric.jar`
- `lnsync-quilt.jar`

> 客户端不提供双击独立更新界面。不要双击 jar；请作为模组由游戏加载。

### 3. 玩家日常流程

1. 确保更新服务器已启动，并且已经构建过清单  
2. 启动游戏 → 模组自动检查 → 有改动则下载/删除托管文件 → 无改动则直接进游戏  
3. 若模组文件有更新且不在极早阶段完成，可能需要再点一次启动（日志里会提示）

---

## 从源码构建

需要：Rust（服务端）、JDK 17+（客户端）。

```bash
# 服务端
cd server
cp config.example.toml config.toml
cargo run --release -- serve --config config.toml

# 客户端
cd client
powershell -ExecutionPolicy Bypass -File .\build.ps1
# 产物：dist/client/lnsync.jar 等
```

Linux 服务端也可在 Linux 环境或 Docker 中 `cargo build --release` 得到 `target/release/lnsync-server`。

---

## 服务端配置（`config.toml`）

复制 `server/config.example.toml`（或 Release 中的 `config.example.toml`）为 `config.toml`。

说明：解析按「`键 = 值`」行匹配，**不依赖 TOML 表层级**；把键写在文件任意位置均可。方括号段落仅便于阅读。

### 监听与路径

| 配置项 | 示例 | 说明 |
|--------|------|------|
| `listen` | `"127.0.0.1"` | 监听地址。仅本机用 `127.0.0.1`；局域网/公网需监听 `0.0.0.0` |
| `port` | `8765` | HTTP 端口 |
| `data_dir` | `"data"` | 数据目录：缓存、对象库、清单、仓库等 |
| `public_url` | `"http://127.0.0.1:8765"` | 对外公布的根地址（给客户端、导出说明用）。域名可用中文；客户端 v0.1.1+ 会自动转 punycode |
| `overlay_dir` | `"./private"` | 私货根目录；实际文件放在其下的 `files/` |

### 整合包源（GitHub）

| 配置项 | 示例 | 说明 |
|--------|------|------|
| `provider` | `"github"` | 源类型（当前为 GitHub Release） |
| `repo` | `"Owner/PackName"` | 仓库 `所有者/仓库名` |
| `api` | `"https://api.github.com"` | GitHub API 根；可用镜像 |
| `tag` | `"v1.0.0"` | Release 标签；也可用兼容键名 `version` |
| `client_asset` | `"*Client*.zip"` | 客户端附件通配符（匹配 Release 资源名） |
| `server_asset` | `"*Server*.zip"` | 服务端附件通配符 |
| `loader` | `"auto"` | 加载器：`auto` / `forge` / `neoforge` / `fabric` / `quilt` |

兼容旧键名（与上方等价，任选其一）：

- `github_repo` ↔ `repo`
- `github_api` ↔ `api`
- `version` ↔ `tag`

### 加载器 `loader` 行为

- **`auto`**：根据附件名与解压后的包内标记（如 `fabric.mod.json`、`mods.toml`、NeoForge、`libraries/` 等）自动判断，结果写入日志与 `data/manifests/meta.json`
- **手动指定**：在配置或管理页固定为某一种加载器，构建时按该类型处理

### 鉴权

| 配置项 | 说明 |
|--------|------|
| `access_token` | 玩家/客户端同步令牌。非空时，客户端请求需带此令牌（写入实例 `lnsync.toml` 的 `update_token`）。空 = 不校验（仅建议本机调试） |
| `server_access_token` | 开服端同步令牌。设置后，`side=server` 必须使用该令牌，与 `access_token` 隔离 |
| `admin_token` | 管理网页口令。空 = 仅本机 `127.0.0.1` 可进管理页；非空则需登录 |

### 配置示例

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

access_token = "换成一长串随机字符串"
server_access_token = "开服端另用一串"
admin_token = "管理页口令"

overlay_dir = "./private"
```

### 服务端常用命令

```bash
# 前台运行（开发 / 调试）
lnsync-server serve --config config.toml

# 从源码
cargo run --release -- serve --config config.toml
```

构建清单一般在管理页点「重新构建」；构建过程会下载 Release、解压、区分 client/server 文件、合并私货并生成对象库。

### 私货目录结构（简述）

```text
private/
  files/           # 要覆盖或追加的文件，路径相对整合包根
  ...
```

具体端侧（仅客户端 / 仅服务端 / 两端）可在管理页维护；私货会参与重建后的清单。

### 官方包调整

管理页「官方包」可按目录分类浏览官方清单文件，搜索后排除或恢复；规则写入 `overlay_dir/official-adjust.toml`：

```toml
[[exclude]]
path = "mods/SomeMod.jar"
side = "both"   # both / client / server
```

保存并重建后，被排除的文件不会进入客户端/服务端仓库与清单。有同名私货时私货优先保留。

---

## 客户端配置（`lnsync.toml`）

放在**游戏实例根目录**（与 `mods/` 同级），文件名必须为 `lnsync.toml`。

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `update_server` | 是 | 更新服务器根地址，如 `http://127.0.0.1:8765` 或 `https://你的域名`。支持中文域名（v0.1.1+ 自动转 punycode） |
| `update_token` | 视服务端 | 对应服务端 `access_token`。服务端未启用令牌时可留空 |
| `instance_dir` | 否 | 实际同步目录。默认当前实例；可填相对路径或绝对路径，用于把文件同步到别处 |

### 配置示例

```toml
update_server = "https://update.example.com"
update_token = "与服务端 access_token 一致"

# 可选：一般不用改
# instance_dir = "."
```

### 客户端行为说明

- 启动早期通过 TransformationService（Forge/NeoForge）或 `preLaunch`（Fabric/Quilt）触发同步  
- 通用版 jar 内含全部加载器元数据，当前环境只会走对应入口；重复触发会去重  
- 同步状态保存在实例根目录 `lnsync-state.json`  
- 运行日志：`logs/lnsync.log`  
- 模组自身（`mods/lnsync*.jar`）不会被同步删除  

若连不上服务器，客户端会尝试备用地址（如本机 `127.0.0.1` / `localhost` 同端口），并在有图形界面时提示重试。

---

## 管理页

- 路径前缀：`/admin/ifgfsgfbijuzoxzq`  
- 完整示例：`http://公网或局域网IP:端口/admin/ifgfsgfbijuzoxzq`  
- 可改：仓库、标签、附件通配符、加载器、监听与对外地址、同步令牌等  
- 可执行：重新构建、查看日志与进度、管理私货、调整官方包文件（分类/搜索排除）、连接信息等  
- 管理令牌不会在页面回显；响应头保留 CSP、X-Frame-Options 等基础防护  

---

## API 概览（给排查用）

| 路径 | 说明 |
|------|------|
| `GET /api/status` | 服务状态与版本指纹等 |
| `GET /api/manifest?side=client\|server` | 端侧文件清单 |
| `GET /api/file/{sha256}` | 按哈希下载对象 |
| `POST /api/pack` | 请求打包下载（大包场景） |

客户端请求在启用令牌时携带 `X-LnSync-Token`（以及端侧相关头）。

---

## 目录结构（仓库）

```text
LnSync/
  server/                 # Rust 服务端
    config.example.toml
    src/
    web/admin.html
  client/                 # Java 客户端模组源码
    build.ps1
    lnsync.toml.example
    resources/loaders/    # forge / neoforge / fabric / quilt 元数据
  dist/client/            # 本地构建产物（可不入库）
  README.md
```

---

## 常见问题

**客户端报 `unsupported URI` 且地址是中文域名？**  
请使用 **v0.1.1 及以上** 客户端；或把 `update_server` 写成 punycode（例如用系统/在线工具把中文域名转成 `xn--....`）。

**本机能开管理页，外网客户端连不上？**  
检查 `listen` 是否为 `0.0.0.0`、防火墙与云安全组是否放行端口、`public_url` 是否写成外网可访问地址。

**401 / 需要访问令牌？**  
服务端启用了 `access_token`，请在实例 `lnsync.toml` 的 `update_token` 填同一字符串。

**开服端同步与玩家令牌冲突？**  
给开服实例使用 `server_access_token`，不要混用玩家的 `access_token`。

**双击 jar 没反应或只打印用法？**  
这是预期行为。客户端只能作为模组加载。

---

## 许可

[Apache License 2.0](LICENSE)（与 [ItemBan](https://github.com/lnsanes/itemban) 相同）
