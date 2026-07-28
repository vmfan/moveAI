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
