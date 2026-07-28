import { requireStep } from "@/lib/gating";

export default async function CapturePage(props: PageProps<"/jobs/[jobId]/capture">) {
  const { jobId } = await props.params;
  const job = await requireStep(jobId, "capture");

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Capture</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Job status: <code>{job.status}</code>. Photo/video capture and the AI pipeline are wired
        up in Build 10-11 — this page exists so Build 9 has a real gated destination to prove the
        server-side redirect against.
      </p>
    </div>
  );
}
