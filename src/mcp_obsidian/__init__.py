import sys
from typing import Any

# Force UTF-8 on stdio before the MCP library wraps the streams. Without this,
# Windows defaults stdin/stdout to the active code page (typically cp1252),
# which mangles non-ASCII bytes in the JSON-RPC payloads. See issue #135.
def _reconfigure_stdio(stream: Any) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


_reconfigure_stdio(sys.stdin)
_reconfigure_stdio(sys.stdout)

from . import server
import asyncio

def main():
    """Main entry point for the package."""
    asyncio.run(server.main())

# Optionally expose other important items at package level
__all__ = ['main', 'server']
