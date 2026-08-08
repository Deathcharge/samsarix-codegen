# Competitive strategy

Last reviewed: 2026-08-08

## Positioning

Samsarix Codegen is a **review-first request compiler for coding models**. It is deliberately not a
general coding agent and not a whole-repository context packer.

Its product promise is narrower and testable:

1. Accept only context that the operator explicitly names or pipes in.
2. Compile that context into a deterministic, provider-neutral request artifact.
3. Make size, provenance, and the approximate input budget visible before any network request.
4. Let a reviewer validate and pin the artifact fingerprint offline.
5. Execute exactly that reviewed message payload once, without file writes, tools, or retries.
6. Publish versioned JSON contracts that independent CI systems can validate without private code.
7. Let operators test the exact provider wire contract with one fixed, content-free request before
   sending reviewed source or logs.
8. Compare two same-request result envelopes offline without reproducing either response or
   pretending structural evidence is a quality score.
9. Reuse checked-in file selections through explicitly invoked manifests without granting
   repository-discovery or glob authority.
10. Verify a stored result against a concrete request artifact and emit local linkage metadata
    without copying prompt or response contents into ordinary logs.
11. Let CI reject a structurally valid result on an unexpected model, excessive response size, or
    excessive/missing reported usage without sending another provider request.
12. Let teams commit one strict, versioned result policy and apply the same reviewed limits locally
    and in CI without implicit configuration discovery or override precedence.
13. Bind one reviewed request to an exact endpoint, model, timeout, input ceiling, output ceiling,
    and optional result-policy fingerprint in a second credential-free approval object that cannot
    be changed by execution-time overrides.
14. Carry that reviewed plan fingerprint into the stored result and verify the complete
    request/plan/result chain offline, while distinguishing the requested model from the model
    label reported by the provider.
15. Bind one strict result-policy fingerprint into the plan, then require, enforce, and record that
    exact policy in the same content-omitting offline evidence gate.
16. Require a bounded JSON object with approved top-level keys and types when a downstream machine
    must consume the response, without exposing response-derived fields or values in evidence.
17. Apply that plan-bound policy inside the one-request `execute` boundary, after response
    normalization but before normal stdout, so CI cannot substitute or omit the gate.
18. Convert a strictly validated, source-located review response into provenance-linked JSON or
    SARIF 2.1.0, while refusing annotations for paths that were not explicitly selected.

## Evidence from adjacent products

The mature agent category already offers capabilities Samsarix should not try to clone:

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode.md) supports CI,
  stdin, sandbox policies, JSONL events, and schema-constrained outputs.
- [Codex CLI diagnostics](https://learn.chatgpt.com/docs/developer-commands?surface=cli) include a
  `doctor` command for installation and runtime troubleshooting, reinforcing that an install-level
  preflight is a normal CLI expectation.
- [Claude Code's CLI](https://code.claude.com/docs/en/cli-reference) supports
  non-interactive operation, structured output, turn limits, sessions, and permission modes.
- [Continue CLI](https://docs.continue.dev/cli/headless-mode) supports headless pipelines, rules,
  JSON output, sessions, and opt-in editing or shell tools.
- [Aider](https://aider.chat/docs/usage/modes.html) provides ask, code, and architect modes, while
  its [Git integration](https://aider.chat/docs/git.html) manages edits, commits, and undo.
- [GitHub Copilot CLI review](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/agentic-code-review)
  can inspect local changes and request permission before running supporting commands.

The context-packing category is also established:

- [Repomix](https://repomix.com/guide/) packs repositories with ignore handling, multiple formats,
  token counts, and secret detection. Its configuration can also include diffs, logs, and token
  budgets.
- [Gitingest](https://gitingest.com/) turns local or remote repositories into prompt-friendly
  digests.
- [Aider's repository map](https://aider.chat/docs/repomap.html) selects important symbols from a
  repository to give its editing agent wider context.

Persistent project context is also common, but usually broader or more implicit than this product's
approval boundary:

- [Aider's options](https://aider.chat/docs/config/options.html) accept repeatable editable and
  read-only files, while its [in-chat commands](https://aider.chat/docs/usage/commands.html) can save
  commands that reconstruct a session's selected files.
- [Claude Code memory](https://code.claude.com/docs/en/memory) loads project instruction files and
  path-scoped rules into sessions.
- [GitHub Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions)
  can apply repository-wide, path-specific, and agent instruction files.

Those workflows validate repeated team context. Samsarix context manifests serve a narrower use
case: an operator must name the manifest, its entries are a finite portable allowlist contained by
one root, and the resulting exact file contents are compiled into the same bounded fingerprinted
artifact used for approval.

The evaluation category validates demand for repeatable model comparisons:

- [Microsoft Foundry playgrounds](https://learn.microsoft.com/azure/foundry/concepts/concept-playgrounds)
  compare up to three models in parallel with synchronized prompt context and parameter settings.
- [LangSmith](https://docs.langchain.com/langsmith/compare-experiment-results) compares experiments,
  outputs, regressions, metrics, and full or diff views.
- [LangSmith privacy controls](https://docs.langchain.com/langsmith/mask-inputs-outputs) can retain
  trace metadata while hiding inputs and outputs, validating demand for content-omitting evidence.
- [Braintrust trace inspection](https://www.braintrust.dev/docs/observe/examine-traces) treats a
  trace as one end-to-end execution and supports navigation back to its prompt or dataset origin.
- [Braintrust tracing](https://www.braintrust.dev/docs/tracing-quickstart) records complete input and
  output, model configuration, token counts, and request/response metadata for each AI call.
- [LangSmith custom LLM tracing](https://docs.langchain.com/langsmith/log-llm-trace) identifies a
  useful trace with structured inputs/outputs, provider and model metadata, and token counts.
- [OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
  distinguish requested and response model labels and server address, and warn that recorded
  instructions can be sensitive. The GenAI conventions are still evolving, so Samsarix does not
  claim wire-level OpenTelemetry compatibility.
- [Promptfoo assertions and metrics](https://www.promptfoo.dev/docs/configuration/expected-outputs/)
  support deterministic checks—including valid JSON and optional JSON Schema validation—plus
  token, cost, and latency thresholds. Its
  [JSON evaluation guide](https://www.promptfoo.dev/docs/guides/evaluate-json/) treats structured
  output validation as a first-class evaluation workflow, while its
  [CI/CD guidance](https://www.promptfoo.dev/docs/integrations/ci-cd/) frames them as quality and
  cost-control gates.
- [Promptfoo configuration](https://www.promptfoo.dev/docs/configuration/guide/) can load shared
  default test configuration from external files across projects, validating the team-reuse need.
  Its [output formats](https://www.promptfoo.dev/docs/configuration/outputs/) also preserve
  pass/fail and failure-reason distinctions for automated consumers.
- [Braintrust evaluations](https://www.braintrust.dev/docs/evaluate) are designed for automated
  regression detection in CI/CD, and its
  [custom reporters](https://www.braintrust.dev/docs/evaluate/run-evaluations) can determine whether
  an evaluation process succeeds.
- [Braintrust scorers](https://www.braintrust.dev/docs/evaluate/write-scorers) include format
  validation and custom pass/fail thresholds, further validating the demand for deterministic
  response-shape gates alongside semantic scoring.
- [Braintrust evaluation parameters](https://www.braintrust.dev/docs/evaluate/write-parameters) are
  reusable and versioned across evaluations and environments, validating demand for stable team
  configuration independently of evaluation code.
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
  can require provider-side conformance to a supplied JSON Schema for supported models. Samsarix's
  local top-level gate is intentionally less expressive but remains provider-neutral and does not
  require that optional wire feature.

Provider/model configuration is itself a repeatability concern in adjacent products:

- [Promptfoo providers](https://www.promptfoo.dev/docs/providers/) can be defined in configuration
  files with provider identifiers and request parameters such as temperature or maximum tokens.
- [Braintrust prompts](https://www.braintrust.dev/docs/deploy/prompts) are versioned objects that
  combine a prompt with a model and parameters; its
  [prompt-building API](https://www.braintrust.dev/docs/evaluate/write-prompts) returns compiled
  messages plus the selected model and parameters.
- [LangSmith model configurations](https://docs.langchain.com/langsmith/managing-model-configurations)
  store a provider, model, and parameters for reuse in Playground and evaluation workflows.
- [GitHub Copilot CLI configuration](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)
  documents model configuration and precedence across invocation and configuration sources.
- [Terraform saved-plan mode](https://developer.hashicorp.com/terraform/cli/commands/apply) applies
  choices already captured in a reviewed plan and refuses new planning options at apply time.
- [GitHub Actions environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
  can hold secrets behind required review, making a credential-free review job followed by a
  protected credential-bearing job a standard automation shape.

These sources support the need to make model/runtime parameters repeatable. Samsarix takes a
narrower approval-oriented approach: one local plan binds the request fingerprint to canonical
non-secret settings and an optional policy fingerprint, has no remote “latest” resolution or
implicit file discovery, and refuses execution-time provider/budget/policy overrides instead of
merging configuration layers. This is an
inference from the adjacent workflows, not a claim that they offer or lack an identical approval
primitive.

Samsarix is not a substitute for those quality-evaluation systems. Its smaller differentiator is a
portable, dependency-free approval chain: a deterministic request, a credential-free plan, a
plan-bound result, an optional plan-bound deterministic policy, and an offline
verifier that emits only operational metadata and a response hash/size. Policy version 2 adds a
narrower alternative to full JSON Schema evaluation: bounded valid JSON-object parsing and
top-level required/allowed/type rules, with no runtime dependency or second model call. `execute`
can require the plan-bound policy before provider setup and apply it after its one provider response
and before stdout, making the deterministic gate operational rather than dependent on a later shell
step. It also compares two
bounded same-request results without datasets, scorers, hosted traces, or another model call. The
single policy-bound chain is an inference from adjacent CI quality-gate demand—such as Promptfoo's
threshold assertions and CI failure controls—not a claim that local hashes provide authenticated
telemetry or semantic evaluation.

These products validate demand for automation and broad context. They also leave a useful boundary
for teams that want a smaller approval object without granting repository discovery, shell access,
or edit authority.

Static-analysis interchange provides a concrete downstream destination for the structured review
slice:

- [GitHub's third-party SARIF upload guidance](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file)
  documents an explicit `upload-sarif` CI step and separate categories for multiple analyses.
- [GitHub's supported SARIF subset](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support-for-code-scanning)
  uses SARIF 2.1.0 rules, `error`/`warning`/`note` result levels, relative source locations, and
  optional partial fingerprints; GitHub can calculate the latter when its upload action has the
  checked-out source.
- The [OASIS SARIF 2.1.0 standard](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
  defines the portable result/rule/location format rather than a GitHub-only response envelope.

These sources support a CI export format, not a claim that an LLM is a static analyzer. Samsarix
marks every rule as AI-generated with low precision, requires a developer to verify it, omits an
invented security score, and leaves upload as an explicit owner action. The converter also rejects
duplicate fields, unsafe or unselected paths, over-limit content, invalid line ranges, and
request/result approval drift before emitting SARIF. This is an inference that a portable,
review-first handoff is useful alongside existing code-scanning UI, not evidence of finding quality
or user adoption.

## Initial real-world use cases

### Pre-commit review

Pipe `git diff --staged` into a bounded request artifact. A developer or CI job can inspect its file
label, bytes, estimate, and fingerprint before choosing a provider.

### CI approval handoff

Build an artifact and execution plan in an unprivileged job, record the plan fingerprint as the
complete non-secret approval object, and execute later in a credential-bearing job with
`--plan --expect-plan-fingerprint`. The artifact contains the model messages and the plan contains
the provider/budget intent plus an optional result-policy fingerprint, so the execution job does
not need source-tree access or configuration precedence.

### Incident and log triage

Pipe a selected log excerpt into a debug request with a hard estimated-input budget. No repository
scan, history, telemetry, or persistent session is required.

### Reproducible provider comparison

Execute the same artifact against two operator-chosen OpenAI-compatible endpoints, then run
`compare-results` on their JSON envelopes. The common fingerprint links both envelopes to the same
reviewed message payload; the comparison omits response bodies and does not claim provider
authenticity, quality, tokenizer equivalence, or authorship.

### Reviewed execution intent

An unprivileged build/review job can create a request artifact, then create an execution plan that
names the exact endpoint, model, timeout, output ceiling, and estimated-input ceiling. A reviewer
can include an exact result-policy fingerprint, validate the files offline, and approve one plan
fingerprint. The credential-bearing job receives only the explicit files, that approved digest, and
an environment-only API key; provider, budget, and policy settings cannot silently redirect,
resize, or weaken the approved run.

This is useful when approval should cover both disclosed prompt content and non-secret execution
intent. It is not endpoint or provider authentication: access control, TLS governance, signing, and
billing reconciliation remain external.

### Content-omitting run evidence

Validate a stored execution result with `inspect-result` and retain a schema-valid metadata record
before a comparison partner exists. CI can record the request link, model label, response size/hash,
and reported usage without copying the response into ordinary job logs. This is validation and
provenance-adjacent bookkeeping, not response evaluation or provider authentication.

Validate the stored request and result together with `verify-result` to confirm that the result's
claimed request fingerprint matches a concrete, internally consistent artifact. The emitted record
keeps only bounded request metrics and result metadata. Unlike hosted observability systems, this
path is local and dependency-free; unlike signatures or attestations, it does not establish
authorship or protect files from an actor who can rewrite both.

For plan-backed runs, retain all three artifacts and optionally an explicit result policy, then run
`verify-execution`. The result records the reviewed plan fingerprint, requested model, and
provider-reported response model separately. Evidence schema version 3 verifies every local
linkage plus the plan's input and reported-output budgets; when a policy is supplied, it also
requires the fingerprint bound by the plan, enforces every rule, and records the exact rules.
Neither prompt nor response is reproduced. The record remains forgeable by an actor who can rewrite
the whole chain and does not prove which provider infrastructure served the request.

### Fail-closed CI result policy

Pass the exact approved policy to `execute` when downstream output must fail closed immediately;
the file and optional approval fingerprint are checked before network access, and the normalized
response is checked before normal stdout. A failed response gets a nonzero artifact exit, empty
stdout, and no retry, although its single completed provider request may still be billable. Retain
successful JSON output and use `inspect-result`, `verify-result`, or `verify-execution` for offline
archiving and evidence. One-run flags remain available only on the offline single-result commands.
Missing usage fails when its ceiling matters. This is a deterministic contract/cost guard, not a
semantic evaluator: it does not establish response quality, pricing, provider authenticity, or
cross-provider tokenizer equivalence.

### Machine-consumable CI handoff

Require result-policy version 2 when a later CI step expects a JSON object such as a diagnosis,
evidence list, and next action. The gate rejects malformed or duplicate-keyed JSON, a non-object
top level, missing or unapproved keys, and wrong top-level value types before `execute` emits the
response to that consumer. For the structured response, evidence retains only the format and key count; it does
not copy response-derived names or values. The full evidence record also includes the approved
policy and content-omitting chain metadata. This is structural readiness, not recursive JSON
Schema validation or proof that the diagnosis is correct.

### Repeatable project review

Commit a small versioned context manifest for a component's implementation, public contract, and
tests. Developers and CI can invoke the same allowlist, add an explicit task-specific file, inspect
the effective content hashes and budget, and compare rebuilt artifacts without relying on local
shell history or repository discovery.

### Source-located CI review export

Build a `review-report` request from explicit component files, bind the checked-in top-level result
policy into an execution plan, execute once, and retain the result. `export-review` validates the
full nested response, exact request/result linkage, optional request/plan approvals, bounded
category/severity/text/line fields, and exact membership of every finding path in the selected
context. It emits either a versioned provenance-linked report or SARIF 2.1.0 with one source
location per finding.

This turns review output into a standard CI artifact without uploading it, reading new repository
paths, or making another provider request. It is deliberately not content-omitting: findings and
paths appear in both formats, so a CI owner must review retention and the explicit upload boundary.
Structural success does not establish correctness, severity, exploitability, provider authorship,
or source-line freshness.

### Zero-account evaluation

Run the checked-in request, plan, synthetic result, result policy, and evidence fixture through
`verify-execution` from a clean clone. The same command is exercised through an installed wheel on
every supported CI platform. This gives evaluators one complete policy-bound artifact-linkage
journey without a provider account, local model download, network request, or ambiguous
fake-provider claim; live quality and compatibility remain separate operator evidence.

After installation, `self-check` provides the smaller preflight: it loads each bundled contract,
checks its declared draft/object shape, and reproduces that deterministic evidence path without
reading project files. Its versioned report contains package/runtime metadata and content-omitting
fingerprints, explicitly records that no network or provider call occurred, and is validated in
every installed-wheel CI job.

## Defensible product constraints

- No automatic repository crawl in the core path.
- No implicit manifest lookup, glob expansion, ignore-file interpretation, or conditional include.
- No implicit result-policy lookup, remote configuration, or file/flag override precedence.
- No implicit execution-plan lookup, remote resolution, stdin loading, or provider/budget override
  precedence.
- No file writes, patch application, shell execution, or tool loop.
- No implicit network request from `build`, `inspect`, `inspect-result`, `verify-result`,
  `verify-execution`, or `export-review`.
- No automatic retry or provider fallback.
- No credential in CLI arguments, artifacts, summaries, or result JSON.
- No claim that an unkeyed fingerprint authenticates the artifact.
- No claim that result hashes, length, or provider-reported usage evaluate response quality.
- No claim that bounded top-level JSON shape validation proves semantic correctness, safety, or
  conformance to a recursive application schema.
- No claim that a schema-valid review report or SARIF file makes model output a trusted static
  analysis result; every finding remains AI-generated, low-precision, and developer-reviewed.
- No claim that a consistent request/plan/result/policy chain is a signed approval, provider receipt,
  or attestation.
- No claim that a token ceiling proves a monetary budget unless the operator separately maps the
  selected model's authenticated usage to current pricing.

## Next evidence gates

1. Distribute one workflow-built, attested evaluator kit and complete the
   [three-developer pilot](PILOT.md) using pre-commit review and one non-code incident-triage
   workflow. The kit reduces setup variance; it is not adoption evidence by itself.
2. Record operator-run conformance reports and deeper contract tests against any local/provider
   endpoints Samsarix chooses to support explicitly.
3. Configure the implemented trusted-publishing/attestation pipeline, reserve the package, and
   execute the documented release and rollback verification.
4. Only after pilot evidence: consider opt-in streaming, ignore-aware discovery, or editor hooks.
