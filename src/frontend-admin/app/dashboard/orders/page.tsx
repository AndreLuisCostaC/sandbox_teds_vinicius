"use client";

import useSWR from "swr";
import { useEffect, useMemo, useState } from "react";

import { parseResponseJson, safeFetcher } from "@/lib/fetcher";

type OrderStatus = "pending" | "paid" | "shipped" | "cancelled";

type OrderItem = {
  id: number;
  product_variant_id: number;
  quantity: number;
  unit_price: string;
  line_total: string;
};

type Payment = {
  id: number;
  provider: string;
  status: string;
  amount: string;
};

type Order = {
  id: number;
  user_id: number | null;
  status: OrderStatus;
  currency: string;
  total_amount: string;
  items: OrderItem[];
  payments: Payment[];
  created_at: string;
};

type OrderListResponse = {
  items: Order[];
  total: number;
  limit: number;
  offset: number;
};

type StockItem = {
  product_variant_id: number;
  quantity: number;
  reserved_quantity: number;
  available_stock: number;
};

type StockListResponse = {
  items: StockItem[];
};

const fetcher = safeFetcher;

const NEXT_STATUS_BY_CURRENT: Record<OrderStatus, OrderStatus[]> = {
  pending: ["paid", "cancelled"],
  paid: ["shipped", "cancelled"],
  shipped: [],
  cancelled: [],
};

export default function OrderManagementPage() {
  const [statusFilter, setStatusFilter] = useState<"all" | OrderStatus>("all");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [updatingOrderId, setUpdatingOrderId] = useState<number | null>(null);
  const [csrfToken, setCsrfToken] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams({
      limit: "10",
      offset: String(offset),
      status: statusFilter,
    });
    return params.toString();
  }, [offset, statusFilter]);

  const { data, isLoading, mutate, error: fetchError } = useSWR<OrderListResponse>(
    `/api/erp/orders?${query}`,
    fetcher
  );
  const orders = useMemo(() => data?.items ?? [], [data]);
  const total = data?.total ?? 0;
  const limit = data?.limit ?? 10;
  const page = Math.floor(offset / limit) + 1;
  const maxPage = Math.max(1, Math.ceil(total / limit));
  const variantIds = useMemo(() => {
    const ids = new Set<number>();
    for (const order of orders) {
      for (const item of order.items) {
        ids.add(item.product_variant_id);
      }
    }
    return Array.from(ids);
  }, [orders]);
  const stockQuery = variantIds.join(",");
  const { data: stockData } = useSWR<StockListResponse>(
    stockQuery ? `/api/erp/inventory/stock?variant_ids=${stockQuery}` : null,
    fetcher
  );
  const stockByVariant = useMemo(() => {
    const map = new Map<number, StockItem>();
    for (const item of stockData?.items ?? []) {
      map.set(item.product_variant_id, item);
    }
    return map;
  }, [stockData]);

  useEffect(() => {
    const loadCsrf = async () => {
      const response = await fetch("/api/auth/csrf");
      if (!response.ok) {
        return;
      }
      const payload = await parseResponseJson<{ csrfToken?: string }>(response);
      if (payload.csrfToken) {
        setCsrfToken(payload.csrfToken);
      }
    };
    void loadCsrf();
  }, []);

  async function updateStatus(orderId: number, nextStatus: OrderStatus) {
    setError(null);
    setSuccess(null);
    setUpdatingOrderId(orderId);
    try {
      const response = await fetch(`/api/erp/orders/${orderId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrfToken },
        body: JSON.stringify({ status: nextStatus }),
      });
      const payload = await parseResponseJson<{ detail?: string }>(response);
      if (!response.ok) {
        throw new Error(payload.detail ?? "Status update failed.");
      }
      setSuccess(`Order #${orderId} moved to ${nextStatus}.`);
      await mutate();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Status update failed.");
    } finally {
      setUpdatingOrderId(null);
    }
  }

  async function handleLogout() {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { "x-csrf-token": csrfToken },
    });
    window.location.href = "/login";
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Order Management</h1>
          <p className="text-sm text-slate-600">
            Update order workflow status and inspect payment/item details.
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href="/dashboard"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            Back to Dashboard
          </a>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            Logout
          </button>
        </div>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex items-end gap-3">
          <label className="text-xs text-slate-600">
            Status filter
            <select
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value as "all" | OrderStatus);
                setOffset(0);
              }}
              className="mt-1 block rounded-md border border-slate-300 px-2 py-1 text-xs"
            >
              <option value="all">all</option>
              <option value="pending">pending</option>
              <option value="paid">paid</option>
              <option value="shipped">shipped</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
        </div>

        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}
        {success ? <p className="mb-3 text-sm text-emerald-700">{success}</p> : null}
        {fetchError ? (
          <p className="mb-3 text-sm text-red-600">
            {fetchError instanceof Error ? fetchError.message : "Could not load orders."}
          </p>
        ) : null}
        {isLoading ? <p className="text-sm text-slate-600">Loading orders...</p> : null}

        <ul className="space-y-3">
          {orders.map((order) => (
            <li key={order.id} className="rounded-md border border-slate-200 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Order #{order.id} · {order.status}
                  </p>
                  <p className="text-xs text-slate-500">
                    User: {order.user_id ?? "guest"} · {new Date(order.created_at).toLocaleString()}
                  </p>
                  <p className="text-xs text-slate-500">
                    Total: {order.currency} {Number(order.total_amount).toFixed(2)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {NEXT_STATUS_BY_CURRENT[order.status].map((nextStatus) => (
                    <button
                      key={nextStatus}
                      type="button"
                      disabled={updatingOrderId === order.id}
                      onClick={() => void updateStatus(order.id, nextStatus)}
                      className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 disabled:opacity-60"
                    >
                      {updatingOrderId === order.id ? "Updating..." : `Set ${nextStatus}`}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase text-slate-600">Items</p>
                  <ul className="space-y-1 text-xs text-slate-700">
                    {order.items.map((item) => (
                      <li key={item.id} className="rounded border border-slate-100 px-2 py-1">
                        Variant #{item.product_variant_id} · Qty {item.quantity} · Unit $
                        {Number(item.unit_price).toFixed(2)} · Line ${Number(item.line_total).toFixed(2)}
                        {stockByVariant.get(item.product_variant_id) ? (
                          <>
                            {" "}
                            · Stock now{" "}
                            {stockByVariant.get(item.product_variant_id)?.available_stock}
                          </>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase text-slate-600">Payments</p>
                  <ul className="space-y-1 text-xs text-slate-700">
                    {order.payments.map((payment) => (
                      <li key={payment.id} className="rounded border border-slate-100 px-2 py-1">
                        {payment.provider} · {payment.status} · ${Number(payment.amount).toFixed(2)}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-4 flex items-center justify-between text-xs text-slate-600">
          <span>
            Page {page} of {maxPage}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setOffset((current) => Math.max(0, current - limit))}
              disabled={offset === 0}
              className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setOffset((current) => current + limit)}
              disabled={offset + limit >= total}
              className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
