"use client";

import React, { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { JobMatch } from "@/types/jobs";
import { getDisplayScore } from "@/lib/jobMatch";
import { useGenerateCV } from "@/hooks/useCV";
import {
  Loader2,
  Download,
  FileText,
  ExternalLink,
  Sparkles,
  Bookmark,
} from "lucide-react";

import { API_BASE_URL } from "@/lib/constants";
import { MarkdownContent } from "@/components/ui/markdown-content";

interface JobDetailSheetProps {
  jobMatch: JobMatch | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave?: (jobId: string) => void;
  onApply?: (jobId: string) => void;
  onCalculateMatch?: (jobId: string) => void;
  isSaving?: boolean;
  isApplying?: boolean;
  isMatching?: boolean;
}

export const JobDetailSheet: React.FC<JobDetailSheetProps> = ({
  jobMatch,
  open,
  onOpenChange,
  onSave,
  onApply,
  onCalculateMatch,
  isSaving = false,
  isApplying = false,
  isMatching = false,
}) => {
  const [generatedCV, setGeneratedCV] = useState<string | null>(null);
  const [cvCached, setCvCached] = useState(false);
  const generateCVMutation = useGenerateCV();

  if (!jobMatch) return null;
  const job = jobMatch.job_offer;
  const isCareer = job.tier === "career";
  const displayScorePercent = Math.round(getDisplayScore(jobMatch) * 100);
  const hasLlm = jobMatch.source === "llm";

  const handleGenerateCV = async (force = false) => {
    try {
      const result = await generateCVMutation.mutateAsync({
        jobId: job.id,
        force,
      });
      setGeneratedCV(result.cv_content);
      setCvCached(Boolean(result.cached));
    } catch (error) {
      console.error("Failed to generate CV:", error);
    }
  };

  const handleDownloadPDF = () => {
    const token = localStorage.getItem("auth_token");
    const url = `${API_BASE_URL}/api/v1/cv/download?job_id=${job.id}&token=${token}`;
    window.open(url, "_blank");
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-xl overflow-y-auto">
        <SheetHeader>
          <div className="flex justify-between items-start pr-8">
            <SheetTitle className="text-2xl font-bold">{job.title}</SheetTitle>
          </div>
          <div className="flex items-center justify-between mt-2 gap-2 flex-wrap">
            <SheetDescription className="text-lg font-medium text-primary flex items-center gap-2">
              {job.company}
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex text-muted-foreground hover:text-primary"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            </SheetDescription>
            <div className="flex gap-2 flex-wrap">
              <Badge
                variant="secondary"
                className={
                  isCareer
                    ? "bg-indigo-50 text-indigo-700 border-indigo-100"
                    : "bg-slate-100 text-slate-600"
                }
              >
                {isCareer ? "In career graph" : "Staging only"}
              </Badge>
              <Badge className="bg-green-100 text-green-800 border-green-200">
                {hasLlm
                  ? `${displayScorePercent}% AI Match`
                  : `${displayScorePercent}% overlap`}
              </Badge>
              {jobMatch.is_stale && (
                <Badge className="bg-amber-50 text-amber-800 border-amber-200">
                  Outdated
                </Badge>
              )}
            </div>
          </div>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {jobMatch.justification && (
            <p className="text-sm text-muted-foreground italic">
              {jobMatch.justification}
            </p>
          )}

          <div>
            <h3 className="text-sm font-semibold mb-2 uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              Required Skills
            </h3>
            <div className="flex flex-wrap gap-2">
              {job.required_skills.map((skill) => {
                const isMatch = (jobMatch.matching_skills || [])
                  .map((s) => s.toLowerCase())
                  .includes(skill.toLowerCase());
                return (
                  <Badge
                    key={skill}
                    variant="secondary"
                    className={
                      isMatch
                        ? "bg-green-100 text-green-800 border-green-200"
                        : "bg-red-50 text-red-700 border-red-100"
                    }
                  >
                    {skill}
                  </Badge>
                );
              })}
            </div>
            {jobMatch.matching_skills?.length ||
            jobMatch.missing_skills?.length ? (
              <p className="text-xs text-muted-foreground mt-2">
                {jobMatch.matching_skills?.length || 0} of{" "}
                {job.required_skills.length} required skills match your profile
                {jobMatch.missing_skills?.length
                  ? ` · missing: ${jobMatch.missing_skills.join(", ")}`
                  : ""}
              </p>
            ) : null}
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-2 uppercase tracking-wider text-muted-foreground">
              Job Description
            </h3>
            <MarkdownContent content={job.description} />
          </div>

          <div className="pt-6 border-t">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Personalized CV
              </h3>
              {generatedCV && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadPDF}
                  className="gap-2 text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </Button>
              )}
            </div>

            {!generatedCV ? (
              <div className="bg-slate-50 p-8 rounded-lg text-center border border-dashed">
                <p className="text-sm text-muted-foreground mb-4">
                  Generate a tailored CV for this role. If the offer is still
                  staging, it will be promoted into your career graph first.
                </p>
                <Button
                  onClick={() => handleGenerateCV(false)}
                  disabled={generateCVMutation.isPending}
                  className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-700"
                >
                  {generateCVMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    "Generate Personalized CV"
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {cvCached && (
                  <p className="text-xs text-indigo-600">Using cached CV</p>
                )}
                <div className="bg-white border rounded-md p-6 overflow-y-auto max-h-96 shadow-inner">
                  <MarkdownContent content={generatedCV} />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleGenerateCV(true)}
                  disabled={generateCVMutation.isPending}
                >
                  Regenerate
                </Button>
              </div>
            )}
          </div>
        </div>

        <SheetFooter className="mt-8 gap-3 sm:flex-row flex-col">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="w-full"
          >
            Close
          </Button>
          {onCalculateMatch && (
            <Button
              variant="outline"
              className="w-full"
              onClick={() => onCalculateMatch(job.id)}
              disabled={isMatching}
            >
              {isMatching ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 h-4 w-4" />
              )}
              Calculate match
            </Button>
          )}
          {!isCareer && onSave && (
            <Button
              variant="outline"
              className="w-full"
              onClick={() => onSave(job.id)}
              disabled={isSaving}
            >
              {isSaving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Bookmark className="mr-2 h-4 w-4" />
              )}
              Save to career graph
            </Button>
          )}
          <Button
            className="w-full bg-gray-900 text-white"
            onClick={() => onApply?.(job.id)}
            disabled={isApplying || !onApply}
          >
            {isApplying ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Apply Now
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
};
