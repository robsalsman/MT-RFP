"""Manage sign-in users from the command line.

  python -m app.manage_users add <username> "<Display Name>" <4-digit-pin>
  python -m app.manage_users remove <username>
  python -m app.manage_users list
"""
import sys

from . import auth


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "add" and len(argv) == 4:
        auth.add_user(argv[1], argv[2], argv[3])
        print(f"user '{auth.normalize_username(argv[1])}' saved")
        return 0
    if cmd == "remove" and len(argv) == 2:
        auth.remove_user(argv[1])
        print(f"user '{auth.normalize_username(argv[1])}' removed")
        return 0
    if cmd == "list":
        for username, u in auth.load_users().items():
            print(f"  {username}  ({u.get('display_name')})")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
