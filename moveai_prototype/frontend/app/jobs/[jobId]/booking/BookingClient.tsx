"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  getBooking,
  resubmitBooking,
  submitBooking,
  type BookingStatusResponse,
} from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  pending_staff_review: "Pending staff review",
  confirmed: "Confirmed",
  needs_customer_clarification: "Needs your reply",
  cancelled: "Cancelled",
};

export function BookingClient({
  jobId,
  initial,
}: {
  jobId: string;
  initial: BookingStatusResponse;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["booking", jobId];

  const { data } = useQuery({
    queryKey,
    queryFn: () => getBooking(jobId),
    initialData: initial,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey });
  }

  const [note, setNote] = useState("");
  const submitMutation = useMutation({
    mutationFn: (customerNote: string) => submitBooking(jobId, customerNote || null),
    onSuccess: () => {
      setNote("");
      invalidate();
    },
  });

  const [reply, setReply] = useState("");
  const resubmitMutation = useMutation({
    mutationFn: (customerNote: string) => resubmitBooking(jobId, customerNote || null),
    onSuccess: () => {
      setReply("");
      invalidate();
    },
  });

  const { booking, blockers } = data;

  return (
    <div className="mt-6 flex flex-col gap-6">
      {(submitMutation.error || resubmitMutation.error) && (
        <p className="text-sm text-red-600">
          {(submitMutation.error ?? resubmitMutation.error)?.message}
        </p>
      )}

      {blockers.length > 0 && (
        <section className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm">
          <p className="font-medium text-amber-900">You can&apos;t request a booking yet</p>
          <ul className="mt-2 list-disc pl-5 text-amber-800">
            {blockers.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <Link
            href={`/jobs/${jobId}/quote`}
            className="mt-3 inline-block rounded-full bg-zinc-900 px-4 py-2 text-xs font-medium text-white hover:bg-zinc-700"
          >
            Back to quote
          </Link>
        </section>
      )}

      {booking && (
        <section className="rounded-lg border border-zinc-200 p-4 text-sm">
          <p className="font-medium text-zinc-900">
            Status: {STATUS_LABEL[booking.status] ?? booking.status}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            Requested {booking.created_at} · Last updated {booking.updated_at}
          </p>
          {booking.customer_note && (
            <p className="mt-2 text-zinc-600">
              <span className="text-xs uppercase tracking-wide text-zinc-500">Your note: </span>
              {booking.customer_note}
            </p>
          )}
          {booking.staff_note && (
            <p className="mt-2 text-zinc-600">
              <span className="text-xs uppercase tracking-wide text-zinc-500">
                Message from our team:{" "}
              </span>
              {booking.staff_note}
            </p>
          )}
        </section>
      )}

      {booking?.status === "needs_customer_clarification" && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            resubmitMutation.mutate(reply);
          }}
        >
          <label className="text-sm font-medium text-zinc-900" htmlFor="reply">
            Your reply
          </label>
          <textarea
            id="reply"
            className="min-h-24 rounded-md border border-zinc-300 p-2 text-sm"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
          />
          <button
            type="submit"
            className="self-start rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
            disabled={resubmitMutation.isPending}
          >
            {resubmitMutation.isPending ? "Sending…" : "Send reply"}
          </button>
        </form>
      )}

      {blockers.length === 0 && (!booking || booking.status === "cancelled") && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submitMutation.mutate(note);
          }}
        >
          <label className="text-sm font-medium text-zinc-900" htmlFor="note">
            Anything you&apos;d like our team to know? (optional)
          </label>
          <textarea
            id="note"
            className="min-h-24 rounded-md border border-zinc-300 p-2 text-sm"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            type="submit"
            className="self-start rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
            disabled={submitMutation.isPending}
          >
            {submitMutation.isPending ? "Requesting…" : "Request booking"}
          </button>
        </form>
      )}
    </div>
  );
}
