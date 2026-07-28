import { requireStep } from "@/lib/gating";
import { getCapturePreview, listSamples } from "@/lib/api";
import { CaptureClient } from "./CaptureClient";

export default async function CapturePage(props: PageProps<"/jobs/[jobId]/capture">) {
  const { jobId } = await props.params;
  await requireStep(jobId, "capture");
  const [samples, preview] = await Promise.all([listSamples(), getCapturePreview(jobId)]);

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Capture</h1>
      <p className="mt-1 text-sm text-zinc-600">
        Pick a photo of the room and we&apos;ll detect and measure the furniture in it.
      </p>
      <CaptureClient jobId={jobId} samples={samples} hasExistingCapture={preview !== null} />
    </div>
  );
}
