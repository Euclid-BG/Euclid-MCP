import os
import sys

__version__ = "0.5.0"
__all__ = ["main"]


def _apply_cli_args() -> None:
    """Funnel `--kb-path` and `--backend` CLI flags into their env vars.

    Runs before the server module is imported because KB preload happens at
    import time (the MCPServer instructions are computed then). The package is
    imported before `__main__` executes, so this must live in `__init__`.
    """
    if "--kb-path" in sys.argv:
        idx = sys.argv.index("--kb-path")
        if idx + 1 < len(sys.argv):
            os.environ["EUCLID_KB_PATH"] = sys.argv[idx + 1]
    if "--backend" in sys.argv:
        idx = sys.argv.index("--backend")
        if idx + 1 < len(sys.argv):
            os.environ["EUCLID_BACKEND"] = sys.argv[idx + 1]


_apply_cli_args()

from .server import main  # noqa: E402
