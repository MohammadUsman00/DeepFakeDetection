"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setToken } from "@/lib/auth";
import { Shield, ArrowLeft } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : Array.isArray(data?.detail) ? data.detail[0]?.msg : null;
        setError(data?.error?.message || detail || "Login failed");
        setLoading(false);
        return;
      }
      setToken(data.access_token);
      router.push("/");
      router.refresh();
    } catch {
      setError("Network error");
    }
    setLoading(false);
  };

  return (
    <div className="relative min-h-screen bg-background bg-app-mesh">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(16,185,129,0.12),transparent)]" />
      <div className="relative mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-12">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to DeepShield
        </Link>
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 ring-1 ring-white/10">
            <Shield className="h-6 w-6 text-primary" />
          </span>
          <div>
            <span className="text-xl font-semibold tracking-tight">DeepShield</span>
            <p className="text-xs text-muted-foreground">Sign in to your account</p>
          </div>
        </div>
        <form
          onSubmit={submit}
          className="rounded-2xl border border-border/80 bg-card/40 p-8 shadow-2xl backdrop-blur-xl"
        >
          <h1 className="mb-6 text-lg font-semibold">Welcome back</h1>
          {error && (
            <p className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive-foreground">
              {error}
            </p>
          )}
          <label className="block text-sm font-medium text-muted-foreground">Email</label>
          <input
            type="email"
            required
            autoComplete="email"
            className="mb-4 mt-1.5 w-full rounded-xl border border-border bg-background/80 px-3 py-2.5 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-primary/50"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <label className="block text-sm font-medium text-muted-foreground">Password</label>
          <input
            type="password"
            required
            autoComplete="current-password"
            className="mb-6 mt-1.5 w-full rounded-xl border border-border bg-background/80 px-3 py-2.5 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-primary/50"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Continue"}
          </button>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            No account?{" "}
            <Link href="/register" className="font-medium text-primary hover:underline">
              Register
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
