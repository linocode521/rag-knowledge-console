# -*- coding: utf-8 -*-
"""
FastGPT 连接层（本地代理 + 页面服务）
- 零依赖：只用 Python 标准库，Python 3.7+ 可运行
- 作用：浏览器只访问 http://127.0.0.1:8100，由它带着 Key 去调 FastGPT
- 启动前必须设置环境变量：FG_KEY（新的应用 Key）、FG_BASE（默认云版）

启动：
  set FG_KEY=fastgpt-你的新key
  set FG_BASE=https://cloud.fastgpt.cn/api
  python proxy.py
然后浏览器打开 http://127.0.0.1:8100
"""
import json
import os
import socket
import socketserver
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# 控制台中文输出（Windows 默认 GBK，避免乱码）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.environ.get("FG_BASE", "https://cloud.fastgpt.cn/api").rstrip("/")
KEY = os.environ.get("FG_KEY", "").strip()
HOST, PORT = "127.0.0.1", 8100
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # 允许从 file:// 打开的原型跨域调用本机连接层
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            f = os.path.join(ROOT, "index.html")
            if not os.path.exists(f):
                return self._send(500, "缺少 index.html，请确认和 proxy.py 在同一目录")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if path == "/api/health":
            return self._send(200, json.dumps({
                "ok": True,
                "base": BASE,
                "key_set": bool(KEY),
                "key_hint": ("****" + KEY[-4:]) if KEY else "",
            }, ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}, ensure_ascii=False))

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/chat":
            return self._send(404, json.dumps({"error": "not found"}, ensure_ascii=False))
        if not KEY:
            return self._send(400, json.dumps(
                {"error": "未设置 FG_KEY 环境变量，请在启动脚本里填写新的应用 Key"},
                ensure_ascii=False))

        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._send(400, json.dumps({"error": "请求不是合法 JSON"}, ensure_ascii=False))

        body.setdefault("stream", False)
        body.setdefault("detail", True)
        body.setdefault("chatId", "local-ui")

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            BASE + "/v1/chat/completions",
            data=data,
            headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = r.read()
            return self._send(200, payload)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")
            try:
                up = json.loads(detail)
            except Exception:
                up = {}
            msg = up.get("statusText") or up.get("message") or ("HTTP %d" % e.code)
            return self._send(502, json.dumps({
                "error": "FastGPT 返回：%s" % msg,
                "hint": "Key 无效或应用未关联知识库；确认 Key 是「应用 Key」且 Base 为 https://cloud.fastgpt.cn/api",
                "upstream_code": up.get("code"),
                "upstream": detail[:800],
            }, ensure_ascii=False))
        except Exception as e:
            return self._send(502, json.dumps({
                "error": "请求失败：%s" % e,
                "hint": "网络不通或被代理拦截；确认地址为 https://cloud.fastgpt.cn/api",
            }, ensure_ascii=False))


class LocalServer(socketserver.ThreadingMixIn, HTTPServer):
    """跳过 socket.getfqdn —— 中文 Windows 主机名会让 Python 3.7 抛 UnicodeDecodeError"""
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = HOST
        self.server_port = self.server_address[1]


if __name__ == "__main__":
    if not KEY:
        print("警告：未设置 FG_KEY，页面能打开但无法问答。")
    print("连接层已启动：http://%s:%d" % (HOST, PORT))
    print("上游地址：%s" % BASE)
    print("提示：浏览器打开上面的地址，Key 只在本地使用，不会暴露给页面。")
    httpd = LocalServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
