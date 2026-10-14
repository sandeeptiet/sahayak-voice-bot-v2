export interface AuthConfig {
  authority: string;
  clientId: string;
  domain: string;
  origin: string;
  redirectUri: string;
}

export function readConfig(env: Record<string, string | undefined>): AuthConfig {
  const pool = env.VITE_COGNITO_POOL_ID?.trim() ?? '';
  const clientId = env.VITE_COGNITO_CLIENT_ID?.trim() ?? '';
  if (!/^ap-south-1_[a-zA-Z0-9]+$/.test(pool) ||
      !/^[a-z0-9]{8,128}$/.test(clientId)) {
    throw new Error('Set the Cognito pool and app client IDs in portal/.env.local.');
  }
  const domain = new URL(env.VITE_COGNITO_DOMAIN ?? '');
  if (domain.protocol !== 'https:' || domain.username || domain.password ||
      domain.port || domain.pathname !== '/' || domain.search || domain.hash ||
      !domain.hostname.endsWith('.auth.ap-south-1.amazoncognito.com')) {
    throw new Error('Use the HTTPS managed-login domain for your Mumbai Cognito pool.');
  }
  const origin = new URL(env.VITE_PORTAL_ORIGIN ?? 'http://localhost:5173');
  if ((origin.protocol !== 'https:' &&
       !(origin.protocol === 'http:' && origin.hostname === 'localhost')) ||
      origin.username || origin.password || origin.pathname !== '/' ||
      origin.search || origin.hash) {
    throw new Error('Use an HTTPS portal origin, or http://localhost:5173 for local development.');
  }
  return {
    authority: `https://cognito-idp.ap-south-1.amazonaws.com/${pool}`,
    clientId, domain: domain.origin, origin: origin.origin,
    redirectUri: `${origin.origin}/auth/callback`,
  };
}
