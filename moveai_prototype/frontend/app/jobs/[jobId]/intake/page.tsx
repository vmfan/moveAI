import { requireStep } from "@/lib/gating";
import { getIntake } from "@/lib/api";
import { IntakeForm } from "./IntakeForm";

export default async function IntakePage(props: PageProps<"/jobs/[jobId]/intake">) {
  const { jobId } = await props.params;
  await requireStep(jobId, "intake");
  const existing = await getIntake(jobId);

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Intake</h1>
      <p className="mt-1 text-sm text-zinc-600">
        Tell us about the move so we can price access correctly.
      </p>
      <IntakeForm jobId={jobId} initial={existing} />
    </div>
  );
}
