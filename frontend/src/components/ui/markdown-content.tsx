"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  if (!content?.trim()) {
    return <p className="text-sm text-muted-foreground italic">No description provided.</p>;
  }

  return (
    <div className={className ?? "prose prose-sm max-w-none text-gray-700"}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
