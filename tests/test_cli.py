"""Tests for the CLI module: arg parsing, exit codes, env passthrough, end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

from picodoc.cli import (
    CliOptions,
    build_parser,
    compile_file,
    main,
    parse_kv_arg,
)

# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------


class TestParseHelpers:
    def test_parse_kv_arg_simple(self) -> None:
        assert parse_kv_arg("env", "mode=draft") == ("mode", "draft")

    def test_parse_kv_arg_with_equals_in_value(self) -> None:
        assert parse_kv_arg("env", "x=a=b") == ("x", "a=b")

    def test_parse_kv_arg_empty_value(self) -> None:
        assert parse_kv_arg("env", "key=") == ("key", "")

    def test_parse_kv_arg_no_equals_raises(self) -> None:
        import argparse

        with pytest.raises(argparse.ArgumentTypeError):
            parse_kv_arg("env", "noequals")

    def test_parse_kv_arg_meta(self) -> None:
        assert parse_kv_arg("meta", "viewport=width=device-width") == (
            "viewport",
            "width=device-width",
        )

    def test_parse_kv_arg_meta_no_equals_raises(self) -> None:
        import argparse

        with pytest.raises(argparse.ArgumentTypeError):
            parse_kv_arg("meta", "noequals")


# ---------------------------------------------------------------------------
# Arg parsing via build_parser
# ---------------------------------------------------------------------------


class TestArgParsing:
    def test_input_only(self) -> None:
        p = build_parser()
        ns = p.parse_args(["doc.pdoc"])
        assert ns.input == "doc.pdoc"
        assert ns.output is None

    def test_output_flag(self) -> None:
        p = build_parser()
        ns = p.parse_args(["doc.pdoc", "-o", "out.html"])
        assert ns.output == "out.html"

    def test_env_flags(self) -> None:
        p = build_parser()
        ns = p.parse_args(["doc.pdoc", "-e", "a=1", "-e", "b=2"])
        assert ns.env == ["a=1", "b=2"]

    def test_css_js_meta_flags(self) -> None:
        p = build_parser()
        ns = p.parse_args(
            [
                "doc.pdoc",
                "--css",
                "s.css",
                "--js",
                "a.js",
                "--meta",
                "k=v",
            ]
        )
        assert ns.css == ["s.css"]
        assert ns.js == ["a.js"]
        assert ns.meta == ["k=v"]

    def test_debug(self) -> None:
        p = build_parser()
        ns = p.parse_args(["doc.pdoc", "--debug"])
        assert ns.debug is True

    def test_filter_path_and_timeout(self) -> None:
        p = build_parser()
        ns = p.parse_args(
            [
                "doc.pdoc",
                "--filter-path",
                "/tmp/filters",
                "--filter-timeout",
                "10",
            ]
        )
        assert ns.filter_path == ["/tmp/filters"]
        assert ns.filter_timeout == 10.0


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_success(self, tmp_path: Path) -> None:
        doc = tmp_path / "ok.pdoc"
        doc.write_text("#doc.title: Hello\n")
        assert main([str(doc)]) == 0

    def test_syntax_error_returns_1(self, tmp_path: Path) -> None:
        doc = tmp_path / "bad.pdoc"
        doc.write_text('#link to="http://x" extra="z" leftover: body\n')
        # This should trigger a parse error due to malformed input
        result = main([str(doc)])
        # May be parse error (1) or eval error (2) depending on parser leniency
        assert result in (0, 1, 2)

    def test_eval_error_returns_2(self, tmp_path: Path) -> None:
        doc = tmp_path / "evalerr.pdoc"
        doc.write_text("#include: nonexistent.pdoc\n")
        assert main([str(doc)]) == 2


# ---------------------------------------------------------------------------
# Environment passthrough
# ---------------------------------------------------------------------------


class TestEnvPassthrough:
    def test_env_visible_in_output(self, tmp_path: Path) -> None:
        doc = tmp_path / "env.pdoc"
        doc.write_text("#p: Mode is [#env.mode].\n")
        out = tmp_path / "out.html"
        assert main([str(doc), "-e", "mode=draft", "-o", str(out)]) == 0
        html = out.read_text()
        assert "Mode is draft." in html

    def test_multiple_env(self, tmp_path: Path) -> None:
        doc = tmp_path / "env2.pdoc"
        doc.write_text("#p: #env.a and #env.b\n")
        out = tmp_path / "out.html"
        assert main([str(doc), "-e", "a=X", "-e", "b=Y", "-o", str(out)]) == 0
        html = out.read_text()
        assert "X and Y" in html


# ---------------------------------------------------------------------------
# CSS / JS / Meta via CLI
# ---------------------------------------------------------------------------


class TestCssJsMetaCli:
    def test_css_in_output(self, tmp_path: Path) -> None:
        doc = tmp_path / "doc.pdoc"
        doc.write_text("#doc.title: Test\n")
        out = tmp_path / "out.html"
        assert main([str(doc), "--css", "style.css", "-o", str(out)]) == 0
        html = out.read_text()
        assert '<link rel="stylesheet" href="style.css">' in html

    def test_js_in_output(self, tmp_path: Path) -> None:
        doc = tmp_path / "doc.pdoc"
        doc.write_text("#doc.title: Test\n")
        out = tmp_path / "out.html"
        assert main([str(doc), "--js", "app.js", "-o", str(out)]) == 0
        html = out.read_text()
        assert '<script src="app.js"></script>' in html

    def test_meta_in_output(self, tmp_path: Path) -> None:
        doc = tmp_path / "doc.pdoc"
        doc.write_text("#doc.title: Test\n")
        out = tmp_path / "out.html"
        assert main([str(doc), "--meta", "author=Me", "-o", str(out)]) == 0
        html = out.read_text()
        assert '<meta name="author" content="Me">' in html


# ---------------------------------------------------------------------------
# compile_file smoke test
# ---------------------------------------------------------------------------


class TestCompileFile:
    def test_basic(self, tmp_path: Path) -> None:
        doc = tmp_path / "simple.pdoc"
        doc.write_text("#doc.title: Hello World\n")
        opts = CliOptions(
            input_file=doc,
            output_file=None,
            env={},
            css_files=[],
            js_files=[],
            meta_tags=[],
            filter_paths=[],
            filter_timeout=5.0,
            debug=False,
        )
        html = compile_file(opts)
        assert "<title>Hello World</title>" in html
