"""Tests for get_frontmatter — Accept header, dict extraction, edge cases."""

from unittest.mock import MagicMock, patch

from mcp_obsidian.obsidian import Obsidian


def _make_obsidian():
    return Obsidian(api_key="test-key", protocol="http", host="localhost", port=27123)


def _note_json_response(**overrides):
    payload = {
        "content": "body text",
        "frontmatter": {},
        "path": "f.md",
        "stat": {"ctime": 1, "mtime": 2, "size": 9},
        "tags": [],
    }
    payload.update(overrides)
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def test_get_frontmatter_sends_note_json_accept_header():
    """Must request the Local REST API's NoteJson view, not the plain text view."""
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.get", return_value=_note_json_response()) as mock_get:
        api.get_frontmatter("f.md")
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Accept"] == "application/vnd.olrapi.note+json"


def test_get_frontmatter_returns_parsed_dict():
    """The server returns frontmatter pre-parsed; the wrapper hands it
    through verbatim, including nested structures."""
    api = _make_obsidian()
    fm = {
        "title": "My Note",
        "tags": ["project", "important"],
        "metadata": {"priority": 1, "status": "open"},
    }
    with patch("mcp_obsidian.obsidian.requests.get", return_value=_note_json_response(frontmatter=fm)):
        assert api.get_frontmatter("f.md") == fm


def test_get_frontmatter_returns_empty_dict_when_no_frontmatter():
    """A note without YAML frontmatter must yield {} — never an error
    and never None."""
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.get", return_value=_note_json_response(frontmatter={})):
        assert api.get_frontmatter("f.md") == {}


def test_get_frontmatter_returns_empty_dict_when_api_omits_key():
    """Defensive: if the API payload lacks 'frontmatter' entirely, treat
    it as no-frontmatter rather than KeyError."""
    api = _make_obsidian()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"content": "x", "path": "f.md"}  # no frontmatter key
    with patch("mcp_obsidian.obsidian.requests.get", return_value=resp):
        assert api.get_frontmatter("f.md") == {}


def test_get_frontmatter_returns_empty_dict_when_api_returns_null_frontmatter():
    """The API can return frontmatter: null for some edge cases — wrapper
    must coerce to {}."""
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.get", return_value=_note_json_response(frontmatter=None)):
        assert api.get_frontmatter("f.md") == {}


def test_get_frontmatter_hits_vault_path():
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.get", return_value=_note_json_response()) as mock_get:
        api.get_frontmatter("notes/sub/foo.md")
        url = mock_get.call_args.args[0]
        assert url.endswith("/vault/notes/sub/foo.md")
