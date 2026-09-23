"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderKanban,
  Briefcase,
  Mail,
  BarChart2,
  Network,
  Award,
  History,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logout, useUser } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Portfolio", href: "/portfolio", icon: FolderKanban },
  { name: "Career", href: "/career", icon: History },
  { name: "Job Search", href: "/jobs", icon: Briefcase },
  { name: "Applications", href: "/applications", icon: Mail },
  { name: "Skills", href: "/skills", icon: BarChart2 },
  { name: "Certificates", href: "/certificates", icon: Award },
  { name: "Knowledge Graph", href: "/kg", icon: Network },
];

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const { data: user } = useUser();

  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .substring(0, 2);
  };

  return (
    <div className="flex h-full w-60 flex-col bg-gray-950 text-white">
      <div className="flex h-16 items-center px-6">
        <Link
          href="/"
          className="flex items-center space-x-2"
          onClick={onClose}
          aria-label="Career AI Home"
        >
          <span className="text-xl font-bold tracking-tight">Career AI</span>
        </Link>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Main Navigation">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={onClose}
              aria-label={item.name}
              className={cn(
                "group flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-white/10 text-white"
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200",
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 h-5 w-5 flex-shrink-0 transition-colors",
                  isActive
                    ? "text-white"
                    : "text-gray-400 group-hover:text-gray-200",
                )}
                aria-hidden="true"
              />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-4 space-y-3">
        <div className="flex items-center space-x-3 px-2">
          <div
            className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center font-bold text-xs"
            aria-hidden="true"
          >
            {user?.full_name ? getInitials(user.full_name) : "U"}
          </div>
          <div className="flex-1 overflow-hidden text-xs">
            <p className="truncate font-medium">
              {user?.full_name || "Loading..."}
            </p>
            <p className="truncate text-gray-500">{user?.email || "User"}</p>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-full justify-start px-3 text-gray-400 hover:bg-white/5 hover:text-gray-200"
          onClick={() => {
            onClose?.();
            logout();
          }}
          aria-label="Log out"
        >
          <LogOut className="mr-3 h-4 w-4" aria-hidden="true" />
          Log out
        </Button>
      </div>
    </div>
  );
}
