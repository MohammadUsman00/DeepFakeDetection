"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Shield, Menu, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { getToken, isAuthRequired } from "@/lib/auth";

const NAV = [
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#technology", label: "Technology" },
  { href: "#analyzer", label: "Analyzer" },
  { href: "#faq", label: "FAQ" },
] as const;

type Props = {
  onSignOut?: () => void;
  className?: string;
};

export function LandingNav({ onSignOut, className }: Props) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const auth = isAuthRequired();
  const signedIn = auth && !!getToken();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const linkCls =
    "text-sm font-medium text-muted-foreground transition hover:text-foreground";

  return (
    <header
      className={cn(
        "sticky top-0 z-50 border-b border-transparent transition-colors duration-300",
        scrolled && "border-border/60 bg-background/75 backdrop-blur-xl",
        className
      )}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 ring-1 ring-white/10">
            <Shield className="h-5 w-5 text-primary" aria-hidden />
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-sm font-semibold tracking-tight">DeepShield</span>
            <span className="hidden text-[10px] font-medium uppercase tracking-wider text-muted-foreground sm:block">
              Media authenticity
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Page sections">
          {NAV.map((item) => (
            <a key={item.href} href={item.href} className={cn(linkCls, "rounded-lg px-3 py-2")}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {auth && signedIn && onSignOut && (
            <button
              type="button"
              onClick={() => {
                onSignOut();
                setOpen(false);
              }}
              className="hidden rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-muted/60 sm:inline-flex"
            >
              Sign out
            </button>
          )}
          {auth && !signedIn && (
            <>
              <Link
                href="/login"
                className="hidden rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition hover:text-foreground sm:inline-block"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="hidden rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-primary/90 sm:inline-block"
              >
                Get started
              </Link>
            </>
          )}
          <button
            type="button"
            className="inline-flex rounded-lg border border-border p-2 md:hidden"
            aria-expanded={open}
            aria-label="Toggle menu"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-border/60 bg-background/95 px-4 py-4 backdrop-blur-xl md:hidden">
          <div className="flex flex-col gap-1">
            {NAV.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-foreground"
                onClick={() => setOpen(false)}
              >
                {item.label}
              </a>
            ))}
            {auth && (
              <div className="mt-3 flex flex-col gap-2 border-t border-border/60 pt-3">
                {signedIn && onSignOut ? (
                  <button type="button" className="rounded-lg py-2 text-left text-sm font-medium" onClick={() => { onSignOut(); setOpen(false); }}>
                    Sign out
                  </button>
                ) : (
                  <>
                    <Link href="/login" className="rounded-lg py-2 text-sm font-medium" onClick={() => setOpen(false)}>
                      Sign in
                    </Link>
                    <Link
                      href="/register"
                      className="rounded-xl bg-primary py-2.5 text-center text-sm font-semibold text-primary-foreground"
                      onClick={() => setOpen(false)}
                    >
                      Get started
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
