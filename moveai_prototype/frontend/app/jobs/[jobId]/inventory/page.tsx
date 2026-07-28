import { requireStep } from "@/lib/gating";

export default async function InventoryPage(props: PageProps<"/jobs/[jobId]/inventory">) {
  const { jobId } = await props.params;
  const job = await requireStep(jobId, "inventory");

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Inventory Review</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Job status: <code>{job.status}</code>. The confirm/correct/boxed-goods review UI is Build
        11&apos;s scope.
      </p>
    </div>
  );
}
