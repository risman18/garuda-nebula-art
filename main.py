#!/usr/bin/env python3
"""Garuda Nebula — entry for make.fun's "Make the coolest art" bounty.

Writes the artwork held in this repository (art.png) to /output/entry.png.
Deterministic: no network, no randomness; every run writes the same bytes.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "art.png")
OUT_DIR = "/output"
OUT = os.path.join(OUT_DIR, "entry.png")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SRC, "rb") as f:
        data = f.read()
    with open(OUT, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
