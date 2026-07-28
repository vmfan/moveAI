"use client";

import type { InventoryItem } from "@/lib/api";

export function StaffEscalatedSection({ items }: { items: InventoryItem[] }) {
  if (items.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-zinc-900">Being reviewed by our team</h2>
      <p className="text-xs text-zinc-500">
        These need a closer look from us before they&apos;re priced &mdash; nothing for you to do here.
      </p>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.id} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm">
            <p className="font-medium text-zinc-900">{item.label}</p>
            <p className="text-xs text-zinc-500">{item.room_label ?? "Unassigned room"}</p>
            {(item.review_reason || item.measurement_error) && (
              <p className="mt-1 text-xs text-zinc-500">
                {item.review_reason ?? item.measurement_error}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
