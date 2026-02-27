"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const GUEST_CART_STORAGE_KEY = "cart_state";
const GUEST_CART_UUID_KEY = "cart_uuid";
const ACCESS_TOKEN_STORAGE_KEY = "access_token";
const CART_DRAWER_OPEN_KEY = "cart_drawer_open";

export type CartUiItem = {
  productVariantId: number;
  name: string;
  price: number;
  quantity: number;
  imageUrl?: string;
  cartItemId?: number;
};

type CartState = {
  cartId: number | null;
  guestToken: string | null;
  mode: "guest" | "auth";
  items: CartUiItem[];
  isOpen: boolean;
  hydrated: boolean;
};

type CartAction =
  | { type: "hydrate"; payload: Partial<CartState> }
  | { type: "set_cart_meta"; payload: { cartId: number; guestToken: string | null; mode: "guest" | "auth" } }
  | { type: "set_items"; payload: CartUiItem[] }
  | { type: "set_open"; payload: boolean }
  | { type: "mark_hydrated" }
  | { type: "reset_cart" };

type ToastState = {
  message: string;
  tone: "success" | "error";
} | null;

type CartContextValue = {
  items: CartUiItem[];
  cartId: number | null;
  subtotal: number;
  itemCount: number;
  isOpen: boolean;
  openCart: () => void;
  closeCart: () => void;
  toggleCart: () => void;
  addItem: (item: Omit<CartUiItem, "quantity" | "cartItemId">, quantity?: number) => Promise<void>;
  updateItemQuantity: (productVariantId: number, quantity: number) => Promise<void>;
  removeItem: (productVariantId: number) => Promise<void>;
  checkout: () => Promise<{ orderId: number } | null>;
  isSyncing: boolean;
};

const initialState: CartState = {
  cartId: null,
  guestToken: null,
  mode: "guest",
  items: [],
  isOpen: false,
  hydrated: false,
};

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case "hydrate":
      return { ...state, ...action.payload };
    case "set_cart_meta":
      return {
        ...state,
        cartId: action.payload.cartId,
        guestToken: action.payload.guestToken,
        mode: action.payload.mode,
      };
    case "set_items":
      return { ...state, items: action.payload };
    case "set_open":
      return { ...state, isOpen: action.payload };
    case "mark_hydrated":
      return { ...state, hydrated: true };
    case "reset_cart":
      return {
        ...initialState,
        hydrated: true,
      };
    default:
      return state;
  }
}

const CartContext = createContext<CartContextValue | null>(null);

function decodeJwtSubject(token: string): number | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || !parts[1]) {
      return null;
    }
    const payload = JSON.parse(atob(parts[1]));
    const rawSubject = payload?.sub;
    if (typeof rawSubject !== "string") {
      return null;
    }
    const parsed = Number(rawSubject);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, initialState);
  const [toast, setToast] = useState<ToastState>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const isAuthenticated = Boolean(authToken);

  const showToast = useCallback((message: string, tone: "success" | "error") => {
    setToast({ message, tone });
    window.setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const syncToken = () => {
      setAuthToken(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY));
    };
    syncToken();
    const intervalId = window.setInterval(syncToken, 1000);
    window.addEventListener("storage", syncToken);
    window.addEventListener("focus", syncToken);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("storage", syncToken);
      window.removeEventListener("focus", syncToken);
    };
  }, []);

  const authHeaders = useMemo(() => {
    if (!authToken) {
      return {};
    }
    return { Authorization: `Bearer ${authToken}` };
  }, [authToken]);

  const persistGuestState = useCallback((next: { cartId: number | null; guestToken: string | null; items: CartUiItem[] }) => {
    if (typeof window === "undefined") {
      return;
    }
    const serialized = JSON.stringify(next);
    window.localStorage.setItem(GUEST_CART_STORAGE_KEY, serialized);
    if (next.guestToken) {
      window.localStorage.setItem(GUEST_CART_UUID_KEY, next.guestToken);
    }
  }, []);

  const createCart = useCallback(
    async (mode: "guest" | "auth", userId?: number | null): Promise<{ cartId: number; guestToken: string | null }> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/carts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(mode === "auth" ? authHeaders : {}),
        },
        body: JSON.stringify(mode === "auth" ? { user_id: userId } : {}),
      });
      if (!response.ok) {
        throw new Error("Failed to create cart");
      }
      const data = (await response.json()) as { id: number; guest_token: string | null };
      return { cartId: data.id, guestToken: data.guest_token };
    },
    [authHeaders]
  );

  useEffect(() => {
    const run = async () => {
      setIsSyncing(true);
      try {
        const savedGuestStateRaw =
          typeof window !== "undefined" ? window.localStorage.getItem(GUEST_CART_STORAGE_KEY) : null;
        const savedGuestState = savedGuestStateRaw
          ? (JSON.parse(savedGuestStateRaw) as {
              cartId: number | null;
              guestToken: string | null;
              items: CartUiItem[];
            })
          : null;
        const savedDrawerOpen =
          typeof window !== "undefined"
            ? window.localStorage.getItem(CART_DRAWER_OPEN_KEY) === "true"
            : false;

        if (!isAuthenticated) {
          if (savedGuestState?.cartId && savedGuestState?.guestToken) {
            dispatch({
              type: "hydrate",
              payload: {
                mode: "guest",
                cartId: savedGuestState.cartId,
                guestToken: savedGuestState.guestToken,
                items: savedGuestState.items ?? [],
                isOpen: savedDrawerOpen,
              },
            });
          } else {
            const { cartId, guestToken } = await createCart("guest");
            dispatch({
              type: "set_cart_meta",
              payload: { cartId, guestToken, mode: "guest" },
            });
            dispatch({ type: "set_open", payload: savedDrawerOpen });
            persistGuestState({ cartId, guestToken, items: [] });
          }
        } else {
          const userId = authToken ? decodeJwtSubject(authToken) : null;
          const { cartId } = await createCart("auth", userId);
          dispatch({
            type: "set_cart_meta",
            payload: { cartId, guestToken: null, mode: "auth" },
          });
          dispatch({ type: "set_open", payload: savedDrawerOpen });

          const mergedFromGuest = new Map<number, CartUiItem>();
          const guestItems = savedGuestState?.items ?? [];
          const failedGuestItems: CartUiItem[] = [];
          if (guestItems.length > 0) {
            for (const item of guestItems) {
              const mergeResponse = await fetch(`${API_BASE_URL}/api/v1/carts/${cartId}/items`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  ...authHeaders,
                },
                body: JSON.stringify({
                  product_variant_id: item.productVariantId,
                  quantity: item.quantity,
                }),
              });
              if (mergeResponse.ok) {
                const payload = (await mergeResponse.json()) as {
                  id: number;
                  product_variant_id: number;
                  quantity: number;
                };
                mergedFromGuest.set(payload.product_variant_id, {
                  ...item,
                  cartItemId: payload.id,
                  quantity: payload.quantity,
                });
              } else {
                failedGuestItems.push(item);
              }
            }
          }

          const cartResponse = await fetch(`${API_BASE_URL}/api/v1/carts/${cartId}`, {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              ...authHeaders,
            },
          });
          if (!cartResponse.ok) {
            throw new Error("Failed to load authenticated cart");
          }
          const cartPayload = (await cartResponse.json()) as {
            items: { id: number; product_variant_id: number; quantity: number }[];
          };
          const hydratedItems: CartUiItem[] = cartPayload.items.map((item) => {
            const merged = mergedFromGuest.get(item.product_variant_id);
            return {
              productVariantId: item.product_variant_id,
              quantity: item.quantity,
              cartItemId: item.id,
              name: merged?.name ?? `Variant #${item.product_variant_id}`,
              price: merged?.price ?? 0,
              imageUrl: merged?.imageUrl,
            };
          });
          dispatch({ type: "set_items", payload: hydratedItems });

          if (failedGuestItems.length > 0 && savedGuestState) {
            persistGuestState({
              cartId: savedGuestState.cartId,
              guestToken: savedGuestState.guestToken,
              items: failedGuestItems,
            });
            showToast("Some guest cart items could not be synced due to stock limits.", "error");
          } else if (savedGuestState) {
            window.localStorage.removeItem(GUEST_CART_STORAGE_KEY);
            window.localStorage.removeItem(GUEST_CART_UUID_KEY);
            if (guestItems.length > 0) {
              showToast("Guest cart synced to your account.", "success");
            }
          }
        }
      } catch {
        showToast("Failed to initialize cart.", "error");
      } finally {
        dispatch({ type: "mark_hydrated" });
        setIsSyncing(false);
      }
    };

    void run();
  }, [authHeaders, authToken, createCart, isAuthenticated, persistGuestState, showToast]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(CART_DRAWER_OPEN_KEY, String(state.isOpen));
  }, [state.isOpen]);

  const openCart = useCallback(() => dispatch({ type: "set_open", payload: true }), []);
  const closeCart = useCallback(() => dispatch({ type: "set_open", payload: false }), []);
  const toggleCart = useCallback(() => dispatch({ type: "set_open", payload: !state.isOpen }), [state.isOpen]);

  const addItem = useCallback<CartContextValue["addItem"]>(
    async (item, quantity = 1) => {
      if (!state.cartId) {
        showToast("Cart is not ready yet.", "error");
        return;
      }
      setIsSyncing(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/carts/${state.cartId}/items`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(state.mode === "guest" ? { "x-guest-token": state.guestToken ?? "" } : authHeaders),
          },
          body: JSON.stringify({
            product_variant_id: item.productVariantId,
            quantity,
          }),
        });

        if (response.status === 409) {
          const payload = (await response.json()) as { detail?: string };
          showToast(payload.detail ?? "Insufficient stock for this item.", "error");
          return;
        }
        if (!response.ok) {
          throw new Error("Failed to add item");
        }

        const payload = (await response.json()) as { id: number; quantity: number; product_variant_id: number };
        const existing = state.items.find((cartItem) => cartItem.productVariantId === item.productVariantId);
        const nextItems = existing
          ? state.items.map((cartItem) =>
              cartItem.productVariantId === item.productVariantId
                ? { ...cartItem, quantity: payload.quantity, cartItemId: payload.id }
                : cartItem
            )
          : [...state.items, { ...item, quantity: payload.quantity, cartItemId: payload.id }];

        dispatch({ type: "set_items", payload: nextItems });
        if (state.mode === "guest") {
          persistGuestState({ cartId: state.cartId, guestToken: state.guestToken, items: nextItems });
        }
      } catch {
        showToast("Could not add item to cart.", "error");
      } finally {
        setIsSyncing(false);
      }
    },
    [authHeaders, persistGuestState, showToast, state.cartId, state.guestToken, state.items, state.mode]
  );

  const updateItemQuantity = useCallback<CartContextValue["updateItemQuantity"]>(
    async (productVariantId, quantity) => {
      if (!state.cartId) {
        return;
      }
      const target = state.items.find((item) => item.productVariantId === productVariantId);
      if (!target?.cartItemId) {
        return;
      }

      setIsSyncing(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/carts/${state.cartId}/items/${target.cartItemId}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            ...(state.mode === "guest" ? { "x-guest-token": state.guestToken ?? "" } : authHeaders),
          },
          body: JSON.stringify({ quantity }),
        });

        if (response.status === 409) {
          const payload = (await response.json()) as { detail?: string };
          showToast(payload.detail ?? "Insufficient stock for this update.", "error");
          return;
        }
        if (!response.ok) {
          throw new Error("Failed to update item quantity");
        }

        const payload = (await response.json()) as { quantity: number };
        const nextItems = state.items.map((item) =>
          item.productVariantId === productVariantId ? { ...item, quantity: payload.quantity } : item
        );
        dispatch({ type: "set_items", payload: nextItems });
        if (state.mode === "guest") {
          persistGuestState({ cartId: state.cartId, guestToken: state.guestToken, items: nextItems });
        }
      } catch {
        showToast("Could not update cart item.", "error");
      } finally {
        setIsSyncing(false);
      }
    },
    [authHeaders, persistGuestState, showToast, state.cartId, state.guestToken, state.items, state.mode]
  );

  const removeItem = useCallback<CartContextValue["removeItem"]>(
    async (productVariantId) => {
      if (!state.cartId) {
        return;
      }
      const target = state.items.find((item) => item.productVariantId === productVariantId);
      if (!target?.cartItemId) {
        return;
      }

      setIsSyncing(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/carts/${state.cartId}/items/${target.cartItemId}`, {
          method: "DELETE",
          headers: state.mode === "guest" ? { "x-guest-token": state.guestToken ?? "" } : authHeaders,
        });
        if (!response.ok) {
          throw new Error("Failed to delete cart item");
        }

        const nextItems = state.items.filter((item) => item.productVariantId !== productVariantId);
        dispatch({ type: "set_items", payload: nextItems });
        if (state.mode === "guest") {
          persistGuestState({ cartId: state.cartId, guestToken: state.guestToken, items: nextItems });
        }
      } catch {
        showToast("Could not remove cart item.", "error");
      } finally {
        setIsSyncing(false);
      }
    },
    [authHeaders, persistGuestState, showToast, state.cartId, state.guestToken, state.items, state.mode]
  );

  const checkout = useCallback<CartContextValue["checkout"]>(
    async () => {
      if (!state.cartId || state.items.length === 0) {
        showToast("Cart is empty.", "error");
        return null;
      }
      setIsSyncing(true);
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          ...(state.mode === "guest"
            ? { "x-guest-token": state.guestToken ?? "" }
            : authHeaders),
        };
        const response = await fetch(`${API_BASE_URL}/api/v1/orders/checkout`, {
          method: "POST",
          headers,
          body: JSON.stringify({ cart_id: state.cartId, currency: "USD" }),
        });
        const payload = (await response.json()) as { id?: number; detail?: string };
        if (!response.ok) {
          throw new Error(payload.detail ?? "Checkout failed");
        }
        const orderId = payload.id;
        if (typeof orderId !== "number") {
          throw new Error("Invalid order response");
        }
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(GUEST_CART_STORAGE_KEY);
          window.localStorage.removeItem(GUEST_CART_UUID_KEY);
        }
        dispatch({ type: "reset_cart" });
        dispatch({ type: "set_open", payload: false });
        showToast(`Order #${orderId} placed successfully. Stock reserved.`, "success");
        return { orderId };
      } catch (err) {
        showToast(err instanceof Error ? err.message : "Checkout failed.", "error");
        return null;
      } finally {
        setIsSyncing(false);
      }
    },
    [
      authHeaders,
      showToast,
      state.cartId,
      state.guestToken,
      state.items.length,
      state.mode,
    ]
  );

  const subtotal = useMemo(
    () => state.items.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [state.items]
  );
  const itemCount = useMemo(
    () => state.items.reduce((sum, item) => sum + item.quantity, 0),
    [state.items]
  );

  const contextValue: CartContextValue = useMemo(
    () => ({
      items: state.items,
      cartId: state.cartId,
      subtotal,
      itemCount,
      isOpen: state.isOpen,
      openCart,
      closeCart,
      toggleCart,
      addItem,
      updateItemQuantity,
      removeItem,
      checkout,
      isSyncing,
    }),
    [
      addItem,
      checkout,
      closeCart,
      isSyncing,
      itemCount,
      openCart,
      removeItem,
      state.cartId,
      state.isOpen,
      state.items,
      subtotal,
      toggleCart,
      updateItemQuantity,
    ]
  );

  return (
    <CartContext.Provider value={contextValue}>
      {children}
      {toast ? (
        <div
          className={`fixed bottom-4 right-4 z-50 rounded-lg px-4 py-2 text-sm text-white shadow-lg ${
            toast.tone === "error" ? "bg-red-600" : "bg-emerald-600"
          }`}
        >
          {toast.message}
        </div>
      ) : null}
      {!state.hydrated ? (
        <div className="pointer-events-none fixed bottom-4 left-4 z-50 rounded-md bg-slate-900/80 px-3 py-1 text-xs text-white">
          Initializing cart...
        </div>
      ) : null}
    </CartContext.Provider>
  );
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used inside CartProvider");
  }
  return context;
}
