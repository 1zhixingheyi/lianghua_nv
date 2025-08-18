#!/usr/bin/env python3
"""
批量更新导入路径脚本
将所有模块导入路径从直接导入改为src.模块导入
"""

import os
import re
import sys
from pathlib import Path

def update_imports_in_file(file_path):
    """更新单个文件的导入路径"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 定义需要更新的模块名
        modules = [
            'backtest', 'config', 'data', 'monitor', 
            'optimization', 'risk', 'strategies', 
            'trading', 'validation'
        ]
        
        # 更新导入语句
        for module in modules:
            # 更新 from module 格式
            pattern1 = rf'from {module}(\.|import|\s)'
            replacement1 = rf'from src.{module}\1'
            content = re.sub(pattern1, replacement1, content)
            
            # 更新 import module 格式
            pattern2 = rf'import {module}(\s|$)'
            replacement2 = rf'import src.{module}\1'
            content = re.sub(pattern2, replacement2, content)
        
        # 如果有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[UPDATE] 更新: {file_path}")
            return True
        else:
            print(f"[SKIP] 无需更新: {file_path}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 错误处理文件 {file_path}: {e}")
        return False

def find_python_files(directory):
    """查找所有Python文件"""
    python_files = []
    
    for root, dirs, files in os.walk(directory):
        # 跳过某些目录
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def main():
    """主函数"""
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"[INFO] 项目根目录: {project_root}")
    
    # 查找需要更新的目录
    target_dirs = [
        project_root / 'tests',
        project_root / 'scripts',
        project_root / 'examples',
        project_root / 'src'  # src目录内的相对导入也需要更新
    ]
    
    updated_files = 0
    total_files = 0
    
    for target_dir in target_dirs:
        if target_dir.exists():
            print(f"\n[PROCESS] 处理目录: {target_dir}")
            python_files = find_python_files(target_dir)
            
            for file_path in python_files:
                total_files += 1
                if update_imports_in_file(file_path):
                    updated_files += 1
    
    print(f"\n[SUMMARY] 总结:")
    print(f"   总文件数: {total_files}")
    print(f"   更新文件数: {updated_files}")
    print(f"   未变化文件数: {total_files - updated_files}")
    
    if updated_files > 0:
        print(f"\n[SUCCESS] 成功更新了 {updated_files} 个文件的导入路径!")
    else:
        print(f"\n[OK] 所有文件的导入路径都已是最新的!")

if __name__ == "__main__":
    main()