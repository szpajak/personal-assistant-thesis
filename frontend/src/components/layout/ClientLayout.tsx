"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { MobileNav } from "@/components/layout/MobileNav";
import { Toaster } from "@/components/ui/toaster";
import { ApiError, OpenAPI } from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";
import { clearSession, getStoredToken, setSession } from "@/lib/authSession";
import { usePathname, useRouter } from "next/navigation";
import { useUser } from "@/hooks/useAuth";

// Initialize OpenAPI BASE URL
OpenAPI.BASE = API_BASE_URL;

// Set auth token before the first render so protected queries don't 401 on mount.
if (typeof window !== "undefined") {
  const token = getStoredToken();
  if (token) {
    OpenAPI.TOKEN = token;
  }
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isAuthPage = pathname === "/login" || pathname === "/register";
  const [hasToken, setHasToken] = useState<boolean | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (token) {
      // Sync cookie for middleware (covers legacy localStorage-only sessions).
      setSession(token);
      setHasToken(true);
      if (isAuthPage) {
        router.replace("/");
      }
    } else {
      setHasToken(false);
      if (!isAuthPage) {
        router.replace("/login");
      }
    }
  }, [isAuthPage, router]);

  const userQuery = useUser(hasToken === true && !isAuthPage);

  useEffect(() => {
    if (!userQuery.isError || isAuthPage) return;
    const status = userQuery.error instanceof ApiError ? userQuery.error.status : undefined;
    if (status !== 401 && status !== 403) return;
    clearSession();
    setHasToken(false);
    router.replace("/login");
  }, [userQuery.isError, userQuery.error, isAuthPage, router]);

  const isUnauthorized =
    userQuery.isError &&
    userQuery.error instanceof ApiError &&
    (userQuery.error.status === 401 || userQuery.error.status === 403);

  // Avoid flashing the protected shell before auth status is known.
  if (!isAuthPage && (hasToken === null || hasToken === false || userQuery.isLoading || isUnauthorized)) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 text-sm text-gray-500">
        {isUnauthorized ? "Redirecting to login..." : "Checking session..."}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col lg:flex-row overflow-hidden bg-gray-50 text-gray-950">
      {!isAuthPage && <MobileNav />}
      {!isAuthPage && (
        <aside className="hidden lg:block">
          <Sidebar />
        </aside>
      )}
      <main className={isAuthPage ? "flex-1 overflow-y-auto" : "flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8"}>
        <div className={isAuthPage ? "h-full" : "mx-auto max-w-6xl"}>
          {children}
        </div>
      </main>
    </div>
  );
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: false,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate>{children}</AuthGate>
      <Toaster />
    </QueryClientProvider>
  );
}
