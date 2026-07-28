import Link from "next/link";
import { notFound } from "next/navigation";
import { getJob } from "@/lib/api";
import { furthestAllowedIndex, STEPS, STEP_LABELS } from "@/lib/gating";

export default async function JobLayout(props: LayoutProps<"/jobs/[jobId]">) {
  const { jobId } = await props.params;
  const job = await getJob(jobId);
  if (!job) notFound();

  const allowed = furthestAllowedIndex(job.status);

  return (
    <div className="flex flex-1 flex-col bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div>
            <p className="text-sm text-zinc-500">Job #{job.id}</p>
            <p className="text-xs uppercase tracking-wide text-zinc-400">status: {job.status}</p>
          </div>
          <nav className="flex gap-4 text-sm">
            {STEPS.map((step, index) => {
              const unlocked = index <= allowed;
              return unlocked ? (
                <Link
                  key={step}
                  href={`/jobs/${jobId}/${step}`}
                  className="text-zinc-700 hover:text-zinc-900 hover:underline"
                >
                  {STEP_LABELS[step]}
                </Link>
              ) : (
                <span key={step} className="text-zinc-300" title="Locked">
                  {STEP_LABELS[step]}
                </span>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">{props.children}</main>
    </div>
  );
}
