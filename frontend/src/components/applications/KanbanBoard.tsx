"use client";

import React, { useState } from "react";
import { ApplicationWithJob, ApplicationCard } from "./ApplicationCard";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ApplicationDetailSheet } from "./ApplicationDetailSheet";

interface KanbanBoardProps {
  applications: ApplicationWithJob[];
}

const COLUMNS = [
  { id: "Applied", title: "Applied" },
  { id: "Responded", title: "Responded" },
  { id: "Interview", title: "Interview" },
  { id: "Offer", title: "Offer" },
  { id: "Rejected", title: "Rejected" },
];

export function KanbanBoard({ applications }: KanbanBoardProps) {
  const [selectedApp, setSelectedApp] = useState<ApplicationWithJob | null>(
    null,
  );
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  const getAppsByStatus = (status: string) => {
    return applications.filter((app) => app.status === status);
  };

  const handleCardClick = (app: ApplicationWithJob) => {
    setSelectedApp(app);
    setIsSheetOpen(true);
  };

  return (
    <>
      <div className="flex flex-col md:flex-row gap-4 h-full min-h-[600px] overflow-x-auto pb-4">
        {COLUMNS.map((column) => {
          const columnApps = getAppsByStatus(column.id);

          return (
            <div
              key={column.id}
              className="flex-1 min-w-[280px] bg-slate-50 rounded-lg flex flex-col border border-slate-200 shadow-sm"
            >
              <div className="p-4 border-b border-slate-200 bg-white/50 rounded-t-lg flex justify-between items-center">
                <h3 className="font-semibold text-sm text-slate-700">
                  {column.title}
                </h3>
                <span className="text-xs font-medium bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full">
                  {columnApps.length}
                </span>
              </div>

              <ScrollArea className="flex-1 p-3">
                <div className="flex flex-col gap-2">
                  {columnApps.length > 0 ? (
                    columnApps.map((app) => (
                      <ApplicationCard
                        key={app.id}
                        application={app}
                        onClick={() => handleCardClick(app)}
                      />
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center py-10 opacity-40">
                      <p className="text-xs italic">No applications</p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          );
        })}
      </div>

      <ApplicationDetailSheet
        application={selectedApp}
        open={isSheetOpen}
        onOpenChange={setIsSheetOpen}
      />
    </>
  );
}
