"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { uploadImages, type UploadedImage } from "@/lib/api";

type PendingPreview = { file: File; previewUrl: string };

export function ImageUploader({
  jobId,
  value,
  onChange,
}: {
  jobId: string;
  value: UploadedImage[];
  onChange: (images: UploadedImage[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<PendingPreview[]>([]);

  useEffect(() => {
    return () => {
      pending.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    };
  }, [pending]);

  const mutation = useMutation({
    mutationFn: (files: File[]) => uploadImages(jobId, files),
    onSuccess: (uploaded) => {
      onChange([...value, ...uploaded]);
      setPending((prev) => {
        prev.forEach((p) => URL.revokeObjectURL(p.previewUrl));
        return [];
      });
    },
  });

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    setPending(files.map((file) => ({ file, previewUrl: URL.createObjectURL(file) })));
    mutation.mutate(files);
  }

  function removeUploaded(name: string) {
    onChange(value.filter((image) => image.name !== name));
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500 transition-colors hover:border-zinc-400"
      >
        <p>Drag photos here, or click to choose files</p>
        <p className="text-xs text-zinc-400">JPEG, PNG, or HEIC — up to 15 MB each</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/heic,image/heif"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {mutation.isPending && <p className="text-xs text-zinc-500">Uploading...</p>}
      {mutation.isError && (
        <p className="text-sm text-red-600">{(mutation.error as Error).message}</p>
      )}

      {(pending.length > 0 || value.length > 0) && (
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
          {value.map((image) => (
            <div key={image.name} className="relative overflow-hidden rounded-lg border border-zinc-200">
              <button
                type="button"
                onClick={() => removeUploaded(image.name)}
                className="absolute right-1 top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900/80 text-[10px] font-medium text-white"
                aria-label="Remove photo"
              >
                ×
              </button>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={image.url} alt={image.name} className="aspect-square w-full object-cover" />
            </div>
          ))}
          {mutation.isPending &&
            pending.map((p) => (
              <div
                key={p.previewUrl}
                className="relative overflow-hidden rounded-lg border border-zinc-200 opacity-50"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.previewUrl} alt={p.file.name} className="aspect-square w-full object-cover" />
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
