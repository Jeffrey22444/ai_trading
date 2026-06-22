#!/bin/bash
# 一键清理所有 Python 缓存文件
# Usage: ./clean_pycache.sh

echo "🧹 开始清理 Python 缓存..."

# 当前目录下的 __pycache__
echo "清理项目 __pycache__..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# .pyc 文件
echo "清理 .pyc 文件..."
find . -name "*.pyc" -type f -delete 2>/dev/null || true

# .pyo 文件
echo "清理 .pyo 文件..."
find . -name "*.pyo" -type f -delete 2>/dev/null || true

# .pyd 文件 (Windows)
echo "清理 .pyd 文件..."
find . -name "*.pyd" -type f -delete 2>/dev/null || true

# pytest 缓存
echo "清理 pytest 缓存..."
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# mypy 缓存
echo "清理 mypy 缓存..."
find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# coverage 缓存
echo "清理 coverage 缓存..."
find . -name ".coverage" -type f -delete 2>/dev/null || true
find . -name "htmlcov" -type d -exec rm -rf {} + 2>/dev/null || true

# tox 缓存
echo "清理 tox 缓存..."
find . -name ".tox" -type d -exec rm -rf {} + 2>/dev/null || true

# .egg-info 目录
echo "清理 .egg-info 目录..."
find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true

# dist 目录
echo "清理 dist 目录..."
find . -name "dist" -type d -exec rm -rf {} + 2>/dev/null || true

# build 目录
echo "清理 build 目录..."
find . -name "build" -type d -exec rm -rf {} + 2>/dev/null || true

# 临时文件
echo "清理临时文件..."
find . -name "*.tmp" -type f -delete 2>/dev/null || true
find . -name "*.log" -type f -delete 2>/dev/null || true

# 检查 Python 虚拟环境中的缓存（可选）
read -p "是否清理虚拟环境缓存? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "清理虚拟环境缓存..."
    if [ -d ".venv" ]; then
        find .venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find .venv -name "*.pyc" -type f -delete 2>/dev/null || true
    fi
    
    # 清理 pip 缓存
    echo "清理 pip 缓存..."
    pip cache purge 2>/dev/null || true
fi

# 显示清理结果
echo ""
echo "✅ Python 缓存清理完成!"
echo ""
echo "清理统计:"
echo "- __pycache__ 目录: 已清理"
echo "- .pyc/.pyo/.pyd 文件: 已清理" 
echo "- 测试缓存: 已清理"
echo "- 构建缓存: 已清理"
echo "- 临时文件: 已清理"
echo ""

# 显示磁盘空间节省（如果可用）
if command -v du >/dev/null 2>&1; then
    echo "当前项目大小:"
    du -sh . | cut -f1
fi

echo "🎉 清理完成!"