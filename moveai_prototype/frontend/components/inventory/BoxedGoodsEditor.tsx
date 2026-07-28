"use client";

import { useState } from "react";
import type { InventoryItem } from "@/lib/api";

export function BoxedGoodsEditor({
  item,
  onSetCount,
}: {
  item: InventoryItem | undefined;
  onSetCount: (id: number, count: number) => void;
}) {
  const [count, setCount] = useState(item?.quantity ?? 0);

  if (!item) return null;

  return (
    <section className="flex flex-col gap-2 rounded-lg border border-zinc-200 p-4">
      <h2 className="text-sm font-medium text-zinc-900">Boxed goods</h2>
      <p className="text-xs text-zinc-500">
        We estimate a box count based on your storage furniture and room count. Adjust it if you
        know better &mdash; this number is what you&apos;re confirming, and a day-of mismatch is
        billed against what you enter here, not our estimate.
      </p>
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          onSetCount(item.id, count);
        }}
      >
        <label className="flex flex-col gap-1 text-xs text-zinc-700">
          Box count
          <input
            type="number"
            min={0}
            className="input"
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
          />
        </label>
        <button type="submit" className="rounded-full bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white">
          Update count
        </button>
        {!item.customer_confirmed && (
          <span className="text-xs text-amber-700">Not yet confirmed &mdash; awaiting your review.</span>
        )}
      </form>
      {item.boxed_goods_seed_json && (
        <details className="text-xs text-zinc-500">
          <summary className="cursor-pointer">How was this estimated?</summary>
          <pre className="mt-2 overflow-x-auto rounded bg-zinc-50 p-2">
            {JSON.stringify(item.boxed_goods_seed_json, null, 2)}
          </pre>
        </details>
      )}
    </section>
  );
}
