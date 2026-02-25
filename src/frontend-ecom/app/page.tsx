"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import FilterSidebar, { type ProductFilterState } from "./components/FilterSidebar";
import ProductGrid from "./components/ProductGrid";

type ApiProduct = {
  id: number;
  name: string;
  description: string | null;
  price: string;
  category_id: number;
  is_active: boolean;
  status: "active" | "inactive";
};

type ApiProductListResponse = {
  items: ApiProduct[];
  total: number;
  limit: number;
  offset: number;
};

type SortOption = "price_asc" | "price_desc" | "best_sellers";

const DEFAULT_MIN_PRICE = 0;
const DEFAULT_MAX_PRICE = 500;
const PAGE_SIZE = 8;
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const numericPrice = (priceLabel: string) => Number(priceLabel);
const categoryLabel = (categoryId: number) => `Category ${categoryId}`;
const productImageFromId = (id: number) =>
  `https://picsum.photos/seed/prodgrade-${id}/900/600`;

export default function Home() {
  const [sort, setSort] = useState<SortOption>("best_sellers");
  const [filters, setFilters] = useState<ProductFilterState>({
    categories: [],
    priceMin: DEFAULT_MIN_PRICE,
    priceMax: DEFAULT_MAX_PRICE,
  });
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const {
    data,
    isLoading,
    isError,
    refetch,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery<ApiProductListResponse>({
    queryKey: ["products", filters, sort],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
        price_min: String(filters.priceMin),
        price_max: String(filters.priceMax),
        sort,
      });

      if (filters.categories.length === 1) {
        const onlyCategory = filters.categories[0]?.replace("Category ", "");
        if (onlyCategory) {
          params.set("category", onlyCategory);
        }
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/products?${params.toString()}`);
      if (!response.ok) {
        throw new Error("Failed to fetch products");
      }
      return (await response.json()) as ApiProductListResponse;
    },
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.limit;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
  });

  useEffect(() => {
    if (!loadMoreRef.current || !hasNextPage || isFetchingNextPage) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry?.isIntersecting) {
          fetchNextPage();
        }
      },
      { root: null, rootMargin: "300px", threshold: 0.01 }
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  const allProducts = useMemo(() => {
    return data?.pages.flatMap((page) => page.items) ?? [];
  }, [data?.pages]);

  const totalProducts = data?.pages[0]?.total ?? 0;

  const categories = useMemo(() => {
    const items = allProducts;
    return Array.from(new Set(items.map((item) => categoryLabel(item.category_id))));
  }, [allProducts]);

  const visibleProducts = useMemo(() => {
    const mapped = allProducts.map((item) => ({
      id: item.id,
      name: item.name,
      description: item.description ?? "No description available.",
      price: `$${Number(item.price).toFixed(2)}`,
      imageUrl: productImageFromId(item.id),
      category: categoryLabel(item.category_id),
    }));

    const filteredByCategory =
      filters.categories.length === 0
        ? mapped
        : mapped.filter((item) => filters.categories.includes(item.category));

    if (sort === "price_asc") {
      return [...filteredByCategory].sort((a, b) => numericPrice(a.price.slice(1)) - numericPrice(b.price.slice(1)));
    }
    if (sort === "price_desc") {
      return [...filteredByCategory].sort((a, b) => numericPrice(b.price.slice(1)) - numericPrice(a.price.slice(1)));
    }
    return [...filteredByCategory].sort((a, b) => b.id - a.id);
  }, [allProducts, filters.categories, sort]);

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="relative overflow-hidden bg-slate-950">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(56,189,248,0.28),_transparent_40%)]" />
        <div className="mx-auto max-w-7xl px-6 py-20 md:px-10 md:py-24">
          <p className="mb-4 inline-flex rounded-full border border-sky-300/40 bg-sky-400/10 px-3 py-1 text-xs font-medium uppercase tracking-widest text-sky-200">
            New collection
          </p>
          <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-white md:text-5xl">
            Shop smarter with modern essentials for everyday life.
          </h1>
          <p className="mt-5 max-w-2xl text-base text-slate-300 md:text-lg">
            Discover curated products with premium quality, clean design, and fast delivery.
            Built to keep your routine moving.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <button className="rounded-lg bg-sky-400 px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-sky-300">
              Shop now
            </button>
            <button className="rounded-lg border border-slate-600 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-slate-400">
              Explore categories
            </button>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-10 md:grid-cols-[280px_1fr] md:px-10 md:py-12">
        <FilterSidebar
          categories={categories}
          initialMin={DEFAULT_MIN_PRICE}
          initialMax={DEFAULT_MAX_PRICE}
          onChange={setFilters}
        />
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Sort products</p>
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as SortOption)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none ring-sky-500 focus:ring-2"
            >
              <option value="best_sellers">Best sellers</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
            </select>
          </div>

          {isError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Failed to load products.
              <button
                type="button"
                onClick={() => refetch()}
                className="ml-2 font-semibold underline"
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              <ProductGrid products={visibleProducts} isLoading={isLoading} />

              {!isLoading && visibleProducts.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
                  No products match your current filters.
                </div>
              ) : null}

              <div ref={loadMoreRef} className="h-4" />

              {isFetchingNextPage ? (
                <p className="text-center text-sm text-slate-500">Loading more products...</p>
              ) : null}

              {!hasNextPage && !isLoading && visibleProducts.length > 0 ? (
                <p className="text-center text-sm text-slate-500">
                  End of catalog ({Math.min(visibleProducts.length, totalProducts)} of {totalProducts})
                </p>
              ) : null}
            </>
          )}
        </div>
      </section>
    </main>
  );
}
