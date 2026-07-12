"""
MiroFish Backend WSGI 入口（生产环境，供 gunicorn 使用）

用法: gunicorn --workers 1 --threads 8 wsgi:app
注意: workers 必须为 1 —— SimulationRunner 在进程内存中跟踪模拟子进程
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config

errors = Config.validate()
if errors:
    print("配置错误:")
    for err in errors:
        print(f"  - {err}")
    print("\n请检查环境变量配置")
    sys.exit(1)

app = create_app()
