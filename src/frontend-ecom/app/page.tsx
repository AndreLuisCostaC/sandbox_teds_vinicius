"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import CartDrawer from "./components/CartDrawer";
import FilterSidebar, { type ProductFilterState } from "./components/FilterSidebar";
import ProductGrid from "./components/ProductGrid";
import { useCart } from "./context/CartContext";

type ApiProduct = {
  id: number;
  name: string;
  description: string | null;
  price: string;
  category_id: number;
  is_active: boolean;
  status: "active" | "inactive";
  variant_id?: number | null;
};

type ApiProductListResponse = {
  items: ApiProduct[];
  total: number;
  limit: number;
  offset: number;
};

type ApiHybridSearchItem = {
  product: ApiProduct;
  score: number;
  matched_by: "semantic" | "keyword" | "hybrid";
};

type ApiHybridSearchResponse = {
  query: string;
  total: number;
  limit: number;
  offset: number;
  items: ApiHybridSearchItem[];
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
  const {
    items: cartItems,
    subtotal,
    itemCount,
    addItem,
    updateItemQuantity,
    removeItem,
    checkout,
    isSyncing,
    isOpen,
    openCart,
    closeCart,
  } = useCart();
  const [sort, setSort] = useState<SortOption>("best_sellers");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [filters, setFilters] = useState<ProductFilterState>({
    categories: [],
    priceMin: DEFAULT_MIN_PRICE,
    priceMax: DEFAULT_MAX_PRICE,
  });
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [searchQuery]);

  const {
    data,
    isLoading,
    isError,
    refetch,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery<ApiProductListResponse | ApiHybridSearchResponse>({
    queryKey: ["products", filters, sort, debouncedSearchQuery],
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

      const isSemanticSearch = debouncedSearchQuery.length > 0;
      if (isSemanticSearch) {
        params.set("query", debouncedSearchQuery);
      }
      const route = isSemanticSearch ? "/api/v1/search" : "/api/v1/products";
      const response = await fetch(`${API_BASE_URL}${route}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(isSemanticSearch ? "Failed to search products" : "Failed to fetch products");
      }
      return (await response.json()) as ApiProductListResponse | ApiHybridSearchResponse;
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
    if (!data?.pages) {
      return [];
    }
    return data.pages.flatMap((page) => {
      if ("query" in page) {
        return page.items.map((entry) => ({
          ...entry.product,
          description:
            `${entry.product.description ?? "No description available."} · ` +
            `Match: ${entry.matched_by} (${(entry.score * 100).toFixed(1)}%)`,
        }));
      }
      return page.items;
    });
  }, [data]);

  const totalProducts = data?.pages[0]?.total ?? 0;

  const categories = useMemo(() => {
    const items = allProducts;
    return Array.from(new Set(items.map((item) => categoryLabel(item.category_id))));
  }, [allProducts]);

  const visibleProducts = useMemo(() => {
    const mapped = allProducts.map((item) => ({
      id: item.id,
      variantId: item.variant_id ?? null,
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

    if (debouncedSearchQuery.length > 0) {
      return filteredByCategory;
    }
    if (sort === "price_asc") {
      return [...filteredByCategory].sort((a, b) => numericPrice(a.price.slice(1)) - numericPrice(b.price.slice(1)));
    }
    if (sort === "price_desc") {
      return [...filteredByCategory].sort((a, b) => numericPrice(b.price.slice(1)) - numericPrice(a.price.slice(1)));
    }
    return [...filteredByCategory].sort((a, b) => b.id - a.id);
  }, [allProducts, debouncedSearchQuery, filters.categories, sort]);

  const cartStateByProduct = useMemo(() => {
    const entry = Object.fromEntries(
      cartItems.map((item) => [item.productVariantId, { quantity: item.quantity }])
    );
    return entry;
  }, [cartItems]);

  const handleAddToCart = async (product: (typeof visibleProducts)[number]) => {
    const variantId = product.variantId;
    if (variantId == null) {
      return;
    }
    await addItem(
      {
        productVariantId: variantId,
        name: product.name,
        price: Number(product.price.slice(1)),
        imageUrl: product.imageUrl,
      },
      1
    );
  };

  const handleIncrease = async (product: (typeof visibleProducts)[number]) => {
    const variantId = product.variantId;
    if (variantId == null) return;
    const quantity = cartStateByProduct[variantId]?.quantity ?? 0;
    await updateItemQuantity(variantId, quantity + 1);
  };

  const handleDecrease = async (product: (typeof visibleProducts)[number]) => {
    const variantId = product.variantId;
    if (variantId == null) return;
    const quantity = cartStateByProduct[variantId]?.quantity ?? 0;
    if (quantity <= 1) {
      await removeItem(variantId);
      return;
    }
    await updateItemQuantity(variantId, quantity - 1);
  };

  const handleRemove = async (product: (typeof visibleProducts)[number]) => {
    const variantId = product.variantId;
    if (variantId == null) return;
    await removeItem(variantId);
  };

  const handleIncreaseFromDrawer = async (item: (typeof cartItems)[number]) => {
    await updateItemQuantity(item.productVariantId, item.quantity + 1);
  };

  const handleDecreaseFromDrawer = async (item: (typeof cartItems)[number]) => {
    if (item.quantity <= 1) {
      await removeItem(item.productVariantId);
      return;
    }
    await updateItemQuantity(item.productVariantId, item.quantity - 1);
  };

  const handleRemoveFromDrawer = async (item: (typeof cartItems)[number]) => {
    await removeItem(item.productVariantId);
  };

  const CartIcon = () => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-6 w-6"
      aria-hidden
    >
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );

  return (
    <main className="min-h-screen bg-slate-50">
      <button
        type="button"
        onClick={openCart}
        aria-label={`Open cart (${itemCount} items)`}
        className="fixed right-6 top-6 z-50 flex items-center gap-2 rounded-full bg-slate-900 px-4 py-3 text-white shadow-lg transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
      >
        <CartIcon />
        <span className="text-sm font-semibold">
          {itemCount} · ${subtotal.toFixed(2)}
        </span>
        {itemCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-sky-500 text-xs font-bold text-white">
            {itemCount}
          </span>
        )}
      </button>

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
          <div className="rounded-xl border border-slate-200 bg-white p-3">
            <label htmlFor="semantic-search" className="mb-2 block text-sm font-medium text-slate-700">
              Semantic search
            </label>
            <input
              id="semantic-search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Try: comfortable running shoes"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none ring-sky-500 focus:ring-2"
            />
            <p className="mt-2 text-xs text-slate-500">
              {debouncedSearchQuery
                ? `Showing semantic+keyword results for "${debouncedSearchQuery}".`
                : "Type to use hybrid semantic search (Task 6)."}
            </p>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Sort products</p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={openCart}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 transition hover:bg-slate-50"
              >
                Cart: <span className="font-semibold">{itemCount}</span> items · $
                <span className="font-semibold">{subtotal.toFixed(2)}</span>
              </button>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SortOption)}
                disabled={debouncedSearchQuery.length > 0}
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none ring-sky-500 focus:ring-2"
              >
                <option value="best_sellers">Best sellers</option>
                <option value="price_asc">Price: low to high</option>
                <option value="price_desc">Price: high to low</option>
              </select>
            </div>
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
              <ProductGrid
                products={visibleProducts}
                isLoading={isLoading}
                cartState={cartStateByProduct}
                onAddToCart={handleAddToCart}
                onIncrease={handleIncrease}
                onDecrease={handleDecrease}
                onRemove={handleRemove}
                isSyncingCart={isSyncing}
              />

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
      <CartDrawer
        isOpen={isOpen}
        items={cartItems}
        subtotal={subtotal}
        isSyncing={isSyncing}
        onClose={closeCart}
        onCheckout={async () => {
          await checkout();
        }}
        onIncrease={handleIncreaseFromDrawer}
        onDecrease={handleDecreaseFromDrawer}
        onRemove={handleRemoveFromDrawer}
      />
    </main>
  );
}
