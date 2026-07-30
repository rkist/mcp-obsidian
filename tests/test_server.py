import asyncio
from collections.abc import Awaitable
from typing import TypeVar
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import TextContent, CallToolRequestParams, PaginatedRequestParams

from mcp_obsidian import server


T = TypeVar("T")


async def _await(awaitable: Awaitable[T]) -> T:
    return await awaitable


def _run(awaitable: Awaitable[T]) -> T:
    return asyncio.run(_await(awaitable))


def _list_tools():
    return _run(server.list_tools(None, PaginatedRequestParams()))


def _call_tool(name, arguments):
    params = CallToolRequestParams(name=name, arguments=arguments)
    return _run(server.call_tool(None, params))


def test_registered_tools_include_expected_new_and_existing_tools():
    names = {tool.name for tool in _list_tools().tools}

    assert {
        "obsidian_list_files_in_vault",
        "obsidian_get_file_contents",
        "obsidian_simple_search",
        "obsidian_patch_content",
        "obsidian_put_content",
        "obsidian_search_by_tag",
        "obsidian_get_frontmatter",
        "obsidian_get_recent_changes",
    }.issubset(names)


def test_get_tool_handler_returns_none_for_unknown_tool():
    assert server.get_tool_handler("missing") is None


def test_call_tool_treats_missing_arguments_as_empty_dict():
    handler = MagicMock()
    handler.run_tool.return_value = [TextContent(type="text", text="ok")]

    with patch("mcp_obsidian.server.get_tool_handler", return_value=handler):
        result = _call_tool("tool", None)

    handler.run_tool.assert_called_once_with({})
    assert result.content == [TextContent(type="text", text="ok")]


def test_call_tool_rejects_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        _call_tool("missing", {})


def test_call_tool_dispatches_to_handler():
    handler = MagicMock()
    handler.run_tool.return_value = [TextContent(type="text", text="ok")]

    with patch("mcp_obsidian.server.get_tool_handler", return_value=handler):
        result = _call_tool("tool", {"a": 1})

    handler.run_tool.assert_called_once_with({"a": 1})
    assert result.content == [TextContent(type="text", text="ok")]


def test_call_tool_wraps_handler_exception():
    handler = MagicMock()
    handler.run_tool.side_effect = RuntimeError("bad args")

    with patch("mcp_obsidian.server.get_tool_handler", return_value=handler):
        with pytest.raises(RuntimeError, match="Caught Exception. Error: bad args"):
            _call_tool("tool", {})
