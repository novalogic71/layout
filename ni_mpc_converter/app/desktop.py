from __future__ import annotations

import argparse
import socket
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Timer

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ni_mpc_converter.app.web import DEFAULT_HOST, DEFAULT_PORT, ConverterRequestHandler
else:
    from .web import DEFAULT_HOST, DEFAULT_PORT, ConverterRequestHandler


def _port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _choose_port(host: str, requested_port: int) -> int:
    if _port_is_available(host, requested_port):
        return requested_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the MPC Converter local desktop app.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind. Default: {DEFAULT_HOST}")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help=f"Preferred port. Default: {DEFAULT_PORT}")
    parser.add_argument("--no-browser", action="store_true", help="Start the local server without opening a browser.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    port = _choose_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), ConverterRequestHandler)
    url = f"http://{args.host}:{port}/"

    print(f"MPC Converter running at {url}")
    print("Close this window or press Ctrl+C to stop.")

    if not args.no_browser:
        Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MPC Converter.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
