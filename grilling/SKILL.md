---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round, then wait for the user's answers before the next round.

## Asking a round

Put the round to the user with the **AskUserQuestion** tool so each question renders as selectable multiple choice, instead of prose they have to answer by hand.

- **Four questions per call, and never drop the rest.** The tool takes at most 4. If the frontier is wider, keep calling it until the frontier is exhausted — the round is not over at question four.
- **Two to four options, each a position someone could actually defend.** Not a real option and a strawman; if a decision has only one live answer, it isn't a frontier question, it's a fact you should go confirm yourself.
- **Lead with your recommendation.** Make it the first option and suffix the label with `(Recommended)`. That replaces the old `➡️` line — you still take a position on every question, it just moves into the option list.
- **Spend the `description` on the trade-off**, not a restatement of the label: what does picking this commit them to, and what does it cost.
- **`header` is a noun for the decision**, 12 characters max — `Auth model`, `Storage`, `Rollout`.
- **Never write your own "Other" option.** The tool appends one, and it takes free text. That is the escape hatch for an answer you failed to anticipate.
- **`multiSelect: true`** when the options combine rather than compete.
- **`preview`** when the choice is between concrete artifacts the user should read side by side — a schema, a call signature, a layout. Single-select only.

Anything that doesn't fit in an option list goes in the message text alongside the call: the reasoning behind the round, what a previous answer just ruled out, what a sub-agent found. The options are for choosing, not for explaining.

## Questions with no options

Some frontier questions have no discrete answers — a name, a threshold, a budget, the shape of an intent. Do not manufacture four fake options to force them through the tool. Ask those in the message text:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs>

➡️ <your recommended answer>
```

Put them in the same message as the tool call. The user picks their options, then answers these in their reply — still one round.

## Working the tree

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
