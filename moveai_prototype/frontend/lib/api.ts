export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Job = {
  id: number;
  status: string;
  created_at: string;
};

export async function getJob(jobId: string): Promise<Job | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET /api/jobs/${jobId} failed: ${res.status}`);
  return res.json();
}

export async function createJob(): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs`, { method: "POST" });
  if (!res.ok) throw new Error(`POST /api/jobs failed: ${res.status}`);
  return res.json();
}

export type Intake = {
  contact_name: string;
  contact_email: string;
  contact_phone: string | null;
  origin_address: string;
  origin_floor: number;
  origin_has_lift: boolean;
  origin_parking_distance_m: number;
  destination_address: string;
  destination_floor: number;
  destination_has_lift: boolean;
  destination_parking_distance_m: number;
  room_count: number;
  preferred_move_date: string | null;
};

export async function getIntake(jobId: string): Promise<Intake | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/intake`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET /api/jobs/${jobId}/intake failed: ${res.status}`);
  return res.json();
}

export async function saveIntake(jobId: string, fields: Intake): Promise<Intake> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/intake`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string" ? body.detail : `PUT intake failed: ${res.status}`,
    );
  }
  return res.json();
}

async function throwOnError(res: Response, label: string): Promise<Response> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `${label} failed: ${res.status}`);
  }
  return res;
}

// -- Samples (Build 11) --------------------------------------------------

export type Sample = { name: string; url: string };

export async function listSamples(): Promise<Sample[]> {
  const res = await fetch(`${API_BASE}/api/samples`, { cache: "no-store" });
  await throwOnError(res, "GET /api/samples");
  const samples: Sample[] = await res.json();
  return samples.map((s) => ({ ...s, url: `${API_BASE}${s.url}` }));
}

// -- Capture (Build 10/11) ------------------------------------------------

export type CaptureRequest = {
  image_name: string;
  furniture_classes?: string[] | null;
  room_label?: string | null;
  box_threshold?: number | null;
  max_detections?: number | null;
};

export type CaptureResult = {
  measured_item_ids: number[];
  escalated_item_ids: number[];
  timings_s: Record<string, number>;
  total_visible_volume_m3: number;
  artifacts: {
    overlay_url: string;
    depth_url: string;
    inventory_url: string;
    point_cloud_url_template: string;
  };
};

export async function runCapture(jobId: string, body: CaptureRequest): Promise<CaptureResult> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(res, "POST capture");
  return res.json();
}

export function overlayUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/capture/overlay.png`;
}

export function depthUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/capture/depth.png`;
}

export type CapturePreviewItem = {
  index: number;
  label: string;
  detection_confidence: number;
  width_m: number | null;
  height_m: number | null;
  depth_m: number | null;
  visible_obb_volume_m3: number | null;
  median_depth_m: number | null;
  point_count: number | null;
  used_axis_aligned_fallback: boolean;
  mask_touches_border: boolean;
  warning: string | null;
};

export type CapturePreview = {
  items: CapturePreviewItem[];
  errors: { index: number; label: string; detection_confidence: number; message: string }[];
  total_visible_volume_m3: number;
  timings_s: Record<string, number>;
};

export async function getCapturePreview(jobId: string): Promise<CapturePreview | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/capture/inventory`, { cache: "no-store" });
  if (res.status === 404) return null;
  await throwOnError(res, "GET capture inventory");
  return res.json();
}

export function pointCloudUrl(jobId: string, itemIndex: number): string {
  return `${API_BASE}/api/jobs/${jobId}/capture/points/${itemIndex}`;
}

export async function getPointCloud(jobId: string, itemIndex: number): Promise<unknown | null> {
  const res = await fetch(pointCloudUrl(jobId, itemIndex), { cache: "no-store" });
  if (res.status === 404) return null;
  await throwOnError(res, "GET point cloud");
  return res.json();
}

// -- Inventory (Build 5/8/11) ---------------------------------------------

export type InventoryItem = {
  id: number;
  job_id: number;
  label: string;
  room_label: string | null;
  measurement_basis: "measured" | "prior_assisted" | "declared";
  is_boxed_goods: number;
  quantity: number;
  width_m: number | null;
  height_m: number | null;
  depth_m: number | null;
  unit_volume_m3: number | null;
  boxed_goods_seed_json: Record<string, unknown> | null;
  detection_confidence: number | null;
  point_count: number | null;
  used_axis_aligned_fallback: number;
  mask_touches_border: number;
  measurement_error: string | null;
  review_state: "auto_accept" | "customer_confirm" | "staff_escalate";
  review_reason: string | null;
  customer_confirmed: number;
  source_image_name: string | null;
};

export type InventorySummary = {
  total_items: number;
  auto_accept_count: number;
  customer_confirm_count: number;
  staff_escalate_count: number;
};

export async function getInventory(
  jobId: string,
): Promise<{ items: InventoryItem[]; summary: InventorySummary }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/inventory`, { cache: "no-store" });
  await throwOnError(res, "GET inventory");
  return res.json();
}

export async function confirmItem(jobId: string, itemId: number): Promise<InventoryItem> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/inventory/${itemId}/confirm`, {
    method: "POST",
  });
  await throwOnError(res, "confirm item");
  return res.json();
}

export type Correction = { width_m: number; height_m: number; depth_m: number };

export async function correctItem(
  jobId: string,
  itemId: number,
  fields: Correction,
): Promise<InventoryItem> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/inventory/${itemId}/correct`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  await throwOnError(res, "correct item");
  return res.json();
}

export async function deleteItem(jobId: string, itemId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/inventory/${itemId}`, {
    method: "DELETE",
  });
  await throwOnError(res, "delete item");
}

export async function setBoxedGoodsCount(
  jobId: string,
  itemId: number,
  count: number,
): Promise<InventoryItem> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/inventory/boxed-goods/count`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: itemId, count }),
  });
  await throwOnError(res, "set boxed-goods count");
  return res.json();
}

export type DeclaredItemInput = {
  label: string;
  room_label?: string | null;
  quantity?: number;
  width_m: number;
  height_m: number;
  depth_m: number;
};

export async function addDeclaredItem(
  jobId: string,
  fields: DeclaredItemInput,
): Promise<InventoryItem> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/inventory/declared`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  await throwOnError(res, "add declared item");
  return res.json();
}
