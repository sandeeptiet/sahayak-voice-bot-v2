import { InMemoryWebStorage, UserManager, WebStorageStateStore } from 'oidc-client-ts';
import { createRemoteJWKSet, jwtVerify } from 'jose';
import type { AuthConfig } from './config';

export interface Identity {
  name: string;
  email: string;
  roles: string[];
  expiresAt: number;
}

// These claims personalize the UI only. The future API must independently verify
// ACCESS tokens, load the active database profile and enforce permissions.
export function createAuth(config: AuthConfig) {
  const manager = new UserManager({
    authority: config.authority,
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    response_type: 'code',
    response_mode: 'query',
    scope: 'openid email profile',
    disablePKCE: false,
    automaticSilentRenew: false,
    monitorSession: false,
    loadUserInfo: false,
    staleStateAgeInSeconds: 600,
    requestTimeoutInSeconds: 15,
    revokeTokenTypes: ['refresh_token'],
    stateStore: new WebStorageStateStore({ store: window.sessionStorage, prefix: 'sahayak.oidc.' }),
    // Tokens live only in memory. Reloading starts a fresh managed-login flow.
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    metadata: {
      issuer: config.authority,
      authorization_endpoint: `${config.domain}/oauth2/authorize`,
      token_endpoint: `${config.domain}/oauth2/token`,
      revocation_endpoint: `${config.domain}/oauth2/revoke`,
      jwks_uri: `${config.authority}/.well-known/jwks.json`,
    },
  });
  const keys = createRemoteJWKSet(new URL(`${config.authority}/.well-known/jwks.json`), {
    timeoutDuration: 15000,
  });
  let callback: Promise<Identity> | undefined;

  async function completeCallback(url: string): Promise<Identity> {
    try {
      const user = await manager.signinRedirectCallback(url);
      if (!user.id_token || user.expired || !user.expires_at) throw new Error('Invalid session');
      // oidc-client-ts handles state, PKCE and nonce. Also verify the ID-token
      // signature and claims before using identity details in the interface.
      const { payload } = await jwtVerify(user.id_token, keys, {
        issuer: config.authority, audience: config.clientId,
        algorithms: ['RS256'], requiredClaims: ['exp', 'iat', 'sub', 'nonce'],
      });
      if (payload.token_use !== 'id' || payload.sub !== user.profile.sub) {
        throw new Error('Invalid token purpose');
      }
      const groups = payload['cognito:groups'];
      return {
        name: typeof payload.name === 'string' ? payload.name : 'there',
        email: typeof payload.email === 'string' ? payload.email : '',
        roles: Array.isArray(groups) ? groups.filter((role): role is string =>
          typeof role === 'string' && ['employee', 'engineer', 'portal_admin'].includes(role)) : [],
        expiresAt: Math.min(user.expires_at, payload.exp!) * 1000,
      };
    } catch {
      await manager.removeUser();
      // Never surface provider responses, authorization codes or tokens in UI/logs.
      throw new Error('We couldn’t complete sign-in. Please try again. If it continues, contact your administrator.');
    }
  }

  return {
    async login() {
      await manager.clearStaleState();
      await manager.signinRedirect({ nonce: crypto.randomUUID(), prompt: 'login' });
    },
    complete(url: string) {
      // Avoid exchanging a one-use authorization code twice under React StrictMode.
      callback ??= completeCallback(url);
      return callback;
    },
    async accessToken() {
      const user = await manager.getUser();
      if (!user || user.expired) throw new Error("Your session has expired. Sign in again.");
      return user.access_token;
    },
    async expire() { await manager.removeUser(); },
    async logout() {
      try { await manager.revokeTokens(['refresh_token']); }
      catch { /* Local sign-out and hosted-session logout still proceed. */ }
      finally { await manager.removeUser(); }
      const url = new URL(`${config.domain}/logout`);
      url.searchParams.set('client_id', config.clientId);
      url.searchParams.set('logout_uri', `${config.origin}/`);
      window.location.assign(url.toString());
    },
  };
}
