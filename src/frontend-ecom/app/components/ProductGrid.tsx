type ProductCard = {
  id: number;
  variantId: number | null;
  name: string;
  description: string;
  price: string;
  imageUrl: string;
  category: string;
};

type ProductCartState = {
  quantity: number;
};

type ProductGridProps = {
  products: ProductCard[];
  isLoading?: boolean;
  cartState?: Record<number, ProductCartState>;
  onAddToCart?: (product: ProductCard) => void;
  onIncrease?: (product: ProductCard) => void;
  onDecrease?: (product: ProductCard) => void;
  onRemove?: (product: ProductCard) => void;
  isSyncingCart?: boolean;
};

function ProductSkeletonCard() {
  return (
    <div className="animate-pulse overflow-hidden rounded-xl border border-sky-100 bg-white shadow-sm">
      <div className="h-44 w-full bg-sky-100" />
      <div className="space-y-3 p-4">
        <div className="h-4 w-2/3 rounded bg-sky-100" />
        <div className="h-3 w-full rounded bg-sky-50" />
        <div className="h-3 w-4/5 rounded bg-sky-50" />
        <div className="h-4 w-1/4 rounded bg-sky-100" />
      </div>
    </div>
  );
}

export default function ProductGrid({
  products,
  isLoading = false,
  cartState = {},
  onAddToCart,
  onIncrease,
  onDecrease,
  onRemove,
  isSyncingCart = false,
}: ProductGridProps) {
  return (
    <section aria-label="Product grid" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Featured products</h2>
        <span className="text-sm text-slate-500">
          {isLoading ? "Loading..." : `${products.length} items`}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: 8 }).map((_, idx) => (
            <ProductSkeletonCard key={`skeleton-${idx}`} />
            ))
          : products.map((item) => (
            <article
              key={item.id}
              className="overflow-hidden rounded-xl border border-sky-100 bg-white shadow-sm transition-transform hover:-translate-y-0.5"
            >
              <div
                aria-label={item.name}
                className="h-44 w-full bg-sky-50 bg-cover bg-center"
                style={{ backgroundImage: `url(${item.imageUrl})` }}
              />

              <div className="space-y-2 p-4">
                <h3 className="text-lg font-medium text-slate-900">{item.name}</h3>
                <p className="text-sm text-slate-600">{item.description}</p>
                <p className="pt-1 text-base font-semibold text-sky-700">{item.price}</p>
                {item.variantId != null && cartState[item.variantId] ? (
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onDecrease?.(item)}
                      disabled={isSyncingCart}
                      className="rounded border border-slate-300 px-2 py-1 text-sm text-slate-700 disabled:opacity-50"
                    >
                      -
                    </button>
                    <span className="text-sm text-slate-700">{cartState[item.variantId]?.quantity}</span>
                    <button
                      type="button"
                      onClick={() => onIncrease?.(item)}
                      disabled={isSyncingCart}
                      className="rounded border border-slate-300 px-2 py-1 text-sm text-slate-700 disabled:opacity-50"
                    >
                      +
                    </button>
                    <button
                      type="button"
                      onClick={() => onRemove?.(item)}
                      disabled={isSyncingCart}
                      className="ml-auto rounded border border-red-200 px-2 py-1 text-xs text-red-700 disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => onAddToCart?.(item)}
                    disabled={isSyncingCart || item.variantId == null}
                    className="mt-3 w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-50"
                  >
                    {item.variantId == null ? "Unavailable" : "Add to cart"}
                  </button>
                )}
              </div>
            </article>
            ))}
      </div>
    </section>
  );
}

