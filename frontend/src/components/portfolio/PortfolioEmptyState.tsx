"use client";

import { FolderPlus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PortfolioEmptyStateProps {
  onAddClick: () => void;
}

export function PortfolioEmptyState({ onAddClick }: PortfolioEmptyStateProps) {
  return (
    <div className="flex h-[450px] shrink-0 items-center justify-center rounded-md border border-dashed bg-white">
      <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-slate-100">
          <FolderPlus className="h-10 w-10 text-slate-400" />
        </div>
        <h3 className="mt-4 text-lg font-semibold">No projects added</h3>
        <p className="mb-6 mt-2 text-sm text-muted-foreground">
          You haven&apos;t added any projects to your portfolio yet. Add your
          first project to showcase your skills.
        </p>
        <Button
          onClick={onAddClick}
          className="bg-gray-900 text-white hover:bg-gray-700"
        >
          Add your first project
        </Button>
      </div>
    </div>
  );
}
