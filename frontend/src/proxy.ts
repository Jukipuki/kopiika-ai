import { NextResponse } from "next/server";
import createIntlMiddleware from "next-intl/middleware";
import { auth } from "@/lib/auth/next-auth-config";
import { routing } from "@/i18n/routing";

const publicPaths = ["/login", "/signup", "/forgot-password"];
const handleI18nRouting = createIntlMiddleware(routing);

export default auth((req) => {
  const { pathname } = req.nextUrl;

  // Allow API auth routes (NextAuth callbacks)
  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  // Extract locale and path after locale
  const segments = pathname.split("/");
  const hasLocalePrefix = routing.locales.includes(
    segments[1] as (typeof routing.locales)[number]
  );
  const locale = hasLocalePrefix ? segments[1] : routing.defaultLocale;
  const pathAfterLocale = hasLocalePrefix
    ? "/" + segments.slice(2).join("/")
    : pathname;

  // Allow public routes without auth check
  const isPublicRoute = publicPaths.some((p) => pathAfterLocale.startsWith(p));

  if (!isPublicRoute && !req.auth) {
    const callbackUrl = encodeURIComponent(pathname);
    return NextResponse.redirect(
      new URL(`/${locale}/login?callbackUrl=${callbackUrl}`, req.url)
    );
  }

  // Handle i18n routing (locale detection, redirects, headers)
  return handleI18nRouting(req);
});

export const runtime = "nodejs";

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|health).*)",
  ],
};
