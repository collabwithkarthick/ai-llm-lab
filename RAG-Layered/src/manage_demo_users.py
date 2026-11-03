"""Create, list, and remove local accounts for the CLI authorization demo."""

import argparse
import getpass
import sys

from demo_auth import add_user, list_users, remove_user
from document_access import KNOWN_GROUPS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    add_command = commands.add_parser("add", help="create a demo user")
    add_command.add_argument("username")
    add_command.add_argument("groups", nargs="+", choices=sorted(KNOWN_GROUPS))

    commands.add_parser("list", help="list demo usernames and access groups")

    remove_command = commands.add_parser("remove", help="remove a demo user")
    remove_command.add_argument("username")

    args = parser.parse_args()
    try:
        if args.command == "add":
            password = getpass.getpass("New password (12+ characters): ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                raise ValueError("Passwords do not match.")
            add_user(args.username, password, tuple(args.groups))
            print(f"Created '{args.username}' with groups: {', '.join(args.groups)}")
        elif args.command == "list":
            for username, groups in sorted(list_users().items()):
                print(f"{username}: {', '.join(groups)}")
        elif args.command == "remove":
            if remove_user(args.username):
                print(f"Removed '{args.username}'.")
            else:
                print(f"User '{args.username}' does not exist.")
                return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
