"""PicoDoc markup language compiler."""

__version__ = "0.1.0"


def compile(
    source: str,
    filename: str = "input.pdoc",
    env: dict[str, str] | None = None,
) -> str:
    """Parse, evaluate, and render PicoDoc source to HTML."""
    from picodoc.eval import evaluate
    from picodoc.parser import parse
    from picodoc.render import render

    doc = parse(source, filename)
    doc = evaluate(doc, filename, env=env)
    return render(doc)
