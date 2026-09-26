#!/usr/bin/env python3
"""Sequential client-sync E2E: four loader packs → four fake MC instances via universal jar gate."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_EXE = ROOT / "server" / "target" / "release" / "lnsync-server.exe"
CLIENT_JAR = ROOT / "dist" / "client" / "lnsync-universal.jar"
JAVA = Path(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin\java.exe")
WORK = ROOT / "_loader_e2e"
FIXTURES = WORK / "fixtures"
INSTANCES = WORK / "instances"
REPORT = WORK / "client_sync_report.json"
PORT = 18765
BASE = f"http://127.0.0.1:{PORT}"

LOADERS = {
    "forge": {
        "tag": "v-forge-1",
        "client": "Demo-Forge-Client.zip",
        "server": "Demo-Forge-Server.zip",
        "markers": {"forge.jar": b"forge", "mods/shared.jar": b"mod"},
        "server_extra": {"libraries/net/minecraftforge/forge/x.txt": b"lib"},
    },
    "neoforge": {
        "tag": "v-neoforge-1",
        "client": "Demo-NeoForge-Client.zip",
        "server": "Demo-NeoForge-Server.zip",
        "markers": {"mods/shared.jar": b"mod"},
        "server_extra": {"libraries/net/neoforged/neoforge/x.txt": b"lib"},
    },
    "fabric": {
        "tag": "v-fabric-1",
        "client": "Demo-Fabric-Client.zip",
        "server": "Demo-Fabric-Server.zip",
        "markers": {"fabric.mod.json": b"{}", "mods/shared.jar": b"mod"},
        "server_extra": {},
    },
    "quilt": {
        "tag": "v-quilt-1",
        "client": "Demo-Quilt-Client.zip",
        "server": "Demo-Quilt-Server.zip",
        "markers": {"quilt.mod.json": b"{}", "mods/shared.jar": b"mod"},
        "server_extra": {},
    },
}


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def build_fixtures() -> None:
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    FIXTURES.mkdir(parents=True)
    for loader, meta in LOADERS.items():
        folder = FIXTURES / loader
        folder.mkdir()
        client_files = dict(meta["markers"])
        client_files["client-only.txt"] = b"client"
        server_files = dict(meta["markers"])
        server_files.update(meta["server_extra"])
        server_files["server-only.txt"] = b"server"
        make_zip(folder / meta["client"], client_files)
        make_zip(folder / meta["server"], server_files)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if "/releases/tags/" in path:
            parts = path.strip("/").split("/")
            try:
                pack = parts[2]
                tag = parts[5]
            except IndexError:
                self.send_error(404)
                return
            loader = pack.replace("Demo-", "").lower()
            meta = LOADERS.get(loader)
            if not meta or meta["tag"] != tag:
                self.send_error(404)
                return
            base = f"http://127.0.0.1:{self.server.server_port}/assets/{loader}"
            body = {
                "tag_name": tag,
                "body": f"fixture {loader}",
                "assets": [
                    {
                        "name": meta["client"],
                        "size": (FIXTURES / loader / meta["client"]).stat().st_size,
                        "browser_download_url": f"{base}/{meta['client']}",
                    },
                    {
                        "name": meta["server"],
                        "size": (FIXTURES / loader / meta["server"]).stat().st_size,
                        "browser_download_url": f"{base}/{meta['server']}",
                    },
                ],
            }
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/assets/"):
            _, _, loader, name = path.split("/", 3)
            file_path = FIXTURES / loader / name
            if not file_path.is_file():
                self.send_error(404)
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)


def free_port(port: int) -> None:
    try:
        import psutil  # type: ignore

        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                try:
                    psutil.Process(conn.pid).kill()
                except Exception:
                    pass
    except Exception:
        # Fallback: PowerShell
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}",
            ],
            check=False,
            capture_output=True,
        )
    time.sleep(0.4)


def write_server_config(path: Path, loader: str, api: str) -> None:
    meta = LOADERS[loader]
    path.write_text(
        f"""
listen = "127.0.0.1"
port = {PORT}
data_dir = "data"
public_url = "{BASE}"
provider = "github"
repo = "LnSync/Demo-{loader}"
api = "{api}"
tag = "{meta['tag']}"
client_asset = "*Client*.zip"
server_asset = "*Server*.zip"
loader = "{loader}"
access_token = ""
server_access_token = ""
admin_token = ""
overlay_dir = "./private"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def wait_ready(timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE}/api/status", timeout=1)
            return True
        except urllib.error.HTTPError as err:
            if err.code in (401, 409, 404):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def rebuild() -> None:
    req = urllib.request.Request(
        f"{BASE}/admin/ifgfsgfbijuzoxzq/api/rebuild",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"rebuild HTTP {resp.status}")


def client_manifest() -> dict:
    with urllib.request.urlopen(f"{BASE}/api/manifest?side=client", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def prepare_instance(loader: str) -> Path:
    inst = INSTANCES / loader
    if inst.exists():
        shutil.rmtree(inst)
    mods = inst / "mods"
    mods.mkdir(parents=True)
    shutil.copy2(CLIENT_JAR, mods / "lnsync.jar")
    (inst / "lnsync.toml").write_text(
        f'update_server = "{BASE}"\nupdate_token = ""\n',
        encoding="utf-8",
    )
    # Loader-flavored marker so the fake instance looks like that ecosystem.
    if loader == "forge":
        (inst / "forge-marker.txt").write_text("forge-instance\n", encoding="utf-8")
    elif loader == "neoforge":
        (inst / "neoforge-marker.txt").write_text("neoforge-instance\n", encoding="utf-8")
    elif loader == "fabric":
        (inst / "fabric-marker.txt").write_text("fabric-instance\n", encoding="utf-8")
    else:
        (inst / "quilt-marker.txt").write_text("quilt-instance\n", encoding="utf-8")
    return inst


def run_gate(instance: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(JAVA), "-Dlnsync.forceClient=true", "-jar", str(instance / "mods" / "lnsync.jar"), "gate"],
        cwd=str(instance),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    log = ""
    log_path = instance / "logs" / "lnsync.log"
    if log_path.is_file():
        log = log_path.read_text(encoding="utf-8", errors="replace")
    return proc.returncode, out + "\n--- log ---\n" + log


def verify_instance(instance: Path, manifest: dict) -> tuple[bool, list[str]]:
    missing = []
    for item in manifest.get("files", []):
        rel = str(item.get("path", "")).replace("\\", "/")
        if not rel or rel.startswith("mods/lnsync"):
            continue
        target = instance / Path(*rel.split("/"))
        if not target.is_file():
            missing.append(rel)
    # Must keep the updater mod itself.
    if not (instance / "mods" / "lnsync.jar").is_file():
        missing.append("mods/lnsync.jar (self)")
    return (not missing), missing


def test_loader(loader: str, api: str) -> dict:
    print(f"\n=== {loader} ===", flush=True)
    free_port(PORT)
    workdir = WORK / f"sync-run-{loader}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    (workdir / "private" / "files").mkdir(parents=True)
    write_server_config(workdir / "config.toml", loader, api)

    proc = subprocess.Popen(
        [str(SERVER_EXE), "serve", "--config", "config.toml"],
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    result: dict = {"loader": loader, "ok": False}
    try:
        if not wait_ready():
            leftover = ""
            try:
                leftover = proc.stdout.read() if proc.stdout else ""
            except Exception:
                pass
            result["error"] = "server not ready: " + leftover[:800]
            print(f"[FAIL] {loader} server not ready", flush=True)
            return result

        rebuild()
        meta_path = workdir / "data" / "manifests" / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        got_loader = meta.get("loader")
        result["resolved_loader"] = got_loader
        if got_loader != loader:
            result["error"] = f"loader mismatch expected={loader} got={got_loader}"
            print(f"[FAIL] {loader} loader mismatch got={got_loader}", flush=True)
            return result

        manifest = client_manifest()
        result["manifest_files"] = len(manifest.get("files", []))
        result["official_version"] = manifest.get("official_version") or meta.get("official_version")

        instance = prepare_instance(loader)
        code1, out1 = run_gate(instance)
        result["gate1_code"] = code1
        result["gate1_out"] = out1[-2000:]
        ok1, missing1 = verify_instance(instance, manifest)
        result["missing_after_gate1"] = missing1

        # Second pass should be a no-op / already latest.
        code2, out2 = run_gate(instance)
        result["gate2_code"] = code2
        result["gate2_out"] = out2[-1500:]
        ok2, missing2 = verify_instance(instance, manifest)
        result["missing_after_gate2"] = missing2
        already = ("已是最新" in out2) or ("已是最新" in (instance / "logs" / "lnsync.log").read_text(encoding="utf-8", errors="replace") if (instance / "logs" / "lnsync.log").is_file() else "")

        result["ok"] = code1 == 0 and ok1 and code2 == 0 and ok2 and bool(already or ok2)
        result["already_latest_on_second"] = bool(already)
        result["instance"] = str(instance)
        status = "OK" if result["ok"] else "FAIL"
        print(
            f"[{status}] {loader} files={result['manifest_files']} "
            f"missing={missing1} latest2={already}",
            flush=True,
        )
        return result
    except Exception as err:
        result["error"] = str(err)
        print(f"[FAIL] {loader} {err}", flush=True)
        return result
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        free_port(PORT)


def main() -> None:
    if not SERVER_EXE.is_file():
        raise SystemExit(f"missing {SERVER_EXE}")
    if not CLIENT_JAR.is_file():
        raise SystemExit(f"missing {CLIENT_JAR} — run client/build.ps1 first")
    if not JAVA.is_file():
        raise SystemExit(f"missing {JAVA}")

    WORK.mkdir(exist_ok=True)
    build_fixtures()
    if INSTANCES.exists():
        shutil.rmtree(INSTANCES)
    INSTANCES.mkdir(parents=True)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    api = f"http://127.0.0.1:{httpd.server_address[1]}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    results = []
    try:
        for loader in ("forge", "neoforge", "fabric", "quilt"):
            results.append(test_loader(loader, api))
    finally:
        httpd.shutdown()

    report = {"client_sync_e2e": results}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fails = [r for r in results if not r.get("ok")]
    print(f"\nclient sync fails={len(fails)}/{len(results)}", flush=True)
    print(f"report={REPORT}", flush=True)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
