#!/usr/bin/env python3
"""
Helper script to generate a Dirigera authentication token.

Usage:
    python generate_token.py <hub_ip_address>

Example:
    python generate_token.py 192.168.1.100

You will be prompted to press the pairing button on your Dirigera hub,
then press ENTER in the terminal to retrieve your token.
"""

import sys

from dirigera.hub.auth import (
    ALPHABET,
    CODE_LENGTH,
    get_token,
    random_code,
    send_challenge,
)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python generate_token.py <hub_ip_address>")
        print("Example: python generate_token.py 192.168.1.100")
        sys.exit(1)

    hub_ip = sys.argv[1]

    print(f"Generating token for Dirigera hub at {hub_ip}")
    print("Starting authentication challenge...")
    print()

    try:
        code_verifier = random_code(ALPHABET, CODE_LENGTH)
        code = send_challenge(hub_ip, code_verifier)
        input("Press the pairing button on your Dirigera hub, then press ENTER...")
        token = get_token(hub_ip, code, code_verifier)
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
