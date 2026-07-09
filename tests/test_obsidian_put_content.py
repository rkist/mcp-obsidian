"""Tests for put_content overwrite semantics and roundtrip behavior."""

from unittest.mock import MagicMock, patch

from mcp_obsidian.obsidian import Obsidian


def _make_obsidian():
    return Obsidian(api_key="test-key", protocol="http", host="localhost", port=27123)


def _ok_response():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    return resp


def test_put_content_uses_http_put_at_vault_path():
    """put_content must hit PUT /vault/{filepath} — not POST (append) or PATCH."""
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.put", return_value=_ok_response()) as mock_put, \
         patch("mcp_obsidian.obsidian.requests.post") as mock_post, \
         patch("mcp_obsidian.obsidian.requests.patch") as mock_patch:
        api.put_content("notes/test.md", "hello")
        assert mock_put.call_count == 1
        mock_post.assert_not_called()
        mock_patch.assert_not_called()
        url = mock_put.call_args.args[0]
        assert url.endswith("/vault/notes/test.md")


def test_put_content_sends_full_body_verbatim():
    """The entire content arg must arrive as the request body — this is the
    contract that makes put_content suitable for full-file overwrites."""
    api = _make_obsidian()
    payload = "# Title\n\nLine one\nLine two\n"
    with patch("mcp_obsidian.obsidian.requests.put", return_value=_ok_response()) as mock_put:
        api.put_content("file.md", payload)
        sent = mock_put.call_args.kwargs["data"]
        assert sent == payload.encode("utf-8") or sent == payload


def test_put_content_overwrites_on_second_call():
    """Two consecutive put_content calls each send their own full body —
    the second is not appended to the first. This is the overwrite contract."""
    api = _make_obsidian()
    with patch("mcp_obsidian.obsidian.requests.put", return_value=_ok_response()) as mock_put:
        api.put_content("file.md", "first version")
        api.put_content("file.md", "second version")
        assert mock_put.call_count == 2
        first_body = mock_put.call_args_list[0].kwargs["data"]
        second_body = mock_put.call_args_list[1].kwargs["data"]
        assert b"first version" in (first_body if isinstance(first_body, bytes) else first_body.encode())
        assert b"second version" in (second_body if isinstance(second_body, bytes) else second_body.encode())
        # The second call must NOT carry the first version's payload
        assert b"first version" not in (second_body if isinstance(second_body, bytes) else second_body.encode())


def test_put_content_roundtrip_via_mocked_get():
    """End-to-end shape: put_content(c) → get_file_contents() returns c.
    Uses two independent mocks since the real API stores state between calls;
    here we just verify our wrapper round-trips the body correctly."""
    api = _make_obsidian()
    payload = "# Roundtrip\n\nbody\n"

    get_resp = MagicMock()
    get_resp.raise_for_status.return_value = None
    get_resp.text = payload

    with patch("mcp_obsidian.obsidian.requests.put", return_value=_ok_response()), \
         patch("mcp_obsidian.obsidian.requests.get", return_value=get_resp):
        api.put_content("rt.md", payload)
        result = api.get_file_contents("rt.md")
        assert result == payload
