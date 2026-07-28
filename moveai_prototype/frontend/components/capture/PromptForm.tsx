"use client";

export type PromptFields = {
  furnitureClassesText: string;
  roomLabel: string;
  boxThreshold: number;
  maxDetections: number;
};

export const DEFAULT_PROMPT_FIELDS: PromptFields = {
  furnitureClassesText: "",
  roomLabel: "",
  boxThreshold: 0.3,
  maxDetections: 8,
};

export function PromptForm({
  value,
  onChange,
}: {
  value: PromptFields;
  onChange: (fields: PromptFields) => void;
}) {
  function set<K extends keyof PromptFields>(key: K, v: PromptFields[K]) {
    onChange({ ...value, [key]: v });
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-zinc-700">
        Room label
        <input
          className="input"
          placeholder="e.g. Living room"
          value={value.roomLabel}
          onChange={(e) => set("roomLabel", e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-zinc-700">
        Furniture classes to look for (comma-separated, optional — defaults used if blank)
        <input
          className="input"
          placeholder="e.g. sofa, coffee table, bookshelf"
          value={value.furnitureClassesText}
          onChange={(e) => set("furnitureClassesText", e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-zinc-700">
        Detection threshold ({value.boxThreshold.toFixed(2)})
        <input
          type="range"
          min={0.1}
          max={0.9}
          step={0.05}
          value={value.boxThreshold}
          onChange={(e) => set("boxThreshold", Number(e.target.value))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-zinc-700">
        Max detections
        <input
          type="number"
          min={1}
          max={30}
          className="input"
          value={value.maxDetections}
          onChange={(e) => set("maxDetections", Number(e.target.value))}
        />
      </label>
    </div>
  );
}

export function promptFieldsToCaptureFields(fields: PromptFields) {
  const furniture_classes = fields.furnitureClassesText
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return {
    furniture_classes: furniture_classes.length > 0 ? furniture_classes : null,
    room_label: fields.roomLabel.trim() || null,
    box_threshold: fields.boxThreshold,
    max_detections: fields.maxDetections,
  };
}
