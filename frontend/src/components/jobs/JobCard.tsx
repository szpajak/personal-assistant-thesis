import React from "react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JobMatch } from "@/types/jobs";
import { getDisplayScore } from "@/lib/jobMatch";
import { Briefcase, Bookmark, Calendar, Loader2, Sparkles } from "lucide-react";

interface JobCardProps {
  match: JobMatch;
  onViewDetails: (jobId: string) => void;
  onSave?: (jobId: string) => void;
  onApply?: (jobId: string) => void;
  onCalculateMatch?: (jobId: string) => void;
  selected?: boolean;
  onToggleSelect?: (jobId: string) => void;
  isSaving?: boolean;
  isApplying?: boolean;
  isMatching?: boolean;
}

export const JobCard: React.FC<JobCardProps> = ({
  match,
  onViewDetails,
  onSave,
  onApply,
  onCalculateMatch,
  selected = false,
  onToggleSelect,
  isSaving = false,
  isApplying = false,
  isMatching = false,
}) => {
  const { job_offer: job, score } = match;
  const scorePercent = Math.round(score * 100);
  const quickPercent = Math.round((match.quick_score ?? score) * 100);
  const displayPercent = Math.round(getDisplayScore(match) * 100);
  const matching = new Set(
    (match.matching_skills || []).map((s) => s.toLowerCase()),
  );
  const isCareer = job.tier === "career";
  const hasLlm = match.source === "llm";

  const getMatchColor = (percent: number) => {
    if (percent >= 80) return "bg-green-100 text-green-800 border-green-200";
    if (percent >= 60) return "bg-amber-100 text-amber-800 border-amber-200";
    return "bg-red-100 text-red-800 border-red-200";
  };

  return (
    <Card className="flex flex-col h-full hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start gap-2">
          <div className="flex flex-wrap gap-1">
            {onToggleSelect && (
              <input
                type="checkbox"
                className="mt-1 mr-1"
                checked={selected}
                onChange={() => onToggleSelect(job.id)}
                aria-label={`Select ${job.title}`}
              />
            )}
            <Badge className={`${getMatchColor(displayPercent)} font-semibold`}>
              {hasLlm ? `${displayPercent}% AI` : `${displayPercent}% overlap`}
            </Badge>
            {hasLlm && quickPercent !== scorePercent && (
              <Badge variant="outline" className="text-[10px]">
                {quickPercent}% quick
              </Badge>
            )}
            {match.is_stale && (
              <Badge className="bg-amber-50 text-amber-800 border-amber-200">
                Outdated
              </Badge>
            )}
            <Badge
              variant="secondary"
              className={
                isCareer
                  ? "bg-indigo-50 text-indigo-700 border-indigo-100"
                  : "bg-slate-100 text-slate-600"
              }
            >
              {isCareer ? "Saved" : "Discovered"}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground flex items-center shrink-0">
            <Calendar className="w-3 h-3 mr-1" />
            {new Date(job.scraped_at).toLocaleDateString()}
          </span>
        </div>
        <CardTitle className="text-lg mt-2 line-clamp-1">{job.title}</CardTitle>
        <div className="text-sm text-muted-foreground flex items-center mt-1">
          <Briefcase className="w-4 h-4 mr-1" />
          {job.company}
        </div>
      </CardHeader>
      <CardContent className="flex-grow pb-2">
        <p className="text-sm text-muted-foreground line-clamp-3 mb-4">
          {job.description}
        </p>
        {match.justification && (
          <p className="text-xs text-muted-foreground mb-3 line-clamp-2 italic">
            {match.justification}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {job.required_skills.slice(0, 5).map((skill) => {
            const isMatch = matching.has(skill.toLowerCase());
            return (
              <Badge
                key={skill}
                variant="secondary"
                className={`text-[10px] px-2 py-0 ${
                  isMatch
                    ? "bg-green-100 text-green-800 border-green-200"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {skill}
              </Badge>
            );
          })}
          {job.required_skills.length > 5 && (
            <span className="text-[10px] text-muted-foreground">
              +{job.required_skills.length - 5} more
            </span>
          )}
        </div>
      </CardContent>
      <CardFooter className="pt-2 gap-2 flex-wrap">
        {onCalculateMatch && (
          <Button
            variant="outline"
            className="flex-1 text-xs h-8 min-w-[4.5rem]"
            onClick={() => onCalculateMatch(job.id)}
            disabled={isMatching}
          >
            {isMatching ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <>
                <Sparkles className="w-3 h-3 mr-1" />
                Match
              </>
            )}
          </Button>
        )}
        <Button
          variant="outline"
          className="flex-1 text-xs h-8 min-w-[4.5rem]"
          onClick={() => onViewDetails(job.id)}
        >
          View
        </Button>
        {!isCareer && onSave && (
          <Button
            variant="outline"
            className="flex-1 text-xs h-8 min-w-[4.5rem]"
            onClick={() => onSave(job.id)}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <>
                <Bookmark className="w-3 h-3 mr-1" />
                Save
              </>
            )}
          </Button>
        )}
        <Button
          className="flex-1 text-xs h-8 min-w-[4.5rem]"
          onClick={() => onApply?.(job.id)}
          disabled={isApplying || !onApply}
        >
          {isApplying ? <Loader2 className="h-3 w-3 animate-spin" /> : "Apply"}
        </Button>
      </CardFooter>
    </Card>
  );
};
