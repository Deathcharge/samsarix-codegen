# Contributing

Samsarix Codegen is a small, read-only prompt-building tool. Changes should preserve its core safety
properties: explicit context selection, project-root containment, bounded resource use, no implicit
file edits or command execution, one visible network request per `run`, and no credential logging.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
python -m build
```

On Windows, activate the virtual environment with `.\.venv\Scripts\Activate.ps1`; on macOS or Linux,
use `source .venv/bin/activate`.

## Change expectations

- Add focused tests for behavior changes, including ordinary failure states.
- Keep the runtime dependency-free unless a dependency has a documented, material benefit.
- Keep model and endpoint behavior provider-neutral within the documented chat-completions subset.
- Do not add automatic retries, repository-wide collection, file edits, shell execution, telemetry,
  or background behavior without a separate product and threat-model decision.
- Update the README and `docs/PRODUCTIZATION.md` when behavior, scope, or release gates change.

## License and contributions

The project is licensed under Apache-2.0. Unless you explicitly state otherwise, a contribution
intentionally submitted for inclusion is provided under Apache-2.0 without additional terms, as
described in section 5 of the license. You must have the right to submit your contribution.

Copyright in an accepted contribution remains with its contributor unless separately assigned.
Questions about contribution or commercial arrangements can be sent to `contact@samsarix.com`.
