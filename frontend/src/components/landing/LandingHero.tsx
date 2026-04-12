"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { isAuthRequired, getToken } from "@/lib/auth";

type Props = {
  onScrollToAnalyzer: () => void;
};

export function LandingHero({ onScrollToAnalyzer }: Props) {
  const needGate = isAuthRequired() && !getToken();

  return (
    <section className="relative overflow-hidden border-b border-border/40">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_90%_60%_at_50%_-10%,rgba(16,185,129,0.18),transparent_55%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_100%_50%,rgba(99,102,241,0.12),transparent_50%)]" />

      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pb-24 sm:pt-16 lg:pb-28 lg:pt-20">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          Face-centric screening
        </div>

        <h1 className="mt-6 max-w-3xl text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-[3.25rem] lg:leading-[1.1]">
          Know whether faces in your media look{" "}
          <span className="bg-gradient-to-r from-primary via-emerald-300 to-secondary bg-clip-text text-transparent">
            consistent with authentic capture
          </span>
        </h1>

        <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          DeepShield runs EfficientNet-based scoring on detected faces, with optional Grad-CAM overlays on the most
          uncertain frames—so investigators and researchers can see both a verdict-style signal and where the model
          looked.
        </p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
          {needGate ? (
            <>
              <Link
                href="/register"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground shadow-xl shadow-primary/25 transition hover:bg-primary/90"
              >
                Create free account
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center justify-center rounded-xl border border-border bg-muted/30 px-6 py-3.5 text-sm font-semibold text-foreground transition hover:bg-muted/50"
              >
                Sign in
              </Link>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={onScrollToAnalyzer}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground shadow-xl shadow-primary/25 transition hover:bg-primary/90"
              >
                Open analyzer
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}
                className="inline-flex items-center justify-center rounded-xl border border-border bg-muted/30 px-6 py-3.5 text-sm font-semibold text-foreground transition hover:bg-muted/50"
              >
                How it works
              </button>
            </>
          )}
        </div>

        <p className="mt-8 text-xs leading-relaxed text-muted-foreground/80 sm:max-w-xl">
          Educational and research use. Outputs are probabilistic and not a substitute for forensic certification or legal
          advice.
        </p>
      </div>
    </section>
  );
}
