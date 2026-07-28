import { requireStep } from "@/lib/gating";

export default async function QuotePage(props: PageProps<"/jobs/[jobId]/quote">) {
  const { jobId } = await props.params;
  const job = await requireStep(jobId, "quote");

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Quote</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Job status: <code>{job.status}</code>. Pricing, truck recommendation, and versioning UI
        are Build 12&apos;s scope.
      </p>
    </div>
  );
}
