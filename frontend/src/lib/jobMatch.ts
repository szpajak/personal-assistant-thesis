import { JobMatch } from "@/types/jobs";

/**
 * The score to actually show the user for a job match.
 *
 * `score` reflects whatever was last persisted for this match (an LLM score,
 * or a stale/fallback overlap score). `quick_score` is always a live overlap
 * recompute. For non-LLM matches we prefer the live `quick_score` so the
 * displayed percentage doesn't go stale relative to `score` - every view
 * showing a match percentage must use this so cards/detail sheets/filters
 * agree on the same number for the same match.
 */
export function getDisplayScore(
  match: Pick<JobMatch, "score" | "quick_score" | "source">,
): number {
  return match.source === "llm"
    ? match.score
    : (match.quick_score ?? match.score);
}
