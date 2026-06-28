# Scoring Rules Example

This file defines an example scoring rubric for early Web3 opportunities.

## Core Dimensions

### Novelty

Questions:

- Has the project appeared in the last `novelty_window_days`?
- Is this a genuinely new entity or just a repeat mention?
- Is the new signal materially different from prior memory?

Example guidance:

- 90-100: new project or major new milestone not seen before
- 60-89: known project with meaningful new development
- 30-59: repeated mention with incremental change
- 0-29: already known and not meaningfully updated

### Traction

Questions:

- Is there evidence of shipping, commits, users, TVL, testnet participation, or ecosystem integration?
- Is the signal first-party, observable, or cross-confirmed?
- Does activity look sustained rather than performative?

Example guidance:

- 85-100: multiple strong signals of execution and usage
- 60-84: clear build or launch evidence with early momentum
- 35-59: promising but sparse execution evidence
- 0-34: mostly narrative with weak proof

### Asymmetry

Questions:

- Is the project still underfollowed relative to possible upside?
- Would this be useful to know before broader market attention?
- Is the opportunity differentiated for the configured user profile?

Example guidance:

- 85-100: strong upside and still clearly under-the-radar
- 60-84: useful early signal with moderate awareness
- 35-59: already somewhat crowded or obvious
- 0-34: broadly known or low upside

## Example Composite Score

```text
opportunity_score =
  novelty * 0.35 +
  traction * 0.40 +
  asymmetry * 0.25
```

Weights can vary by user preference:

- conservative users may overweight traction
- experimental users may overweight novelty and asymmetry

## Suggested Qualitative Labels

- 85+: high-priority follow
- 70-84: strong candidate
- 55-69: monitor
- below 55: low priority for now

## Rejection Heuristics

Reject or downrank when:

- only signal is fundraising with no build evidence
- source trace is weak or unverifiable
- project identity is ambiguous after merging
- novelty is artificially inflated by duplicate mentions
- the idea is interesting but not aligned with configured chains or sectors
