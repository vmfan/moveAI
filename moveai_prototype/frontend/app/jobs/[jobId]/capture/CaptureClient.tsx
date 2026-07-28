"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { runCapture, type Sample } from "@/lib/api";
import { ImagePicker } from "@/components/capture/ImagePicker";
import {
  DEFAULT_PROMPT_FIELDS,
  PromptForm,
  promptFieldsToCaptureFields,
  type PromptFields,
} from "@/components/capture/PromptForm";
import { PipelineOutputTabs } from "@/components/capture/PipelineOutputTabs";

export function CaptureClient({
  jobId,
  samples,
  hasExistingCapture,
}: {
  jobId: string;
  samples: Sample[];
  hasExistingCapture: boolean;
}) {
  const router = useRouter();
  const [imageName, setImageName] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<PromptFields>(DEFAULT_PROMPT_FIELDS);

  const mutation = useMutation({
    mutationFn: () => {
      if (!imageName) throw new Error("Pick an image first.");
      return runCapture(jobId, { image_name: imageName, ...promptFieldsToCaptureFields(prompt) });
    },
    onSuccess: () => router.push(`/jobs/${jobId}/inventory`),
  });

  return (
    <div className="mt-6 flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-zinc-900">1. Pick a photo</h2>
        <ImagePicker samples={samples} value={imageName} onChange={setImageName} />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-zinc-900">2. Describe the room</h2>
        <PromptForm value={prompt} onChange={setPrompt} />
      </section>

      {mutation.isError && <p className="text-sm text-red-600">{(mutation.error as Error).message}</p>}

      <button
        type="button"
        disabled={!imageName || mutation.isPending}
        onClick={() => mutation.mutate()}
        className="self-start rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50"
      >
        {mutation.isPending ? "Analyzing..." : "Run capture"}
      </button>

      {hasExistingCapture && !mutation.isPending && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-zinc-900">Last capture for this job</h2>
          <PipelineOutputTabs jobId={jobId} />
        </section>
      )}
    </div>
  );
}
