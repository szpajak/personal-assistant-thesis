"use client";

import { useApplications } from "@/hooks/useApplications";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Mail, RefreshCw } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KanbanBoard } from "@/components/applications/KanbanBoard";
import { EmailService } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";

export default function ApplicationsPage() {
  const { data: applications, isLoading } = useApplications();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const syncMutation = useMutation({
    mutationFn: () => EmailService.syncEmailsApiV1EmailSyncPost(),
    onSuccess: (emails) => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["application-emails"] });
      queryClient.invalidateQueries({ queryKey: ["kg-stats"] });
      const count = Array.isArray(emails) ? emails.length : 0;
      toast({
        title: count ? "Inbox synced" : "No new emails",
        description: count
          ? `Processed ${count} new message${count === 1 ? "" : "s"}.`
          : "Your inbox was checked; nothing new to ingest.",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Email sync failed",
        description: error.message || "Could not reach the mail server.",
        variant: "destructive",
      });
    },
  });

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] space-y-6">
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Application Tracker</h1>
          <p className="text-sm text-gray-500">Track your job applications and interview progress.</p>
        </div>
        <Button 
          onClick={() => syncMutation.mutate()} 
          disabled={syncMutation.isPending}
          className="bg-indigo-600 text-white hover:bg-indigo-500"
        >
          {syncMutation.isPending ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Mail className="mr-2 h-4 w-4" />
          )}
          Check Emails
        </Button>
      </div>

      <div className="flex-1 min-h-0">
        {isLoading ? (
          <div className="grid grid-cols-5 gap-4 h-full">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="w-full h-full rounded-xl" />
            ))}
          </div>
        ) : (
          <KanbanBoard applications={applications || []} />
        )}
      </div>
    </div>
  );
}
