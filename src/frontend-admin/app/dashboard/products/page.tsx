"use client";

import useSWR from "swr";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { parseResponseJson, safeFetcher } from "@/lib/fetcher";

type ProductStatus = "active" | "inactive";

type ProductApiItem = {
  id: number;
  name: string;
  description: string | null;
  price: string;
  category_id: number;
  status: ProductStatus;
  variant_id?: number | null;
};

type ProductListResponse = {
  items: ProductApiItem[];
  total: number;
  limit: number;
  offset: number;
};

type FormState = {
  name: string;
  description: string;
  price: string;
  categoryId: string;
  status: ProductStatus;
  imageUrl: string;
  quantity: string;
};

const IMAGE_MARKER_PREFIX = "[[image_url:";
const IMAGE_MARKER_SUFFIX = "]]";

const fetcher = safeFetcher;

function parseDescription(raw: string | null): { text: string; imageUrl: string } {
  if (!raw) {
    return { text: "", imageUrl: "" };
  }
  const start = raw.indexOf(IMAGE_MARKER_PREFIX);
  const end = raw.indexOf(IMAGE_MARKER_SUFFIX, start + IMAGE_MARKER_PREFIX.length);
  if (start === -1 || end === -1) {
    return { text: raw, imageUrl: "" };
  }
  const marker = raw.slice(start + IMAGE_MARKER_PREFIX.length, end).trim();
  const text = `${raw.slice(0, start)}${raw.slice(end + IMAGE_MARKER_SUFFIX.length)}`.trim();
  return { text, imageUrl: marker };
}

function composeDescription(text: string, imageUrl: string): string | null {
  const normalizedText = text.trim();
  if (!normalizedText && !imageUrl.trim()) {
    return null;
  }
  if (!imageUrl.trim()) {
    return normalizedText || null;
  }
  const chunks = [];
  if (normalizedText) {
    chunks.push(normalizedText);
  }
  chunks.push(`${IMAGE_MARKER_PREFIX}${imageUrl.trim()}${IMAGE_MARKER_SUFFIX}`);
  return chunks.join("\n\n");
}

const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  price: "",
  categoryId: "1",
  status: "active",
  imageUrl: "",
  quantity: "0",
};

export default function ProductCrudPage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  const [editingVariantId, setEditingVariantId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | ProductStatus>("all");
  const [csrfToken, setCsrfToken] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: "100", offset: "0" });
    if (statusFilter !== "all") {
      params.set("status", statusFilter);
    }
    return params.toString();
  }, [statusFilter]);

  const {
    data: productsResponse,
    error: fetchError,
    isLoading,
    mutate,
  } = useSWR<ProductListResponse>(`/api/erp/products?${query}`, fetcher);

  const products = productsResponse?.items ?? [];

  const variantIds = useMemo(
    () =>
      products
        .map((p) => p.variant_id)
        .filter((id): id is number => id != null && id > 0),
    [products]
  );
  const stockQuery = useMemo(
    () =>
      variantIds.length > 0
        ? `variant_ids=${variantIds.join(",")}`
        : null,
    [variantIds]
  );
  const {
    data: stockResponse,
    mutate: mutateStock,
  } = useSWR<{ items: { product_variant_id: number; quantity: number }[] }>(
    stockQuery ? `/api/erp/inventory/stock?${stockQuery}` : null,
    fetcher
  );
  const stockByVariant = useMemo(() => {
    const map = new Map<number, number>();
    for (const item of stockResponse?.items ?? []) {
      map.set(item.product_variant_id, item.quantity);
    }
    return map;
  }, [stockResponse]);

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

  async function uploadImage(file: File) {
    setIsUploading(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/upload/image", {
        method: "POST",
        body,
        headers: { "x-csrf-token": csrfToken },
      });
      const payload = await parseResponseJson<{ imageUrl?: string; detail?: string }>(response);
      if (!response.ok || !payload.imageUrl) {
        throw new Error(payload.detail ?? "Image upload failed.");
      }
      setForm((prev) => ({ ...prev, imageUrl: payload.imageUrl ?? "" }));
      setSuccess("Image uploaded successfully.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Image upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  function beginEdit(product: ProductApiItem) {
    const parsed = parseDescription(product.description);
    const variantId = product.variant_id ?? null;
    const qty = variantId != null ? stockByVariant.get(variantId) ?? 0 : 0;
    setEditingProductId(product.id);
    setEditingVariantId(variantId);
    setForm({
      name: product.name,
      description: parsed.text,
      price: String(product.price),
      categoryId: String(product.category_id),
      status: product.status,
      imageUrl: parsed.imageUrl,
      quantity: String(qty),
    });
    setError(null);
    setSuccess(null);
  }

  function clearForm() {
    setEditingProductId(null);
    setEditingVariantId(null);
    setForm(EMPTY_FORM);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    const payload = {
      name: form.name.trim(),
      description: composeDescription(form.description, form.imageUrl),
      price: Number(form.price),
      category_id: Number(form.categoryId),
      status: form.status,
    };

    try {
      const endpoint = editingProductId
        ? `/api/erp/products/${editingProductId}`
        : "/api/erp/products";
      const method = editingProductId ? "PATCH" : "POST";
      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json", "x-csrf-token": csrfToken },
        body: JSON.stringify(payload),
      });
      const json = await parseResponseJson(response);
      if (!response.ok) {
        throw new Error(json.detail ?? "Could not save product.");
      }
      if (editingVariantId != null) {
        const qtyNum = Math.max(0, Math.floor(Number(form.quantity)));
        const stockRes = await fetch(
          `/api/erp/inventory/stock/${editingVariantId}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "x-csrf-token": csrfToken },
            body: JSON.stringify({ quantity: qtyNum }),
          }
        );
        if (!stockRes.ok) {
          const stockJson = await parseResponseJson<{ detail?: string }>(stockRes);
          throw new Error(stockJson.detail ?? "Could not update quantity.");
        }
        await mutateStock();
      }
      await mutate();
      setSuccess(editingProductId ? "Product updated." : "Product created.");
      clearForm();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Save failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function removeProduct(productId: number) {
    setError(null);
    setSuccess(null);
    const confirmed = window.confirm("Delete this product?");
    if (!confirmed) {
      return;
    }
    const response = await fetch(`/api/erp/products/${productId}`, {
      method: "DELETE",
      headers: { "x-csrf-token": csrfToken },
    });
    if (response.status === 204) {
      await mutate();
      setSuccess("Product deleted.");
      if (editingProductId === productId) {
        clearForm();
      }
      return;
    }
    const payload = await parseResponseJson<{ detail?: string }>(response);
    const detail = payload.detail ?? "Delete failed.";
    setError(detail);
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
          <h1 className="text-2xl font-semibold text-slate-900">Product Management</h1>
          <p className="text-sm text-slate-600">
            Admin CRUD for ERP products with image upload and list management.
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

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
        <form onSubmit={onSubmit} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            {editingProductId ? `Edit Product #${editingProductId}` : "Create Product"}
          </h2>
          <div className="mt-4 space-y-3">
            <label className="block text-sm text-slate-700">
              Name
              <input
                required
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm text-slate-700">
              Description
              <textarea
                value={form.description}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, description: event.target.value }))
                }
                rows={4}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block text-sm text-slate-700">
                Price
                <input
                  required
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={form.price}
                  onChange={(event) => setForm((prev) => ({ ...prev, price: event.target.value }))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm text-slate-700">
                Category ID
                <input
                  required
                  type="number"
                  min="1"
                  value={form.categoryId}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, categoryId: event.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </label>
            </div>
            <label className="block text-sm text-slate-700">
              Status
              <select
                value={form.status}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, status: event.target.value as ProductStatus }))
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
            </label>

            {editingProductId != null && editingVariantId != null ? (
              <label className="block text-sm text-slate-700">
                Quantity (stock)
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={form.quantity}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, quantity: event.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </label>
            ) : null}

            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-600">Product Image (Cloudinary)</p>
              <input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    void uploadImage(file);
                  }
                }}
                className="mt-2 text-xs"
              />
              {isUploading ? <p className="mt-2 text-xs text-slate-600">Uploading image...</p> : null}
              {form.imageUrl ? (
                <div className="mt-3">
                  <div
                    className="h-28 w-full rounded bg-cover bg-center"
                    style={{ backgroundImage: `url(${form.imageUrl})` }}
                  />
                </div>
              ) : null}
            </div>
          </div>

          {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
          {success ? <p className="mt-3 text-sm text-emerald-700">{success}</p> : null}

          <div className="mt-4 flex gap-2">
            <button
              type="submit"
              disabled={isSubmitting || isUploading}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {isSubmitting ? "Saving..." : editingProductId ? "Update Product" : "Create Product"}
            </button>
            {editingProductId ? (
              <button
                type="button"
                onClick={clearForm}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700"
              >
                Cancel
              </button>
            ) : null}
          </div>
        </form>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Products</h2>
            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as "all" | ProductStatus)
              }
              className="rounded border border-slate-300 px-2 py-1 text-xs"
            >
              <option value="all">All statuses</option>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </div>

          {fetchError ? (
            <p className="text-sm text-red-600">
              {fetchError instanceof Error ? fetchError.message : "Could not load products."}
            </p>
          ) : null}
          {isLoading ? <p className="text-sm text-slate-600">Loading products...</p> : null}

          <ul className="space-y-3">
            {products.map((product) => {
              const parsed = parseDescription(product.description);
              return (
                <li key={product.id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex gap-3">
                    <div
                      className="h-16 w-16 shrink-0 rounded bg-slate-100 bg-cover bg-center"
                      style={{
                        backgroundImage: parsed.imageUrl ? `url(${parsed.imageUrl})` : undefined,
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{product.name}</p>
                          <p className="text-xs text-slate-500">
                            ID #{product.id} · Category {product.category_id} · {product.status}
                            {product.variant_id != null ? (
                              <> · Qty: {stockByVariant.get(product.variant_id) ?? "—"}</>
                            ) : null}
                          </p>
                        </div>
                        <p className="text-sm font-semibold text-slate-800">
                          ${Number(product.price).toFixed(2)}
                        </p>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-600">
                        {parsed.text || "No description"}
                      </p>
                      <div className="mt-3 flex gap-2">
                        <button
                          type="button"
                          onClick={() => beginEdit(product)}
                          className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void removeProduct(product.id)}
                          className="rounded border border-red-200 px-2 py-1 text-xs text-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      </section>
    </main>
  );
}
