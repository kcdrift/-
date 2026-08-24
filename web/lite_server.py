"""轻量Web服务器：直接提供静态数据文件，无需实时计算。"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = r"D:\足彩"

# 预加载静态数据
with open(os.path.join(ROOT, "web", "mobile", "static_data_new.json"), "r", encoding="utf-8") as f:
    ALL_PREDICTIONS = json.load(f)

print(f"已加载 {len(ALL_PREDICTIONS)} 场预测，{len(set(p['league'] for p in ALL_PREDICTIONS))} 个联赛")


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path
        if path in ("/", "/index.html"):
            self._send_file(os.path.join(ROOT, "web", "templates", "index.html"),
                            "text/html; charset=utf-8")
        elif path == "/mobile" or path == "/mobile/":
            self._send_file(os.path.join(ROOT, "web", "mobile", "index.html"),
                            "text/html; charset=utf-8")
        elif path.startswith("/mobile/"):
            file_path = os.path.join(ROOT, "web", "mobile", path[len("/mobile/"):])
            if os.path.exists(file_path):
                mime_type = "application/json" if file_path.endswith('.json') else "text/html"
                self._send_file(file_path, mime_type)
            else:
                self.send_error(404)
        elif path == "/api/filters":
            leagues = sorted(set(p["league"] for p in ALL_PREDICTIONS))
            dates = sorted(set(p["date"] for p in ALL_PREDICTIONS))
            self._send_json({"leagues": leagues, "dates": dates})
        elif path == "/api/predictions":
            # 支持筛选
            league = self.headers.get("X-League")
            date = self.headers.get("X-Date")
            data = ALL_PREDICTIONS
            if league:
                data = [p for p in data if p["league"] == league]
            if date:
                data = [p for p in data if p["date"] == date]
            self._send_json(data)
        elif path == "/api/stats":
            # 统计信息
            from collections import Counter
            league_counts = Counter(p["league"] for p in ALL_PREDICTIONS)
            date_counts = Counter(p["date"] for p in ALL_PREDICTIONS)
            high_conf = sum(1 for p in ALL_PREDICTIONS if p.get("confidence", {}).get("level") == "高")
            self._send_json({
                "total": len(ALL_PREDICTIONS),
                "leagues": dict(league_counts),
                "by_date": dict(date_counts),
                "high_confidence": high_conf
            })
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


def run(host="0.0.0.0", port=8080):
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"足彩预测界面已启动: http://localhost:{port}")
    print(f"移动端: http://localhost:{port}/mobile/")
    print(f"API: http://localhost:{port}/api/stats")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    run()
