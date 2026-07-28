"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  getQuote,
  getQuoteVersions,
  regenerateQuote,
  type Intake,
  type QuoteResponse,
} from "@/lib/api";

const BASIS_LABEL: Record<string, string> = {
  measured: "Measured — our estimate, our risk if it's wrong",
  prior_assisted: "Estimated from typical dimensions — our estimate, our risk if it's wrong",
  declared: "You supplied this — a day-of surcharge applies if it's wrong",
};

export function QuoteClient({
  jobId,
  initial,
  intake,
}: {
  jobId: string;
  initial: QuoteResponse;
  intake: Intake | null;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["quote", jobId];
  const versionsKey = ["quote-versions", jobId];

  const { data } = useQuery({
    queryKey,
    queryFn: () => getQuote(jobId),
    initialData: initial,
  });

  const { data: versions } = useQuery({
    queryKey: versionsKey,
    queryFn: () => getQuoteVersions(jobId),
  });

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateQuote(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: versionsKey });
    },
  });

  const { quote, lines, staff_review_reasons: reasons, stale, version } = data;

  return (
    <div className="mt-6 flex flex-col gap-8">
      {stale && (
        <section className="rounded-lg border border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-900">
            Your inventory has changed since quote version {version}. The numbers below are a
            preview of what a new quote would look like — regenerate to make it official.
          </p>
          <button
            type="button"
            className="mt-3 rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending}
          >
            {regenerateMutation.isPending ? "Regenerating…" : "Regenerate quote"}
          </button>
          {regenerateMutation.error && (
            <p className="mt-2 text-sm text-red-600">{regenerateMutation.error.message}</p>
          )}
        </section>
      )}

      {reasons.length > 0 && (
        <section className="rounded-lg border border-amber-300 bg-amber-50 p-4">
          <h2 className="text-sm font-medium text-amber-900">This job needs a staff look before booking</h2>
          <ul className="mt-2 list-disc pl-5 text-sm text-amber-800">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-amber-700">
            You can still request a booking — this won&apos;t cost you anything, it just means our
            team reviews the job before confirming it.
          </p>
        </section>
      )}

      <section className="rounded-lg border border-zinc-200 p-5">
        <p className="text-3xl font-semibold text-zinc-900">
          HK${quote.total_price.toFixed(0)}
        </p>
        <p className="mt-1 text-sm text-zinc-600">
          {version != null && `Version ${version}`}
          {quote.recommended_truck && ` · Recommended truck: ${quote.recommended_truck}`}
        </p>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-zinc-500">Raw estimated volume</dt>
            <dd className="text-zinc-900">{quote.total_volume_m3.toFixed(2)} m³</dd>
          </div>
          <div>
            <dt className="text-zinc-500">
              Quoted volume (+{(quote.volume_margin_fraction * 100).toFixed(0)}% margin)
            </dt>
            <dd className="text-zinc-900">{quote.upper_bound_volume_m3.toFixed(2)} m³</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Access multiplier</dt>
            <dd className="text-zinc-900">{quote.access_multiplier.toFixed(2)}×</dd>
          </div>
        </dl>
        <p className="mt-2 text-xs text-zinc-500">
          We price from the upper end of our volume estimate, once — that margin is the only
          conservatism added on top of what was measured.
        </p>

        {intake && (
          <div className="mt-4 border-t border-zinc-100 pt-3 text-xs text-zinc-500">
            <p>
              Origin: floor {intake.origin_floor}, {intake.origin_has_lift ? "lift available" : "no lift"},{" "}
              {intake.origin_parking_distance_m}m parking distance
            </p>
            <p>
              Destination: floor {intake.destination_floor},{" "}
              {intake.destination_has_lift ? "lift available" : "no lift"},{" "}
              {intake.destination_parking_distance_m}m parking distance
            </p>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-medium text-zinc-900">Line items</h2>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                <th className="py-2 pr-4">Item</th>
                <th className="py-2 pr-4">Room</th>
                <th className="py-2 pr-4">Volume (quoted)</th>
                <th className="py-2 pr-4">Price</th>
                <th className="py-2">Basis</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => (
                <tr key={line.inventory_item_id} className="border-b border-zinc-100">
                  <td className="py-2 pr-4 text-zinc-900">{line.label}</td>
                  <td className="py-2 pr-4 text-zinc-600">{line.room_label ?? "—"}</td>
                  <td className="py-2 pr-4 text-zinc-600">{line.volume_m3.toFixed(3)} m³</td>
                  <td className="py-2 pr-4 text-zinc-600">HK${line.price_component.toFixed(0)}</td>
                  <td className="py-2 text-xs text-zinc-500">{BASIS_LABEL[line.measurement_basis]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {(quote.escalated_item_ids.length > 0 || quote.unmeasured_item_ids.length > 0) && (
        <section className="rounded-lg border border-zinc-200 p-4 text-sm">
          <h2 className="font-medium text-zinc-900">Not included in this price yet</h2>
          {quote.escalated_item_ids.length > 0 && (
            <p className="mt-1 text-zinc-600">
              {quote.escalated_item_ids.length} item(s) are under staff review and aren&apos;t priced
              yet.
            </p>
          )}
          {quote.unmeasured_item_ids.length > 0 && (
            <p className="mt-1 text-zinc-600">
              {quote.unmeasured_item_ids.length} item(s) have no resolvable volume yet.
            </p>
          )}
        </section>
      )}

      <section className="rounded-lg border border-zinc-200 p-4 text-sm text-zinc-600">
        <h2 className="font-medium text-zinc-900">Day-of surcharge</h2>
        <p className="mt-1">
          Quantities you supplied yourself — boxed goods, manually added items, or a correction you
          made — are covered by a day-of surcharge if the actual amount is significantly more than
          what you told us: roughly +20% of the total if it&apos;s over by more than 20%, and
          +30–50% if it&apos;s over by more than 50%. Anything we measured from your photos is our
          estimate and our risk — it never triggers a surcharge.
        </p>
      </section>

      {versions && versions.length > 1 && (
        <section>
          <h2 className="text-sm font-medium text-zinc-900">Version history</h2>
          <table className="mt-2 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                <th className="py-2 pr-4">Version</th>
                <th className="py-2 pr-4">Total price</th>
                <th className="py-2 pr-4">Created</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {versions
                .slice()
                .reverse()
                .map((v) => (
                  <tr key={v.id} className="border-b border-zinc-100">
                    <td className="py-2 pr-4 text-zinc-900">{v.version}</td>
                    <td className="py-2 pr-4 text-zinc-600">HK${v.total_price.toFixed(0)}</td>
                    <td className="py-2 pr-4 text-zinc-600">{v.created_at}</td>
                    <td className="py-2 text-zinc-600">
                      {v.is_superseded ? "Superseded" : "Active"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}

      <footer className="flex items-center justify-end border-t border-zinc-200 pt-4">
        <Link
          href={`/jobs/${jobId}/booking`}
          className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700"
        >
          Continue to booking
        </Link>
      </footer>
    </div>
  );
}
