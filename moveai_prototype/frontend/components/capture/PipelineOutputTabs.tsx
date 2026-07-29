"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import {
  depthUrl,
  getCapturePreview,
  getPointCloud,
  listCaptureImages,
  overlayUrl,
  type CapturePreview,
} from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const TABS = ["overlay", "depth", "inventory", "points"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  overlay: "Overlay",
  depth: "Depth",
  inventory: "Inventory",
  points: "Point Cloud",
};

export function PipelineOutputTabs({ jobId }: { jobId: string }) {
  const [tab, setTab] = useState<Tab>("overlay");
  const [preview, setPreview] = useState<CapturePreview | null | undefined>(undefined);
  const [images, setImages] = useState<string[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCapturePreview(jobId).then((result) => {
      if (!cancelled) setPreview(result);
    });
    listCaptureImages(jobId).then((names) => {
      if (cancelled) return;
      setImages(names);
      setSelectedImage((current) => current ?? names[0] ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  return (
    <div className="mt-8 flex flex-col gap-4">
      <div className="flex gap-4 border-b border-zinc-200 text-sm">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-1 pb-2 ${
              tab === t ? "border-zinc-900 font-medium text-zinc-900" : "border-transparent text-zinc-500"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {(tab === "overlay" || tab === "depth" || tab === "points") && images.length > 0 && (
        <label className="flex flex-col gap-1 text-sm text-zinc-700">
          Photo
          <select
            className="input"
            value={selectedImage ?? ""}
            onChange={(e) => setSelectedImage(e.target.value)}
          >
            {images.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      )}

      {tab === "overlay" &&
        (selectedImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={overlayUrl(jobId, selectedImage)}
            alt="Detection overlay"
            className="w-full rounded-lg border border-zinc-200"
          />
        ) : (
          <p className="text-sm text-zinc-500">No photos captured yet.</p>
        ))}
      {tab === "depth" &&
        (selectedImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={depthUrl(jobId, selectedImage)}
            alt="Depth map"
            className="w-full rounded-lg border border-zinc-200"
          />
        ) : (
          <p className="text-sm text-zinc-500">No photos captured yet.</p>
        ))}
      {tab === "inventory" && <InventoryPreviewTable preview={preview} />}
      {tab === "points" && (
        <PointCloudTab jobId={jobId} preview={preview} selectedImage={selectedImage} />
      )}
    </div>
  );
}

function InventoryPreviewTable({ preview }: { preview: CapturePreview | null | undefined }) {
  if (preview === undefined) return <p className="text-sm text-zinc-500">Loading...</p>;
  if (preview === null) return <p className="text-sm text-zinc-500">No capture inventory available.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-zinc-500">
            <th className="py-1 pr-4">#</th>
            <th className="py-1 pr-4">Photo</th>
            <th className="py-1 pr-4">Label</th>
            <th className="py-1 pr-4">Confidence</th>
            <th className="py-1 pr-4">W x H x D (m)</th>
            <th className="py-1 pr-4">Volume (m3)</th>
          </tr>
        </thead>
        <tbody>
          {preview.items.map((item) => (
            <tr key={`${item.source_image_name}-${item.index}`} className="border-t border-zinc-100">
              <td className="py-1 pr-4">{item.index}</td>
              <td className="py-1 pr-4 text-zinc-500">{item.source_image_name}</td>
              <td className="py-1 pr-4">{item.label}</td>
              <td className="py-1 pr-4">{item.detection_confidence.toFixed(2)}</td>
              <td className="py-1 pr-4">
                {item.width_m?.toFixed(2) ?? "-"} x {item.height_m?.toFixed(2) ?? "-"} x{" "}
                {item.depth_m?.toFixed(2) ?? "-"}
              </td>
              <td className="py-1 pr-4">{item.visible_obb_volume_m3?.toFixed(3) ?? "-"}</td>
            </tr>
          ))}
          {preview.errors.map((err) => (
            <tr
              key={`err-${err.source_image_name}-${err.index}`}
              className="border-t border-zinc-100 text-red-600"
            >
              <td className="py-1 pr-4">{err.index}</td>
              <td className="py-1 pr-4">{err.source_image_name}</td>
              <td className="py-1 pr-4">{err.label}</td>
              <td colSpan={3} className="py-1 pr-4">
                {err.message}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PointCloudTab({
  jobId,
  preview,
  selectedImage,
}: {
  jobId: string;
  preview: CapturePreview | null | undefined;
  selectedImage: string | null;
}) {
  const [itemIndex, setItemIndex] = useState<number | null>(null);
  const [figure, setFigure] = useState<{ data: unknown[]; layout: Record<string, unknown> } | null>(null);

  const itemsForImage =
    preview && selectedImage
      ? preview.items.filter((item) => item.source_image_name === selectedImage)
      : [];

  useEffect(() => {
    setItemIndex(itemsForImage.length > 0 ? itemsForImage[0].index : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedImage]);

  useEffect(() => {
    if (itemIndex === null || !selectedImage) return;
    let cancelled = false;
    setFigure(null);
    getPointCloud(jobId, selectedImage, itemIndex).then((result) => {
      if (!cancelled) setFigure(result as { data: unknown[]; layout: Record<string, unknown> } | null);
    });
    return () => {
      cancelled = true;
    };
  }, [jobId, selectedImage, itemIndex]);

  if (preview === undefined) return <p className="text-sm text-zinc-500">Loading...</p>;
  if (!selectedImage || itemsForImage.length === 0) {
    return <p className="text-sm text-zinc-500">No measured items to show a point cloud for.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-zinc-700">
        Item
        <select
          className="input"
          value={itemIndex ?? ""}
          onChange={(e) => setItemIndex(Number(e.target.value))}
        >
          {itemsForImage.map((item) => (
            <option key={item.index} value={item.index}>
              {item.index}. {item.label}
            </option>
          ))}
        </select>
      </label>
      {figure ? (
        <Plot
          data={figure.data as never}
          layout={{ ...(figure.layout as object), autosize: true, height: 420 }}
          style={{ width: "100%" }}
          useResizeHandler
        />
      ) : (
        <p className="text-sm text-zinc-500">Loading point cloud...</p>
      )}
    </div>
  );
}
