import { listConsoleBookings } from "@/lib/api";
import { ConsoleClient } from "./ConsoleClient";

export default async function ConsolePage() {
  const rows = await listConsoleBookings();

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-xl font-semibold text-zinc-900">Company Console</h1>
      <p className="mt-1 text-sm text-zinc-600">
        Prototype only — unauthenticated. Any visitor with this URL can see and act on every job&apos;s
        bookings.
      </p>
      <ConsoleClient initial={rows} />
    </main>
  );
}
