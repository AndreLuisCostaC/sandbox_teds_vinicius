"use client";

import { useState } from "react";
import type { CartUiItem } from "../context/CartContext";

type CartDrawerProps = {
  isOpen: boolean;
  items: CartUiItem[];
  subtotal: number;
  isSyncing: boolean;
  onClose: () => void;
  onCheckout: () => Promise<void>;
  onIncrease: (item: CartUiItem) => void;
  onDecrease: (item: CartUiItem) => void;
  onRemove: (item: CartUiItem) => void;
};

export default function CartDrawer({
  isOpen,
  items,
  subtotal,
  isSyncing,
  onClose,
  onCheckout,
  onIncrease,
  onDecrease,
  onRemove,
}: CartDrawerProps) {
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const handleCheckout = async () => {
    setIsCheckingOut(true);
    try {
      await onCheckout();
    } finally {
      setIsCheckingOut(false);
    }
  };
  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-slate-900/45 transition-opacity ${
          isOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        aria-label="Shopping cart"
        className={`fixed right-0 top-0 z-50 h-full w-full max-w-md transform border-l border-slate-200 bg-white shadow-xl transition-transform ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <h2 className="text-lg font-semibold text-slate-900">Your cart</h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-slate-300 px-2 py-1 text-sm text-slate-700"
            >
              Close
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {items.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                Your cart is empty.
              </div>
            ) : (
              items.map((item) => (
                <article key={item.productVariantId} className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="flex gap-3">
                    <div
                      className="h-16 w-16 shrink-0 rounded bg-slate-100 bg-cover bg-center"
                      style={{ backgroundImage: item.imageUrl ? `url(${item.imageUrl})` : undefined }}
                    />
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-sm font-medium text-slate-900">{item.name}</h3>
                      <p className="text-xs text-slate-500">${item.price.toFixed(2)} each</p>
                      <p className="text-xs font-medium text-slate-700">
                        Subtotal: ${(item.price * item.quantity).toFixed(2)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onDecrease(item)}
                      disabled={isSyncing}
                      className="rounded border border-slate-300 px-2 py-1 text-sm disabled:opacity-50"
                    >
                      -
                    </button>
                    <span className="text-sm text-slate-700">{item.quantity}</span>
                    <button
                      type="button"
                      onClick={() => onIncrease(item)}
                      disabled={isSyncing}
                      className="rounded border border-slate-300 px-2 py-1 text-sm disabled:opacity-50"
                    >
                      +
                    </button>
                    <button
                      type="button"
                      onClick={() => onRemove(item)}
                      disabled={isSyncing}
                      className="ml-auto rounded border border-red-200 px-2 py-1 text-xs text-red-700 disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>

          <div className="border-t border-slate-200 p-4">
            <div className="flex items-center justify-between text-sm text-slate-700">
              <span>Grand total</span>
              <span className="text-base font-semibold text-slate-900">${subtotal.toFixed(2)}</span>
            </div>
            <button
              type="button"
              onClick={handleCheckout}
              disabled={items.length === 0 || isSyncing || isCheckingOut}
              className="mt-3 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {isCheckingOut ? "Processing..." : "Checkout"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
