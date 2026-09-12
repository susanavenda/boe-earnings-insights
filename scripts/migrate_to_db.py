#!/usr/bin/env python3
"""Migrate data/processed CSV/JSON into data/boe.sqlite."""
from store import migrate_processed
import json

if __name__ == "__main__":
    print(json.dumps(migrate_processed(), indent=2))
