from unittest.mock import MagicMock

import mcp_obsidian


def test_reconfigure_stdio_calls_stream_reconfigure_with_utf8():
    stream = MagicMock()

    mcp_obsidian._reconfigure_stdio(stream)

    stream.reconfigure.assert_called_once_with(encoding="utf-8")


def test_reconfigure_stdio_ignores_stream_without_reconfigure():
    class Stream:
        pass

    mcp_obsidian._reconfigure_stdio(Stream())


def test_reconfigure_stdio_ignores_non_callable_reconfigure_attribute():
    class Stream:
        reconfigure = "not-callable"

    mcp_obsidian._reconfigure_stdio(Stream())
