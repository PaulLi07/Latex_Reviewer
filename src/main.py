"""
LaTeX 论文 AI 审稿工具

主入口
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import main

if __name__ == "__main__":
    main()
