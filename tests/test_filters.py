"""Tests for external filter discovery and invocation."""

from __future__ import annotations

import stat
import textwrap
from pathlib import Path

import pytest

from picodoc.errors import EvalError
from picodoc.filters import FilterRegistry
from picodoc.tokens import Position, Span

_SPAN = Span(Position(1, 1, 0), Position(1, 1, 0))


def _make_filter_script(path: Path, body: str) -> None:
    """Write a small executable filter script."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class TestFilterDiscovery:
    def test_local_filters_dir(self, tmp_path: Path) -> None:
        _make_filter_script(tmp_path / "filters" / "greet", 'echo "hello"')
        reg = FilterRegistry(document_dir=tmp_path)
        result = reg.find_filter("greet")
        assert result is not None
        assert result == tmp_path / "filters" / "greet"

    def test_extra_paths(self, tmp_path: Path) -> None:
        extra = tmp_path / "extras"
        _make_filter_script(extra / "hello", 'echo "hi"')
        reg = FilterRegistry(document_dir=tmp_path, extra_paths=[extra])
        result = reg.find_filter("hello")
        assert result is not None
        assert result == extra / "hello"

    def test_not_found_returns_none(self, tmp_path: Path) -> None:
        reg = FilterRegistry(document_dir=tmp_path)
        assert reg.find_filter("nonexistent") is None

    def test_cache_hit(self, tmp_path: Path) -> None:
        _make_filter_script(tmp_path / "filters" / "cached", 'echo ""')
        reg = FilterRegistry(document_dir=tmp_path)
        first = reg.find_filter("cached")
        second = reg.find_filter("cached")
        assert first is second

    def test_non_executable_skipped(self, tmp_path: Path) -> None:
        fpath = tmp_path / "filters" / "noexec"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text("#!/bin/sh\necho hi\n")
        # Do NOT chmod +x
        reg = FilterRegistry(document_dir=tmp_path)
        assert reg.find_filter("noexec") is None

    def test_local_before_extra(self, tmp_path: Path) -> None:
        _make_filter_script(tmp_path / "filters" / "dup", 'echo "local"')
        extra = tmp_path / "extras"
        _make_filter_script(extra / "dup", 'echo "extra"')
        reg = FilterRegistry(document_dir=tmp_path, extra_paths=[extra])
        result = reg.find_filter("dup")
        assert result == tmp_path / "filters" / "dup"


class TestFilterInvocation:
    def test_basic_stdout(self, tmp_path: Path) -> None:
        # Filter that echoes fixed markup
        _make_filter_script(
            tmp_path / "filters" / "upper",
            'echo "#p: hello from filter"',
        )
        reg = FilterRegistry(document_dir=tmp_path)
        fpath = reg.find_filter("upper")
        assert fpath is not None
        result = reg.invoke_filter("upper", fpath, {}, None, {}, _SPAN)
        assert "#p: hello from filter" in result

    def test_receives_json_stdin(self, tmp_path: Path) -> None:
        # Filter that reads stdin and echoes the 'greeting' arg
        script = textwrap.dedent("""\
            #!/usr/bin/env python3
            import json, sys
            data = json.load(sys.stdin)
            print(f"#p: {data['greeting']}")
        """)
        fpath = tmp_path / "filters" / "echo_arg"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(script)
        fpath.chmod(fpath.stat().st_mode | stat.S_IEXEC)

        reg = FilterRegistry(document_dir=tmp_path)
        result = reg.invoke_filter(
            "echo_arg", fpath, {"greeting": "hi"}, None, {"mode": "test"}, _SPAN
        )
        assert "#p: hi" in result

    def test_receives_body_and_env(self, tmp_path: Path) -> None:
        script = textwrap.dedent("""\
            #!/usr/bin/env python3
            import json, sys
            data = json.load(sys.stdin)
            print(f"body={data['body']} mode={data['env']['mode']}")
        """)
        fpath = tmp_path / "filters" / "bodyenv"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(script)
        fpath.chmod(fpath.stat().st_mode | stat.S_IEXEC)

        reg = FilterRegistry(document_dir=tmp_path)
        result = reg.invoke_filter("bodyenv", fpath, {}, "some body", {"mode": "draft"}, _SPAN)
        assert "body=some body" in result
        assert "mode=draft" in result

    def test_nonzero_exit_raises(self, tmp_path: Path) -> None:
        _make_filter_script(
            tmp_path / "filters" / "fail",
            'echo "bad stuff" >&2; exit 1',
        )
        reg = FilterRegistry(document_dir=tmp_path)
        fpath = reg.find_filter("fail")
        assert fpath is not None
        with pytest.raises(EvalError, match="filter 'fail' failed"):
            reg.invoke_filter("fail", fpath, {}, None, {}, _SPAN)

    def test_nonzero_includes_stderr(self, tmp_path: Path) -> None:
        _make_filter_script(
            tmp_path / "filters" / "fail2",
            'echo "details here" >&2; exit 2',
        )
        reg = FilterRegistry(document_dir=tmp_path)
        fpath = reg.find_filter("fail2")
        assert fpath is not None
        with pytest.raises(EvalError, match="details here"):
            reg.invoke_filter("fail2", fpath, {}, None, {}, _SPAN)

    def test_timeout_raises(self, tmp_path: Path) -> None:
        _make_filter_script(
            tmp_path / "filters" / "slow",
            "sleep 10",
        )
        reg = FilterRegistry(document_dir=tmp_path, timeout=0.2)
        fpath = reg.find_filter("slow")
        assert fpath is not None
        with pytest.raises(EvalError, match="timed out"):
            reg.invoke_filter("slow", fpath, {}, None, {}, _SPAN)
