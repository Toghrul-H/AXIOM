import { NextRequest } from "next/server";

function unavailable() {
  return Response.json(
    { detail: "Study Partner service unavailable. Please retry." },
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
    GET: /^(?:me|partners|requests|chats(?:\/[1-9][0-9]*\/(?:messages|attachments\/[1-9][0-9]*\/(?:download|preview)))?)$/,
    PUT: /^me$/,
    POST: /^(?:requests(?:\/[1-9][0-9]*\/(?:accept|decline|cancel))?|blocks|chats\/[1-9][0-9]*\/(?:read|typing|attachments|messages(?:\/[1-9][0-9]*\/reactions)?))$/,
    DELETE:
      /^(?:blocks\/[1-9][0-9]*|chats\/[1-9][0-9]*\/(?:attachments\/[1-9][0-9]*|messages\/[1-9][0-9]*\/reactions))$/,
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
    "x-chat-filename",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const response = await fetch(
      `${base.replace(/\/$/, "")}/study-partner/${suffix}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body:
          request.method === "POST" && suffix.endsWith("/attachments")
            ? await request.arrayBuffer()
            : ["POST", "PUT"].includes(request.method) ||
                (request.method === "DELETE" && suffix.endsWith("/reactions"))
              ? await request.text()
              : undefined,
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
    if (response.status >= 300 && response.status < 400)
      return Response.json(
        { detail: "Unexpected Study Partner service redirect" },
        {
          status: 502,
          headers: { "Cache-Control": "no-store", Vary: "Cookie" },
        },
      );
    const responseHeaders = new Headers({
      "Content-Type":
        response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
      Vary: "Cookie",
      "X-Content-Type-Options": "nosniff",
    });
    const contentDisposition = response.headers.get("content-disposition");
    if (contentDisposition)
      responseHeaders.set("Content-Disposition", contentDisposition);
    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return unavailable();
  }
}

export const GET = forward;
export const PUT = forward;
export const POST = forward;
export const DELETE = forward;
