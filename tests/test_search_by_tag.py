"""Tests for search_by_tag — JsonLogic query construction and result mapping."""

from unittest.mock import MagicMock, patch

from mcp_obsidian.obsidian import Obsidian


def _make_obsidian():
    return Obsidian(api_key="test-key", protocol="http", host="localhost", port=27123)


def _api_results(*paths):
    return [{"filename": p, "result": True} for p in paths]


def test_search_by_tag_uses_jsonlogic_in_predicate():
    """Without dirpath, the query is the plain 'tag in tags' JsonLogic predicate."""
    api = _make_obsidian()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = _api_results("note-a.md", "work/note-b.md")

    with patch("mcp_obsidian.obsidian.requests.post", return_value=resp) as mock_post:
        api.search_by_tag("project")
        sent = mock_post.call_args.kwargs["json"]
        assert sent == {"in": ["project", {"var": "tags"}]}


def test_search_by_tag_returns_filenames_only():
    """The wrapper extracts just the filename list from the API's
    {filename,result} objects — callers don't need the result column."""
    api = _make_obsidian()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = _api_results("a.md", "b.md", "c.md")

    with patch("mcp_obsidian.obsidian.requests.post", return_value=resp):
        result = api.search_by_tag("anything")
        assert result == ["a.md", "b.md", "c.md"]


def test_search_by_tag_with_dirpath_adds_glob_clause():
    """With dirpath, the query becomes an 'and' of the tag predicate and
    a glob on path."""
    api = _make_obsidian()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = _api_results("work/projects/x.md")

    with patch("mcp_obsidian.obsidian.requests.post", return_value=resp) as mock_post:
        api.search_by_tag("tasks", dirpath="work/projects")
        sent = mock_post.call_args.kwargs["json"]
        assert sent == {
            "and": [
                {"in": ["tasks", {"var": "tags"}]},
                {"glob": ["work/projects/*", {"var": "path"}]},
            ]
        }


def test_search_by_tag_strips_trailing_slash_from_dirpath():
    """Trailing slash on dirpath must not produce 'work/projects//*'."""
    api = _make_obsidian()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = []

    with patch("mcp_obsidian.obsidian.requests.post", return_value=resp) as mock_post:
        api.search_by_tag("tasks", dirpath="work/projects/")
        sent = mock_post.call_args.kwargs["json"]
        assert sent["and"][1] == {"glob": ["work/projects/*", {"var": "path"}]}


def test_search_by_tag_empty_results_returns_empty_list():
    api = _make_obsidian()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = []

    with patch("mcp_obsidian.obsidian.requests.post", return_value=resp):
        assert api.search_by_tag("nonexistent") == []
