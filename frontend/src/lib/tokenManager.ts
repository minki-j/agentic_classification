import { jwtDecode } from "jwt-decode";

interface TokenPayload {
  sub: string;
  exp: number;
  type: string;
}

class TokenManager {
  private static ACCESS_TOKEN_KEY = "access_token";
  private static REFRESH_TOKEN_KEY = "refresh_token";
  private static REMEMBER_ME_KEY = "remember_me";
  private static TOKEN_REFRESH_BUFFER = 5 * 60 * 1000; // 5 minutes before expiration

  // Get token with fallback to cookies
  static getToken(key: string): string | null {
    // First try localStorage
    let token = localStorage.getItem(key);

    // If not in localStorage, try cookies
    if (!token) {
      const cookies = document.cookie.split(";");
      for (const cookie of cookies) {
        const [name, value] = cookie.trim().split("=");
        if (name === key) {
          token = decodeURIComponent(value);
          // Sync back to localStorage
          localStorage.setItem(key, token);
          break;
        }
      }
    }

    return token;
  }

  // Set token in both localStorage and secure cookie
  static setToken(
    key: string,
    token: string,
    rememberMe: boolean = false
  ): void {
    // Store in localStorage
    localStorage.setItem(key, token);

    // Also store in secure cookie
    const isSecure = window.location.protocol === "https:";
    const maxAge = rememberMe ? 30 * 24 * 60 * 60 : 6 * 60 * 60; // 30 days or 6 hours

    document.cookie = `${key}=${encodeURIComponent(token)}; path=/; ${
      isSecure ? "secure;" : ""
    } samesite=strict; max-age=${maxAge}`;
  }

  // Remove token from both storage methods
  static removeToken(key: string): void {
    localStorage.removeItem(key);
    // Remove cookie by setting expiration to past
    document.cookie = `${key}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  }

  // Get access token
  static getAccessToken(): string | null {
    return this.getToken(this.ACCESS_TOKEN_KEY);
  }

  // Get refresh token
  static getRefreshToken(): string | null {
    return this.getToken(this.REFRESH_TOKEN_KEY);
  }

  // Set tokens
  static setTokens(
    accessToken: string,
    refreshToken: string,
    rememberMe: boolean = false
  ): void {
    this.setToken(this.ACCESS_TOKEN_KEY, accessToken, rememberMe);
    this.setToken(this.REFRESH_TOKEN_KEY, refreshToken, rememberMe);
    if (rememberMe) {
      localStorage.setItem(this.REMEMBER_ME_KEY, "true");
    }
  }

  // Clear all auth data
  static clearTokens(): void {
    this.removeToken(this.ACCESS_TOKEN_KEY);
    this.removeToken(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.REMEMBER_ME_KEY);
  }

  // Check if token is expired or about to expire
  static isTokenExpiringSoon(token: string): boolean {
    try {
      const decoded = jwtDecode<TokenPayload>(token);
      const expirationTime = decoded.exp * 1000; // Convert to milliseconds
      const currentTime = Date.now();

      // Check if token expires within the buffer time
      return expirationTime - currentTime <= this.TOKEN_REFRESH_BUFFER;
    } catch {
      // If we can't decode the token, consider it expired
      return true;
    }
  }

  // Get token expiration time
  static getTokenExpiration(token: string): Date | null {
    try {
      const decoded = jwtDecode<TokenPayload>(token);
      return new Date(decoded.exp * 1000);
    } catch {
      return null;
    }
  }

  // Check if remember me is enabled
  static isRememberMeEnabled(): boolean {
    return localStorage.getItem(this.REMEMBER_ME_KEY) === "true";
  }
}

export default TokenManager;
