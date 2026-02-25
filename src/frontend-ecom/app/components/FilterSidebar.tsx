import { useEffect, useMemo, useState } from "react";

export type ProductFilterState = {
  categories: string[];
  priceMin: number;
  priceMax: number;
};

type FilterSidebarProps = {
  categories: string[];
  initialMin: number;
  initialMax: number;
  onChange: (filters: ProductFilterState) => void;
};

export default function FilterSidebar({
  categories,
  initialMin,
  initialMax,
  onChange,
}: FilterSidebarProps) {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [minValue, setMinValue] = useState<number>(initialMin);
  const [maxValue, setMaxValue] = useState<number>(initialMax);

  const sortedCategories = useMemo(() => [...categories].sort(), [categories]);
  const safeMin = Math.min(minValue, maxValue);
  const safeMax = Math.max(minValue, maxValue);

  useEffect(() => {
    const timeout = setTimeout(() => {
      onChange({
        categories: selectedCategories,
        priceMin: safeMin,
        priceMax: safeMax,
      });
    }, 220);

    return () => clearTimeout(timeout);
  }, [selectedCategories, safeMin, safeMax, onChange]);

  const toggleCategory = (category: string) => {
    setSelectedCategories((current) =>
      current.includes(category) ? current.filter((value) => value !== category) : [...current, category]
    );
  };

  const clearFilters = () => {
    setSelectedCategories([]);
    setMinValue(initialMin);
    setMaxValue(initialMax);
    onChange({
      categories: [],
      priceMin: initialMin,
      priceMax: initialMax,
    });
  };

  return (
    <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Filters</h2>
        <button
          type="button"
          onClick={clearFilters}
          className="text-xs font-medium text-sky-700 hover:text-sky-600"
        >
          Clear all
        </button>
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-800">Categories</h3>
        <div className="space-y-2">
          {sortedCategories.map((category) => (
            <label key={category} className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={selectedCategories.includes(category)}
                onChange={() => toggleCategory(category)}
                className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
              />
              {category}
            </label>
          ))}
        </div>
      </section>

      <section className="mt-6 space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">Price range</h3>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500" htmlFor="price-min">
            Min (${minValue})
          </label>
          <input
            id="price-min"
            type="range"
            min={initialMin}
            max={initialMax}
            step={1}
            value={minValue}
            onChange={(event) => setMinValue(Number(event.target.value))}
            className="w-full accent-sky-600"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500" htmlFor="price-max">
            Max (${maxValue})
          </label>
          <input
            id="price-max"
            type="range"
            min={initialMin}
            max={initialMax}
            step={1}
            value={maxValue}
            onChange={(event) => setMaxValue(Number(event.target.value))}
            className="w-full accent-sky-600"
          />
        </div>
      </section>
    </aside>
  );
}

