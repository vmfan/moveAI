"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { runCapture, type CaptureResult, type Sample, type UploadedImage } from "@/lib/api";
import { ImagePicker } from "@/components/capture/ImagePicker";
import { ImageUploader } from "@/components/capture/ImageUploader";
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
  const [source, setSource] = useState<"upload" | "sample">("upload");
  const [sampleNames, setSampleNames] = useState<string[]>([]);
  const [uploadedImages, setUploadedImages] = useState<UploadedImage[]>([]);
  const [prompt, setPrompt] = useState<PromptFields>(DEFAULT_PROMPT_FIELDS);
  const [result, setResult] = useState<CaptureResult | null>(null);

  const imageNames = [...uploadedImages.map((image) => image.name), ...sampleNames];

  const mutation = useMutation({
    mutationFn: () => {
      if (imageNames.length === 0) throw new Error("Pick at least one photo first.");
      return runCapture(jobId, { image_names: imageNames, ...promptFieldsToCaptureFields(prompt) });
    },
    onSuccess: (captureResult) => {
      setResult(captureResult);
      if (!captureResult.dedup_error) {
        router.push(`/jobs/${jobId}/inventory`);
      }
    },
  });

  return (
    <div className="mt-6 flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-zinc-900">1. Pick photos</h2>
        <p className="text-xs text-zinc-500">
          Pick one or more photos of the same job. If you pick more than one, we&apos;ll
          automatically merge any item that shows up in more than one photo.
        </p>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={() => setSource("upload")}
            className={`rounded-full px-3 py-1 font-medium transition-colors ${
              source === "upload" ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            Upload photos
          </button>
          <button
            type="button"
            onClick={() => setSource("sample")}
            className={`rounded-full px-3 py-1 font-medium transition-colors ${
              source === "sample" ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            Use sample photos
          </button>
        </div>
        {source === "upload" ? (
          <ImageUploader jobId={jobId} value={uploadedImages} onChange={setUploadedImages} />
        ) : (
          <ImagePicker samples={samples} value={sampleNames} onChange={setSampleNames} />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-zinc-900">2. Describe the room</h2>
        <PromptForm value={prompt} onChange={setPrompt} />
      </section>

      {mutation.isError && <p className="text-sm text-red-600">{(mutation.error as Error).message}</p>}
      {result?.dedup_error && (
        <div className="flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          <p>
            Captured {imageNames.length} photo{imageNames.length === 1 ? "" : "s"}, but couldn&apos;t
            automatically merge duplicates across them ({result.dedup_error}). You can merge or remove
            duplicates by hand on the next page.
          </p>
          <button
            type="button"
            onClick={() => router.push(`/jobs/${jobId}/inventory`)}
            className="self-start rounded-full bg-amber-800 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-amber-700"
          >
            Continue to inventory
          </button>
        </div>
      )}

      <button
        type="button"
        disabled={imageNames.length === 0 || mutation.isPending}
        onClick={() => mutation.mutate()}
        className="self-start rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50"
      >
        {mutation.isPending
          ? "Analyzing..."
          : `Run capture${imageNames.length > 1 ? ` (${imageNames.length} photos)` : ""}`}
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
