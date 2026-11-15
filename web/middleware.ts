import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifySessionCookie, COOKIE_NAME } from "./lib/auth";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Allow public pages, static assets, and auth endpoints without login
  const isPublicPage =
    pathname === "/login" ||
    pathname === "/privacy" ||
    pathname === "/about";

  const isPublicApi =
    pathname === "/api/auth/login";

  const isStaticAsset =
    pathname.startsWith("/_next") ||
    pathname.startsWith("/static") ||
    pathname === "/favicon.ico" ||
    pathname.endsWith(".svg") ||
    pathname.endsWith(".png") ||
    pathname.endsWith(".jpg") ||
    pathname.endsWith(".ico");

  if (isPublicPage || isPublicApi || isStaticAsset) {
    return NextResponse.next();
  }

  // 2. Verify Session Cookie
  const secret = process.env.SESSION_SECRET || "default-secret-string-min-32-chars-long";
  const cookieValue = request.cookies.get(COOKIE_NAME)?.value;
  const isAuthenticated = await verifySessionCookie(cookieValue, secret);

  if (!isAuthenticated) {
    // If it's an API route, return 401 Unauthorized
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // Otherwise redirect browser to /login with callbackUrl
    const loginUrl = new URL("/login", request.url);
    if (pathname !== "/") {
      loginUrl.searchParams.set("callbackUrl", pathname);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
