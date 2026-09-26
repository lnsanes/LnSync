# LnSync

面向 Minecraft 整合包的通用文件更新器：服务端按清单托管文件，客户端在游戏启动早期按哈希增量同步。支持 Forge、NeoForge、Fabric、Quilt，也可使用一份通用客户端模组。

## 能做什么

- **服务端**（`server/`，Rust）：从可配置的 GitHub Release 拉取 Client / Server 包，构建 sha256 对象库与端侧清单；提供状态、清单、单文件与打包下载接口。
- **客户端**（`client/`，Java 模组）：放入实例 `mods/` 后，启动时自动检查并拉取改动文件；状态记在 `lnsync-state.json`。
- **权限**：可分别配置玩家同步令牌、开服端同步令牌与管理页口令。

## 加载器

配置项 `loader` 支持 `auto`、`forge`、`neoforge`、`fabric`、`quilt`：

- **手动指定**：在管理页「源与加载器」或 `config.toml` 中选择。
- **自动识别**：构建时根据 Release 附件名与包内标记（如 `fabric.mod.json`、`mods.toml`、NeoForge、`libraries/` 等）判断，并写入日志与 `meta.json`。

## 自定义整合包源

仓库、标签与附件通配符均可配置，不绑定某一个固定整合包：

```toml
repo = "Owner/PackName"
api = "https://api.github.com"
tag = "v1.0.0"
client_asset = "*Client*.zip"
server_asset = "*Server*.zip"
loader = "auto"
```

也可在管理页修改上述项并重新拉取构建。

## 快速开始

### 服务端

```bash
cd server
cp config.example.toml config.toml   # 填写仓库、标签与令牌
cargo run --release -- serve --config config.toml
```

### 客户端模组（需 JDK 17+）

```bash
cd client
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

产物在 `dist/client/`。推荐使用通用版：

1. 将 `lnsync.jar`（与 `lnsync-universal.jar` 相同）放入实例 `mods/`
2. 把 `lnsync.toml.example` 复制为实例根目录的 `lnsync.toml`，填写 `update_server` 与 `update_token`
3. 用启动器正常开游戏，模组会在启动早期完成同步

若只想保留单一加载器入口，也可使用：

- `lnsync-forge.jar`
- `lnsync-neoforge.jar`
- `lnsync-fabric.jar`
- `lnsync-quilt.jar`

通用版内含各加载器元数据；实际只会走当前加载器的入口，重复触发会自动去重。客户端不提供双击独立同步界面；`Main` 仅保留内部 `fetch-job` 子进程（大包多进程下载用）。

## 管理页

默认路径前缀：`/admin/ifgfsgfbijuzoxzq`。管理令牌不会回显；已保留基础安全响应头（如 CSP、X-Frame-Options）。

## 许可

MIT
