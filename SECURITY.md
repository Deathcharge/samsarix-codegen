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

Samsarix Codegen reads only explicitly selected files, never applies or executes model output, and
makes a network request only through the `run` command. File content, endpoint responses, and model
output remain untrusted. See the README for the implemented limits and residual risks.
