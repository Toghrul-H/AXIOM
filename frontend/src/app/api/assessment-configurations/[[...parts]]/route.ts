import type { NextRequest } from "next/server";
// Keep staff requests on the same origin and explicitly forward the HttpOnly session.
async function forward(
  request: NextRequest,
  context: { params: Promise<{ parts?: string[] }> },
) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  const patterns: Record<string, RegExp> = {
    GET: /^(?:[1-9][0-9]*(?:\/rules|\/documents\/(?:DATES_OF_ASSESSMENTS|ENDTERM_TEST_INFORMATION|RULES_OF_ASSESSMENT|RULES_OF_EARNING_PLUS_POINTS|MIDTERM_TEST_INFORMATION|TEST_RETAKE_INFORMATION|COURSEWORK_ASSIGNMENT_INFORMATION)\/latex)?)?$/,
    POST: /^(?:[1-9][0-9]*\/(?:events(?:\/[1-9][0-9]*\/rooms)?|documents\/(?:DATES_OF_ASSESSMENTS|ENDTERM_TEST_INFORMATION|RULES_OF_ASSESSMENT|RULES_OF_EARNING_PLUS_POINTS|MIDTERM_TEST_INFORMATION|TEST_RETAKE_INFORMATION|COURSEWORK_ASSIGNMENT_INFORMATION)\/(?:preview|pdf)))?$/,
    PATCH: /^[1-9][0-9]*$/,
    PUT: /^[1-9][0-9]*\/(?:events\/[1-9][0-9]*(?:\/rooms\/[1-9][0-9]*)?|rules|policies\/(?:SHORT_QUIZZES|MIDTERM|ENDTERM|COURSEWORK))$/,
    DELETE: /^[1-9][0-9]*(?:\/events\/[1-9][0-9]*(?:\/rooms\/[1-9][0-9]*)?)?$/,
  };
  if (!patterns[request.method]?.test(suffix))
    return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL;
  if (!base)
    return Response.json(
      { detail: "Assessment service unavailable" },
      { status: 503 },
    );
  const url = new URL(
    base.replace(/\/$/, "") +
      "/assessment-configurations" +
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
      body: ["POST", "PUT", "PATCH"].includes(request.method)
        ? await request.text()
        : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
    // Never let an upstream redirect send the browser to the backend origin.
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected assessment service redirect" },
        { status: 502 },
      );
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
        Vary: "Cookie",
        ...(response.headers.get("content-disposition")
          ? {
              "Content-Disposition": response.headers.get(
                "content-disposition",
              )!,
            }
          : {}),
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return Response.json(
      { detail: "Assessment service unavailable. Please retry." },
      { status: 503 },
    );
  }
}
export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
