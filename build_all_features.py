#!/usr/bin/env python3
"""Build all three competitive features for Helix CLI"""

import os
import json
from pathlib import Path

# Create directory structure
dirs = [
    "helix_codegen",
    "helix_vscode_ext",
    "helix_interactive",
    "helix_codegen/src",
    "helix_vscode_ext/src",
    "helix_interactive/src",
]

for d in dirs:
    Path(d).mkdir(parents=True, exist_ok=True)

print("✓ Directory structure created")
print("Ready to build three competitive features!")
