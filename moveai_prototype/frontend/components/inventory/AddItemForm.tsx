"use client";

import { useState } from "react";
import type { DeclaredItemInput } from "@/lib/api";

const EMPTY: DeclaredItemInput = {
  label: "",
  room_label: "",
  quantity: 1,
  width_m: 0,
  height_m: 0,
  depth_m: 0,
};

export function AddItemForm({ onAdd }: { onAdd: (fields: DeclaredItemInput) => void }) {
  const [fields, setFields] = useState<DeclaredItemInput>(EMPTY);

  function set<K extends keyof DeclaredItemInput>(key: K, value: DeclaredItemInput[K]) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-4">
      <h2 className="text-sm font-medium text-zinc-900">Add something we missed</h2>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          onAdd(fields);
          setFields(EMPTY);
        }}
      >
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Item
          <input
            required
            className="input"
            value={fields.label}
            onChange={(e) => set("label", e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Room
          <input
            className="input"
            value={fields.room_label ?? ""}
            onChange={(e) => set("room_label", e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Quantity
          <input
            type="number"
            min={1}
            className="input"
            value={fields.quantity ?? 1}
            onChange={(e) => set("quantity", Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Width (m)
          <input
            required
            type="number"
            step="0.01"
            className="input"
            value={fields.width_m}
            onChange={(e) => set("width_m", Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Height (m)
          <input
            required
            type="number"
            step="0.01"
            className="input"
            value={fields.height_m}
            onChange={(e) => set("height_m", Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Depth (m)
          <input
            required
            type="number"
            step="0.01"
            className="input"
            value={fields.depth_m}
            onChange={(e) => set("depth_m", Number(e.target.value))}
          />
        </label>
        <button type="submit" className="rounded-full bg-zinc-900 px-4 py-2 text-xs font-medium text-white">
          Add item
        </button>
      </form>
    </section>
  );
}
