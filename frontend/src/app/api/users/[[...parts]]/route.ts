import type { NextRequest } from "next/server";
// Keep staff requests on the same origin and explicitly forward the HttpOnly session.
async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const valid =
    request.method === "GET"
      ? parts.length === 0
      : request.method === "POST" &&
        parts.length === 2 &&
        /^[1-9][0-9]*$/.test(parts[0]) &&
        ["role", "status"].includes(parts[1]);
  if (!valid || parts.some((p) => !/^[a-zA-Z0-9-]+$/.test(p)))
    return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL;
  if (!base)
    return Response.json(
      { detail: "Staff management service unavailable" },
      { status: 503 },
    );
  const url = new URL(
    base.replace(/\/$/, "") +
      "/users" +
      (parts.length ? "/" + parts.join("/") : "") +
      request.nextUrl.search,
  );
  const headers = new Headers();
  for (const key of [
    "cookie",
    "x-csrf-token",
    "origin",
    "sec-fetch-site",
    "content-type",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
    // Never let an upstream redirect send the browser to the backend origin.
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected staff service redirect" },
        { status: 502 },
      );
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
        Vary: "Cookie",
      },
    });
  } catch {
    return Response.json(
      { detail: "Staff management service unavailable. Please retry." },
      { status: 503 },
    );
  }
}
export const GET = forward;
export const POST = forward;
