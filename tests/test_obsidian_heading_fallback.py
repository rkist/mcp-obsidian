"""Tests for the bare-heading auto-qualify fallback in patch_content (issue #125)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from mcp_obsidian.obsidian import Obsidian, _find_heading_paths


def _make_obsidian():
    return Obsidian(api_key="test-key", protocol="http", host="localhost", port=27123)


def _http_error(status: int, error_code: int, message: str) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    resp._content = (
        b'{"errorCode": ' + str(error_code).encode() + b', "message": "' + message.encode() + b'"}'
    )
    err = requests.HTTPError(response=resp)
    return err


# --- _find_heading_paths unit tests ---------------------------------------


def test_find_heading_paths_returns_qualified_path_for_unique_match():
    content = "# Outer\n\n## Übersicht\n\nbody\n"
    assert _find_heading_paths(content, "Übersicht") == ["Outer::Übersicht"]


def test_find_heading_paths_case_insensitive():
    content = "# Outer\n\n## Übersicht\n\nbody\n"
    assert _find_heading_paths(content, "übersicht") == ["Outer::Übersicht"]


def test_find_heading_paths_returns_all_candidates_when_ambiguous():
    content = "# A\n\n## Übersicht\n\n# B\n\n## Übersicht\n"
    assert _find_heading_paths(content, "Übersicht") == ["A::Übersicht", "B::Übersicht"]


def test_find_heading_paths_returns_empty_when_no_match():
    content = "# Outer\n\n## Other\n"
    assert _find_heading_paths(content, "Missing") == []


def test_find_heading_paths_ignores_headings_inside_code_fences():
    content = "# Real\n\n```\n# Fake\n```\n\n## Übersicht\n"
    # The "# Fake" inside the fence must not appear in any candidate path
    paths = _find_heading_paths(content, "Übersicht")
    assert paths == ["Real::Übersicht"]


def test_find_heading_paths_handles_sibling_after_descent():
    # Outer h1, then sibling h1 — stack must reset, not accumulate.
    content = "# First\n\n## Sub\n\n# Second\n\n## Übersicht\n"
    assert _find_heading_paths(content, "Übersicht") == ["Second::Übersicht"]


def test_find_heading_paths_strips_closing_atx_hashes():
    content = "# Outer\n\n## Done ##\n\nbody\n"
    assert _find_heading_paths(content, "Done") == ["Outer::Done"]


def test_find_heading_paths_allows_up_to_three_leading_spaces():
    content = "# Outer\n\n   ## Indented\n\nbody\n"
    assert _find_heading_paths(content, "Indented") == ["Outer::Indented"]


def test_find_heading_paths_handles_fences_with_language_markers():
    content = "# Real\n\n```python\n# Fake\n```\n\n## Actual\n"
    assert _find_heading_paths(content, "Actual") == ["Real::Actual"]


# --- patch_content fallback integration tests -----------------------------


def test_qualified_path_passes_through_without_get():
    """A target already containing '::' must skip the fallback entirely."""
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.patch") as mock_patch, \
         patch.object(api, "get_file_contents") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_patch.return_value = mock_resp

        api.patch_content("f.md", "append", "heading", "A::B", "x")

        assert mock_patch.call_count == 1
        mock_get.assert_not_called()


def test_bare_heading_unique_match_autoqualifies():
    api = _make_obsidian()
    file_content = "# Outer\n\n## Übersicht\n\nbody\n"

    # First PATCH fails with 40080, second PATCH succeeds.
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = _http_error(400, 40080, "invalid-target")
    fail_resp.content = b'{"errorCode": 40080, "message": "invalid-target"}'
    fail_resp.json.return_value = {"errorCode": 40080, "message": "invalid-target"}

    ok_resp = MagicMock()
    ok_resp.raise_for_status.return_value = None

    with patch("mcp_obsidian.obsidian.requests.patch", side_effect=[fail_resp, ok_resp]) as mock_patch, \
         patch.object(api, "get_file_contents", return_value=file_content) as mock_get:
        api.patch_content("f.md", "append", "heading", "Übersicht", "x")

        assert mock_patch.call_count == 2
        mock_get.assert_called_once_with("f.md")
        # Second call must carry the qualified target (URL-quoted)
        second_headers = mock_patch.call_args_list[1].kwargs["headers"]
        # urllib.parse.quote(...) escapes the colons too; check the underlying decoded value
        assert "Outer" in second_headers["Target"] and "bersicht" in second_headers["Target"]


def test_bare_heading_case_insensitive_match():
    api = _make_obsidian()
    file_content = "# Outer\n\n## Übersicht\n"

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = _http_error(400, 40080, "invalid-target")
    fail_resp.content = b'{"errorCode": 40080, "message": "invalid-target"}'
    fail_resp.json.return_value = {"errorCode": 40080, "message": "invalid-target"}
    ok_resp = MagicMock()
    ok_resp.raise_for_status.return_value = None

    with patch("mcp_obsidian.obsidian.requests.patch", side_effect=[fail_resp, ok_resp]), \
         patch.object(api, "get_file_contents", return_value=file_content):
        api.patch_content("f.md", "append", "heading", "übersicht", "x")
        # If we got here without raising, the case-insensitive match succeeded.


def test_bare_heading_ambiguous_raises_with_candidates():
    api = _make_obsidian()
    file_content = "# A\n\n## Übersicht\n\n# B\n\n## Übersicht\n"

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = _http_error(400, 40080, "invalid-target")
    fail_resp.content = b'{"errorCode": 40080, "message": "invalid-target"}'
    fail_resp.json.return_value = {"errorCode": 40080, "message": "invalid-target"}

    with patch("mcp_obsidian.obsidian.requests.patch", return_value=fail_resp), \
         patch.object(api, "get_file_contents", return_value=file_content):
        with pytest.raises(Exception) as excinfo:
            api.patch_content("f.md", "append", "heading", "Übersicht", "x")
        msg = str(excinfo.value)
        assert "Ambiguous heading" in msg
        assert "A::Übersicht" in msg
        assert "B::Übersicht" in msg


def test_bare_heading_not_found_reraises_original_error():
    api = _make_obsidian()
    file_content = "# Outer\n\n## Other\n"

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = _http_error(400, 40080, "invalid-target")
    fail_resp.content = b'{"errorCode": 40080, "message": "invalid-target"}'
    fail_resp.json.return_value = {"errorCode": 40080, "message": "invalid-target"}

    with patch("mcp_obsidian.obsidian.requests.patch", return_value=fail_resp), \
         patch.object(api, "get_file_contents", return_value=file_content):
        with pytest.raises(Exception) as excinfo:
            api.patch_content("f.md", "append", "heading", "Missing", "x")
        # Original error message format from _safe_call
        assert "Error 40080" in str(excinfo.value)


def test_bare_heading_get_failure_reraises_original_patch_error():
    api = _make_obsidian()

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = _http_error(400, 40080, "invalid-target")
    fail_resp.content = b'{"errorCode": 40080, "message": "invalid-target"}'
    fail_resp.json.return_value = {"errorCode": 40080, "message": "invalid-target"}

    with patch("mcp_obsidian.obsidian.requests.patch", return_value=fail_resp), \
         patch.object(api, "get_file_contents", side_effect=Exception("read failed")):
        with pytest.raises(Exception) as excinfo:
            api.patch_content("f.md", "append", "heading", "Missing", "x")
        assert "Error 40080" in str(excinfo.value)


def test_non_heading_target_type_does_not_trigger_fallback():
    """For target_type='block' or 'frontmatter', a 40080 error must propagate as-is."""
    api = _make_obsidian()

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = _http_error(400, 40080, "invalid-target")
    fail_resp.content = b'{"errorCode": 40080, "message": "invalid-target"}'
    fail_resp.json.return_value = {"errorCode": 40080, "message": "invalid-target"}

    with patch("mcp_obsidian.obsidian.requests.patch", return_value=fail_resp), \
         patch.object(api, "get_file_contents") as mock_get:
        with pytest.raises(Exception):
            api.patch_content("f.md", "append", "block", "blk-id", "x")
        mock_get.assert_not_called()
