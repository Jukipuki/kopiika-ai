import "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    locale?: string;
    error?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: number;
    locale?: string;
    error?: string;
  }
}
