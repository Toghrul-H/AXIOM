import type { NextRequest } from "next/server";

const allowed: Record<string, RegExp> = {
  GET: /^$/,
  POST: /^(?:|[1-9][0-9]*\/(?:publish|unpublish))$/,
  PUT: /^[1-9][0-9]*$/,
  DELETE: /^[1-9][0-9]*$/,
};

async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  if (!allowed[request.method]?.test(suffix))
    return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL;
  if (!base)
    return Response.json(
      { detail: "Announcement service unavailable." },
      { status: 503 },
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
    const response = await fetch(
      new URL(
        `${base.replace(/\/$/, "")}/announcements${suffix ? `/${suffix}` : ""}${request.nextUrl.search}`,
      ),
      {
        method: request.method,
        headers,
        body: request.method === "GET" ? undefined : await request.text(),
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
        Vary: "Cookie",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return Response.json(
      { detail: "Announcement service unavailable." },
      { status: 503, headers: { "Cache-Control": "no-store", Vary: "Cookie" } },
    );
  }
}
export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const DELETE = forward;
