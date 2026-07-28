import { redirect } from "next/navigation";
import { getJob } from "@/lib/api";
import { furthestAllowedIndex, STEPS } from "@/lib/gating";

export default async function JobIndexPage(props: PageProps<"/jobs/[jobId]">) {
  const { jobId } = await props.params;
  const job = await getJob(jobId);
  const step = job ? STEPS[furthestAllowedIndex(job.status)] : "intake";
  redirect(`/jobs/${jobId}/${step}`);
}
