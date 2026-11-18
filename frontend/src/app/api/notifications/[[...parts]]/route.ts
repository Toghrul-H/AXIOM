import { NextRequest } from "next/server";

function unavailable() {
  return Response.json(
    { detail: "Notification service unavailable. Please retry." },
    { status: 503, headers: { "Cache-Control": "no-store", Vary: "Cookie" } },
  );
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  const patterns: Record<string, RegExp> = {
    GET: /^(?:|unread-count)$/,
    POST: /^(?:read-all|[1-9][0-9]*\/read)$/,
  };
  if (!patterns[request.method]?.test(suffix))
    return new Response(null, { status: 404 });

  const base = process.env.API_BASE_URL;
  if (!base) return unavailable();
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
      `${base.replace(/\/$/, "")}/notifications${suffix ? `/${suffix}` : ""}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: request.method === "POST" ? await request.text() : undefined,
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected notification service redirect" },
        {
          status: 502,
          headers: { "Cache-Control": "no-store", Vary: "Cookie" },
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
    return unavailable();
  }
}

export const GET = forward;
export const POST = forward;
