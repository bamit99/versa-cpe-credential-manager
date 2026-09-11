import Keycloak from "keycloak-js";

const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL || "https://localhost/auth";
const realm = import.meta.env.VITE_KEYCLOAK_REALM || "versa-telecom";
const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "versa-cpe-manager";

export const keycloak = new Keycloak({
  url: keycloakUrl,
  realm,
  clientId,
});

/**
 * Redirect URI MUST match Keycloak client config. When served by the stack's
 * nginx, the console and app share the https://localhost origin, so OIDC
 * redirects resolve to / (the SPA).
 */
export const getRedirectUri = () => {
  if (window.location.port === "3000") {
    return `http://localhost:3000/`;
  }
  return `${window.location.origin}/`;
};

export function login(): Promise<void> {
  return keycloak.init({ onLoad: "login-required", redirectUri: getRedirectUri() }).then(
    (authenticated) => {
      if (!authenticated) throw new Error("Not authenticated");
    },
  );
}

export function logout(): void {
  keycloak.logout({ redirectUri: `${window.location.origin}/` });
}

export function refreshToken(): Promise<boolean> {
  return keycloak.updateToken(30);
}

export const getToken = (): string | undefined => keycloak.token;
export const getRoles = (): string[] =>
  keycloak.tokenParsed
    ? [
        ...((keycloak.tokenParsed as any).realm_access?.roles ?? []),
        ...((keycloak.tokenParsed as any).resource_access?.[clientId]?.roles ?? []),
      ]
    : [];