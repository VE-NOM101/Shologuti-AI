"""Entry point for the Tkinter client."""

from __future__ import annotations

import argparse

from .ui import ClientApp


def main() -> None:
    parser = argparse.ArgumentParser(description="Shologuti Python client")
    parser.parse_args()
    app = ClientApp()
    app.run()


if __name__ == "__main__":
    main()


