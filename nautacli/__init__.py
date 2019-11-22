import argparse
import logging
import os
from textwrap import dedent

import requests

from nautacli.__about__ import __name__, __version__
from nautacli.cli import Cli


def main():
    nauta = Cli(
        os.getenv(
            "NAUTA_CONFIG_DIR",
            os.path.expanduser("~/.local/share/nauta/")
        )
    )

    parser = argparse.ArgumentParser(
        epilog=dedent("""\
        Subcommands:

          up [-t] [username]
          down
          cards [-v] [-f] [-c]
          cards add [username]
          cards clean
          cards rm username [username ...]
          cards info username

        Use -h after a subcommand for more info
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers()
    parser.add_argument("-d", "--debug",
        action="store_true",
        help="show debug info"
    )

    parser.add_argument("--version", action="version", version="{} v{}".format(__name__, __version__))

    cards_parser = subparsers.add_parser('cards')
    cards_parser.set_defaults(func=nauta.cards)
    cards_parser.add_argument("-v",
        action="store_true",
        help="show full passwords"
    )
    cards_parser.add_argument("-f", "--fresh",
        action="store_true",
        help="force a fresh request of card time"
    )
    cards_parser.add_argument("-c", "--cached",
        action="store_true",
        help="shows cached data, avoids the network"
    )
    cards_subparsers = cards_parser.add_subparsers()
    cards_add_parser = cards_subparsers.add_parser('add')
    cards_add_parser.set_defaults(func=nauta.cards_add)
    cards_add_parser.add_argument('username', nargs="?")

    cards_clean_parser = cards_subparsers.add_parser('clean')
    cards_clean_parser.set_defaults(func=nauta.cards_clean)

    cards_rm_parser = cards_subparsers.add_parser('rm')
    cards_rm_parser.set_defaults(func=nauta.cards_rm)
    cards_rm_parser.add_argument('usernames', nargs="+")

    cards_info_parser = cards_subparsers.add_parser('info')
    cards_info_parser.set_defaults(func=nauta.cards_info)
    cards_info_parser.add_argument('username')

    up_parser = subparsers.add_parser('up')
    up_parser.set_defaults(func=nauta.up)
    up_parser.add_argument('username', nargs="?")
    up_parser.add_argument('-t', '--time', help='Define la duracion maxima (en segundos) para esta conexion', type=int)

    down_parser = subparsers.add_parser('down')
    down_parser.set_defaults(func=nauta.down)

    args = parser.parse_args()

    if 'username' in args and args.username and '@' not in args.username:
        args.username = nauta.expand_username(args.username)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        from http.client import HTTPConnection
        HTTPConnection.debuglevel = 2

    if 'func' in args:
        try:
            args.func(args)
        except requests.exceptions.ConnectionError as ex:
            print("Conection error. Check your connection and try again.")
            import traceback
            nauta.log(traceback.format_exc())
    else:
        parser.print_help()