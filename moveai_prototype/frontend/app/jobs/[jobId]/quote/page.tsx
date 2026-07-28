import { requireStep } from "@/lib/gating";
import { getIntake, getQuote } from "@/lib/api";
import { QuoteClient } from "./QuoteClient";

export default async function QuotePage(props: PageProps<"/jobs/[jobId]/quote">) {
  const { jobId } = await props.params;
  await requireStep(jobId, "quote");
  const [quote, intake] = await Promise.all([getQuote(jobId), getIntake(jobId)]);

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Quote</h1>
      <p className="mt-1 text-sm text-zinc-600">
        Your price, based on the upper end of our volume estimate so there are no surprises later.
      </p>
      <QuoteClient jobId={jobId} initial={quote} intake={intake} />
    </div>
  );
}
