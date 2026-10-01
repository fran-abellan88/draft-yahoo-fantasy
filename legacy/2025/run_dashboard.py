#!/usr/bin/env python3
"""
NBA Fantasy Draft Dashboard Launcher
Automatically starts web server and opens dashboard in browser
"""

import http.server
import os
import socketserver
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def check_data_files():
    """Check if JSON data files exist, run preprocessing if needed."""
    teams_file = Path("teams_data.json")
    players_file = Path("players_data.json")

    if not teams_file.exists() or not players_file.exists():
        print("⚠️  Data files not found. Running preprocessing...")
        print()

        try:
            subprocess.run([sys.executable, "preprocess_data.py"], check=True)
            print()
            print("✅ Preprocessing complete!")
            print()
        except subprocess.CalledProcessError:
            print("❌ Error during preprocessing. Please check preprocess_data.py")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ Error: preprocess_data.py not found!")
            sys.exit(1)


def find_free_port(start_port=8001):
    """Find an available port starting from start_port."""
    port = start_port
    while True:
        try:
            with socketserver.TCPServer(("", port), None) as s:
                return port
        except OSError:
            print(f"⚠️  Port {port} is already in use, trying next port...")
            port += 1


def start_server(port):
    """Start HTTP server on specified port."""
    handler = http.server.SimpleHTTPRequestHandler

    class QuietHTTPServer(socketserver.TCPServer):
        """HTTP server that doesn't print every request."""

        allow_reuse_address = True

        def handle_error(self, request, client_address):
            """Suppress error output."""
            pass

    httpd = QuietHTTPServer(("", port), handler)

    print(f"🚀 Starting web server on port {port}...")
    print()
    print(f"📱 Dashboard URL: http://localhost:{port}/dashboard.html")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    print()

    return httpd


def main():
    """Main entry point."""
    print("🏀 NBA Fantasy Draft Dashboard Launcher")
    print("=" * 50)
    print()

    # Check if dashboard.html exists
    if not Path("dashboard.html").exists():
        print("❌ Error: dashboard.html not found!")
        print("Please make sure you're running this script from the project directory.")
        sys.exit(1)

    # Check and create data files if needed
    check_data_files()

    # Find available port
    port = find_free_port(8001)

    # Start server
    httpd = start_server(port)

    # Wait for server to start
    time.sleep(1)

    # Open browser
    url = f"http://localhost:{port}/dashboard.html"
    try:
        webbrowser.open(url)
        print("✅ Dashboard opened in your default browser")
        print()
    except Exception as e:
        print(f"⚠️  Could not open browser automatically: {e}")
        print(f"Please open your browser and navigate to: {url}")
        print()

    # Run server
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        print()
        print("🛑 Shutting down server...")
        httpd.shutdown()
        print("✅ Server stopped. Goodbye!")


if __name__ == "__main__":
    main()
