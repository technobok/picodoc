"""Allow running PicoDoc as ``python -m picodoc``."""

import sys

from picodoc.cli import main

sys.exit(main())
