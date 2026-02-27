"use client";

import useSWR from "swr";
import { useMemo, useState } from "react";

import { safeFetcher } from "@/lib/fetcher";

type Movement = {
  id: number;
  product_variant_id: number;
  user_id: number | null;
  movement_type: string;
  delta_quantity: number;
  reason: string | null;
  created_at: string;
};

type MovementResponse = {
  items: Movement[];
  total: number;
  limit: number;
  offset: number;
};

const fetcher = safeFetcher;

export default function InventoryAuditPage() {
  const [variantFilter, setVariantFilter] = useState("");
  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: "100", offset: "0" });
    if (variantFilter.trim()) {
      params.set("variant_id", variantFilter.trim());
    }
    return params.toString();
  }, [variantFilter]);

  const { data, isLoading, error } = useSWR<MovementResponse>(
    `/api/erp/inventory/movements?${query}`,
    fetcher
  );
  const items = data?.items ?? [];

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Inventory Audit Trail</h1>
          <p className="text-sm text-slate-600">
            Movement log with timestamp, user, reason, and quantity delta.
          </p>
        </div>
        <a
          href="/dashboard"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
        >
          Back to Dashboard
        </a>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3">
          <label className="text-xs text-slate-600">
            Filter by variant ID
            <input
              value={variantFilter}
              onChange={(event) => setVariantFilter(event.target.value)}
              className="mt-1 block rounded-md border border-slate-300 px-2 py-1 text-xs"
              placeholder="e.g. 5"
            />
          </label>
        </div>

        {error ? (
          <p className="mb-3 text-sm text-red-600">
            {error instanceof Error ? error.message : "Could not load inventory movements."}
          </p>
        ) : null}
        {isLoading ? <p className="text-sm text-slate-600">Loading movements...</p> : null}

        <ul className="space-y-2">
          {items.map((movement) => (
            <li key={movement.id} className="rounded border border-slate-200 px-3 py-2 text-xs">
              <p className="font-semibold text-slate-800">
                #{movement.id} · Variant {movement.product_variant_id} · {movement.movement_type}
              </p>
              <p className="text-slate-600">
                Delta: {movement.delta_quantity} · User: {movement.user_id ?? "system"} ·{" "}
                {new Date(movement.created_at).toLocaleString()}
              </p>
              {movement.reason ? <p className="text-slate-600">Reason: {movement.reason}</p> : null}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
