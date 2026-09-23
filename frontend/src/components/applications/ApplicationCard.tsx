"use client";

import React from "react";
import { Application } from "@/types/applications";
import { JobOffer } from "@/types/jobs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Building2 } from "lucide-react";

export interface ApplicationWithJob extends Application {
  job_offer?: JobOffer | null;
}

interface ApplicationCardProps {
  application: ApplicationWithJob;
  onClick: () => void;
}

const statusColors: Record<string, string> = {
  Applied: "bg-blue-100 text-blue-800 hover:bg-blue-100",
  Responded: "bg-purple-100 text-purple-800 hover:bg-purple-100",
  Interview: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100",
  Offer: "bg-green-100 text-green-800 hover:bg-green-100",
  Rejected: "bg-red-100 text-red-800 hover:bg-red-100",
};

export function ApplicationCard({
  application,
  onClick,
}: ApplicationCardProps) {
  const { job_offer, status, applied_at } = application;

  const formattedDate = applied_at
    ? new Date(applied_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "N/A";

  return (
    <Card
      className="mb-3 hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <CardHeader className="p-4 pb-2">
        <div className="flex justify-between items-start">
          <CardTitle className="text-sm font-bold truncate flex-1 mr-2">
            {job_offer?.title || "Unknown Position"}
          </CardTitle>
          <Badge className={statusColors[status] || "bg-gray-100"}>
            {status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="flex flex-col gap-1 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Building2 className="h-3 w-3" />
            <span className="truncate">
              {job_offer?.company || "Unknown Company"}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>Applied: {formattedDate}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
