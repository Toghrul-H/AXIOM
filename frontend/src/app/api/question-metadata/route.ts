import type { NextRequest } from "next/server";

function unavailable() {
  return Response.json(
    { detail: "Question metadata service unavailable. Please retry." },
    {
      status: 503,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    },
  );
}

// The explicit same-origin proxy forwards the HttpOnly session to FastAPI.
export async function GET(request: NextRequest) {
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
        `${base.replace(/\/$/, "")}/question-metadata${request.nextUrl.search}`,
      ),
      {
        method: "GET",
        headers,
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected question metadata service redirect" },
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
