import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    items: [
      { id: 101, name: "Runner Pro Shoes", units: 120, revenue: 8400 },
      { id: 102, name: "Trail Max Backpack", units: 96, revenue: 6240 },
      { id: 103, name: "Performance Tee", units: 88, revenue: 2640 },
      { id: 104, name: "Hydration Bottle", units: 75, revenue: 1875 },
      { id: 105, name: "Workout Shorts", units: 63, revenue: 2520 },
    ],
  });
}
