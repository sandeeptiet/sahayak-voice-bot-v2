# Sahayak portal — login preview

React + TypeScript + Vite frontend for the existing Cognito public app client.
Employees create and view only their own tickets. Engineers view all tickets,
claim unassigned human escalations, and record outcomes for their assigned tickets.
The backend enforces these permissions independently of the browser.
See [backend setup](../docs/portal-backend.md) before using ticket features.

## Run locally

Use Node 22.12+ (22 LTS) or 24+. This slice was built with Node 25.9.0.

```sh
cd /Users/sandeepkapoor/Desktop/prep/sahayak-voice-agent-v2/portal
npm ci
cp .env.example .env.local  # Only on first setup; don't replace existing values.
# Fill the public Cognito settings in .env.local.
npm run dev
```

Open http://localhost:5173. The ignored .env.local on the development machine
already contains the user's supplied public pool/client IDs and verified domain.
Never put database credentials, AWS keys, tokens or a client secret in a VITE_
setting; these values are browser-visible.

Cognito client configuration must allow authorization code, openid/email/profile,
http://localhost:5173/auth/callback and logout http://localhost:5173/.
Passwords and MFA are entered only on the Cognito managed-login page.

## Session behavior

- Authorization code + S256 PKCE, random state and nonce via oidc-client-ts.
- ID-token signature verified against pool JWKS using jose; issuer, audience,
  expiry and token_use=id checked before displaying identity.
- The pending login state is held in tab session storage for at most ten minutes.
  Tokens are held in memory only. Refreshing/closing the page requires sign-in
  again. Automatic refresh is disabled; expired sessions return to sign-in.
- Logout attempts refresh-token revocation, clears the local token store and
  navigates through Cognito's logout endpoint even if revocation fails.
- Callback codes/errors are removed from the address bar. No tokens or raw
  provider errors are printed to the UI or application logs.
- The backend independently validates access tokens, checks the live Cognito
  userInfo endpoint, and intersects active database roles with token groups.

## Verification

```sh
npm run build
npx playwright install chromium
npm test
```

The 20 browser tests use synthetic tokens and intercepted API/Cognito responses.
They cover authentication, employee views, creation retries, engineer assignment,
outcomes, conflicts, escaping and mobile layout. Screenshots are in test-results/.
`npm run test:db` runs 22 migration/trigger/grant checks using ephemeral PGlite
PostgreSQL. This does not test RDS connectivity or concurrent database sessions.

User confirmed live Cognito login/logout. Live RDS migration and end-to-end ticket
acceptance remain pending. No queue consumer or telephone calling is enabled.

## Hosting later

This dev server binds to localhost and is not a deployment. Production hosting
must enforce HTTPS, an appropriate CSP/security headers, and SPA routing for
/auth/callback. Register exact deployed callback/logout URLs and update
VITE_PORTAL_ORIGIN before deploying. Hosting remains undecided.

References:
- https://authts.github.io/oidc-client-ts/
- https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html
- https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html
