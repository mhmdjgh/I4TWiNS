# AI usage disclosure

The task allows AI coding assistants and asks for disclosure. This is where and how one was used.

**Tool:** Claude Code (Anthropic), working from the brief in [`CLAUDE.md`](CLAUDE.md).

**Used for**
- Implementing modules from the design in `CLAUDE.md`, writing tests and fixing lint/type issues.
- Running the evaluation and the real-model checks, and analysing the results (reasoning-token
  truncation, prompt failures). The fixes that followed are recorded in the commit history and in
  [`docs/prompt-engineering.md`](docs/prompt-engineering.md).
- Drafting the README, the prompt-engineering log, the proposal and the PR descriptions.

**Decisions made or approved by me**
- The architecture: registry-driven skills, the context-protection strategy, parallel vs
  sequential execution, fallback policies, extract-then-execute calculator, and the CLI plus
  dashboard split.
- Choice of provider and model under the free-tier and ≤35B constraints.

**Not AI-assisted at runtime beyond the product itself:** the agent's own LLM calls go to the
models listed in the README (§9); no other AI service is involved.
