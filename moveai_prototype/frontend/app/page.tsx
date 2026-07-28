"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createJob } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startJob() {
    setPending(true);
    setError(null);
    try {
      const job = await createJob();
      router.push(`/jobs/${job.id}/intake`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job.");
      setPending(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-zinc-50 px-6 text-center">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">MoveAI</h1>
        <p className="mt-2 max-w-md text-zinc-600">
          Capture your space once and get a measured inventory and quote.
        </p>
      </div>
      <button
        type="button"
        onClick={startJob}
        disabled={pending}
        className="rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50"
      >
        {pending ? "Starting..." : "Start a new job"}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
