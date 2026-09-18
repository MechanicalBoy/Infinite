---
name: release-notes-draft
description: Draft user-facing release notes for Infinite from raw git history — walks every commit since the last tag (not just merge commits), reads each one's full body and diff (not just its subject, which is frequently generic or misleading), filters out internal-only work, and groups what's left into a concise, deduplicated, house-style draft. Use when asked "what's new since v0.X", "show me the commit history since last release", "prepare release notes", "draft the changelog", "what changed since the last tag", or before cutting any new version tag. Complements release-notes-audit, which checks notes already published — this skill is for writing them in the first place.
---

Paths below are relative to the repo root (`/Users/namansoni/infinte`), not
this skill directory.

## Why this exists

A commit's subject line is not a reliable table of contents. Real example
from this repo: `1d05bf1 feat(panels): viewport panel persistence, patch/gesture
updates, semi-brain refresh` sounds like housekeeping. It actually shipped a
brand-new 7-mode Arrangement tool selector (Select/Trim/Range/Blade/Zoom/Hand/
Pencil), new toolbar icons, and keyboard shortcuts for all of them — 990 lines
in `main.cpp`, invisible from the subject alone. A release-notes pass that
only reads `git log --oneline` will silently drop features like this. This
skill exists to make reading the actual diff the default, not a fallback.

## Procedure

### 1. Establish the range

```bash
git tag --list
git log --oneline <last_tag>..HEAD
git log --oneline <last_tag>..HEAD | wc -l
```

If the user says "since v0.4" but means the tag, resolve it exactly
(`git tag -l | grep -i v0.4` — tags don't always match the spoken version
loosely). If no tag exists yet for the current cycle, use the last
published release's tag from `gh release list`.

### 2. Pull full commit bodies, not just subjects

```bash
git log <last_tag>..HEAD --format="=== %h %s ===%n%b" -- | grep -v "^Co-Authored-By"
```

Read every body. Bodies in this repo often explain the *why* and name
specific bugs fixed, kernels touched, or files affected — that's usually
better release-notes material than the subject line, and sometimes the
subject only covers a fraction of what the body describes.

### 3. Never trust a generic or vague subject — check its diff

Any commit whose subject is `chore(...)`, mentions "refresh"/"update"/
"cleanup" alone, or is a merge commit with no body, gets its diffstat and
(if diffstat looks non-trivial) its full diff read before being excluded
or summarized:

```bash
git show --stat <hash>
git show <hash> -- <file>          # for any file whose change size looks
                                     # disproportionate to the subject
```

Rule of thumb: if a commit changes more than ~100 lines in a source file
(not a generated corpus/dataset/asset file) and the subject doesn't name
what changed there, read the diff. This is the check that would have
caught `1d05bf1`.

### 4. Filter internal-only commits out

Exclude, but keep a short list of what was excluded and why (useful for
the user to sanity-check the filter, not for the release notes themselves):

- Pure tooling/skill/audit-script additions with no product-facing effect
  (e.g. `param-truth-audit` script itself — the *bugs it found and fixed*
  are user-facing, the audit tool is not).
- `chore(semi-brain)` corpus/dataset/training-data refreshes.
- Pure test-only additions with no behavior change.
- Website copy that's marketing/CTA polish rather than a product change —
  judgment call; ask if unsure whether the user wants a "Website" section.

Do not exclude a commit just because its subject sounds internal
(`feat(panels): ... semi-brain refresh"` — see above). Filter on what the
diff actually contains, not the label.

### 5. Group by user impact, not by directory or commit order

This project's standing section taxonomy (use the ones that apply this
cycle, drop empty ones, keep the order below — `Bug Fixes` always last):

- **Nodes** — new node types, and non-trivial changes to an existing
  node's own behavior/params/layout. If a single node got a new type plus
  several follow-up refinement commits in the same cycle (e.g. a whole
  new instrument), it can get its own named subsection under here (e.g.
  "Analog Synth") instead of being flattened into a bullet list — but it
  still lives under the Nodes header, not as a top-level section.
- **Modulation & Modulation Matrix** — mod matrix UI/behavior, curve
  shaping, expressions, gesture recording/playback, ParamRef/mailbox
  wiring changes a user can perceive.
- **Performance Matrix** — the live-performance macro/element panel
  specifically (distinct from the mod matrix above).
- **Timeline Arrangement** — the Arrange panel: clips, tracks, tools,
  shortcuts, drag/drop, waveform/thumbnail rendering, export/render
  queue.
- **Audio** — DSP/kernel changes (effects, synths' sound engine, filters)
  that change what things sound like, as distinct from a node's UI/layout
  (that goes under Nodes) and distinct from bugs in that DSP (goes under
  Bug Fixes).
- **Rendering & Performance** — viewport/GL rendering changes, frame-rate
  or perf-sensitive changes, render passes, export/output quality.
- **UI/UX** — cross-cutting interface changes not specific to one panel
  above (panel persistence, dialogs, icons, general layout/theming,
  website).
- **Misc/Others** — tooling/infra that indirectly benefits users (e.g. an
  audit skill that will keep future kernels honest) and anything real
  that doesn't fit a category above. Don't force a fit elsewhere just to
  avoid using this section.
- **Bug Fixes** — always last, always its own section. A fix never lives
  in a feature section even if the feature it fixes is brand-new this
  cycle (see rule 6, dedup).

### 6. Deduplicate — each change gets exactly one home

A commit that's both "new feature" and "fixes a bug in that same feature
introduced this cycle" only needs the fix mentioned once, under Fixes,
with enough context to not need the feature bullet repeated. Don't
cross-list the same bullet under two section headers — pick the section
where a user would look first (Fixes for anything framed as "fixed X",
even if X is a brand-new node).

### 7. Write in house style

Match the voice of already-published notes (`gh release view <tag> --json
body -q .body` on the most recent real release — read it fresh each time,
don't assume the style from memory):

- Bold the feature name, then one concise sentence — no marketing fluff,
  no emoji, no restating the commit subject verbatim.
- Concrete and specific ("16 delay lines, wider hall-scale delay times")
  beats vague ("improved reverb").
- Skip internal implementation detail a user can't perceive (exact param
  names, internal clamp ranges) unless the *bug* was that a user-visible
  control didn't do what it claimed.
- Keep it short. A 35-commit cycle should produce a notes body a user can
  read in under a minute — cut, don't pad.

### 8. Flag release-readiness, don't assume it

Before presenting the draft as ready to publish, check whether this
codebase's release pipeline has actually run over these commits (CI,
platform builds — see this project's release/shipping skills and any
memory about pending pipeline work). State plainly if the draft is
content-only and the commits haven't been through the release process yet.

## Output

Present the categorized draft in chat first. Do not create a
`docs/releases/` file or run `gh release create`/`gh release edit` without
the user explicitly asking — this mirrors release-notes-audit's "ask
first" rule for touching a public release. If asked to also audit an
already-published set of notes against the tagged code, hand off to
`release-notes-audit` — that skill verifies claims against the tree at a
tag; this one only drafts from commits that haven't been tagged yet.
