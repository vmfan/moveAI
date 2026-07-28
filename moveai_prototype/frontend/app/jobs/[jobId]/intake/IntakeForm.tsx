"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { saveIntake, type Intake } from "@/lib/api";

const EMPTY: Intake = {
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  origin_address: "",
  origin_floor: 0,
  origin_has_lift: false,
  origin_parking_distance_m: 0,
  destination_address: "",
  destination_floor: 0,
  destination_has_lift: false,
  destination_parking_distance_m: 0,
  room_count: 1,
  preferred_move_date: "",
};

export function IntakeForm({ jobId, initial }: { jobId: string; initial: Intake | null }) {
  const router = useRouter();
  const [fields, setFields] = useState<Intake>(initial ?? EMPTY);

  const mutation = useMutation({
    mutationFn: () => saveIntake(jobId, fields),
    onSuccess: () => router.push(`/jobs/${jobId}/capture`),
  });

  function set<K extends keyof Intake>(key: K, value: Intake[K]) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <form
      className="mt-6 flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium text-zinc-900">Contact</legend>
        <Field label="Full name">
          <input
            required
            className="input"
            value={fields.contact_name}
            onChange={(e) => set("contact_name", e.target.value)}
          />
        </Field>
        <Field label="Email">
          <input
            required
            type="email"
            className="input"
            value={fields.contact_email}
            onChange={(e) => set("contact_email", e.target.value)}
          />
        </Field>
        <Field label="Phone (optional)">
          <input
            className="input"
            value={fields.contact_phone ?? ""}
            onChange={(e) => set("contact_phone", e.target.value)}
          />
        </Field>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium text-zinc-900">Origin</legend>
        <Field label="Address">
          <input
            required
            className="input"
            value={fields.origin_address}
            onChange={(e) => set("origin_address", e.target.value)}
          />
        </Field>
        <Field label="Floor">
          <input
            type="number"
            className="input"
            value={fields.origin_floor}
            onChange={(e) => set("origin_floor", Number(e.target.value))}
          />
        </Field>
        <Checkbox
          label="Lift available"
          checked={fields.origin_has_lift}
          onChange={(v) => set("origin_has_lift", v)}
        />
        <Field label="Parking distance (m)">
          <input
            type="number"
            step="0.1"
            className="input"
            value={fields.origin_parking_distance_m}
            onChange={(e) => set("origin_parking_distance_m", Number(e.target.value))}
          />
        </Field>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium text-zinc-900">Destination</legend>
        <Field label="Address">
          <input
            required
            className="input"
            value={fields.destination_address}
            onChange={(e) => set("destination_address", e.target.value)}
          />
        </Field>
        <Field label="Floor">
          <input
            type="number"
            className="input"
            value={fields.destination_floor}
            onChange={(e) => set("destination_floor", Number(e.target.value))}
          />
        </Field>
        <Checkbox
          label="Lift available"
          checked={fields.destination_has_lift}
          onChange={(v) => set("destination_has_lift", v)}
        />
        <Field label="Parking distance (m)">
          <input
            type="number"
            step="0.1"
            className="input"
            value={fields.destination_parking_distance_m}
            onChange={(e) => set("destination_parking_distance_m", Number(e.target.value))}
          />
        </Field>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium text-zinc-900">Move details</legend>
        <Field label="Number of rooms">
          <input
            type="number"
            min={1}
            className="input"
            value={fields.room_count}
            onChange={(e) => set("room_count", Number(e.target.value))}
          />
        </Field>
        <Field label="Preferred move date (optional)">
          <input
            type="date"
            className="input"
            value={fields.preferred_move_date ?? ""}
            onChange={(e) => set("preferred_move_date", e.target.value)}
          />
        </Field>
      </fieldset>

      {mutation.isError && (
        <p className="text-sm text-red-600">{(mutation.error as Error).message}</p>
      )}

      <button
        type="submit"
        disabled={mutation.isPending}
        className="self-start rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50"
      >
        {mutation.isPending ? "Saving..." : "Continue"}
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-zinc-700">
      {label}
      {children}
    </label>
  );
}

function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-zinc-700">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
