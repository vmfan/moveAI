"use client";

import { useState } from "react";
import type { InventoryItem } from "@/lib/api";

export function NeedsConfirmationSection({
  items,
  onConfirm,
  onCorrect,
  onRemove,
}: {
  items: InventoryItem[];
  onConfirm: (id: number) => void;
  onCorrect: (id: number, fields: { width_m: number; height_m: number; depth_m: number }) => void;
  onRemove: (id: number) => void;
}) {
  if (items.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-zinc-900">Needs your confirmation</h2>
      <p className="text-xs text-zinc-500">
        We measured these but want you to double-check them before they enter your quote.
      </p>
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <ConfirmRow key={item.id} item={item} onConfirm={onConfirm} onCorrect={onCorrect} onRemove={onRemove} />
        ))}
      </ul>
    </section>
  );
}

function ConfirmRow({
  item,
  onConfirm,
  onCorrect,
  onRemove,
}: {
  item: InventoryItem;
  onConfirm: (id: number) => void;
  onCorrect: (id: number, fields: { width_m: number; height_m: number; depth_m: number }) => void;
  onRemove: (id: number) => void;
}) {
  const [correcting, setCorrecting] = useState(false);
  const [width, setWidth] = useState(item.width_m ?? 0);
  const [height, setHeight] = useState(item.height_m ?? 0);
  const [depth, setDepth] = useState(item.depth_m ?? 0);

  return (
    <li className="rounded-lg border border-amber-200 bg-amber-50 p-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-zinc-900">{item.label}</p>
          <p className="text-xs text-zinc-500">
            {item.room_label ?? "Unassigned room"} &middot;{" "}
            {item.width_m?.toFixed(2) ?? "?"} x {item.height_m?.toFixed(2) ?? "?"} x{" "}
            {item.depth_m?.toFixed(2) ?? "?"} m
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-white hover:bg-zinc-700"
            onClick={() => onConfirm(item.id)}
          >
            Confirm
          </button>
          <button
            type="button"
            className="rounded-full border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100"
            onClick={() => setCorrecting((v) => !v)}
          >
            Correct
          </button>
          <button
            type="button"
            className="rounded-full border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
            onClick={() => onRemove(item.id)}
          >
            Remove
          </button>
        </div>
      </div>

      {correcting && (
        <form
          className="mt-3 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onCorrect(item.id, { width_m: width, height_m: height, depth_m: depth });
            setCorrecting(false);
          }}
        >
          <label className="flex flex-col gap-1 text-xs text-zinc-700">
            Width (m)
            <input
              type="number"
              step="0.01"
              className="input"
              value={width}
              onChange={(e) => setWidth(Number(e.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-700">
            Height (m)
            <input
              type="number"
              step="0.01"
              className="input"
              value={height}
              onChange={(e) => setHeight(Number(e.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-700">
            Depth (m)
            <input
              type="number"
              step="0.01"
              className="input"
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
            />
          </label>
          <button type="submit" className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-white">
            Save correction
          </button>
        </form>
      )}
      {item.review_reason && <p className="mt-2 text-xs text-amber-700">{item.review_reason}</p>}
    </li>
  );
}
