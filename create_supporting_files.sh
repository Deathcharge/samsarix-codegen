#!/bin/bash

# Create pyproject.toml for code generation
cat > helix_codegen/pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "helix-codegen"
version = "1.0.0"
description = "AI-powered code generation for Helix CLI"
authors = [{name = "Helix Collective"}]
license = {text = "Apache-2.0"}
requires-python = ">=3.9"
dependencies = [
    "click>=8.0",
    "rich>=10.0",
    "requests>=2.28",
    "pydantic>=1.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "black>=22.0",
    "flake8>=4.0",
    "mypy>=0.950",
]
EOF

# Create package.json for VS Code extension
cat > helix_vscode_ext/package.json << 'EOF'
{
  "name": "helix-ai",
  "displayName": "Helix AI Assistant",
  "description": "AI-powered code generation and analysis for VS Code",
  "version": "1.0.0",
  "publisher": "HelixCollective",
  "license": "Apache-2.0",
  "engines": {
    "vscode": "^1.85.0"
  },
  "categories": [
    "AI",
    "Programming Languages",
    "Linters"
  ],
  "keywords": [
    "ai",
    "code-generation",
    "code-analysis",
    "refactoring",
    "optimization"
  ],
  "activationEvents": [
    "onStartupFinished"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      {
        "command": "helix.generate.function",
        "title": "Generate Function",
        "category": "Helix"
      },
      {
        "command": "helix.generate.class",
        "title": "Generate Class",
        "category": "Helix"
      },
      {
        "command": "helix.generate.test",
        "title": "Generate Tests",
        "category": "Helix"
      },
      {
        "command": "helix.analyze.file",
        "title": "Analyze File",
        "category": "Helix"
      },
      {
        "command": "helix.refactor.code",
        "title": "Refactor Code",
        "category": "Helix"
      },
      {
        "command": "helix.optimize.performance",
        "title": "Optimize Performance",
        "category": "Helix"
      },
      {
        "command": "helix.interactive.start",
        "title": "Start Interactive Mode",
        "category": "Helix"
      }
    ],
    "keybindings": [
      {
        "command": "helix.generate.function",
        "key": "ctrl+shift+g",
        "mac": "cmd+shift+g"
      },
      {
        "command": "helix.interactive.start",
        "key": "ctrl+shift+i",
        "mac": "cmd+shift+i"
      }
    ]
  },
  "scripts": {
    "vscode:prepublish": "npm run esbuild-base -- --minify",
    "esbuild-base": "esbuild ./src/extension.ts --bundle --outfile=out/extension.js --external:vscode --format=cjs --platform=node",
    "esbuild": "npm run esbuild-base -- --sourcemap",
    "esbuild-watch": "npm run esbuild-base -- --sourcemap --watch",
    "test": "node ./out/test/runTest.js",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./"
  },
  "devDependencies": {
    "@types/vscode": "^1.85.0",
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0",
    "esbuild": "^0.19.0"
  }
}
EOF

# Create pyproject.toml for interactive mode
cat > helix_interactive/pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "helix-interactive"
version = "1.0.0"
description = "Interactive development mode for Helix CLI"
authors = [{name = "Helix Collective"}]
license = {text = "Apache-2.0"}
requires-python = ">=3.9"
dependencies = [
    "click>=8.0",
    "rich>=10.0",
    "requests>=2.28",
    "pydantic>=1.9",
    "prompt-toolkit>=3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "black>=22.0",
    "flake8>=4.0",
    "mypy>=0.950",
]
EOF

echo "✓ Supporting files created"
