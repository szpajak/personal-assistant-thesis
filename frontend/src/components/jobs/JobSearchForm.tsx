"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Search } from "lucide-react";
import type { JobScrapeRequest, JobTypeFilter } from "@/lib/api";

const COUNTRIES = [
  "Poland",
  "USA",
  "UK",
  "Germany",
  "France",
  "Netherlands",
  "Spain",
  "Italy",
  "Canada",
  "Australia",
  "Ireland",
  "Sweden",
  "Switzerland",
] as const;

const SITES = [
  { id: "linkedin", label: "LinkedIn" },
  { id: "indeed", label: "Indeed" },
  { id: "glassdoor", label: "Glassdoor" },
  { id: "zip_recruiter", label: "ZipRecruiter" },
  { id: "google", label: "Google" },
] as const;

const JOB_TYPES: { value: JobTypeFilter; label: string }[] = [
  { value: "fulltime", label: "Full-time" },
  { value: "parttime", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
];

const HOURS_OLD_OPTIONS = [
  { value: "any", label: "Any time" },
  { value: "24", label: "Last 24 hours" },
  { value: "72", label: "Last 3 days" },
  { value: "168", label: "Last week" },
] as const;

export interface JobSearchFormProps {
  onSearch: (filters: JobScrapeRequest) => void;
  isSearching?: boolean;
}

export const JobSearchForm: React.FC<JobSearchFormProps> = ({
  onSearch,
  isSearching = false,
}) => {
  const [searchTerm, setSearchTerm] = useState("Python Developer");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState<string>("Poland");
  const [jobType, setJobType] = useState<string>("any");
  const [hoursOld, setHoursOld] = useState<string>("any");
  const [isRemote, setIsRemote] = useState(false);
  const [selectedSites, setSelectedSites] = useState<string[]>([
    "linkedin",
    "indeed",
  ]);
  const [resultsWanted, setResultsWanted] = useState("25");

  const toggleSite = (siteId: string) => {
    setSelectedSites((prev) =>
      prev.includes(siteId)
        ? prev.filter((s) => s !== siteId)
        : [...prev, siteId],
    );
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = searchTerm.trim();
    if (!trimmed || selectedSites.length === 0) {
      return;
    }

    const wanted = Math.min(50, Math.max(1, Number(resultsWanted) || 25));

    onSearch({
      search_term: trimmed,
      location: location.trim() || null,
      country: country || null,
      sites: selectedSites,
      job_type: jobType === "any" ? null : (jobType as JobTypeFilter),
      is_remote: isRemote,
      hours_old: hoursOld === "any" ? null : Number(hoursOld),
      results_wanted: wanted,
      include_remoteok: false,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-card border rounded-lg p-4 space-y-4"
    >
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-grow space-y-2">
          <Label
            htmlFor="job-search-term"
            className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
          >
            Job title / keywords
          </Label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              id="job-search-term"
              placeholder="e.g. Python Developer"
              className="pl-10"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="w-full md:w-56 space-y-2">
          <Label
            htmlFor="job-location"
            className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
          >
            Location
          </Label>
          <Input
            id="job-location"
            placeholder="e.g. Warsaw, Poland"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </div>

        <div className="w-full md:w-44 space-y-2">
          <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Country
          </Label>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger>
              <SelectValue placeholder="Country" />
            </SelectTrigger>
            <SelectContent>
              {COUNTRIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-full md:w-48 space-y-2">
          <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Job type
          </Label>
          <Select value={jobType} onValueChange={setJobType}>
            <SelectTrigger>
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              {JOB_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-full md:w-48 space-y-2">
          <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Posted within
          </Label>
          <Select value={hoursOld} onValueChange={setHoursOld}>
            <SelectTrigger>
              <SelectValue placeholder="Any time" />
            </SelectTrigger>
            <SelectContent>
              {HOURS_OLD_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-full md:w-40 space-y-2">
          <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Results / site
          </Label>
          <Select value={resultsWanted} onValueChange={setResultsWanted}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-end pb-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-input accent-indigo-600"
              checked={isRemote}
              onChange={(e) => setIsRemote(e.target.checked)}
            />
            Remote only
          </label>
        </div>
      </div>

      <div className="space-y-2">
        <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Job boards
        </Label>
        <p className="text-xs text-muted-foreground">
          Cost and volume scale with boards × results per site.
        </p>
        <div className="flex flex-wrap gap-3">
          {SITES.map((site) => (
            <label
              key={site.id}
              className="flex items-center gap-2 text-sm cursor-pointer select-none"
            >
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input accent-indigo-600"
                checked={selectedSites.includes(site.id)}
                onChange={() => toggleSite(site.id)}
              />
              {site.label}
            </label>
          ))}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Note: Indeed/LinkedIn may ignore some filter combinations (e.g.
          posted-within together with job type or remote).
        </p>
        <Button
          type="submit"
          disabled={
            isSearching || !searchTerm.trim() || selectedSites.length === 0
          }
          className="bg-indigo-600 text-white hover:bg-indigo-500 shrink-0"
        >
          {isSearching ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Search className="mr-2 h-4 w-4" />
          )}
          Search jobs
        </Button>
      </div>
    </form>
  );
};
