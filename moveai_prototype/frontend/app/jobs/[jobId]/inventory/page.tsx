import { requireStep } from "@/lib/gating";
import { getInventory } from "@/lib/api";
import { InventoryReviewClient } from "./InventoryReviewClient";

export default async function InventoryPage(props: PageProps<"/jobs/[jobId]/inventory">) {
  const { jobId } = await props.params;
  await requireStep(jobId, "inventory");
  const inventory = await getInventory(jobId);

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Inventory Review</h1>
      <p className="mt-1 text-sm text-zinc-600">
        Check what we found, confirm anything we flagged, and add whatever we missed.
      </p>
      <InventoryReviewClient jobId={jobId} initial={inventory} />
    </div>
  );
}
