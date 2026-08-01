# Context manifest contract

Samsarix Codegen context manifest schema version `1` is a small, checked-in allowlist for repeatable
request construction. It improves explicit-input ergonomics without adding repository discovery,
glob expansion, ignore rules, or an implicit configuration file.

## Document shape

The document is UTF-8 JSON with exactly two fields:

```json
{
  "schema_version": 1,
  "files": [
    "src/app.py",
    "tests/test_app.py"
  ]
}
```

`files` must contain 1–20 unique strings. Paths use `/`, are relative to the command's `--root`,
and cannot contain absolute prefixes, empty/`.`/`..` segments, control characters, backslashes,
non-portable filename characters or endings, or Windows-reserved device segments. A manifest is
limited to 64 KiB. The runtime parser rejects unknown or duplicate JSON fields.

Export the standalone Draft 2020-12 schema without network access:

```bash
samsarix-codegen schema context-manifest > context-manifest-v1.schema.json
```

JSON Schema validates the portable document shape. `parse_context_manifest()` remains authoritative
for byte limits, duplicate JSON fields, Unicode validity, and reserved path segments.

## Resolution and composition

Use a manifest only by naming it:

```bash
samsarix-codegen build "Review this surface" \
  --root . \
  --context-manifest examples/review-context-v1.json \
  --format json
```

- Samsarix does not search for a default manifest.
- The manifest file itself must resolve to a regular file inside `--root`. Symlinks are resolved
  before containment is checked.
- Every listed path flows through the existing context loader. Each must resolve to a regular UTF-8
  file inside the same root and satisfy the selected byte budget.
- Repeat `--context-manifest` to compose context sets. Repeated `--file` values are loaded first,
  then manifests in command-line order, then entries in array order. Resolved duplicates are
  included once in first-seen order.
- Direct entries, manifest entries, and named stdin share the 20-declaration limit. This bound is
  checked before source files are read; duplicate declarations still count.
- The effective selected content—not the manifest filename or formatting—is captured in the
  request artifact. Reformatting a manifest without changing its effective files cannot by itself
  change the request fingerprint.

Multiple small manifests are a deliberate alternative to named sets, inheritance, or conditionals:

```bash
samsarix-codegen build "Review the API and its tests" \
  --context-manifest context/core.json \
  --context-manifest context/tests.json \
  --file docs/api-contract.md
```

## Trust and cost boundary

A committed manifest is reviewable project configuration, not authorization to crawl its
directory. It can become stale or reference a missing file; either condition fails closed. File
contents remain untrusted prompt data and may contain prompt injection. The generated request
artifact still exposes context names, content hashes, total bytes, an estimated token count, and a
fingerprint before any optional network request.

Manifests can reveal repository structure even though they contain no source contents. Apply normal
repository access controls. Do not list secrets merely because a file is root-contained.
