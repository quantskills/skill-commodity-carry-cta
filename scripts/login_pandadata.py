"""Interactive PandaAI data login helper.

The password is read with getpass so it is not printed to the terminal.
"""

from __future__ import annotations

import argparse
import getpass
import importlib
import os


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Login to PandaAI data and save the local token.")
    parser.add_argument("--username", default=os.getenv("PANDADATA_USERNAME") or os.getenv("DEFAULT_USERNAME") or "")
    parser.add_argument("--base-url", default=os.getenv("PANDADATA_BASE_URL") or os.getenv("JAVA_SERVICE_BASE_URL") or "http://pandadata.pandaaiquant.com")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    username = args.username.strip() or input("PandaAI username: ").strip()
    password = os.getenv("PANDADATA_PASSWORD") or os.getenv("DEFAULT_PASSWORD") or getpass.getpass("PandaAI password: ")

    if not username or not password:
        print("Login failed: username and password are required.")
        return 1

    panda_data = importlib.import_module("panda_data")
    panda_data.init_token(username=username, password=password, base_url=args.base_url)
    print("PandaAI data login succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
