"""Allow `python -m tabprep ...` as an alternative to the `tabprep` script."""
from tabprep.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
