"""Local curation desk for the HuniePop PT-BR locale.

Bind is loopback by default. The desk reads and writes the locale CSVs
in this repository; it does not open the Steam install.

    python scripts/curate.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from store import GROUP_RE, Store

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 200_000


class Handler(BaseHTTPRequestHandler):
    store: Store = None  # type: ignore
    server_version = "HuniePopCuradoria/0.1"

    def log_message(self, fmt: str, *args) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"ok": True})
            return
        if parsed.path == "/api/catalog":
            self._json(self.store.catalog())
            return
        if parsed.path == "/api/scene":
            gid = (parse_qs(parsed.query).get("id") or [""])[0]
            if not GROUP_RE.fullmatch(gid):
                self._json({"error": "cena desconhecida"}, 400)
                return
            scene = self.store.scene(gid)
            if not scene:
                self._json({"error": "cena desconhecida"}, 404)
                return
            self._json(scene)
            return
        if parsed.path == "/":
            self._file(STATIC / "index.html")
            return
        if parsed.path in {"/app.js", "/app.css"}:
            self._file(STATIC / parsed.path.lstrip("/"))
            return
        self._json({"error": "não encontrado"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._body()
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        try:
            if parsed.path == "/api/preview":
                result = self.store.preview(str(payload.get("id") or ""), str(payload.get("pt") if payload.get("pt") is not None else ""))
                if not result:
                    self._json({"error": "frase desconhecida"}, 404)
                    return
                self._json(result)
                return
            if parsed.path == "/api/line":
                result = self.store.update(
                    str(payload.get("id") or ""),
                    str(payload.get("pt") if payload.get("pt") is not None else ""),
                    str(payload.get("status") or ""),
                    str(payload.get("note") or ""),
                )
                self._json(result)
                return
            if parsed.path == "/api/apply":
                self._json(self.store.apply())
                return
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"error": "não encontrado"}, 404)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY:
            raise ValueError("corpo grande demais")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("json inválido") from exc
        if not isinstance(data, dict):
            raise ValueError("json inválido")
        return data

    def _json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
        accept = self.headers.get("Accept-Encoding") or ""
        if len(raw) > 800 and "gzip" in accept:
            raw = gzip.compress(raw, compresslevel=6)
            headers["Content-Encoding"] = "gzip"
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self._json({"error": "não encontrado"}, 404)
            return
        kind = "text/html; charset=utf-8"
        if path.suffix == ".js":
            kind = "text/javascript; charset=utf-8"
        elif path.suffix == ".css":
            kind = "text/css; charset=utf-8"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def serve(store: Store, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    Handler.store = store
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    store = Store.open()
    httpd = serve(store, args.host, args.port)
    print(f"Curadoria em http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
