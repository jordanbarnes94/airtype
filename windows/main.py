#!/usr/bin/env python3
"""
AirType - CLI Version
Run the server from command line with configurable options.
"""

import argparse
import asyncio
import logging

from server import AirTypeServer, get_local_ip


def main():
    parser = argparse.ArgumentParser(
        description="AirType - Type on your PC from your phone"
    )
    parser.add_argument(
        "--mode",
        choices=["ascii", "unicode"],
        default="ascii",
        help="Typing mode: ascii (direct) or unicode (clipboard-based)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket port (default: 8765)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (shows all messages)"
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Silent mode (minimal output)"
    )

    args = parser.parse_args()

    # Configure logging based on flags
    if args.silent:
        log_level = logging.WARNING
    elif args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    local_ip = get_local_ip()

    print("=" * 50)
    print("  AirType")
    print("=" * 50)
    print(f"  Mode: {args.mode.upper()}")
    if args.mode == "unicode":
        print("  Warning: Unicode mode will overwrite your clipboard")
    print()
    print(f"  Enter this on your phone: {local_ip}:{args.port}")
    print()
    print("  Waiting for connection...")
    print("=" * 50)

    server = AirTypeServer(
        port=args.port,
        mode=args.mode,
        on_connect=lambda ip: print(f"\n[+] Client connected: {ip}"),
        on_disconnect=lambda ip: print(f"[-] Client disconnected: {ip}"),
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
