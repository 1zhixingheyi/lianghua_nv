#!/usr/bin/env python3
"""
量化交易系统安装配置文件
"""

from setuptools import setup, find_packages
import os

# 读取README文件
def read_readme():
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "量化交易系统"

# 读取requirements文件
def read_requirements():
    try:
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        return []

# 读取版本信息
def get_version():
    version_file = os.path.join('src', '__init__.py')
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    return line.split('=')[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    return "1.0.0"

setup(
    name="lianghua-trading-system",
    version=get_version(),
    author="Lianghua Trading Team",
    author_email="contact@lianghua.com",
    description="专业量化交易系统",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/lianghua/trading-system",
    
    # 包配置
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    # 包含非Python文件
    include_package_data=True,
    package_data={
        "monitor": ["static/**/*", "templates/**/*"],
    },
    
    # 依赖管理
    install_requires=read_requirements(),
    
    # Python版本要求
    python_requires=">=3.8",
    
    # 分类信息
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    
    # 关键词
    keywords="trading, quantitative, finance, backtest, strategy",
    
    # 项目URL
    project_urls={
        "Bug Reports": "https://github.com/lianghua/trading-system/issues",
        "Source": "https://github.com/lianghua/trading-system",
        "Documentation": "https://lianghua-trading.readthedocs.io/",
    },
    
    # 入口点配置
    entry_points={
        "console_scripts": [
            "lianghua-backtest=src.backtest.engine:main",
            "lianghua-monitor=src.monitor.web_app:main",
            "lianghua-trading=src.trading.trade_executor:main",
        ],
    },
    
    # 额外依赖
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "isort>=5.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "docs": [
            "sphinx>=4.0",
            "sphinx-rtd-theme>=0.5",
        ],
        "test": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "pytest-mock>=3.0",
        ],
    },
    
    # 许可证
    license="MIT",
    
    # 是否压缩
    zip_safe=False,
)