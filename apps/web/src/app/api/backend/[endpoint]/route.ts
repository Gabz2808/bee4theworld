import { NextRequest, NextResponse } from "next/server";

// Only these backend routes are exposed; the browser never chooses an upstream URL.
async function forward(request: NextRequest, endpoint: string, method: "GET" | "POST") {
  if ((method === "GET" && endpoint !== "catalog") || (method === "POST" && endpoint !== "explorations")) {
    return NextResponse.json({ error: { code: "NOT_FOUND" } }, { status: 404 });
  }
  const base = process.env.IYOK_API_URL || "http://127.0.0.1:8000";
  let url: URL;
  try {
    url = new URL(base);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error();
  } catch {
    return NextResponse.json({ error: { code: "API_CONFIGURATION_ERROR" } }, { status: 503 });
  }
  let body: string | undefined;
  if (method === "POST") {
    try {
      body = await request.text();
      if (body.length > 4096) return NextResponse.json({ error: { code: "INVALID_REQUEST" } }, { status: 413 });
      JSON.parse(body);
    } catch { return NextResponse.json({ error: { code: "INVALID_REQUEST" } }, { status: 400 }); }
  }
  const timeout = AbortSignal.timeout(method === "GET" ? 15000 : 90000);
  try {
    const response = await fetch(`${base.replace(/\/+$/, "")}/api/v1/${endpoint}`, {
      method, body, headers: body ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store", signal: timeout,
    });
    const content = await response.text();
    return new NextResponse(content, { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    if (timeout.aborted && method === "POST") return NextResponse.json({ error: { code: "BACKEND_TIMEOUT" } }, { status: 504 });
    return NextResponse.json({ error: { code: "BACKEND_UNAVAILABLE" } }, { status: 503 });
  }
}

type Context = { params: Promise<{ endpoint: string }> };
export async function GET(request: NextRequest, context: Context) { return forward(request, (await context.params).endpoint, "GET"); }
export async function POST(request: NextRequest, context: Context) { return forward(request, (await context.params).endpoint, "POST"); }
