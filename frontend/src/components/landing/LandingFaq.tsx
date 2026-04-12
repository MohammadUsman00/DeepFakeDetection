"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

const FAQ = [
  {
    q: "What file types are supported?",
    a: "Video: MP4 and MOV. Images: JPEG and PNG. Exact MIME and size limits follow your server configuration (see backend config / Docker).",
  },
  {
    q: "Do I need an account?",
    a: "Deployments can run in open mode or require sign-in. When SaaS mode is on, you register once; jobs are tied to your account and free-tier daily limits apply.",
  },
  {
    q: "How fast is analysis?",
    a: "Throughput depends on CPU/GPU, video length, sampling FPS, and face density. Long clips may run asynchronously with progress polled from /api/results.",
  },
  {
    q: "Where is my data stored?",
    a: "Uploads and artifacts live under the configured storage directories (local volume in Docker). Review retention and cleanup settings for production.",
  },
] as const;

export function LandingFaq() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section id="faq" className="scroll-mt-24 border-b border-border/40 bg-muted/10">
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:py-24">
        <p className="text-center text-[11px] font-semibold uppercase tracking-[0.25em] text-primary">FAQ</p>
        <h2 className="mt-2 text-center text-3xl font-bold tracking-tight sm:text-4xl">Questions end users ask</h2>
        <p className="mt-4 text-center text-muted-foreground">
          Straight answers—adjust copy if your deployment policies differ.
        </p>

        <div className="mt-12 space-y-3">
          {FAQ.map((item, i) => {
            const isOpen = open === i;
            return (
              <div
                key={item.q}
                className="overflow-hidden rounded-2xl border border-border/60 bg-card/50"
              >
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                >
                  {item.q}
                  <ChevronDown className={cn("h-5 w-5 shrink-0 text-muted-foreground transition", isOpen && "rotate-180")} />
                </button>
                {isOpen && (
                  <div className="border-t border-border/50 px-5 py-4 text-sm leading-relaxed text-muted-foreground">
                    {item.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
