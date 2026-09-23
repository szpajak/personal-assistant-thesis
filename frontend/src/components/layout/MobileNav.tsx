"use client";

import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { useState } from "react";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center lg:hidden h-16 border-b bg-white px-4">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Open menu">
            <Menu className="h-6 w-6" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-60 bg-gray-950 border-r-0">
          <Sidebar onClose={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="ml-4 flex-1">
        <span className="text-lg font-bold tracking-tight">Career AI</span>
      </div>
    </div>
  );
}
