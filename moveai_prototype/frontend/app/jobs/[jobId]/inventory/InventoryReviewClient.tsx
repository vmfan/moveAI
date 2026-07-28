"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  addDeclaredItem,
  confirmItem,
  correctItem,
  deleteItem,
  getInventory,
  setBoxedGoodsCount,
  type DeclaredItemInput,
  type InventoryItem,
  type InventorySummary,
} from "@/lib/api";
import { NeedsConfirmationSection } from "@/components/inventory/NeedsConfirmationSection";
import { BoxedGoodsEditor } from "@/components/inventory/BoxedGoodsEditor";
import { InventoryByRoom } from "@/components/inventory/InventoryByRoom";
import { StaffEscalatedSection } from "@/components/inventory/StaffEscalatedSection";
import { AddItemForm } from "@/components/inventory/AddItemForm";

export function InventoryReviewClient({
  jobId,
  initial,
}: {
  jobId: string;
  initial: { items: InventoryItem[]; summary: InventorySummary };
}) {
  const queryClient = useQueryClient();
  const queryKey = ["inventory", jobId];

  const { data } = useQuery({
    queryKey,
    queryFn: () => getInventory(jobId),
    initialData: initial,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey });
  }

  const confirmMutation = useMutation({
    mutationFn: (itemId: number) => confirmItem(jobId, itemId),
    onSuccess: invalidate,
  });
  const correctMutation = useMutation({
    mutationFn: ({ itemId, fields }: { itemId: number; fields: { width_m: number; height_m: number; depth_m: number } }) =>
      correctItem(jobId, itemId, fields),
    onSuccess: invalidate,
  });
  const removeMutation = useMutation({
    mutationFn: (itemId: number) => deleteItem(jobId, itemId),
    onSuccess: invalidate,
  });
  const boxedGoodsMutation = useMutation({
    mutationFn: ({ itemId, count }: { itemId: number; count: number }) => setBoxedGoodsCount(jobId, itemId, count),
    onSuccess: invalidate,
  });
  const addItemMutation = useMutation({
    mutationFn: (fields: DeclaredItemInput) => addDeclaredItem(jobId, fields),
    onSuccess: invalidate,
  });

  const items = data.items;
  const boxedGoods = items.find((i) => !!i.is_boxed_goods);
  const needsConfirmation = items.filter(
    (i) => i.review_state === "customer_confirm" && !i.customer_confirmed && !i.is_boxed_goods,
  );
  const staffEscalated = items.filter((i) => i.review_state === "staff_escalate");
  const confirmedOrAuto = items.filter(
    (i) =>
      !i.is_boxed_goods &&
      i.review_state !== "staff_escalate" &&
      (i.review_state === "auto_accept" || i.customer_confirmed),
  );

  const anyMutationError = [
    confirmMutation.error,
    correctMutation.error,
    removeMutation.error,
    boxedGoodsMutation.error,
    addItemMutation.error,
  ].find(Boolean) as Error | undefined;

  return (
    <div className="mt-6 flex flex-col gap-10">
      {anyMutationError && <p className="text-sm text-red-600">{anyMutationError.message}</p>}

      <NeedsConfirmationSection
        items={needsConfirmation}
        onConfirm={(id) => confirmMutation.mutate(id)}
        onCorrect={(id, fields) => correctMutation.mutate({ itemId: id, fields })}
        onRemove={(id) => removeMutation.mutate(id)}
      />

      <BoxedGoodsEditor item={boxedGoods} onSetCount={(id, count) => boxedGoodsMutation.mutate({ itemId: id, count })} />

      <InventoryByRoom items={confirmedOrAuto} onRemove={(id) => removeMutation.mutate(id)} />

      <StaffEscalatedSection items={staffEscalated} />

      <AddItemForm onAdd={(fields) => addItemMutation.mutate(fields)} />

      <footer className="flex items-center justify-between border-t border-zinc-200 pt-4 text-sm text-zinc-600">
        <p>
          {data.summary.total_items} item{data.summary.total_items === 1 ? "" : "s"} &middot;{" "}
          {data.summary.customer_confirm_count} awaiting your confirmation &middot;{" "}
          {data.summary.staff_escalate_count} with our team
        </p>
        <Link
          href={`/jobs/${jobId}/quote`}
          className="rounded-full bg-zinc-900 px-5 py-2 font-medium text-white hover:bg-zinc-700"
        >
          Continue to quote
        </Link>
      </footer>
    </div>
  );
}
