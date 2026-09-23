# Annotation codebook (Dataset A is pre-labelled; use this for Dataset B)

Judge **before** looking at system scores. Freeze the graph snapshot first.

## Retrieval (nodes)

Query is a CV/evidence lookup, not a chat question. For each candidate
`Project` / `Skill` / `Certificate` node:

| Grade | Meaning |
|---|---|
| 2 | Highly relevant: the node is evidence the query is asking for |
| 1 | Partial: related skill or neighbouring project, not the main answer |
| 0 | Not relevant, including another person’s nodes |

Do not reward a `JobOffer` as CV evidence.

## Job fit (this person vs this posting)

| Grade | Meaning |
|---|---|
| 2 | Good fit: core stack overlaps; seniority in band |
| 1 | Partial: some overlap or transferable, but wrong focus |
| 0 | Poor fit: different occupation or stack |

This is **not** hire/no-hire. It is graded relevance for ranking.

## Emails

- `classification`: `career_related` or `other`
- `application_stage`: `applied_ack` | `interview_invite` | `assessment` | `offer` | `rejection` | `none`
- Expected Kanban status if the email should move an existing application:
  Responded / Interview / Offer / Rejected, else `unchanged`

## CV usefulness (1–5)

Score only tailored sections (headline, summary, bullets), not contact
blocks.

1. Irrelevant or invented experience
2. Generic, weak grounding
3. Usable but missing the job’s emphasis
4. Relevant, graph-grounded, minor issues
5. Specific evidence, no invented facts, on-target for the offer

**Faithfulness is separate:** each atomic claim is supported /
unsupported / contradictory vs the graph.

## Skill-gap gold

A skill is `missing` if the person has no `HAS_SKILL` (and no finished
project `USES`). It is `underleveled` if held below the typical
`REQUIRES.level` on the demand set. Skills at or above that level are
not gaps.
