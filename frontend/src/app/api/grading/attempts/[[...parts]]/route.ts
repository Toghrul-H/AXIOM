import { NextRequest } from "next/server";
// Same-origin transport for M7; existing session and CSRF enforcement stays upstream.
async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const valid =
    request.method === "GET"
      ? parts.length <= 1
      : parts.length === 3 && parts[1] === "answers";
  if (!valid || parts.some((p) => !/^[a-zA-Z0-9-]+$/.test(p)))
    return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL;
  if (!base)
    return Response.json(
      { detail: "Grading service unavailable" },
      { status: 503 },
    );
  const url = new URL(
    base.replace(/\/$/, "") +
      "/grading/attempts" +
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
      body: request.method === "PUT" ? await request.text() : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
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
      { detail: "Grading service unavailable. Please retry." },
      { status: 503 },
    );
  }
}
export const GET = forward;
export const PUT = forward;
