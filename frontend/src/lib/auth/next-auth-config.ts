import NextAuth from "next-auth";
import CognitoProvider from "next-auth/providers/cognito";
import CredentialsProvider from "next-auth/providers/credentials";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    CognitoProvider({
      clientId: process.env.AUTH_COGNITO_ID || "",
      clientSecret: process.env.AUTH_COGNITO_SECRET || "unused",
      issuer: process.env.AUTH_COGNITO_ISSUER || "",
    }),
    CredentialsProvider({
      name: "credentials",
      credentials: {
        accessToken: { type: "text" },
        refreshToken: { type: "text" },
        expiresIn: { type: "text" },
        userId: { type: "text" },
        email: { type: "text" },
        locale: { type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.accessToken || !credentials?.email) {
          return null;
        }

        return {
          id: credentials.userId as string,
          email: credentials.email as string,
          accessToken: credentials.accessToken as string,
          refreshToken: credentials.refreshToken as string,
          expiresIn: parseInt(credentials.expiresIn as string, 10),
          locale: credentials.locale as string,
        };
      },
    }),
  ],
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user, account }) {
      // Initial sign in via Cognito OAuth
      if (account && account.provider !== "credentials") {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
        return token;
      }

      // Initial sign in via credentials
      if (user) {
        const u = user as typeof user & {
          accessToken: string;
          refreshToken: string;
          expiresIn: number;
          locale: string;
        };
        token.accessToken = u.accessToken;
        token.refreshToken = u.refreshToken;
        token.expiresAt = Math.floor(Date.now() / 1000) + u.expiresIn;
        token.locale = u.locale;
        return token;
      }

      // Token not expired yet (refresh 60 seconds before actual expiry)
      if (token.expiresAt && Date.now() / 1000 < (token.expiresAt as number) - 60) {
        return token;
      }

      // Token expired or about to expire — attempt refresh
      if (token.refreshToken) {
        try {
          const response = await fetch(
            `${API_URL}/api/v1/auth/refresh-token`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                refreshToken: token.refreshToken,
                email: token.email,
              }),
            }
          );

          if (response.ok) {
            const data = await response.json();
            token.accessToken = data.accessToken;
            token.expiresAt = Math.floor(Date.now() / 1000) + data.expiresIn;
            delete token.error;
            return token;
          }
        } catch {
          // Refresh failed — force re-login
        }
      }

      // Refresh failed or no refresh token — mark as expired
      token.error = "TokenRefreshFailed";
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.locale = (token.locale as string) || "uk";
      if (token.error === "TokenRefreshFailed") {
        session.error = "TokenRefreshFailed";
      }
      return session;
    },
  },
  pages: {
    // NextAuth requires a static string — cannot be dynamic per-locale.
    // Defaults to Ukrainian (primary market). The proxy.ts handles
    // locale-aware redirects before this fallback is reached.
    signIn: "/uk/login",
  },
});
