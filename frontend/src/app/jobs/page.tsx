"use client";

import {
  useJobs,
  useJobMatches,
  useTriggerJobScrape,
  usePromoteJob,
  useCreateApplication,
  useScrapedJobs,
  useDeleteScrapedJob,
  useMatchSingleJob,
  useMatchJobsBatch,
} from "@/hooks/useJobs";
import { JobCard } from "@/components/jobs/JobCard";
import { JobFilters } from "@/components/jobs/JobFilters";
import { ScrapedJobFilters } from "@/components/jobs/ScrapedJobFilters";
import { JobSearchForm } from "@/components/jobs/JobSearchForm";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Sparkles, Trash2, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { JobOffer, JobMatch, ExperienceBracket, SeniorityFilter } from "@/types/jobs";
import { JobDetailSheet } from "@/components/jobs/JobDetailSheet";
import { getDisplayScore } from "@/lib/jobMatch";
import type { JobScrapeRequest } from "@/lib/api";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

type JobsTab = "match" | "scraped";

export default function JobsPage() {
  const [tab, setTab] = useState<JobsTab>("match");

  const { data: allJobs, isLoading: jobsLoading } = useJobs();
  const { data: matches, isLoading: matchesLoading } = useJobMatches();
  const scrapeMutation = useTriggerJobScrape();
  const promoteMutation = usePromoteJob();
  const applyMutation = useCreateApplication();
  const deleteScraped = useDeleteScrapedJob();
  const matchOne = useMatchSingleJob();
  const matchBatch = useMatchJobsBatch();

  const [minMatch, setMinMatch] = useState(0);
  const [selectedSkill, setSelectedSkill] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [scrapedSearch, setScrapedSearch] = useState("");
  const [seniority, setSeniority] = useState<SeniorityFilter | "">("");
  const [experienceBracket, setExperienceBracket] = useState<ExperienceBracket | "">("");

  const scrapedFilters = useMemo(
    () => ({
      search: scrapedSearch || undefined,
      seniority: seniority || undefined,
      experience_bracket: experienceBracket || undefined,
    }),
    [scrapedSearch, seniority, experienceBracket]
  );

  const { data: scrapedJobs, isLoading: scrapedLoading } = useScrapedJobs(scrapedFilters);

  const isLoading = jobsLoading || matchesLoading;

  const handleSearch = (filters: JobScrapeRequest) => {
    scrapeMutation.mutate(filters);
    setTab("scraped");
  };

  const handleMatchAllCareer = () => {
    matchBatch.mutate(null);
  };

  const handleMatchSelected = () => {
    if (selectedIds.size === 0) return;
    matchBatch.mutate(Array.from(selectedIds));
  };

  const handleCalculateMatch = (jobId: string) => {
    setPendingJobId(jobId);
    matchOne.mutate(jobId, {
      onSettled: () => setPendingJobId(null),
    });
  };

  const toggleSelect = (jobId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const handleViewDetails = (jobId: string) => {
    setSelectedJobId(jobId);
    setIsDetailOpen(true);
  };

  const handleSave = (jobId: string) => {
    setPendingJobId(jobId);
    promoteMutation.mutate(jobId, {
      onSettled: () => setPendingJobId(null),
    });
  };

  const handleApply = (jobId: string) => {
    setPendingJobId(jobId);
    applyMutation.mutate(
      {
        job_offer_id: jobId,
        status: "Applied",
        applied_at: new Date().toISOString(),
      },
      {
        onSettled: () => setPendingJobId(null),
      }
    );
  };

  const handleDeleteScraped = (jobId: string) => {
    setPendingJobId(jobId);
    deleteScraped.mutate(jobId, {
      onSettled: () => setPendingJobId(null),
    });
  };

  const normalizedMatches: JobMatch[] = useMemo(() => {
    const saved =
      (matches || []).filter((m) => m.job_offer.tier === "career");
    if (saved.length > 0) return saved;
    return (allJobs || [])
      .filter((job: JobOffer) => job.tier === "career")
      .map((job: JobOffer) => ({
        job_offer: job,
        score: 0,
        quick_score: 0,
        source: "none" as const,
      }));
  }, [matches, allJobs]);

  const matchById = useMemo(() => {
    const map = new Map<string, JobMatch>();
    for (const match of matches || []) {
      map.set(match.job_offer.id, match);
    }
    return map;
  }, [matches]);

  const filteredMatches = normalizedMatches.filter((m) => {
    const matchesSkill =
      !selectedSkill ||
      m.job_offer.required_skills.some((s) =>
        s.toLowerCase().includes(selectedSkill.toLowerCase())
      );
    const displayScore = getDisplayScore(m) * 100;
    return matchesSkill && displayScore >= minMatch;
  });

  const selectedJobMatch =
    (matches || []).find((m) => m.job_offer.id === selectedJobId) ||
    normalizedMatches.find((m) => m.job_offer.id === selectedJobId) ||
    (scrapedJobs || [])
      .filter((j) => j.id === selectedJobId)
      .map((job) => ({
        job_offer: job,
        score: 0,
        quick_score: 0,
        source: "none" as const,
      }))[0];

  const batchPending = matchBatch.isPending;
  const matchError =
    (matchOne.error as Error | null)?.message ||
    (matchBatch.error as Error | null)?.message;

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Job Search</h1>
          <p className="text-sm text-gray-500">
            Search boards into staging. Estimated skill overlap is computed on
            fetch; Save / Apply / Generate CV promotes an offer into your career
            graph. AI match runs only when you ask.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={handleMatchSelected}
            disabled={batchPending || selectedIds.size === 0}
          >
            {batchPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Match selected ({selectedIds.size})
          </Button>
          <Button
            variant="outline"
            onClick={handleMatchAllCareer}
            disabled={batchPending}
          >
            {batchPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Match all saved
          </Button>
        </div>
      </div>

      <JobSearchForm
        onSearch={handleSearch}
        isSearching={scrapeMutation.isPending}
      />

      {scrapeMutation.isSuccess && (
        <p className="text-xs text-indigo-600 -mt-4">
          Queued a scrape into staging (rate-limited, may take a few minutes).
          Check the Scraped Offers tab.
        </p>
      )}
      {scrapeMutation.isError && (
        <p className="text-xs text-red-600 -mt-4">
          Failed to queue the job board search. Try again in a moment.
        </p>
      )}
      {matchError && <p className="text-xs text-red-600 -mt-4">{matchError}</p>}
      {promoteMutation.isSuccess && (
        <p className="text-xs text-indigo-600 -mt-4">
          Offer saved to your career knowledge graph.
        </p>
      )}
      {applyMutation.isSuccess && (
        <p className="text-xs text-indigo-600 -mt-4">
          Application created (offer promoted if it was still staging).
        </p>
      )}

      <div className="flex gap-2 border-b pb-2">
        <Button
          variant={tab === "match" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("match")}
        >
          Saved Offers
        </Button>
        <Button
          variant={tab === "scraped" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("scraped")}
        >
          Scraped Offers
          {scrapedJobs && scrapedJobs.length > 0 && (
            <Badge variant="secondary" className="ml-2">
              {scrapedJobs.length}
            </Badge>
          )}
        </Button>
      </div>

      {tab === "match" ? (
        <>
          <JobFilters
            minMatch={minMatch}
            setMinMatch={setMinMatch}
            selectedSkill={selectedSkill}
            setSelectedSkill={setSelectedSkill}
          />

          {isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <Skeleton key={i} className="h-[250px] w-full rounded-xl" />
              ))}
            </div>
          ) : filteredMatches.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-3">
              {filteredMatches.map((match) => (
                <JobCard
                  key={match.job_offer.id}
                  match={match}
                  onViewDetails={handleViewDetails}
                  onSave={handleSave}
                  onApply={handleApply}
                  onCalculateMatch={handleCalculateMatch}
                  selected={selectedIds.has(match.job_offer.id)}
                  onToggleSelect={toggleSelect}
                  isSaving={
                    promoteMutation.isPending && pendingJobId === match.job_offer.id
                  }
                  isApplying={
                    applyMutation.isPending && pendingJobId === match.job_offer.id
                  }
                  isMatching={
                    matchOne.isPending && pendingJobId === match.job_offer.id
                  }
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center border rounded-xl bg-white">
              <Search className="h-12 w-12 text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No jobs found</h3>
              <p className="text-sm text-gray-500 max-w-xs mt-2">
                Save scraped offers to your career graph, then calculate AI match
                on demand.
              </p>
              <Button
                variant="outline"
                className="mt-6"
                onClick={() => {
                  setMinMatch(0);
                  setSelectedSkill("");
                }}
              >
                Clear Filters
              </Button>
            </div>
          )}
        </>
      ) : (
        <>
          <ScrapedJobFilters
            search={scrapedSearch}
            setSearch={setScrapedSearch}
            seniority={seniority}
            setSeniority={setSeniority}
            experienceBracket={experienceBracket}
            setExperienceBracket={setExperienceBracket}
          />

          {scrapedLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-[220px] w-full rounded-xl" />
              ))}
            </div>
          ) : scrapedJobs && scrapedJobs.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-3">
              {scrapedJobs.map((job) => {
                const match = matchById.get(job.id);
                const skills =
                  job.required_skills.length > 0
                    ? job.required_skills
                    : match?.job_offer.required_skills || [];
                const matching = new Set(
                  (match?.matching_skills || []).map((s) => s.toLowerCase())
                );
                const displayPercent = match
                  ? Math.round(getDisplayScore(match) * 100)
                  : 0;
                const matchColor =
                  displayPercent >= 80
                    ? "bg-green-100 text-green-800 border-green-200"
                    : displayPercent >= 60
                      ? "bg-amber-100 text-amber-800 border-amber-200"
                      : "bg-red-100 text-red-800 border-red-200";
                return (
                  <Card key={job.id} className="flex flex-col h-full">
                  <CardHeader className="pb-2">
                    <div className="flex flex-wrap gap-1 mb-1">
                      {match && (
                        <Badge className={`${matchColor} font-semibold`}>
                          {displayPercent}% overlap
                        </Badge>
                      )}
                      {job.seniority && (
                        <Badge variant="secondary" className="capitalize">
                          {job.seniority}
                        </Badge>
                      )}
                      {job.source && (
                        <Badge variant="outline">{job.source}</Badge>
                      )}
                    </div>
                    <CardTitle className="text-lg line-clamp-1">{job.title}</CardTitle>
                    <p className="text-sm text-muted-foreground">{job.company}</p>
                  </CardHeader>
                  <CardContent className="flex-1 pb-2">
                    <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                      {job.description}
                    </p>
                    {skills.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {skills.slice(0, 5).map((skill) => (
                          <Badge
                            key={skill}
                            variant="secondary"
                            className={`text-[10px] px-2 py-0 ${
                              matching.has(skill.toLowerCase())
                                ? "bg-green-100 text-green-800 border-green-200"
                                : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {skill}
                          </Badge>
                        ))}
                        {skills.length > 5 && (
                          <span className="text-[10px] text-muted-foreground">
                            +{skills.length - 5} more
                          </span>
                        )}
                      </div>
                    )}
                  </CardContent>
                  <CardFooter className="gap-2 flex-wrap">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleCalculateMatch(job.id)}
                      disabled={matchOne.isPending && pendingJobId === job.id}
                    >
                      {matchOne.isPending && pendingJobId === job.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <>
                          <Sparkles className="h-3 w-3 mr-1" />
                          Match
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleViewDetails(job.id)}
                    >
                      View
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleSave(job.id)}
                      disabled={promoteMutation.isPending && pendingJobId === job.id}
                    >
                      Save
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-red-600"
                      onClick={() => handleDeleteScraped(job.id)}
                      disabled={deleteScraped.isPending && pendingJobId === job.id}
                    >
                      {deleteScraped.isPending && pendingJobId === job.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Trash2 className="h-3 w-3" />
                      )}
                    </Button>
                  </CardFooter>
                </Card>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center border rounded-xl bg-white">
              <Search className="h-12 w-12 text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No scraped offers</h3>
              <p className="text-sm text-gray-500 max-w-xs mt-2">
                Run a job board search above. Results persist here until you save or delete them.
              </p>
            </div>
          )}
        </>
      )}

      {selectedJobMatch && (
        <JobDetailSheet
          open={isDetailOpen}
          onOpenChange={setIsDetailOpen}
          jobMatch={selectedJobMatch}
          onSave={handleSave}
          onApply={handleApply}
          onCalculateMatch={handleCalculateMatch}
          isSaving={
            promoteMutation.isPending &&
            pendingJobId === selectedJobMatch.job_offer.id
          }
          isApplying={
            applyMutation.isPending &&
            pendingJobId === selectedJobMatch.job_offer.id
          }
          isMatching={
            matchOne.isPending &&
            pendingJobId === selectedJobMatch.job_offer.id
          }
        />
      )}
    </div>
  );
}
