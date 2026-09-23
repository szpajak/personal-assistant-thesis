import React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Filter } from "lucide-react";

interface JobFiltersProps {
  minMatch: number;
  setMinMatch: (match: number) => void;
  selectedSkill: string;
  setSelectedSkill: (skill: string) => void;
}

export const JobFilters: React.FC<JobFiltersProps> = ({
  minMatch,
  setMinMatch,
  selectedSkill,
  setSelectedSkill,
}) => {
  return (
    <div className="bg-card border rounded-lg p-4">
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-full md:w-48 space-y-2">
          <Label
            htmlFor="skill"
            className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
          >
            Filter by Skill
          </Label>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              id="skill"
              placeholder="e.g. React"
              className="pl-10"
              value={selectedSkill}
              onChange={(e) => setSelectedSkill(e.target.value)}
            />
          </div>
        </div>

        <div className="w-full md:w-48 space-y-2">
          <Label
            htmlFor="match"
            className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
          >
            Min Match: {minMatch}%
          </Label>
          <input
            id="match"
            type="range"
            min="0"
            max="100"
            step="5"
            className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            value={minMatch}
            onChange={(e) => setMinMatch(parseInt(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
};
