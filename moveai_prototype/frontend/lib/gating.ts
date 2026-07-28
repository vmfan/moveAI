import { notFound, redirect } from "next/navigation";
import { getJob, type Job } from "./api";

export const STEPS = ["intake", "capture", "inventory", "quote", "booking"] as const;
export type Step = (typeof STEPS)[number];

export const STEP_LABELS: Record<Step, string> = {
  intake: "Intake",
  capture: "Capture",
  inventory: "Inventory Review",
  quote: "Quote",
  booking: "Booking",
};

// db.py JOB_STATUSES: intake -> capture -> inventory_review -> quoted -> booked | cancelled.
// A job's status names the furthest step it has reached; booked/cancelled are terminal and
// leave every step reachable (there is nothing further to gate against).
const STATUS_TO_STEP_INDEX: Record<string, number> = {
  intake: 0,
  capture: 1,
  inventory_review: 2,
  quoted: 3,
  booked: 4,
  cancelled: 4,
};

export function furthestAllowedIndex(status: string): number {
  return STATUS_TO_STEP_INDEX[status] ?? 0;
}

/**
 * Fetches the job and, if `step` is further along than the job's status allows,
 * issues a real server-side redirect to the furthest step the job has actually reached.
 * Call this at the top of every gated page — the layout only renders shared chrome.
 */
export async function requireStep(jobId: string, step: Step): Promise<Job> {
  const job = await getJob(jobId);
  if (!job) notFound();

  const allowed = furthestAllowedIndex(job.status);
  const wanted = STEPS.indexOf(step);
  if (wanted > allowed) {
    redirect(`/jobs/${jobId}/${STEPS[allowed]}`);
  }
  return job;
}
