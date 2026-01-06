#!/usr/bin/env python3
"""
Helper script to generate a Dirigera authentication token.

Usage:
    python generate_token.py <hub_ip_address>

Example:
    python generate_token.py 192.168.1.100

You will be prompted to press the pairing button on your Dirigera hub.
"""

import sys

import dirigera


def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_token.py <hub_ip_address>")
        print("Example: python generate_token.py 192.168.1.100")
        sys.exit(1)

    hub_ip = sys.argv[1]

    print(f"Generating token for Dirigera hub at {hub_ip}")
    print("Please press the pairing button on your Dirigera hub when prompted...")
    print()

    try:
        token = dirigera.create_token(hub_ip)
        print("✓ Token generated successfully!")
        print()
        print("=" * 70)
        print("Your Dirigera Token:")
        print(token)
        print("=" * 70)
        print()
        print("Save this token securely. You'll need it to connect to the dashboard.")
    except Exception as e:
        print(f"✗ Error generating token: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
