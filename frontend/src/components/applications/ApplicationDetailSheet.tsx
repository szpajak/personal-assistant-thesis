"use client";

import React from "react";
import { 
  Sheet, 
  SheetContent, 
  SheetHeader, 
  SheetTitle, 
  SheetFooter
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ApplicationWithJob } from "./ApplicationCard";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { 
  Building2, 
  Clock, 
  FileText, 
  Mail, 
  Loader2,
  ExternalLink
} from "lucide-react";

import { ApplicationsService } from "@/lib/api";
import { apiFetch } from "@/lib/apiFetch";
import type { Email } from "@/types/email";

interface ApplicationDetailSheetProps {
  application: ApplicationWithJob | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const statusOptions = ["Applied", "Responded", "Interview", "Offer", "Rejected"];

function formatEmailDate(value: string | null | undefined): string {
  if (!value) return "Unknown date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ApplicationDetailSheet({
  application,
  open,
  onOpenChange
}: ApplicationDetailSheetProps) {
  const queryClient = useQueryClient();

  const emailsQuery = useQuery({
    queryKey: ["application-emails", application?.id],
    queryFn: () =>
      apiFetch<Email[]>(`/api/v1/applications/${application!.id}/emails`),
    enabled: open && !!application?.id,
  });

  const updateMutation = useMutation({
    mutationFn: (newStatus: string) => {
      if (!application) throw new Error("No application selected");
      return ApplicationsService.updateApplicationApiV1ApplicationsIdPatch(
        application.id,
        { status: newStatus }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
    },
  });
  if (!application) return null;

  const job = application.job_offer;
  const emails = emailsQuery.data || [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[500px]">
        <SheetHeader>
          <div className="flex justify-between items-start">
            <div className="space-y-1">
              <SheetTitle className="text-xl font-bold">{job?.title || "Application Details"}</SheetTitle>
              <div className="flex items-center text-sm text-muted-foreground">
                <Building2 className="mr-1 h-4 w-4" />
                {job?.company || "Unknown Company"}
              </div>
            </div>
            <Badge variant="outline" className="mt-1">
              {application.status}
            </Badge>
          </div>
        </SheetHeader>

        <div className="grid gap-6 py-6">
          <div className="space-y-4">
            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center">
              <Clock className="mr-2 h-4 w-4" />
              Progress
            </h4>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <Select 
                  value={application.status} 
                  onValueChange={(val) => updateMutation.mutate(val)}
                  disabled={updateMutation.isPending}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Update Status" />
                  </SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((opt) => (
                      <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {updateMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center">
              <FileText className="mr-2 h-4 w-4" />
              Description
            </h4>
            <ScrollArea className="h-40 rounded-md border p-4 bg-muted/30">
              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                {job?.description || "No description provided."}
              </p>
            </ScrollArea>
            {job?.url && (
              <Button variant="link" size="sm" className="px-0" asChild>
                <a href={job.url} target="_blank" rel="noopener noreferrer">
                  View original posting <ExternalLink className="ml-1 h-3 w-3" />
                </a>
              </Button>
            )}
          </div>

          <div className="space-y-4">
            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center">
              <Mail className="mr-2 h-4 w-4" />
              Communication
            </h4>
            {emailsQuery.isLoading ? (
              <div className="rounded-md border bg-slate-50 p-6 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading emails…
              </div>
            ) : emailsQuery.isError ? (
              <div className="rounded-md border border-red-100 bg-red-50 p-4 text-center text-sm text-red-700">
                Could not load emails. Try again after syncing your inbox.
              </div>
            ) : emails.length === 0 ? (
              <div className="rounded-md border bg-slate-50 p-6 text-center italic text-gray-400 text-sm">
                No recent emails detected. Sync your inbox to see communication history.
              </div>
            ) : (
              <ScrollArea className="h-48 rounded-md border">
                <div className="divide-y">
                  {emails.map((email) => (
                    <div key={email.id} className="p-3 space-y-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium leading-snug">
                          {email.subject || "(no subject)"}
                        </p>
                        {email.classification && (
                          <Badge variant="secondary" className="text-[10px] shrink-0">
                            {email.classification}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {email.sender || "Unknown sender"} · {formatEmailDate(email.received_at)}
                      </p>
                      {email.summary && (
                        <p className="text-sm text-gray-700">{email.summary}</p>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        </div>

        <SheetFooter className="mt-auto">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full">
            Close
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
