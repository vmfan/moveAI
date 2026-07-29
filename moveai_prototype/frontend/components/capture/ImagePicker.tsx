"use client";

import type { Sample } from "@/lib/api";

export function ImagePicker({
  samples,
  value,
  onChange,
}: {
  samples: Sample[];
  value: string[];
  onChange: (names: string[]) => void;
}) {
  function toggle(name: string) {
    onChange(value.includes(name) ? value.filter((n) => n !== name) : [...value, name]);
  }

  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <p className="text-xs text-zinc-500">
          {value.length} photo{value.length === 1 ? "" : "s"} selected
        </p>
      )}
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
        {samples.map((sample) => {
          const selected = value.includes(sample.name);
          return (
            <button
              key={sample.name}
              type="button"
              onClick={() => toggle(sample.name)}
              className={`relative overflow-hidden rounded-lg border text-left transition-colors ${
                selected ? "border-zinc-900 ring-2 ring-zinc-900" : "border-zinc-200 hover:border-zinc-400"
              }`}
            >
              {selected && (
                <span className="absolute right-1 top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[10px] font-medium text-white">
                  {value.indexOf(sample.name) + 1}
                </span>
              )}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={sample.url} alt={sample.name} className="aspect-square w-full object-cover" />
              <p className="truncate px-1 py-1 text-[10px] text-zinc-500">{sample.name}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
