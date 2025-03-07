from setuptools import setup, find_packages

setup(
    name="pytorch_hud",
    version="0.1.0",
    description="Python library and MCP server for PyTorch HUD API",
    author="PyTorch Team",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "fastapi",
        "uvicorn",
        "pydantic",
        "mcp>=1.3.0"
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "pytorch-hud=pytorch_hud.__main__:main",
        ],
    },
)