# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Email
`support@samsarix.com` with the subject `Security: Samsarix Codegen` and include the affected
version, reproduction steps, impact, and any suggested mitigation. Remove API keys, proprietary
source, personal data, and other secrets from the report whenever possible.

Samsarix LLC will acknowledge the report and coordinate validation and disclosure privately. No
specific response or remediation deadline is promised for this pre-release project.

## Supported versions

Until the first public release, only the latest commit on the repository's default branch is
eligible for security fixes. After publication, this section will identify supported release lines.

## Scope and trust boundaries

Samsarix Codegen reads only explicitly selected files or a deliberately named stdin stream, never
applies or executes model output, and makes a network request only through `run` or `execute`.
File content, request artifacts, endpoint responses, and model output remain untrusted.

Request artifacts contain the complete model messages and therefore can contain source code, logs,
or other sensitive input. Store and transmit them under the same access and retention policy as
their source material. Artifact fingerprints and per-context hashes detect drift but are unkeyed;
they do not prove who created or approved an artifact. Use external access controls or signing when
authenticity across a trust boundary is required. See the README and
`docs/REQUEST_ARTIFACT.md` for implemented limits and residual risks.
