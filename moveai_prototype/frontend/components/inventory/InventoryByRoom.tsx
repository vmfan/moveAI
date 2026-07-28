"use client";

import type { InventoryItem } from "@/lib/api";

export function InventoryByRoom({
  items,
  onRemove,
}: {
  items: InventoryItem[];
  onRemove: (id: number) => void;
}) {
  const byRoom = new Map<string, InventoryItem[]>();
  for (const item of items) {
    const room = item.room_label ?? "Unassigned room";
    byRoom.set(room, [...(byRoom.get(room) ?? []), item]);
  }

  if (items.length === 0) {
    return (
      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium text-zinc-900">Your inventory</h2>
        <p className="text-xs text-zinc-500">Nothing confirmed yet.</p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-sm font-medium text-zinc-900">Your inventory</h2>
      {Array.from(byRoom.entries()).map(([room, roomItems]) => (
        <div key={room} className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">{room}</h3>
          <ul className="flex flex-col gap-1">
            {roomItems.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm"
              >
                <div>
                  <span className="font-medium text-zinc-900">{item.label}</span>
                  <span className="ml-2 text-xs text-zinc-500">
                    {item.width_m?.toFixed(2) ?? "?"} x {item.height_m?.toFixed(2) ?? "?"} x{" "}
                    {item.depth_m?.toFixed(2) ?? "?"} m &middot; {item.measurement_basis}
                  </span>
                </div>
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline"
                  onClick={() => onRemove(item.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
