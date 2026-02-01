"""Tests for TOML config file loading."""

from __future__ import annotations

from pathlib import Path

from picodoc.cli import build_parser, load_config, resolve_options


class TestLoadConfig:
    def test_missing_config_returns_empty(self, tmp_path: Path) -> None:
        assert load_config(None, tmp_path) == {}

    def test_explicit_path(self, tmp_path: Path) -> None:
        cfg = tmp_path / "custom.toml"
        cfg.write_text('[env]\nmode = "test"\n')
        result = load_config(cfg, tmp_path)
        assert result["env"] == {"mode": "test"}

    def test_auto_discover_picodoc_toml(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[env]\nauthor = "Alice"\n')
        result = load_config(None, tmp_path)
        assert result["env"] == {"author": "Alice"}


class TestConfigMerge:
    def test_config_env_merged(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[env]\nmode = "prod"\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc)])
        opts = resolve_options(ns)
        assert opts.env == {"mode": "prod"}

    def test_cli_overrides_config_env(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[env]\nmode = "prod"\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc), "-e", "mode=dev"])
        opts = resolve_options(ns)
        assert opts.env["mode"] == "dev"

    def test_config_css_and_cli_css(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[css]\nfiles = ["base.css"]\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc), "--css", "extra.css"])
        opts = resolve_options(ns)
        assert opts.css_files == ["base.css", "extra.css"]

    def test_config_js(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[js]\nfiles = ["app.js"]\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc)])
        opts = resolve_options(ns)
        assert opts.js_files == ["app.js"]

    def test_config_meta(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[meta]\nviewport = "width=device-width"\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc)])
        opts = resolve_options(ns)
        assert ("viewport", "width=device-width") in opts.meta_tags

    def test_config_filter_paths_and_timeout(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text('[filters]\npaths = ["/opt/filters"]\ntimeout = 15.0\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc)])
        opts = resolve_options(ns)
        assert Path("/opt/filters") in opts.filter_paths
        assert opts.filter_timeout == 15.0

    def test_cli_filter_timeout_overrides_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picodoc.toml"
        cfg.write_text("[filters]\ntimeout = 15.0\n")
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc), "--filter-timeout", "3"])
        opts = resolve_options(ns)
        assert opts.filter_timeout == 3.0

    def test_explicit_config_flag(self, tmp_path: Path) -> None:
        cfg = tmp_path / "alt.toml"
        cfg.write_text('[env]\nkey = "val"\n')
        doc = tmp_path / "doc.pdoc"
        doc.write_text("")
        p = build_parser()
        ns = p.parse_args([str(doc), "--config", str(cfg)])
        opts = resolve_options(ns)
        assert opts.env == {"key": "val"}
