import { requireStep } from "@/lib/gating";
import { getBooking } from "@/lib/api";
import { BookingClient } from "./BookingClient";

export default async function BookingPage(props: PageProps<"/jobs/[jobId]/booking">) {
  const { jobId } = await props.params;
  await requireStep(jobId, "booking");
  const booking = await getBooking(jobId);

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Booking</h1>
      <p className="mt-1 text-sm text-zinc-600">
        Request a booking, or reply if our team needs a clarification from you.
      </p>
      <BookingClient jobId={jobId} initial={booking} />
    </div>
  );
}
