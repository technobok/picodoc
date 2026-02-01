"""External filter discovery and invocation (JSON stdin/stdout protocol)."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from picodoc.errors import EvalError
from picodoc.tokens import Span


@dataclass
class FilterRegistry:
    """Discovers and invokes external filter executables."""

    document_dir: Path
    extra_paths: list[Path] = field(default_factory=list)
    timeout: float = 5.0
    _cache: dict[str, Path | None] = field(default_factory=dict, init=False)

    def find_filter(self, name: str) -> Path | None:
        """Look up a filter executable by name. Results are cached."""
        if name in self._cache:
            return self._cache[name]
        result = self._discover(name)
        self._cache[name] = result
        return result

    def _discover(self, name: str) -> Path | None:
        # 1. filters/<name> next to document
        local = self.document_dir / "filters" / name
        if local.is_file() and _is_executable(local):
            return local

        # 2. Extra configured paths
        for d in self.extra_paths:
            candidate = d / name
            if candidate.is_file() and _is_executable(candidate):
                return candidate

        # 3. picodoc-<name> on $PATH
        on_path = shutil.which(f"picodoc-{name}")
        if on_path is not None:
            return Path(on_path)

        return None

    def invoke_filter(
        self,
        name: str,
        filter_path: Path,
        args: dict[str, str],
        body: str | None,
        env: dict[str, str],
        span: Span,
    ) -> str:
        """Run a filter executable and return its stdout (PicoDoc markup)."""
        payload: dict[str, object] = {**args}
        if body is not None:
            payload["body"] = body
        payload["env"] = env

        json_input = json.dumps(payload)

        try:
            result = subprocess.run(
                [str(filter_path)],
                input=json_input,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            raise EvalError(
                f"filter '{name}' timed out after {self.timeout}s",
                span,
                "",
            ) from None

        if result.returncode != 0:
            stderr = result.stderr.strip()
            msg = f"filter '{name}' failed (exit {result.returncode})"
            if stderr:
                msg += f": {stderr}"
            raise EvalError(msg, span, "")

        return result.stdout


def _is_executable(path: Path) -> bool:
    """Check whether a path is an executable file."""
    import os

    return os.access(path, os.X_OK)
