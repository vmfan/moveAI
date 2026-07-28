"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  decideBooking,
  listConsoleBookings,
  type BookingStatus,
  type ConsoleBookingRow,
} from "@/lib/api";

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "pending_staff_review", label: "Pending staff review" },
  { value: "confirmed", label: "Confirmed" },
  { value: "needs_customer_clarification", label: "Needs customer reply" },
  { value: "cancelled", label: "Cancelled" },
];

export function ConsoleClient({ initial }: { initial: ConsoleBookingRow[] }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const queryKey = ["console-bookings", status];

  const { data, isFetching } = useQuery({
    queryKey,
    queryFn: () => listConsoleBookings(status || null),
    initialData: status === "" ? initial : undefined,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["console-bookings"] });
  }

  const decisionMutation = useMutation({
    mutationFn: ({
      bookingId,
      newStatus,
      staffNote,
    }: {
      bookingId: number;
      newStatus: BookingStatus;
      staffNote?: string | null;
    }) => decideBooking(bookingId, newStatus, staffNote),
    onSuccess: invalidate,
  });

  const rows = data ?? [];

  return (
    <div className="mt-6 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <label htmlFor="status-filter" className="text-sm text-zinc-600">
          Filter by status
        </label>
        <select
          id="status-filter"
          className="rounded-md border border-zinc-300 px-2 py-1 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {isFetching && <span className="text-xs text-zinc-400">Refreshing…</span>}
      </div>

      {decisionMutation.error && (
        <p className="text-sm text-red-600">{decisionMutation.error.message}</p>
      )}

      {rows.length === 0 && <p className="text-sm text-zinc-500">No bookings found.</p>}

      <ul className="flex flex-col gap-4">
        {rows.map((row) => (
          <ConsoleRow
            key={row.booking.id}
            row={row}
            onDecide={(newStatus, staffNote) =>
              decisionMutation.mutate({ bookingId: row.booking.id, newStatus, staffNote })
            }
          />
        ))}
      </ul>
    </div>
  );
}

function ConsoleRow({
  row,
  onDecide,
}: {
  row: ConsoleBookingRow;
  onDecide: (status: BookingStatus, staffNote?: string | null) => void;
}) {
  const { booking, intake, reasons, pinned_quote_superseded: pinnedSuperseded } = row;
  const [asking, setAsking] = useState(false);
  const [staffNote, setStaffNote] = useState("");

  return (
    <li className="rounded-lg border border-zinc-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-zinc-900">
            Job #{booking.job_id} · Booking #{booking.id} · {booking.status}
          </p>
          {intake && (
            <p className="text-xs text-zinc-500">
              {intake.contact_name} · {intake.contact_email}
              {intake.contact_phone ? ` · ${intake.contact_phone}` : ""}
            </p>
          )}
          {intake && (
            <p className="mt-1 text-xs text-zinc-500">
              {intake.origin_address} → {intake.destination_address}
            </p>
          )}
          <p className="mt-1 text-xs text-zinc-500">
            {booking.total_price != null ? `HK$${booking.total_price.toFixed(0)}` : "No price"}
            {booking.recommended_truck ? ` · ${booking.recommended_truck}` : ""}
          </p>
        </div>
        <Link
          href={`/jobs/${booking.job_id}`}
          className="rounded-full border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100"
        >
          Open this job
        </Link>
      </div>

      {pinnedSuperseded && (
        <p className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-800">
          The customer&apos;s active quote has changed since this booking was requested.
        </p>
      )}

      {reasons.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-amber-700">
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      {booking.customer_note && (
        <p className="mt-2 text-xs text-zinc-600">
          <span className="uppercase tracking-wide text-zinc-500">Customer note: </span>
          {booking.customer_note}
        </p>
      )}
      {booking.staff_note && (
        <p className="mt-1 text-xs text-zinc-600">
          <span className="uppercase tracking-wide text-zinc-500">Staff note: </span>
          {booking.staff_note}
        </p>
      )}

      {booking.status !== "confirmed" && booking.status !== "cancelled" && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-white hover:bg-zinc-700"
            onClick={() => onDecide("confirmed")}
          >
            Confirm
          </button>
          <button
            type="button"
            className="rounded-full border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100"
            onClick={() => setAsking((v) => !v)}
          >
            Ask customer
          </button>
          <button
            type="button"
            className="rounded-full border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
            onClick={() => onDecide("cancelled")}
          >
            Cancel
          </button>
        </div>
      )}

      {asking && (
        <form
          className="mt-3 flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onDecide("needs_customer_clarification", staffNote);
            setAsking(false);
            setStaffNote("");
          }}
        >
          <textarea
            className="min-h-16 rounded-md border border-zinc-300 p-2 text-xs"
            placeholder="What do you need clarified?"
            value={staffNote}
            onChange={(e) => setStaffNote(e.target.value)}
          />
          <button
            type="submit"
            className="self-start rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-white"
          >
            Send
          </button>
        </form>
      )}
    </li>
  );
}
