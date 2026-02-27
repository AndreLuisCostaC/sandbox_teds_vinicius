import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    items: [
      { variantId: 301, sku: "RP-RED-42", name: "Runner Pro Shoes - Red 42", stock: 3 },
      { variantId: 302, sku: "TB-BLK-STD", name: "Trail Max Backpack - Black", stock: 4 },
      { variantId: 303, sku: "PT-GRY-M", name: "Performance Tee - Gray M", stock: 2 },
      { variantId: 304, sku: "WB-BLU-700", name: "Hydration Bottle - Blue", stock: 5 },
    ],
  });
}
