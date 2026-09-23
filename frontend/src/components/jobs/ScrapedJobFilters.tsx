"use client";

import React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ExperienceBracket, SeniorityFilter } from "@/types/jobs";

interface ScrapedJobFiltersProps {
  search: string;
  setSearch: (value: string) => void;
  seniority: SeniorityFilter | "";
  setSeniority: (value: SeniorityFilter | "") => void;
  experienceBracket: ExperienceBracket | "";
  setExperienceBracket: (value: ExperienceBracket | "") => void;
}

export function ScrapedJobFilters({
  search,
  setSearch,
  seniority,
  setSeniority,
  experienceBracket,
  setExperienceBracket,
}: ScrapedJobFiltersProps) {
  return (
    <div className="bg-card border rounded-lg p-4">
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-full md:flex-1 space-y-2">
          <Label
            htmlFor="scraped-search"
            className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
          >
            Search
          </Label>
          <Input
            id="scraped-search"
            placeholder="Title or company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="w-full md:w-44 space-y-2">
          <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Level
          </Label>
          <Select
            value={seniority || "any"}
            onValueChange={(v) =>
              setSeniority(v === "any" ? "" : (v as SeniorityFilter))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Any level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any level</SelectItem>
              <SelectItem value="junior">Junior</SelectItem>
              <SelectItem value="mid">Mid</SelectItem>
              <SelectItem value="senior">Senior</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-full md:w-44 space-y-2">
          <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Experience
          </Label>
          <Select
            value={experienceBracket || "any"}
            onValueChange={(v) =>
              setExperienceBracket(v === "any" ? "" : (v as ExperienceBracket))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Any experience" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any experience</SelectItem>
              <SelectItem value="0-2">0–2 years</SelectItem>
              <SelectItem value="2-5">2–5 years</SelectItem>
              <SelectItem value="5+">5+ years</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
