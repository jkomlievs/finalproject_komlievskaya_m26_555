import sys

from valutatrade_hub.cli.interface import run_cli, run_repl


def main() -> None:
    if len(sys.argv) > 1:
        run_cli(sys.argv[1:])
    else:
        run_repl()


if __name__ == "__main__":
    main()