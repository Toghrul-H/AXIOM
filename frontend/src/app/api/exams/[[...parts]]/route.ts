import type { NextRequest } from "next/server";

const paths: Record<string, RegExp> = {
  GET: /^(?:|[1-9][0-9]*(?:\/documents\/(?:exam|answer-key)\/pdf)?)$/,
  POST: /^(?:|[1-9][0-9]*\/finalize)$/,
  PATCH: /^[1-9][0-9]*$/,
  DELETE: /^[1-9][0-9]*$/,
};

function unavailable() {
  return Response.json(
    { detail: "Exam Builder service unavailable. Please retry." },
    { status: 503, headers: { "Cache-Control": "no-store", Vary: "Cookie" } },
  );
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  if (!paths[request.method]?.test(suffix))
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
      new URL(
        `${base.replace(/\/$/, "")}/exams${suffix ? `/${suffix}` : ""}${request.nextUrl.search}`,
      ),
      {
        method: request.method,
        headers,
        body: ["POST", "PATCH"].includes(request.method)
          ? await request.text()
          : undefined,
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected exam service redirect" },
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
        ...(response.headers.get("content-disposition")
          ? {
              "Content-Disposition": response.headers.get(
                "content-disposition",
              )!,
            }
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
