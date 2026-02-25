type ProductCard = {
  id: number;
  name: string;
  description: string;
  price: string;
  imageUrl: string;
  category: string;
};

type ProductGridProps = {
  products: ProductCard[];
  isLoading?: boolean;
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

export default function ProductGrid({ products, isLoading = false }: ProductGridProps) {
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
              </div>
            </article>
            ))}
      </div>
    </section>
  );
}

