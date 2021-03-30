import io

from setuptools import setup

meta = {}

with io.open("./__version__.py", encoding="utf-8") as f:
    exec(f.read(), meta)  # pylint: disable=W0122

setup(
    name="rstbot",
    description="A simple framework for RSTBot using Python.",
    long_description="See [rstbot](https://github.com/xiyaowong/rstbot).",
    long_description_content_type="text/markdown",
    version=meta["__version__"],
    author="wongxy",
    author_email="xiyao.wong@foxmail.com",
    url="https://github.com/xiyaowong/rstbot",
    license="MIT",
    keywords=["RSTBot"],
    py_modules=["rstbot"],
    install_requires=[
        "python-socketio==4.6.0",
        "websocket-client >= 0.57.0",
        "python-engineio==3.14.2",
        "httpx",
    ],
    python_requires=">=3.6",
)
