import type { NextRequest } from "next/server";

const pathPatterns: Record<string, RegExp> = {
  GET: /^(?:|[1-9][0-9]*)$/,
  POST: /^(?:|[1-9][0-9]*\/check)$/,
  PATCH: /^[1-9][0-9]*$/,
  DELETE: /^[1-9][0-9]*$/,
};

function unavailable() {
  return Response.json(
    { detail: "Question bank service unavailable. Please retry." },
    {
      status: 503,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    },
  );
}

// Keep Question Bank traffic on the Vercel origin so the HttpOnly session is
// sent to this handler and can be forwarded only to the configured backend.
async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  if (!pathPatterns[request.method]?.test(suffix))
    return new Response(null, { status: 404 });

  const base = process.env.API_BASE_URL;
  if (!base) return unavailable();

  const url = new URL(
    `${base.replace(/\/$/, "")}/questions${suffix ? `/${suffix}` : ""}${request.nextUrl.search}`,
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
      body: ["POST", "PATCH"].includes(request.method)
        ? await request.text()
        : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
    // A backend redirect must never move the browser to the backend origin.
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected question bank service redirect" },
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
        ...(response.headers.get("location")
          ? { Location: response.headers.get("location")! }
          : {}),
      },
    });
  } catch {
    return unavailable();
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
