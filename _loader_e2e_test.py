#!/usr/bin/env python3
"""Fixture E2E: mock GitHub API + tiny Client/Server zips for each loader; run lnsync build."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server"
EXE = SERVER / "target" / "release" / "lnsync-server.exe"
WORK = ROOT / "_loader_e2e"
FIXTURES = WORK / "fixtures"
REPORT = WORK / "report.json"

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
        server_files = dict(meta["markers"])
        server_files.update(meta["server_extra"])
        # Distinct server-only file so ingest has something for server side.
        server_files["server-only.txt"] = b"server"
        client_files["client-only.txt"] = b"client"
        make_zip(folder / meta["client"], client_files)
        make_zip(folder / meta["server"], server_files)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        # /repos/LnSync/Demo-{loader}/releases/tags/{tag}
        if "/releases/tags/" in path:
            parts = path.strip("/").split("/")
            # repos Owner Pack releases tags TAG
            try:
                pack = parts[2]  # Demo-forge
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


def write_config(path: Path, loader: str, api: str, mode: str) -> None:
    meta = LOADERS[loader]
    loader_field = "auto" if mode == "auto" else loader
    path.write_text(
        f"""
listen = "127.0.0.1"
port = 18765
data_dir = "data"
public_url = "http://127.0.0.1:18765"
provider = "github"
repo = "LnSync/Demo-{loader}"
api = "{api}"
tag = "{meta['tag']}"
client_asset = "*Client*.zip"
server_asset = "*Server*.zip"
loader = "{loader_field}"
access_token = ""
server_access_token = ""
admin_token = ""
overlay_dir = "./private"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def run_build(workdir: Path) -> tuple[int, str]:
    # Invoke build via a tiny helper: start serve is heavy; call through cargo run with env?
    # LnSync only exposes `serve`. Use admin rebuild by posting to a one-shot binary path.
    # Instead compile a one-liner using the same code path: run server briefly and POST rebuild.
    # Simpler: use `cargo run` isn't available for build. Call internal via rustc test?
    # We'll shell out to a small rust one-off... Actually admin rebuild needs running server.
    # Use Python to call the release binary with a hidden approach:
    # Start serve, wait, POST /admin/.../api/rebuild, read meta.
    proc = subprocess.Popen(
        [str(EXE), "serve", "--config", "config.toml"],
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log = []
    try:
        deadline = time.time() + 20
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                return proc.returncode or 1, out
            try:
                import urllib.error
                import urllib.request

                try:
                    urllib.request.urlopen("http://127.0.0.1:18765/api/status", timeout=1)
                    ready = True
                    break
                except urllib.error.HTTPError as err:
                    # 401/409 still means the HTTP server is up
                    if err.code in (401, 409, 404):
                        ready = True
                        break
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(0.2)
        if not ready:
            proc.kill()
            leftover = ""
            try:
                leftover = proc.stdout.read() if proc.stdout else ""
            except Exception:
                pass
            return 1, "server not ready: " + leftover[:800]
        import urllib.request

        req = urllib.request.Request(
            "http://127.0.0.1:18765/admin/ifgfsgfbijuzoxzq/api/rebuild",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode("utf-8", "replace")
                log.append(f"rebuild={resp.status} {body[:300]}")
        except Exception as err:
            log.append(f"rebuild_err={err}")
            # keep going to capture notes / meta
        time.sleep(0.5)
        meta_path = workdir / "data" / "manifests" / "meta.json"
        notes = ""
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:18765/admin/ifgfsgfbijuzoxzq/api/state", timeout=5
            ) as resp:
                notes = resp.read().decode("utf-8", "replace")
        except Exception as err:
            notes = f"state_err={err}"
        return 0, json.dumps({"log": log, "meta_exists": meta_path.is_file(), "state": notes[:2000]}, ensure_ascii=False)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def check_real_github() -> list[dict]:
    import urllib.request

    packs = [
        {"loader_expect": "forge", "repo": "Jasons-impart/Create-Delight-Remake", "tag": "v0.5.0.15"},
        {"loader_expect": "forge", "repo": "GregTechCEu/GregTech-Community-Pack", "tag": "v1.7.5"},
        {"loader_expect": "forge", "repo": "ThePansmith/CABIN", "tag": "2.0.8"},
        # Fabric / NeoForge / Quilt: many public packs don't ship named Client/Server assets;
        # we still probe a few known release pages for asset-name signals.
        {"loader_expect": "fabric", "repo": "Fabulously-Optimized/fabulously-optimized", "tag": "v.1.20.1.1"},
        {"loader_expect": "neoforge", "repo": "AllTheMods/ATM-10", "tag": "2.0"},
    ]
    out = []
    for pack in packs:
        url = f"https://api.github.com/repos/{pack['repo']}/releases/tags/{pack['tag']}"
        req = urllib.request.Request(url, headers={"User-Agent": "lnsync-test", "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                doc = json.loads(resp.read().decode())
            names = [a.get("name", "") for a in doc.get("assets", [])]
            joined = " ".join(names).lower()
            scores = {
                "neoforge": sum(k in joined for k in ("neoforge", "neoforged", "neo-forge")),
                "quilt": sum(k in joined for k in ("quilt", "quilt-loader")),
                "fabric": sum(k in joined for k in ("fabric", "fabric-loader")),
                "forge": sum(k in joined for k in ("forge", "minecraftforge")),
            }
            # Prefer specific
            best = max(scores, key=lambda k: (scores[k], {"neoforge": 3, "quilt": 2, "fabric": 1, "forge": 0}[k]))
            detected = best if scores[best] > 0 else None
            out.append(
                {
                    "repo": pack["repo"],
                    "tag": pack["tag"],
                    "assets": names,
                    "name_detect": detected,
                    "note": "附件名检测；无关键词时需依赖包内标记（构建后）",
                }
            )
        except Exception as err:
            out.append({"repo": pack["repo"], "tag": pack["tag"], "error": str(err)})
    return out


def main() -> None:
    if not EXE.is_file():
        raise SystemExit(f"missing binary {EXE}")
    WORK.mkdir(exist_ok=True)
    build_fixtures()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    api = f"http://127.0.0.1:{port}"
    results = []
    for loader in LOADERS:
        for mode in ("auto", "manual"):
            workdir = WORK / f"run-{loader}-{mode}"
            if workdir.exists():
                shutil.rmtree(workdir)
            workdir.mkdir(parents=True)
            (workdir / "private" / "files").mkdir(parents=True)
            write_config(workdir / "config.toml", loader, api, mode)
            code, detail = run_build(workdir)
            meta = {}
            meta_path = workdir / "data" / "manifests" / "meta.json"
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            expected = loader
            got = meta.get("loader")
            ok = code == 0 and got == expected
            # also accept resolved_loader from state JSON
            if not ok and detail:
                try:
                    parsed = json.loads(detail)
                    state = json.loads(parsed.get("state") or "{}")
                    got = got or state.get("resolved_loader")
                    ok = got == expected
                except Exception:
                    pass
            results.append(
                {
                    "loader": loader,
                    "mode": mode,
                    "ok": ok,
                    "expected": expected,
                    "got": got,
                    "detail": detail[:1500],
                    "client_files": sum(1 for p in (workdir / "data" / "repos" / "client").rglob("*") if p.is_file()) if (workdir / "data" / "repos" / "client").exists() else 0,
                    "server_files": sum(1 for p in (workdir / "data" / "repos" / "server").rglob("*") if p.is_file()) if (workdir / "data" / "repos" / "server").exists() else 0,
                }
            )
            print(f"[{'OK' if ok else 'FAIL'}] {loader}/{mode} got={got}")
    httpd.shutdown()
    real = check_real_github()
    report = {"fixture_e2e": results, "real_github_assets": real}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fails = [r for r in results if not r["ok"]]
    print(f"fixture fails={len(fails)}/{len(results)}")
    print(f"report={REPORT}")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
