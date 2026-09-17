"""Windows/Linux 通用启动入口。

uvicorn 0.53 在 Windows 上默认强制 ProactorEventLoop，与 psycopg async 不兼容；
通过自定义 Config 覆盖 get_loop_factory 强制 SelectorEventLoop，并用 Server.run()
（内部 asyncio.run 会使用该 loop_factory）。

注意：Windows 开发环境不支持 uvicorn --reload（reload 子进程走标准 uvicorn 会退回
Proactor）；改代码后手动重启即可。
"""
import asyncio
import sys

from uvicorn.config import Config
from uvicorn.server import Server


class _SelectorConfig(Config):
    def get_loop_factory(self):
        if sys.platform == "win32":
            return asyncio.SelectorEventLoop
        return super().get_loop_factory()


if __name__ == "__main__":
    config = _SelectorConfig("app.main:app", host="0.0.0.0", port=8000)
    Server(config).run()
