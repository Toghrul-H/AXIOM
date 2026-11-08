import { NextRequest } from "next/server";

async function forward(request: NextRequest, context: { params: Promise<{ parts?: string[] }> }) {
  const { parts = [] } = await context.params;
  const suffix = parts.join("/");
  const patterns: Record<string, RegExp> = {
    GET: /^(?:demonstrator-vacancies|demonstrator-applications\/me|notifications\/recruitment|staff\/demonstrator-vacancies(?:\/[1-9][0-9]*(?:\/applications(?:\/[1-9][0-9]*)?(?:\.xlsx)?)?)?)$/,
    POST: /^(?:demonstrator-vacancies\/[1-9][0-9]*\/applications|demonstrator-applications\/[1-9][0-9]*\/withdraw|staff\/demonstrator-vacancies)$/,
    PATCH: /^staff\/demonstrator-vacancies\/[1-9][0-9]*(?:\/applications\/[1-9][0-9]*)?$/,
  };
  if (!patterns[request.method]?.test(suffix)) return new Response(null, { status: 404 });
  const base = process.env.API_BASE_URL;
  if (!base) return Response.json({ detail: "Recruitment service unavailable" }, { status: 503 });
  const headers = new Headers();
  for (const key of ["cookie", "x-csrf-token", "origin", "sec-fetch-site", "content-type"]) { const value = request.headers.get(key); if (value) headers.set(key, value); }
  try {
    const response = await fetch(`${base.replace(/\/$/, "")}/${suffix}${request.nextUrl.search}`, { method: request.method, headers, body: ["POST", "PATCH"].includes(request.method) ? await request.text() : undefined, cache: "no-store", redirect: "manual", signal: request.signal });
    return new Response(response.body, { status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json", "Content-Disposition": response.headers.get("content-disposition") ?? "", "Cache-Control": "no-store", Vary: "Cookie" } });
  } catch { return Response.json({ detail: "Recruitment service unavailable" }, { status: 503 }); }
}
export const GET = forward; export const POST = forward; export const PATCH = forward;
