import { NextResponse } from "next/server";

type SalesPoint = {
  label: string;
  revenue: number;
  orders: number;
};

function buildSeries(days: number): SalesPoint[] {
  const today = new Date();
  const items: SalesPoint[] = [];
  for (let index = days - 1; index >= 0; index -= 1) {
    const current = new Date(today);
    current.setDate(today.getDate() - index);
    const weekday = current.toLocaleDateString("en-US", { weekday: "short" });
    const orders = 8 + ((days - index) % 6) * 2;
    const revenue = orders * (35 + ((days - index) % 4) * 7);
    items.push({ label: weekday, orders, revenue });
  }
  return items;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const from = searchParams.get("from");
  const to = searchParams.get("to");
  const days = from && to ? 14 : 7;

  const series = buildSeries(days);
  const totalOrders = series.reduce((sum, point) => sum + point.orders, 0);
  const totalRevenue = series.reduce((sum, point) => sum + point.revenue, 0);
  const totalSales = totalOrders;

  return NextResponse.json({
    from,
    to,
    totalSales,
    totalRevenue,
    trend: series,
  });
}
