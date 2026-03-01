"""Command-line interface for PicoDoc."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from picodoc.errors import EvalError, LexError, ParseError, RenderError


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
    p.add_argument("--debug", action="store_true", help="Dump AST to stderr")
    return p


def parse_kv_arg(label: str, s: str) -> tuple[str, str]:
    """Parse a NAME=VALUE string into (name, value)."""
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"invalid {label} format (expected NAME=VALUE): {s}")
    name, _, value = s.partition("=")
    return name, value


def resolve_options(args: argparse.Namespace) -> CliOptions:
    """Resolve CLI args into CliOptions."""
    input_file = Path(args.input)

    env: dict[str, str] = {}
    for raw in args.env:
        name, value = parse_kv_arg("env", raw)
        env[name] = value

    meta_tags: list[tuple[str, str]] = []
    for raw in args.meta:
        meta_tags.append(parse_kv_arg("meta", raw))

    filter_paths = [Path(p) for p in args.filter_path]
    filter_timeout = args.filter_timeout if args.filter_timeout is not None else 5.0

    output_file = Path(args.output) if args.output else None

    return CliOptions(
        input_file=input_file,
        output_file=output_file,
        env=env,
        css_files=list(args.css),
        js_files=list(args.js),
        meta_tags=meta_tags,
        filter_paths=filter_paths,
        filter_timeout=filter_timeout,
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

    doc = evaluate(doc, str(options.input_file), source=source, env=options.env, filters=filters)

    if options.debug:
        dump_ast(doc)

    doc = inject_head_items(doc, options.css_files, options.js_files, options.meta_tags)
    return render(doc)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code (0/1/2). Does not call sys.exit()."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        options = resolve_options(args)
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        html = compile_file(options)
    except (LexError, ParseError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (EvalError, RenderError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if options.output_file:
        options.output_file.write_text(html, encoding="utf-8")
    else:
        sys.stdout.write(html)

    return 0
