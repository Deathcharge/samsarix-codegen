# Helix Codegen

Helix Codegen is a read-only Python CLI and library for building bounded, inspectable prompts for
coding tasks. It can work entirely offline by rendering a prompt for review or copy/paste, or send
one explicitly bounded request to an OpenAI-compatible chat-completions endpoint.

It is for developers who want a small, transparent bridge between selected source files and a
model—not an autonomous agent. Helix Codegen never edits files, executes generated code, runs shell
commands, scans a repository automatically, or retries a paid request behind the user's back.

> **Status:** `0.1.0` release candidate. The local build and run journeys are implemented and
> tested. No package has been published, and the repository currently has no owner-approved license.

## Why this exists

Full coding agents already provide repository indexing, tool execution, and automated edits. Helix
Codegen deliberately covers a narrower workflow:

1. You select the files a model may see.
2. Helix verifies that they are UTF-8 text files inside a chosen project root and applies byte caps.
3. It builds a task-specific request that marks file content as untrusted data.
4. You inspect or export the request locally, or make one bounded API call.
5. The model response goes to standard output for you to review.

This shape is independently useful as a scriptable prompt builder and as a minimal reference client
for local or hosted OpenAI-compatible endpoints.

## Quick start: no model or credentials

Prerequisites: Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
helix-codegen build "Explain the behavior and edge cases" `
  --task explain `
  --file examples/sample.py
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` and use `\` for shell
line continuation. The command prints a complete Markdown prompt and performs no network request.

Machine-readable output uses the same messages and includes a transparent token estimate:

```bash
helix-codegen build "Review for correctness and missing tests" \
  --task review \
  --file examples/sample.py \
  --format json
```

## Run with a model

### Local OpenAI-compatible endpoint

The default endpoint is `http://127.0.0.1:11434/v1`, matching Ollama's OpenAI-compatible API. Start
your local service and name an installed model explicitly:

```bash
helix-codegen run "Write focused tests for this function" \
  --task tests \
  --file examples/sample.py \
  --model your-local-model \
  --max-output-tokens 1200
```

Helix prints the approximate input size and configured output cap to standard error, the model text
to standard output, and provider-reported usage when available. It makes one non-streaming request
and does not retry automatically.

### Hosted endpoint

Use HTTPS and place credentials only in the environment. For PowerShell:

```powershell
$env:HELIX_API_BASE = "https://provider.example/v1"
$env:HELIX_MODEL = "provider-model-name"
$env:HELIX_API_KEY = "your-provider-key"
helix-codegen run "Identify security and reliability problems" `
  --task review `
  --file src/helix_codegen/provider.py
```

Equivalent POSIX shells use `export HELIX_API_BASE=...`. There is intentionally no `--api-key`
option, which reduces accidental exposure in shell history and process listings.

## Tasks

`--task` selects focused guidance while the user's instruction remains authoritative:

| Task | Intended output |
| --- | --- |
| `generate` | Requested code, assumptions, and verification steps |
| `explain` | Behavior, inputs, outputs, edge cases, and trade-offs |
| `debug` | Plausible root cause, smallest fix, and regression tests |
| `refactor` | Behavior-preserving refactor with rationale |
| `tests` | Normal, boundary, and failure tests |
| `review` | Correctness, security, reliability, maintainability, and test gaps |

Use `helix-codegen build --help` and `helix-codegen run --help` for all options.

## Context and safety limits

- Only paths supplied with `--file` are read; the option can be repeated up to 20 times.
- Paths are resolved and must remain inside `--root` (the current directory by default).
- Symlinks are checked after resolution, duplicate files are included once, and directories fail.
- Files must be valid UTF-8 text without NUL bytes.
- Total context defaults to 200,000 bytes and can be lowered or raised to a hard maximum of
  5,000,000 with `--max-context-bytes`.
- Instructions are limited to 20,000 characters.
- Output is capped with `--max-output-tokens` (default 1,024; hard maximum 32,768).
- Network calls time out after 60 seconds by default and can be bounded from 1 to 300 seconds.
- Plain HTTP is accepted only for `localhost` and loopback addresses; remote endpoints require HTTPS.
- Responses larger than 10 MiB are rejected.

The token estimate is `ceil(total UTF-8 message bytes / 4)`. It is a planning approximation, not
provider billing data. Consult the chosen provider's current pricing before using a paid endpoint.

## Configuration

| Environment variable | CLI equivalent | Default |
| --- | --- | --- |
| `HELIX_API_BASE` | `--endpoint` | `http://127.0.0.1:11434/v1` |
| `HELIX_MODEL` | `--model` | none; required for `run` |
| `HELIX_API_KEY` | none by design | none |
| `HELIX_TIMEOUT` | `--timeout` | `60` |
| `HELIX_MAX_OUTPUT_TOKENS` | `--max-output-tokens` | `1024` |

Command-line values override environment-backed defaults. Configuration is read at process start;
Helix does not load `.env` files, persist credentials, or log request content.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Unexpected internal failure |
| `2` | Invalid command or provider configuration |
| `3` | Invalid, unsafe, or unreadable context input |
| `4` | Endpoint, HTTP, timeout, or response-contract failure |
| `130` | Cancelled with `Ctrl+C` |

## Library API

The public API exposes validated request objects, context loading, prompt rendering, and the minimal
provider client:

```python
from helix_codegen import PromptRequest, Task, build_messages, render_markdown

request = PromptRequest(task=Task.DEBUG, instruction="Find the likely failure")
messages = build_messages(request)
print(render_markdown(messages))
```

Unstable implementation helpers are not exported from `helix_codegen`.

## Development and verification

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
python -m build
```

CI is configured to run those checks plus a built-wheel installation and primary-journey smoke test
on Python 3.10 and 3.14 across Ubuntu and Windows. To inspect the package manually:

```bash
python -m build
python -m pip install --force-reinstall --no-deps dist/*.whl
helix-codegen --version
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations and
[docs/PRODUCTIZATION.md](docs/PRODUCTIZATION.md) for the audit record and release gates.

## Architecture

```text
CLI arguments and environment
        |
        v
validated request + explicitly loaded context
        |
        v
provider-neutral system/user messages
        |                         |
        v                         v
Markdown/JSON output       one chat-completions request
                                  |
                                  v
                         normalized text on stdout
```

The package uses only the Python standard library at runtime. The network client relies on Python's
default TLS verification and implements only the non-streaming OpenAI-compatible
`/chat/completions` subset used by the documented journey.

## Security, privacy, and limitations

- Selected file contents and instructions leave the machine only when `run` is used.
- File contents are untrusted prompt data. The system message asks the model not to follow embedded
  instructions, but prompt injection cannot be eliminated; review every response.
- Generated code may be incorrect or unsafe. Helix never executes or applies it.
- API compatibility varies by provider and model. Tool calling, images, streaming, automatic edits,
  repository discovery, conversation persistence, and provider-specific Responses APIs are out of
  scope for `0.1.0`.
- There is no telemetry, analytics, background process, retry loop, or local history.
- Helix cannot calculate monetary cost without provider- and model-specific pricing. The input
  estimate and output cap are the enforceable local controls.

## Distribution and license status

The supported local distribution path is `pip install .` or `pipx install .`. Building an sdist and
wheel with `python -m build` is supported, but publishing to PyPI requires owner credentials, a final
package-name check, and an owner-approved license decision.

This repository currently contains **no license file**. Earlier prototype metadata made conflicting
Apache/proprietary claims without the referenced license files. Those claims were removed. Copyright
law therefore reserves all rights by default; do not assume permission to copy, modify, or
redistribute this project until the owner adds an explicit license.
