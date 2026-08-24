# CLI Research and Knowledge Agents

**Status:** adopted
**Date:** 2026-08-23

## 1. Purpose

Remove the manual copying of project context between ChatGPT, Claude Code, and Codex.
Claude Code remains the orchestrator. Two local Codex CLI agents provide project knowledge
and research support while `research/` remains the shared source of truth.

The first version uses `codex exec`. It does not introduce an MCP server, SDK orchestrator,
database, vector store, or persistent agent service. Those become relevant only if CLI
startup latency or thread continuity becomes a demonstrated problem.

## 2. Ownership and permissions

| Actor | Reads | Writes | Git |
|---|---|---|---|
| Claude Code | repository, including `research/` | repository except `research/`; within `research/`, only `decisions.yaml` and `INDEX.md` | reviews and commits the complete task |
| Knowledge Agent | repository, including `research/` | nothing | prohibited |
| Research Agent | entire repository and approved external sources | `research/addenda/`, `research/references.bib`, and the temporary handoff ledger | prohibited |

The Knowledge Agent runs in a read-only Codex sandbox. The Research Agent runs with
`research/` as its writable workspace. A Claude `PreToolUse` hook rejects Write/Edit in
`research/` except `research/decisions.yaml` and `research/INDEX.md`. Those two files are
project governance: Claude updates the registry for approved decisions and indexes reviewed
research outputs. Both agents otherwise treat them as read-only.

The hook matches only `Write`, `Edit`, `MultiEdit`, and `NotebookEdit`. A `Bash` command that edits
`research/` is not intercepted; that prohibition is a repository rule in `CLAUDE.md`, not a
mechanically enforced one. A reader should not conclude from this section that the boundary
is sealed against every tool.

All existing top-level research corpus Markdown files other than the governance index and
temporary handoff ledger are immutable to both Claude and the Research Agent, whether or
not they currently source an adopted decision. This makes protection deliberate rather
than something that changes when a new ID is registered. New evidence or a correction goes
into `research/addenda/YYYY-MM-DD-<topic>.md`; after review, Claude adds the addendum to
`research/INDEX.md` and registers any approved decision change. This file-level rule
protects corpus history without implementing PD-D06 section hashing.

The Research Agent may leave an allowed research diff but may not approve or commit it.
Claude reviews that diff and commits it with the implementation task that required it.

If the Research Agent finds unrelated existing changes in `research/`, it stops rather
than overwriting them.

## 3. Components

The minimum implementation contains:

1. A Knowledge Agent command that invokes `codex exec --sandbox read-only`.
2. A Research Agent command that invokes
   `codex exec -C research --sandbox workspace-write -c tools.web_search=true`, with shell
   network access explicitly disabled. `--search` is a top-level `codex` flag and `exec`
   rejects it; the tool is enabled as configuration instead. A smoke run confirmed the
   model actually issues a `web_search` item under that key.
3. A JSON Schema for Knowledge Agent output.
4. Agent instructions defining ownership, source policy, language, and response behavior.
5. Claude rules and a `PreToolUse` hook describing when to call each agent and allowing
   Claude writes only to the two research governance files.
6. `research/references.bib` as the shared bibliography when the first verified citation is
   added. An empty bibliography is not created in advance.
7. A preflight and post-run guard. Preflight requires a clean `research/` diff, which
   makes `HEAD` the baseline every later restore uses — there is no separate snapshot, and
   the clean-tree requirement is what makes that safe. Preflight also records which paths
   outside `research/` already differ, so the post-run check can tell a pre-existing change
   from one the agent made, by content rather than by path — a file already dirty when the
   run began must not be exempt for the rest of it. Post-run refuses outright if any
   git-visible path outside `research/` differs from what preflight recorded, since that
   would mean the sandbox did not confine the agent, and otherwise permits only addenda,
   bibliography, and handoff-ledger changes.

   **What that check does not reach.** It sees only what git shows. Ignored paths —
   `.venv/`, the caches, run outputs — appear in neither `git diff HEAD` nor
   `ls-files --others --exclude-standard`, so a write there goes unreported. Widening the
   check to cover them would flag every `make check`, which writes `.mypy_cache/`, and a
   check that cries wolf gets switched off. **The sandbox is the containment; this is a
   backstop over git-visible content.** It writes any rejected
   change to a temporary patch first, then restores forbidden tracked paths from `HEAD`
   and quarantines forbidden new ones, and reports the patch path to Claude. Allowed
   changes remain in the working tree for review, so a rejection cannot deadlock the next
   run with forbidden residue.

The Knowledge command deliberately does not enable web search; it answers only from
repository knowledge. The same smoke run confirmed the asymmetry holds in practice: the
research transcript contains a `web_search` item and the knowledge transcript contains
none.

Both commands pass `stdin=subprocess.DEVNULL`. Codex otherwise inherits the caller's stdin
and blocks reading it, which hangs every invocation made from a tool that keeps stdin open. It uses `--output-schema`, `--json`, and `-o`/`--output-last-message` so the CLI,
not Claude's prose parser, enforces and captures the structured response.

The Knowledge Agent uses `gpt-5.6-luna` with medium reasoning for inexpensive frequent
lookups. The Research Agent uses `gpt-5.6-terra` with high reasoning for evidence synthesis.
`gpt-5.6-sol` is a manual, user-visible escalation when Terra reports unresolved complex or
conflicting evidence; it is never an automatic retry. Model, reasoning effort, and usage are
included in command output so cost can be reviewed against representative tasks.

## 4. Invocation flow

Claude invokes the Knowledge Agent for questions about project facts, rationale, research,
or adopted decisions. It does not invoke it for mechanical work such as formatting, tests,
Git operations, typo fixes, or implementation against an already-approved unambiguous spec.

Claude invokes the Research Agent in either case:

- **Explicit:** the user asks to research a topic.
- **Automatic:** existing knowledge is missing, contradictory, uncited, or plausibly stale.

Before an automatic research call, Claude tells the user why research is needed. A research
question gets one Research Agent run. If authoritative evidence remains unavailable, the
agent returns an open question and stops; it does not loop or broaden scope silently.

The normal flow is:

```text
User question
  -> Claude calls Knowledge Agent
  -> Knowledge Agent returns structured answer
  -> if needs_research:
       Claude explains why
       -> Research Agent updates research/ without committing
       -> Claude reviews the diff
       -> Knowledge Agent reads the updated corpus
  -> Claude answers the user in Thai
```

## 5. Knowledge Agent behavior

The Knowledge Agent supports two modes.

### 5.1 Knowledge lookup

It answers from repository evidence and returns:

- a readable answer;
- sources with repository paths and decision IDs where applicable;
- confidence (`high`, `medium`, or `low`);
- whether new research is required; and
- a self-contained research question when new research is required.

It does not treat missing information as permission to guess.

### 5.2 Decision support

Before Claude asks the user to choose a project, scope, or architecture option, the
Knowledge Agent may evaluate the options against the repository. It:

- recommends an option when repository evidence and professional judgment support one;
- identifies supporting and conflicting decisions;
- separates evidence, inference, and opinion;
- states trade-offs and rejected alternatives;
- may recommend a justified hybrid or refinement not present in the original choices;
- identifies hidden assumptions, prerequisites, safeguards, and limitations; and
- never creates or changes a project decision on its own.

When the repository does not settle a genuine preference or value trade-off, the agent
sets `defer_to_user` instead of manufacturing a recommendation. It still explains the
trade-off and identifies any constraints the repository does establish. In this case,
`recommended_option` and `recommended_refinement` are null.

A constructive recommendation may say, for example, "choose option 2 as the normal path,
but use option 3 only as an explicit cold-start prior." The agent must explain why that
refinement is better and label professional judgment as opinion rather than adopted policy.
The user remains the final decision-maker.

The machine-readable response links sources to individual claims. Claude renders it as a
concise Thai recommendation, leads with the choice, and includes a short source list at the
end rather than cluttering every sentence with citations.

## 6. Knowledge output contract

The schema supports both modes with these logical fields:

```json
{
  "mode": "lookup | decision_support",
  "answer": "string",
  "recommended_option": "string | null",
  "recommended_refinement": "string | null",
  "opinion": "string | null",
  "defer_to_user": false,
  "touched_decision_ids": ["ST-D03"],
  "claims": [
    {
      "text": "string",
      "type": "evidence | inference | hypothesis | decision | open_question | opinion",
      "sources": [
        {
          "file": "string",
          "decision_id": "string | null"
        }
      ]
    }
  ],
  "tradeoffs": ["string"],
  "alternatives_rejected": [
    {
      "option": "string",
      "reason": "string"
    }
  ],
  "conflicts": ["string"],
  "confidence": "high | medium | low",
  "needs_research": false,
  "research_question": null
}
```

The implementation JSON Schema makes required fields and nullability explicit. Invalid
structured output is a failed agent call; Claude must not silently reconstruct or invent a
result.

## 7. Research quality policy

The Research Agent may use only:

- peer-reviewed journal and conference papers;
- official standards and specifications;
- official project or product documentation;
- preprints explicitly labelled as preprints; and
- official issue trackers solely for verifiable software behavior or defects, not for
  academic claims.

Blogs, forums, Reddit, secondary summaries, and AI answers are not research evidence.

Every research statement is classified as `evidence`, `inference`, `hypothesis`,
`decision`, or `open_question`. A decision is binding only when represented by an ID in
`research/decisions.yaml`. If suitable evidence is unavailable, the agent records an open
question instead of converting an assumption into a fact.

The existing research corpus is immutable. Known defects recorded in `research/INDEX.md`
remain untouched until their scheduled cleanup. The Research Agent proposes an unscheduled
correction in a dated addendum rather than silently rewriting corpus history. Every reviewed
addendum is indexed by Claude; an unindexed addendum is not part of the authoritative corpus.
The temporary `research/CHATGPT_KNOWLEDGE_HANDOFF.md` remains Research Agent-owned until its
pending items are migrated; it is deleted when the ledger is empty.

Academic metadata is verified with the native web-search tool against publisher pages,
official proceedings, or DOI landing pages. Shell network access remains disabled; the
agent does not call Crossref or other APIs. DOI is the primary duplicate key. The agent
never invents titles, authors, venues, DOI values, or experimental results. Sources without
a DOI require an official URL and access date. Existing citation keys are stable and may
not be renamed or deleted while referenced.

Research documents and bibliography entries are English. User-facing answers and summaries
are Thai; paper titles, technical terms, and citations retain their source language.

## 8. Failure handling

- Missing authoritative evidence produces `open_question`.
- Conflicting evidence is reported on both sides and lowers confidence.
- Unverified bibliographic metadata is not added to `references.bib`.
- A write outside `research/` is expected to be refused by the sandbox. The guard does not
  rely on that alone: it records the content of every git-visible path outside `research/`
  that already differs from `HEAD`, and refuses afterwards if any of them changed or a new
  one appeared. Within git's view that turns a sandbox failure into a loud blocker rather
  than a silent commit. Outside it — ignored paths — the sandbox is the only thing standing
  there, and the guard will not notice.
- An unrelated pre-existing research diff stops the Research Agent before it starts, with
  its own exit code — the tree is untouched, which is a different situation from a run that
  began and could not finish.
- An attempted edit outside the Research Agent allowlist is written to a temporary rejected
  patch first. A forbidden tracked path is then restored from `HEAD`, which resets the index
  as well as the working tree; a forbidden new path is moved into quarantine and dropped
  from the index. The agent reports the patch path and proposes the correction as a new
  addendum.
- A schema-invalid Knowledge Agent response fails closed.
- A research run that cannot resolve its question stops after one pass and returns the
  remaining uncertainty.

## 9. Verification

The implementation leaves the smallest runnable checks proving the boundaries:

1. Knowledge Agent cannot write a file.
2. Research Agent can write under `research/`. Its confinement outside `research/` is the
   sandbox's job and is not verified here — no test in this repository proves codex resolves
   its writable root to `--cd research`. What is verified is detection: the guard reports a
   git-visible change outside `research/`, including an overwrite of a file that was already
   dirty and a revert of one, and stays silent about a pre-existing change it did not cause.
3. Knowledge Agent output validates against the JSON Schema.
4. Once `research/references.bib` exists, bibliography records are unique and every new
   Markdown citation key resolves. No custom citation-key naming convention is imposed.
5. The repository documentation and decision checker passes after a research diff.
6. The diff guard detects, exports, and restores a forbidden corpus or governance change
   without removing an allowed addendum change.
7. The Claude `PreToolUse` hook rejects a Write/Edit outside the two research governance
   files and permits registry and index updates.

Tests use temporary files or a harmless fixture and do not call paid model inference unless
an explicit integration test is requested. A manual smoke run verifies the real CLI wiring
after the deterministic checks pass. It specifically verifies that `-C research` can read
the parent repository and discovers root instructions. `writable_roots` is not used as a
restriction because additional writable roots do not remove write access from the primary
workspace.

## 10. Deferred work

- MCP integration, until CLI invocation or continuity is measurably inadequate.
- Codex SDK orchestration, until a long-lived workflow requires programmatic threads,
  retries, or richer lifecycle control.
- Vector search, until the research corpus is too large for direct repository retrieval.
- Automatic commits or unattended research merges; human/Claude review remains required.
