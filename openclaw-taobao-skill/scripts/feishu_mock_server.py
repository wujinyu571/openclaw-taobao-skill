"""
本地飞书模拟器 - 用于测试 Task 下发和结果回传
运行方式: python scripts/feishu_mock_server.py
"""
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from typing import List, Dict, Any
import queue
import sys

# 全局任务队列和结果存储
task_queue = queue.Queue()
results_store: List[Dict[str, Any]] = []


class FeishuMockHandler(BaseHTTPRequestHandler):
    """处理飞书相关的 HTTP 请求"""

    def do_GET(self):
        """GET 请求 - 用于拉取任务"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/api/get_task':
            # 从队列中获取任务（阻塞式，超时返回空）
            try:
                task = task_queue.get(timeout=5)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "code": 0,
                    "data": task
                }
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
                print(f"✅ [任务下发] {json.dumps(task, ensure_ascii=False)}")
            except queue.Empty:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "code": 1,
                    "message": "No tasks available"
                }
                self.wfile.write(json.dumps(response).encode())

        elif parsed_path.path == '/api/results':
            # 查看所有回传结果
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "code": 0,
                "count": len(results_store),
                "results": results_store
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode())

        elif parsed_path.path == '/health':
            # 健康检查接口
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """POST 请求 - 用于接收结果回传和添加任务"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/api/webhook':
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                result_data = json.loads(body.decode('utf-8'))

                # 存储结果
                result_record = {
                    "timestamp": datetime.now().isoformat(),
                    "result": result_data
                }
                results_store.append(result_record)

                # 打印结果
                print("\n" + "="*60)
                print("📨 [收到飞书回传]")
                print("="*60)
                print(json.dumps(result_data, ensure_ascii=False, indent=2))
                print("="*60 + "\n")

                # 返回成功响应
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "code": 0,
                    "message": "Success"
                }
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "code": 1,
                    "message": str(e)
                }
                self.wfile.write(json.dumps(response).encode())

        elif parsed_path.path == '/api/add_task':
            # 手动添加任务到队列
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                task_data = json.loads(body.decode('utf-8'))
                add_task(task_data)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "code": 0,
                    "message": "Task added successfully"
                }
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "code": 1,
                    "message": str(e)
                }
                self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """抑制默认日志输出"""
        pass


def add_task(task_data: Dict[str, Any]):
    """向任务队列添加任务"""
    task_queue.put(task_data)
    print(f"📥 [任务已加入队列] {json.dumps(task_data, ensure_ascii=False)}")


def get_results() -> List[Dict[str, Any]]:
    """获取所有回传结果"""
    return results_store.copy()


def start_server(port=8080):
    """启动 HTTP 服务器"""
    server = HTTPServer(('localhost', port), FeishuMockHandler)

    # 使用 UTF-8 编码输出
    sys.stdout.reconfigure(encoding='utf-8')

    print("🚀 飞书模拟器启动成功!", flush=True)
    print(f"   - 任务下发接口: http://localhost:{port}/api/get_task", flush=True)
    print(f"   - 结果回传接口: http://localhost:{port}/api/webhook", flush=True)
    print(f"   - 健康检查接口: http://localhost:{port}/health", flush=True)
    print(f"   - 按 Ctrl+C 停止服务器\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  服务器已停止")
        server.shutdown()


if __name__ == '__main__':
    start_server(8080)
