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
    let message = `${label} failed: ${res.status}`;
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      message = body.detail.join(" ");
    }
    throw new Error(message);
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
  image_names: string[];
  furniture_classes?: string[] | null;
  room_label?: string | null;
  box_threshold?: number | null;
  max_detections?: number | null;
};

export type CaptureImageSummary = {
  measured_item_ids: number[];
  escalated_item_ids: number[];
  timings_s: Record<string, number>;
  total_visible_volume_m3: number;
};

export type CaptureDuplicateGroup = { kept_item_id: number; removed_item_ids: number[] };

export type CaptureResult = {
  images: Record<string, CaptureImageSummary>;
  duplicates_removed: CaptureDuplicateGroup[];
  room_labels_assigned: Record<string, string>;
  dedup_error: string | null;
  artifacts: {
    overlay_url_template: string;
    depth_url_template: string;
    inventory_url: string;
    point_cloud_url_template: string;
    images_url: string;
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

export async function listCaptureImages(jobId: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/capture/images`, { cache: "no-store" });
  await throwOnError(res, "GET capture images");
  const body: { image_names: string[] } = await res.json();
  return body.image_names;
}

export function overlayUrl(jobId: string, imageName: string): string {
  return `${API_BASE}/api/jobs/${jobId}/capture/overlay.png?image_name=${encodeURIComponent(imageName)}`;
}

export function depthUrl(jobId: string, imageName: string): string {
  return `${API_BASE}/api/jobs/${jobId}/capture/depth.png?image_name=${encodeURIComponent(imageName)}`;
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
  source_image_name: string;
};

export type CapturePreview = {
  items: CapturePreviewItem[];
  errors: {
    index: number;
    label: string;
    detection_confidence: number;
    message: string;
    source_image_name: string;
  }[];
  total_visible_volume_m3: number;
  timings_s: Record<string, number>;
};

export async function getCapturePreview(jobId: string): Promise<CapturePreview | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/capture/inventory`, { cache: "no-store" });
  if (res.status === 404) return null;
  await throwOnError(res, "GET capture inventory");
  return res.json();
}

export function pointCloudUrl(jobId: string, imageName: string, itemIndex: number): string {
  return `${API_BASE}/api/jobs/${jobId}/capture/points/${itemIndex}?image_name=${encodeURIComponent(imageName)}`;
}

export async function getPointCloud(
  jobId: string,
  imageName: string,
  itemIndex: number,
): Promise<unknown | null> {
  const res = await fetch(pointCloudUrl(jobId, imageName, itemIndex), { cache: "no-store" });
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

// -- Quote (Build 6/8/12) --------------------------------------------------

export type QuoteLine = {
  inventory_item_id: number;
  measurement_basis: "measured" | "prior_assisted" | "declared";
  raw_volume_m3: number;
  volume_m3: number;
  price_component: number;
};

export type Quote = {
  lines: QuoteLine[];
  total_volume_m3: number;
  upper_bound_volume_m3: number;
  volume_margin_fraction: number;
  access_multiplier: number;
  total_price: number;
  recommended_truck: string | null;
  escalated_item_ids: number[];
  unmeasured_item_ids: number[];
};

export type QuoteViewRow = {
  inventory_item_id: number;
  label: string;
  room_label: string | null;
  measurement_basis: "measured" | "prior_assisted" | "declared";
  raw_volume_m3: number;
  volume_m3: number;
  price_component: number;
  surcharge_eligible: boolean;
};

export type QuoteResponse = {
  quote: Quote;
  version: number;
  stale: boolean;
  lines: QuoteViewRow[];
  staff_review_reasons: string[];
};

export type QuoteVersion = {
  id: number;
  job_id: number;
  version: number;
  pricing_config_id: number;
  total_volume_m3: number;
  upper_bound_volume_m3: number;
  volume_margin_fraction: number;
  access_multiplier: number;
  total_price: number;
  recommended_truck: string | null;
  is_superseded: number;
  created_at: string;
};

export async function getQuote(jobId: string): Promise<QuoteResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/quote`, { cache: "no-store" });
  await throwOnError(res, "GET quote");
  return res.json();
}

export async function regenerateQuote(jobId: string): Promise<QuoteResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/quote/regenerate`, { method: "POST" });
  await throwOnError(res, "regenerate quote");
  return res.json();
}

export async function getQuoteVersions(jobId: string): Promise<QuoteVersion[]> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/quote/versions`, { cache: "no-store" });
  await throwOnError(res, "GET quote versions");
  return res.json();
}

// -- Booking (Build 7/8/12) -------------------------------------------------

export type BookingStatus =
  | "pending_staff_review"
  | "confirmed"
  | "needs_customer_clarification"
  | "cancelled";

export type Booking = {
  id: number;
  job_id: number;
  quote_id: number;
  status: BookingStatus;
  customer_note: string | null;
  staff_note: string | null;
  created_at: string;
  updated_at: string;
};

export type BookingStatusResponse = {
  booking: Booking | null;
  blockers: string[];
};

export async function getBooking(jobId: string): Promise<BookingStatusResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/booking`, { cache: "no-store" });
  await throwOnError(res, "GET booking");
  return res.json();
}

export async function submitBooking(
  jobId: string,
  customerNote?: string | null,
): Promise<{ booking: Booking; created: boolean }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/booking/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_note: customerNote ?? null }),
  });
  await throwOnError(res, "submit booking");
  return res.json();
}

export async function resubmitBooking(
  jobId: string,
  customerNote?: string | null,
): Promise<Booking> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/booking/resubmit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_note: customerNote ?? null }),
  });
  await throwOnError(res, "resubmit booking");
  return res.json();
}

// -- Company Console (Build 7/8/12) -----------------------------------------

export type ConsoleBooking = Booking & {
  job_status: string;
  total_price: number;
  recommended_truck: string | null;
};

export type ConsoleBookingRow = {
  booking: ConsoleBooking;
  intake: Intake | null;
  reasons: string[];
  pinned_quote_superseded: boolean;
};

export async function listConsoleBookings(status?: string | null): Promise<ConsoleBookingRow[]> {
  const url = new URL(`${API_BASE}/api/console/bookings`);
  if (status) url.searchParams.set("status", status);
  const res = await fetch(url, { cache: "no-store" });
  await throwOnError(res, "GET console bookings");
  return res.json();
}

export async function decideBooking(
  bookingId: number,
  status: BookingStatus,
  staffNote?: string | null,
): Promise<Booking> {
  const res = await fetch(`${API_BASE}/api/console/bookings/${bookingId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, staff_note: staffNote ?? null }),
  });
  await throwOnError(res, "decide booking");
  return res.json();
}
