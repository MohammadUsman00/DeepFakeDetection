"use client";

import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

const STEPS = ["Choose", "Upload", "Analyze", "Results"] as const;

type Stage = "SELECTION" | "UPLOAD" | "ANALYSIS" | "RESULT";

const MAP: Record<Stage, number> = {
  SELECTION: 0,
  UPLOAD: 1,
  ANALYSIS: 2,
  RESULT: 3,
};

type Props = {
  stage: Stage;
  className?: string;
};

export function WorkflowRail({ stage, className }: Props) {
  const active = MAP[stage];

  return (
    <nav aria-label="Workflow progress" className={cn("w-full", className)}>
      <ol className="flex items-center">
        {STEPS.map((label, i) => {
          const done = i < active;
          const current = i === active;
          return (
            <li key={label} className="flex min-w-0 flex-1 items-center">
              <div className="flex min-w-0 flex-col items-center gap-1.5">
                <div
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-[11px] font-bold transition-all",
                    done && "border-primary bg-primary/15 text-primary",
                    current && !done && "border-primary bg-primary text-primary-foreground shadow-[0_0_18px_rgba(16,185,129,0.35)]",
                    !done && !current && "border-border bg-muted/50 text-muted-foreground"
                  )}
                >
                  {done ? <Check className="h-4 w-4" strokeWidth={3} /> : i + 1}
                </div>
                <span
                  className={cn(
                    "hidden max-w-[5rem] truncate text-center text-[9px] font-semibold uppercase tracking-wider sm:block",
                    current ? "text-primary" : "text-muted-foreground"
                  )}
                >
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn("mx-1 h-0.5 min-w-[8px] flex-1 sm:mx-2", i < active ? "bg-primary/50" : "bg-border")}
                  aria-hidden
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
