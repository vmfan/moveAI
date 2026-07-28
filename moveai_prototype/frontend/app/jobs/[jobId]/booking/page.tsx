import { requireStep } from "@/lib/gating";

export default async function BookingPage(props: PageProps<"/jobs/[jobId]/booking">) {
  const { jobId } = await props.params;
  const job = await requireStep(jobId, "booking");

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Booking</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Job status: <code>{job.status}</code>. Booking submission and clarification UI are Build
        12&apos;s scope.
      </p>
    </div>
  );
}
