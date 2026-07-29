# Samsarix Codegen

Samsarix Codegen is a read-only Python CLI and library for building bounded, inspectable prompts
for coding tasks. It can work entirely offline by rendering a prompt for review or copy/paste, or
send one explicitly bounded request to an OpenAI-compatible chat-completions endpoint.

It is for developers who want a small, transparent bridge between selected source files and a
model—not an autonomous agent. Samsarix Codegen never edits files, executes generated code, runs
shell commands, scans a repository automatically, or retries a paid request behind the user's back.

> **Status:** `0.1.0` release candidate. The local `build` and provider-backed `run` journeys are
> implemented and tested. No package has been published to PyPI.

## Why this exists

Full coding agents already provide repository indexing, tool execution, and automated edits.
Samsarix Codegen deliberately covers a narrower workflow:

1. You select the files a model may see.
2. The CLI verifies that they are UTF-8 text files inside a chosen project root and applies byte
   caps.
3. It builds a task-specific request that marks file content as untrusted data.
4. You inspect or export the request locally, or make one bounded API call.
5. The model response goes to standard output for you to review.

This repository stands on its own. It does not require a private Samsarix service, the Samsarix
CLI, SDK, editor extension, or any other repository in the wider portfolio.

## Quick start: no model or credentials

Prerequisite: Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
samsarix-codegen build "Explain the behavior and edge cases" `
  --task explain `
  --file examples/sample.py
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` and use `\` for shell
line continuation. The command prints a complete Markdown prompt and performs no network request.

Machine-readable output uses the same messages and includes a transparent token estimate:

```bash
samsarix-codegen build "Review for correctness and missing tests" \
  --task review \
  --file examples/sample.py \
  --format json
```

## Run with a model

### Local OpenAI-compatible endpoint

The default endpoint is `http://127.0.0.1:11434/v1`, matching the common local OpenAI-compatible
shape. Start your local service and name an installed model explicitly:

```bash
samsarix-codegen run "Write focused tests for this function" \
  --task tests \
  --file examples/sample.py \
  --model your-local-model \
  --max-output-tokens 1200
```

The CLI prints the approximate input size and configured output cap to standard error, the model
text to standard output, and provider-reported usage when available. It makes one non-streaming
request and does not retry automatically.

### Hosted endpoint

Use HTTPS and place credentials only in the environment. For PowerShell:

```powershell
$env:SAMSARIX_API_BASE = "https://provider.example/v1"
$env:SAMSARIX_MODEL = "provider-model-name"
$env:SAMSARIX_API_KEY = "your-provider-key"
samsarix-codegen run "Identify security and reliability problems" `
  --task review `
  --file src/samsarix_codegen/provider.py
```

Equivalent POSIX shells use `export SAMSARIX_API_BASE=...`. There is intentionally no `--api-key`
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

Use `samsarix-codegen build --help` and `samsarix-codegen run --help` for all options.

## Context and safety limits

- Only paths supplied with `--file` are read; the option can be repeated up to 20 times.
- Paths are resolved and must remain inside `--root` (the current directory by default).
- Symlinks are checked after resolution, duplicate files are included once, and directories fail.
- Files must be valid UTF-8 text without NUL bytes.
- Total context defaults to 200,000 bytes and can be raised only to a hard maximum of 5,000,000
  with `--max-context-bytes`.
- Instructions are limited to 20,000 characters.
- Output is capped with `--max-output-tokens` (default 1,024; hard maximum 32,768).
- Network calls time out after 60 seconds by default and can be bounded from 1 to 300 seconds.
- Plain HTTP is accepted only for `localhost` and loopback addresses; remote endpoints require
  HTTPS.
- Responses larger than 10 MiB are rejected.

The token estimate is `ceil(total UTF-8 message bytes / 4)`. It is a planning approximation, not
provider billing data. Consult the chosen provider's current pricing before using a paid endpoint.

## Configuration

| Environment variable | CLI equivalent | Default |
| --- | --- | --- |
| `SAMSARIX_API_BASE` | `--endpoint` | `http://127.0.0.1:11434/v1` |
| `SAMSARIX_MODEL` | `--model` | none; required for `run` |
| `SAMSARIX_API_KEY` | none by design | none |
| `SAMSARIX_TIMEOUT` | `--timeout` | `60` |
| `SAMSARIX_MAX_OUTPUT_TOKENS` | `--max-output-tokens` | `1024` |

Command-line values override environment-backed defaults. Configuration is read at process start;
Samsarix Codegen does not load `.env` files, persist credentials, or log request content.

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

The public API exposes validated request objects, context loading, prompt rendering, and the
minimal provider client:

```python
from samsarix_codegen import PromptRequest, Task, build_messages, render_markdown

request = PromptRequest(task=Task.DEBUG, instruction="Find the likely failure")
messages = build_messages(request)
print(render_markdown(messages))
```

Unstable implementation helpers are not exported from `samsarix_codegen`.

## Development and verification

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
python -m build
```

CI runs these checks plus a built-wheel installation and primary-journey smoke test on Python 3.10
and 3.14 across Ubuntu and Windows. To inspect the package manually:

```bash
python -m build
python -m pip install --force-reinstall --no-deps dist/*.whl
samsarix-codegen --version
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations,
[SECURITY.md](SECURITY.md) for private vulnerability reporting, [SUPPORT.md](SUPPORT.md) for support
channels, and [docs/PRODUCTIZATION.md](docs/PRODUCTIZATION.md) for the audit record and release
gates.

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

## Security, privacy, reliability, and cost

- Selected file contents and instructions leave the machine only when `run` is used.
- File contents are untrusted prompt data. The system message asks the model not to follow embedded
  instructions, but prompt injection cannot be eliminated; review every response.
- Generated code may be incorrect or unsafe. Samsarix Codegen never executes or applies it.
- There is no telemetry, analytics, background process, retry loop, or local history.
- Provider compatibility varies. Tool calling, images, streaming, automatic edits, repository
  discovery, conversation persistence, and provider-specific Responses APIs are out of scope for
  `0.1.0`.
- Monetary cost cannot be calculated without provider- and model-specific pricing. The input
  estimate, one-request behavior, timeout, and output cap are the enforceable local controls.

## License, attribution, and support

Copyright 2026 Samsarix LLC. Licensed under the [Apache License 2.0](LICENSE).

Distributions must follow the license's attribution and notice requirements; [NOTICE](NOTICE)
identifies Samsarix LLC, and [CITATION.cff](CITATION.cff) provides citation metadata. Apache-2.0 is a
permissive open-source license and does not require downstream modifications to be published. It
also does not grant broader rights to use the Samsarix name or branding beyond the license terms.

For product and licensing questions, email `contact@samsarix.com`. For support or private security
reports, email `support@samsarix.com`.
