"""Command-line interface for PicoDoc."""

from __future__ import annotations

import argparse
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from picodoc.errors import EvalError, LexError, ParseError


@dataclass(frozen=True, slots=True)
class CliOptions:
    """Parsed CLI options."""

    input_file: Path
    output_file: Path | None
    env: dict[str, str]
    css_files: list[str]
    js_files: list[str]
    meta_tags: list[tuple[str, str]]
    filter_paths: list[Path]
    filter_timeout: float
    watch: bool
    debug: bool


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (separate function for testability)."""
    p = argparse.ArgumentParser(
        prog="picodoc",
        description="PicoDoc markup language compiler",
    )
    p.add_argument("input", help="Input .pdoc file")
    p.add_argument("-o", "--output", help="Output file (default: stdout)")
    p.add_argument(
        "-e",
        "--env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Set environment variable (repeatable)",
    )
    p.add_argument(
        "--css",
        action="append",
        default=[],
        metavar="FILE",
        help="CSS file to include (repeatable)",
    )
    p.add_argument(
        "--js",
        action="append",
        default=[],
        metavar="FILE",
        help="JS file to include (repeatable)",
    )
    p.add_argument(
        "--meta",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Meta tag to add (repeatable)",
    )
    p.add_argument(
        "--config",
        metavar="FILE",
        help="Config file (default: auto-discover picodoc.toml)",
    )
    p.add_argument(
        "--filter-path",
        action="append",
        default=[],
        metavar="DIR",
        help="Extra filter search directory (repeatable)",
    )
    p.add_argument(
        "--filter-timeout",
        type=float,
        default=None,
        metavar="SECS",
        help="Filter execution timeout in seconds (default: 5.0)",
    )
    p.add_argument("--watch", action="store_true", help="Watch for changes and recompile")
    p.add_argument("--debug", action="store_true", help="Dump AST to stderr")
    return p


def parse_env_arg(s: str) -> tuple[str, str]:
    """Parse a NAME=VALUE string into (name, value)."""
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"invalid env format (expected NAME=VALUE): {s}")
    name, _, value = s.partition("=")
    return name, value


def parse_meta_arg(s: str) -> tuple[str, str]:
    """Parse a NAME=VALUE string into (name, value) for meta tags."""
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"invalid meta format (expected NAME=VALUE): {s}")
    name, _, value = s.partition("=")
    return name, value


def load_config(config_path: Path | None, input_dir: Path) -> dict[str, Any]:
    """Load a TOML config file, returning an empty dict on missing/absent file."""
    path = config_path if config_path is not None else input_dir / "picodoc.toml"

    if not path.is_file():
        return {}

    with open(path, "rb") as f:
        return tomllib.load(f)


def resolve_options(args: argparse.Namespace) -> CliOptions:
    """Merge config file and CLI args into CliOptions.

    Precedence: config file < CLI flags.
    """
    input_file = Path(args.input)
    input_dir = input_file.parent
    if not input_dir.parts:
        input_dir = Path(".")

    config_path = Path(args.config) if args.config else None
    config = load_config(config_path, input_dir)

    # Environment variables: config < CLI
    env: dict[str, str] = {}
    cfg_env = config.get("env")
    if isinstance(cfg_env, dict):
        for k, v in cfg_env.items():
            env[str(k)] = str(v)
    for raw in args.env:
        name, value = parse_env_arg(raw)
        env[name] = value

    # CSS files: config < CLI
    css_files: list[str] = []
    cfg_css = config.get("css")
    if isinstance(cfg_css, dict):
        cfg_css_files = cfg_css.get("files")
        if isinstance(cfg_css_files, list):
            css_files.extend(str(f) for f in cfg_css_files)
    css_files.extend(args.css)

    # JS files: config < CLI
    js_files: list[str] = []
    cfg_js = config.get("js")
    if isinstance(cfg_js, dict):
        cfg_js_files = cfg_js.get("files")
        if isinstance(cfg_js_files, list):
            js_files.extend(str(f) for f in cfg_js_files)
    js_files.extend(args.js)

    # Meta tags: config < CLI
    meta_tags: list[tuple[str, str]] = []
    cfg_meta = config.get("meta")
    if isinstance(cfg_meta, dict):
        for k, v in cfg_meta.items():
            meta_tags.append((str(k), str(v)))
    for raw in args.meta:
        meta_tags.append(parse_meta_arg(raw))

    # Filter paths: config < CLI
    filter_paths: list[Path] = []
    cfg_filters = config.get("filters")
    if isinstance(cfg_filters, dict):
        cfg_fpaths = cfg_filters.get("paths")
        if isinstance(cfg_fpaths, list):
            filter_paths.extend(Path(p) for p in cfg_fpaths)
    filter_paths.extend(Path(p) for p in args.filter_path)

    # Filter timeout: config < CLI
    filter_timeout = 5.0
    if isinstance(cfg_filters, dict):
        cfg_timeout = cfg_filters.get("timeout")
        if isinstance(cfg_timeout, (int, float)):
            filter_timeout = float(cfg_timeout)
    if args.filter_timeout is not None:
        filter_timeout = args.filter_timeout

    output_file = Path(args.output) if args.output else None

    return CliOptions(
        input_file=input_file,
        output_file=output_file,
        env=env,
        css_files=css_files,
        js_files=js_files,
        meta_tags=meta_tags,
        filter_paths=filter_paths,
        filter_timeout=filter_timeout,
        watch=args.watch,
        debug=args.debug,
    )


def compile_file(options: CliOptions) -> str:
    """Read, parse, evaluate, inject, and render a PicoDoc file to HTML."""
    from picodoc.debug import dump_ast
    from picodoc.eval import evaluate
    from picodoc.filters import FilterRegistry
    from picodoc.inject import inject_head_items
    from picodoc.parser import parse
    from picodoc.render import render

    source = options.input_file.read_text(encoding="utf-8")
    doc = parse(source, str(options.input_file))

    doc_dir = options.input_file.parent
    if not doc_dir.parts:
        doc_dir = Path(".")

    filters = FilterRegistry(
        document_dir=doc_dir,
        extra_paths=list(options.filter_paths),
        timeout=options.filter_timeout,
    )

    doc = evaluate(doc, str(options.input_file), env=options.env, filters=filters)

    if options.debug:
        dump_ast(doc)

    doc = inject_head_items(doc, options.css_files, options.js_files, options.meta_tags)
    return render(doc)


def watch_loop(options: CliOptions) -> None:
    """Poll input file for changes, recompile on each modification."""
    last_mtime = 0.0
    print(f"Watching {options.input_file} for changes...", file=sys.stderr)
    try:
        while True:
            try:
                mtime = options.input_file.stat().st_mtime
            except OSError:
                time.sleep(0.5)
                continue
            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    html = compile_file(options)
                    if options.output_file:
                        options.output_file.write_text(html, encoding="utf-8")
                    else:
                        sys.stdout.write(html)
                        sys.stdout.flush()
                    print(f"Compiled {options.input_file}", file=sys.stderr)
                except (LexError, ParseError, EvalError) as exc:
                    print(str(exc), file=sys.stderr)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code (0/1/2). Does not call sys.exit()."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        options = resolve_options(args)
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if options.watch:
        watch_loop(options)
        return 0

    try:
        html = compile_file(options)
    except (LexError, ParseError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except EvalError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if options.output_file:
        options.output_file.write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)

    return 0
