import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const origin = process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000";
  const response = await fetch(`${origin}/api/v1/demo/sign-in`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.json({ detail: "Demo sign-in unavailable" }, { status: response.status });
  }

  const upstreamCookie = response.headers.get("set-cookie") ?? "";
  const session = /^outcomeos_session=([^;]+)/.exec(upstreamCookie)?.[1];
  if (!session) {
    return NextResponse.json({ detail: "Demo sign-in did not create a session" }, { status: 502 });
  }

  const redirect = NextResponse.redirect(new URL("/overview", request.url), 303);
  redirect.cookies.set("outcomeos_session", decodeURIComponent(session), {
    httpOnly: true,
    sameSite: "lax",
    secure: false,
    maxAge: 3600,
    path: "/",
  });
  return redirect;
}
