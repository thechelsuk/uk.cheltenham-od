"""Make the _python scripts importable from the tests (they import each other
as top-level modules, e.g. `import helper`)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
