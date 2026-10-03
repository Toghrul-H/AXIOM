import type { NextRequest } from "next/server";

async function forward(
  request: NextRequest,
  context: { params: Promise<{ action: string }> },
) {
  const { action } = await context.params;
  if (
    !(request.method === "GET"
      ? action === "me"
      : request.method === "POST" &&
        [
          "login",
          "register",
          "logout",
          "verify-email",
          "resend-verification",
        ].includes(action))
  )
    return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL;
  const privateHeaders = { "Cache-Control": "no-store", Vary: "Cookie" };
  const unavailable = () =>
    Response.json(
      { detail: "Authentication service unavailable. Please retry." },
      { status: 503, headers: privateHeaders },
    );
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
    const upstream = await fetch(`${base.replace(/\/$/, "")}/auth/${action}`, {
      method: request.method,
      headers,
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
    if (upstream.status >= 300 && upstream.status < 400) return unavailable();
    const output = new Headers(privateHeaders);
    output.set(
      "Content-Type",
      upstream.headers.get("content-type") ?? "application/json",
    );
    for (const cookie of upstream.headers.getSetCookie())
      output.append("Set-Cookie", cookie);
    if (upstream.headers.has("retry-after"))
      output.set("Retry-After", upstream.headers.get("retry-after")!);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: output,
    });
  } catch {
    return unavailable();
  }
}
export const GET = forward;
export const POST = forward;
