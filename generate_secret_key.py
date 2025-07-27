#!/usr/bin/env python
"""
Simple script to generate a Django SECRET_KEY
"""

from django.core.management.utils import get_random_secret_key

if __name__ == "__main__":
    secret_key = get_random_secret_key()
    print("Generated SECRET_KEY:")
    print(secret_key)
    print("\nAdd this to your Railway environment variables:")
    print(f"SECRET_KEY={secret_key}")