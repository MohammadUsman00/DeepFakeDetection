import React from "react";
import Link from "next/link";
import { Shield } from "lucide-react";

export function LandingFooter() {
  return (
    <footer className="bg-background">
      <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <div className="flex flex-col gap-10 border-t border-border/60 pt-10 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="h-6 w-6 text-primary" aria-hidden />
              <span className="font-semibold">DeepShield</span>
            </div>
            <p className="mt-3 max-w-sm text-sm text-muted-foreground">
              Face-focused deepfake screening with explainable overlays. Built for researchers, analysts, and product
              teams evaluating media authenticity.
            </p>
          </div>
          <div className="flex flex-wrap gap-8 text-sm">
            <div>
              <p className="font-semibold text-foreground">Product</p>
              <ul className="mt-3 space-y-2 text-muted-foreground">
                <li>
                  <a href="#analyzer" className="hover:text-foreground">
                    Analyzer
                  </a>
                </li>
                <li>
                  <a href="#features" className="hover:text-foreground">
                    Features
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <p className="font-semibold text-foreground">Account</p>
              <ul className="mt-3 space-y-2 text-muted-foreground">
                <li>
                  <Link href="/login" className="hover:text-foreground">
                    Sign in
                  </Link>
                </li>
                <li>
                  <Link href="/register" className="hover:text-foreground">
                    Register
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="font-semibold text-foreground">Developers</p>
              <ul className="mt-3 space-y-2 text-muted-foreground">
                <li>
                  <a href="/api/docs" className="hover:text-foreground" target="_blank" rel="noreferrer">
                    API docs
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
        <p className="mt-12 text-center text-[11px] text-muted-foreground/70">
          © {new Date().getFullYear()} DeepShield · Not legal evidence · Research & educational use
        </p>
      </div>
    </footer>
  );
}
