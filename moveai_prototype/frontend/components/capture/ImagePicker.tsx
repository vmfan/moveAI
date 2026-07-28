"use client";

import type { Sample } from "@/lib/api";

export function ImagePicker({
  samples,
  value,
  onChange,
}: {
  samples: Sample[];
  value: string | null;
  onChange: (name: string) => void;
}) {
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
      {samples.map((sample) => {
        const selected = sample.name === value;
        return (
          <button
            key={sample.name}
            type="button"
            onClick={() => onChange(sample.name)}
            className={`overflow-hidden rounded-lg border text-left transition-colors ${
              selected ? "border-zinc-900 ring-2 ring-zinc-900" : "border-zinc-200 hover:border-zinc-400"
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={sample.url} alt={sample.name} className="aspect-square w-full object-cover" />
            <p className="truncate px-1 py-1 text-[10px] text-zinc-500">{sample.name}</p>
          </button>
        );
      })}
    </div>
  );
}
