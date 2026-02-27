"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import useSWR from "swr";

import { parseResponseJson, safeFetcher } from "@/lib/fetcher";

type SalesTrendPoint = {
  label: string;
  revenue: number;
  orders: number;
};

type SalesResponse = {
  totalSales: number;
  totalRevenue: number;
  trend: SalesTrendPoint[];
};

type TopProduct = {
  id: number;
  name: string;
  units: number;
  revenue: number;
};

type LowInventoryItem = {
  variantId: number;
  sku: string;
  name: string;
  stock: number;
};

type ToastMessage = {
  id: string;
  tone: "info" | "warning";
  text: string;
};

const LOW_STOCK_THRESHOLD = 10;
const fetcher = safeFetcher;

export default function DashboardPage() {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [csrfToken, setCsrfToken] = useState("");
  const latestSalesRef = useRef<number | null>(null);
  const alertedLowStockRef = useRef<Set<number>>(new Set());

  const salesParams = useMemo(() => {
    const params = new URLSearchParams();
    if (fromDate) {
      params.set("from", fromDate);
    }
    if (toDate) {
      params.set("to", toDate);
    }
    return params.toString();
  }, [fromDate, toDate]);
  const salesKey = salesParams ? `/api/sales?${salesParams}` : "/api/sales";

  const {
    data: sales,
    error: salesError,
    isLoading: salesLoading,
    isValidating: salesValidating,
    mutate: mutateSales,
  } = useSWR<SalesResponse>(salesKey, fetcher, {
    refreshInterval: 10000,
    onSuccess: (nextSales) => {
      if (
        latestSalesRef.current !== null &&
        nextSales.totalSales > latestSalesRef.current
      ) {
        const delta = nextSales.totalSales - latestSalesRef.current;
        pushToast("info", `${delta} new order${delta > 1 ? "s" : ""} detected. KPIs refreshed.`);
      }
      latestSalesRef.current = nextSales.totalSales;
    },
  });
  const {
    data: topProductsData,
    error: topProductsError,
    isLoading: topProductsLoading,
    mutate: mutateTopProducts,
  } = useSWR<{ items: TopProduct[] }>("/api/products/top", fetcher, {
    refreshInterval: 15000,
  });
  const {
    data: lowInventoryData,
    error: lowInventoryError,
    isLoading: lowInventoryLoading,
    mutate: mutateLowInventory,
  } = useSWR<{ items: LowInventoryItem[] }>("/api/inventory/low", fetcher, {
    refreshInterval: 8000,
    onSuccess: (payload) => {
      for (const item of payload.items) {
        if (item.stock < LOW_STOCK_THRESHOLD && !alertedLowStockRef.current.has(item.variantId)) {
          alertedLowStockRef.current.add(item.variantId);
          pushToast("warning", `Low stock alert: ${item.name} has only ${item.stock} units left.`);
        }
      }
    },
  });

  const topProducts = useMemo(() => topProductsData?.items ?? [], [topProductsData]);
  const lowInventory = useMemo(() => lowInventoryData?.items ?? [], [lowInventoryData]);
  const isLoading = salesLoading || topProductsLoading || lowInventoryLoading;
  const error = salesError ?? topProductsError ?? lowInventoryError;
  const isMounted = typeof window !== "undefined";

  const pushToast = (tone: ToastMessage["tone"], text: string) => {
    const toastId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((current) => [...current, { id: toastId, tone, text }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== toastId));
    }, 4500);
  };

  const totalProductsTracked = useMemo(
    () => topProducts.reduce((sum, item) => sum + item.units, 0),
    [topProducts]
  );

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

  async function handleLogout() {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { "x-csrf-token": csrfToken },
    });
    window.location.href = "/login";
  }

  async function handleRefresh() {
    await Promise.all([mutateSales(), mutateTopProducts(), mutateLowInventory()]);
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-10">
      <div className="fixed right-4 top-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`max-w-sm rounded-md border px-3 py-2 text-sm shadow ${
              toast.tone === "warning"
                ? "border-amber-300 bg-amber-50 text-amber-800"
                : "border-sky-300 bg-sky-50 text-sky-800"
            }`}
          >
            {toast.text}
          </div>
        ))}
      </div>

      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Admin Dashboard</h1>
          <p className="text-sm text-slate-600">
            This route is protected and only available for admin users.
          </p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
        >
          Logout
        </button>
      </header>

      <div className="mb-4">
        <div className="flex gap-2">
          <a
            href="/dashboard/products"
            className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            Manage products
          </a>
          <a
            href="/dashboard/orders"
            className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            Manage orders
          </a>
          <a
            href="/dashboard/inventory"
            className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            Inventory audit
          </a>
        </div>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <h2 className="text-lg font-medium text-slate-900">Sales Overview</h2>
            <p className="mt-1 text-sm text-slate-600">
              Revenue and sales KPIs with date-based filtering.
            </p>
          </div>
          <div className="ml-auto flex gap-2">
            <label className="text-xs text-slate-600">
              From
              <input
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
                className="mt-1 block rounded-md border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <label className="text-xs text-slate-600">
              To
              <input
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
                className="mt-1 block rounded-md border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={handleRefresh}
            className="rounded-md border border-slate-300 px-3 py-2 text-xs text-slate-700"
          >
            {salesValidating ? "Refreshing..." : "Refresh now"}
          </button>
        </div>

        {error ? (
          <p className="mt-4 text-sm text-red-600">
            {error instanceof Error ? error.message : "Could not load dashboard metrics."}
          </p>
        ) : null}

        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
          <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-600">Total Sales</h3>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {isLoading ? "..." : sales?.totalSales ?? 0}
            </p>
          </article>
          <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-600">Total Revenue</h3>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {isLoading ? "..." : `$${(sales?.totalRevenue ?? 0).toLocaleString()}`}
            </p>
          </article>
          <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-600">Top Units Sold</h3>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {isLoading ? "..." : totalProductsTracked}
            </p>
          </article>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">Revenue Trend</h3>
            <div className="h-60">
              {isMounted ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={sales?.trend ?? []}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="revenue" stroke="#0f172a" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full rounded bg-slate-50" />
              )}
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">Order Volume</h3>
            <div className="h-60">
              {isMounted ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sales?.trend ?? []}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="orders" fill="#334155" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full rounded bg-slate-50" />
              )}
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">Top Products</h3>
            <ul className="space-y-2 text-sm text-slate-700">
              {topProducts.map((item) => (
                <li key={item.id} className="flex items-center justify-between rounded border border-slate-100 px-3 py-2">
                  <span>{item.name}</span>
                  <span className="text-xs text-slate-500">
                    {item.units} units · ${item.revenue.toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">Low Inventory</h3>
            <ul className="space-y-2 text-sm text-slate-700">
              {lowInventory.map((item) => (
                <li
                  key={item.variantId}
                  className="flex items-center justify-between rounded border border-slate-100 px-3 py-2"
                >
                  <div>
                    <p>{item.name}</p>
                    <p className="text-xs text-slate-500">{item.sku}</p>
                  </div>
                  <span className="rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
                    {item.stock} left
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}
