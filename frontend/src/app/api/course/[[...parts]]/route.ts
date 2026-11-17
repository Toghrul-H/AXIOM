import { NextRequest } from "next/server";

function unavailable() {
  return Response.json(
    { detail: "Course service unavailable. Please retry." },
    { status: 503, headers: { "Cache-Control": "no-store", Vary: "Cookie" } },
  );
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  const allowed: Record<string, RegExp> = {
    GET: /^(?:chapters|manage\/chapters|lessons\/[1-9][0-9]*)$/,
    POST: /^(?:chapters|lessons|chapters\/[1-9][0-9]*\/(?:publish|unpublish)|lessons\/[1-9][0-9]*\/(?:publish|unpublish))$/,
    PATCH: /^(?:chapters|lessons)\/[1-9][0-9]*$/,
    PUT: /^(?:chapters\/reorder|chapters\/[1-9][0-9]*\/lessons\/reorder)$/,
    DELETE: /^(?:chapters|lessons)\/[1-9][0-9]*$/,
  };
  if (!allowed[request.method]?.test(suffix))
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
      `${base.replace(/\/$/, "")}/course/${suffix}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: ["POST", "PATCH", "PUT"].includes(request.method)
          ? await request.text()
          : undefined,
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected course service redirect" },
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
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
