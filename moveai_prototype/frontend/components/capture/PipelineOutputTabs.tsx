"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import {
  depthUrl,
  getCapturePreview,
  getPointCloud,
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

  useEffect(() => {
    let cancelled = false;
    getCapturePreview(jobId).then((result) => {
      if (!cancelled) setPreview(result);
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

      {tab === "overlay" && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={overlayUrl(jobId)} alt="Detection overlay" className="w-full rounded-lg border border-zinc-200" />
      )}
      {tab === "depth" && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={depthUrl(jobId)} alt="Depth map" className="w-full rounded-lg border border-zinc-200" />
      )}
      {tab === "inventory" && <InventoryPreviewTable preview={preview} />}
      {tab === "points" && <PointCloudTab jobId={jobId} preview={preview} />}
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
            <th className="py-1 pr-4">Label</th>
            <th className="py-1 pr-4">Confidence</th>
            <th className="py-1 pr-4">W x H x D (m)</th>
            <th className="py-1 pr-4">Volume (m3)</th>
          </tr>
        </thead>
        <tbody>
          {preview.items.map((item) => (
            <tr key={item.index} className="border-t border-zinc-100">
              <td className="py-1 pr-4">{item.index}</td>
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
            <tr key={`err-${err.index}`} className="border-t border-zinc-100 text-red-600">
              <td className="py-1 pr-4">{err.index}</td>
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
}: {
  jobId: string;
  preview: CapturePreview | null | undefined;
}) {
  const [itemIndex, setItemIndex] = useState<number | null>(null);
  const [figure, setFigure] = useState<{ data: unknown[]; layout: Record<string, unknown> } | null>(null);

  useEffect(() => {
    if (preview && preview.items.length > 0 && itemIndex === null) {
      setItemIndex(preview.items[0].index);
    }
  }, [preview, itemIndex]);

  useEffect(() => {
    if (itemIndex === null) return;
    let cancelled = false;
    setFigure(null);
    getPointCloud(jobId, itemIndex).then((result) => {
      if (!cancelled) setFigure(result as { data: unknown[]; layout: Record<string, unknown> } | null);
    });
    return () => {
      cancelled = true;
    };
  }, [jobId, itemIndex]);

  if (preview === undefined) return <p className="text-sm text-zinc-500">Loading...</p>;
  if (preview === null || preview.items.length === 0) {
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
          {preview.items.map((item) => (
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
