import { expect, test, type Page } from '@playwright/test';
import { exportJWK, generateKeyPair, SignJWT } from 'jose';
import { createHash } from 'node:crypto';

const issuer = 'https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_TestPool';
const domain = 'https://sahayak-test.auth.ap-south-1.amazoncognito.com';
const clientId = 'testclient12345678';

type Options = { badState?: boolean; badAudience?: boolean; badIssuer?: boolean;
  badSignature?: boolean; badNonce?: boolean; expired?: boolean; denied?: boolean;
  tokenFailure?: boolean; shortSession?: boolean; groups?: string[]; revokeFailure?: boolean };

async function mockCognito(page: Page, options: Options = {}) {
  const { publicKey, privateKey } = await generateKeyPair('RS256', { extractable: true });
  const jwk = { ...await exportJWK(publicKey), kid: 'test-key', alg: 'RS256', use: 'sig' };
  const otherKey = options.badSignature ? (await generateKeyPair('RS256')).privateKey : privateKey;
  let authorization: URL;
  let exchanges = 0;
  let revocations = 0;
  let verifierMatched = false;
  await page.route(`${issuer}/.well-known/jwks.json`, route => route.fulfill({ json: { keys: [jwk] } }));
  await page.route(`${domain}/oauth2/authorize?**`, async route => {
    authorization = new URL(route.request().url());
    const callback = new URL(authorization.searchParams.get('redirect_uri')!);
    callback.searchParams.set('state', options.badState ? 'wrong-state' : authorization.searchParams.get('state')!);
    callback.searchParams.set(options.denied ? 'error' : 'code', options.denied ? 'access_denied' : 'test-code');
    await route.fulfill({ status: 302, headers: { location: callback.toString() } });
  });
  await page.route(`${domain}/oauth2/token`, async route => {
    if (route.request().method() === 'OPTIONS') { await route.fulfill({ status: 204 }); return; }
    exchanges++;
    const body = new URLSearchParams(route.request().postData()!);
    const verifier = body.get('code_verifier') ?? '';
    verifierMatched = createHash('sha256').update(verifier).digest('base64url') === authorization.searchParams.get('code_challenge');
    expect(body.get('grant_type')).toBe('authorization_code');
    expect(body.get('client_secret')).toBeNull();
    expect(verifier.length).toBeGreaterThanOrEqual(43);
    if (options.tokenFailure) { await route.fulfill({ status: 400, json: { error: 'invalid_grant' } }); return; }
    const now = Math.floor(Date.now() / 1000);
    const token = await new SignJWT({
      sub: 'employee-test-sub', name: 'Test Employee', email: 'test@example.invalid', token_use: 'id',
      nonce: options.badNonce ? 'wrong-nonce' : authorization.searchParams.get('nonce'),
      'cognito:groups': options.groups ?? ['employee'],
    }).setProtectedHeader({ alg: 'RS256', kid: 'test-key' })
      .setIssuer(options.badIssuer ? 'https://untrusted.example' : issuer)
      .setAudience(options.badAudience ? 'other-client' : clientId)
      .setIssuedAt(now).setExpirationTime(options.expired ? now - 60 : now + 900).sign(otherKey);
    await route.fulfill({ json: {
      id_token: token, access_token: 'fake-access-token', refresh_token: 'fake-refresh-token',
      token_type: 'Bearer', scope: 'openid email profile', expires_in: options.shortSession ? 2 : 900,
    } });
  });
  await page.route(`${domain}/oauth2/revoke`, async route => {
    if (route.request().method() === 'OPTIONS') { await route.fulfill({ status: 204 }); return; }
    revocations++;
    await route.fulfill({ status: options.revokeFailure ? 500 : 200, body: '' });
  });
  await page.route(`${domain}/logout?**`, async route => {
    const url = new URL(route.request().url());
    expect(url.searchParams.get('client_id')).toBe(clientId);
    expect(url.searchParams.get('logout_uri')).toBe('http://localhost:5174/');
    await route.fulfill({ status: 302, headers: { location: 'http://localhost:5174/' } });
  });
  await page.route('http://localhost:8000/api/me', route => {
    const roles = options.groups ?? ['employee'];
    return route.fulfill(roles.some(r => ['employee','engineer'].includes(r)) ? { json: {
      id:'11111111-1111-4111-8111-111111111111', name:'Test Employee', roles, phone_ready:true,
    } } : {status:403,json:{detail:'Your account needs an employee or engineer role'}});
  });
  await page.route('http://localhost:8000/api/tickets?**', route => route.fulfill({json:{items:[],next_cursor:null}}));
  return { get exchanges() { return exchanges; }, get revocations() { return revocations; },
    get authorization() { return authorization; }, get verifierMatched() { return verifierMatched; } };
}

async function signIn(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in with work account' }).click();
}

test('PKCE sign-in verifies identity, clears callback and stores no tokens on disk', async ({ page }) => {
  const provider = await mockCognito(page);
  await signIn(page);
  await expect(page.getByRole('heading', { name: 'My tickets.' })).toBeVisible();
  expect(provider.exchanges).toBe(1);
  expect(provider.verifierMatched).toBe(true);
  expect(provider.authorization.searchParams.get('code_challenge_method')).toBe('S256');
  expect(provider.authorization.searchParams.get('scope')).toBe('openid email profile');
  expect(page.url()).toBe('http://localhost:5174/');
  const storage = await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]));
  expect(storage).not.toContain('fake-access-token');
  expect(storage).not.toContain('fake-refresh-token');
  expect(storage).not.toContain('id_token');
  await expect(page.getByText('No tickets yet.', { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Sign in with work account' })).toBeVisible();
});

for (const option of ['badState', 'badAudience', 'badIssuer', 'badSignature', 'badNonce', 'expired', 'denied', 'tokenFailure'] as const) {
  test(`rejects ${option} without exposing callback values`, async ({ page }) => {
    const provider = await mockCognito(page, { [option]: true });
    await signIn(page);
    await expect(page.getByRole('alert')).toContainText('couldn’t complete sign-in');
    await expect(page.getByRole('heading', { name: 'My tickets.' })).toHaveCount(0);
    expect(page.url()).toBe('http://localhost:5174/');
    if (option === 'badState' || option === 'denied') expect(provider.exchanges).toBe(0);
    await expect(page.locator('body')).not.toContainText('test-code');
  });
}

test('rejects callback without a matching login transaction', async ({ page }) => {
  await page.goto('/auth/callback?code=untrusted-code&state=unknown');
  await expect(page.getByRole('alert')).toContainText('couldn’t complete sign-in');
  expect(page.url()).toBe('http://localhost:5174/');
});

test('expires a session and returns to sign-in', async ({ page }) => {
  await mockCognito(page, { shortSession: true });
  await signIn(page);
  await expect(page.getByRole('heading', { name: 'My tickets.' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('session has expired', { timeout: 8000 });
  await expect(page.getByRole('button', { name: 'Sign in with work account' })).toBeEnabled();
});

for (const revokeFailure of [false, true]) {
  test(`logout clears session (revocation failure: ${revokeFailure})`, async ({ page }) => {
    const provider = await mockCognito(page, { revokeFailure });
    await signIn(page);
    await page.getByRole('button', { name: 'Sign out' }).first().click();
    await expect(page.getByRole('button', { name: 'Sign in with work account' })).toBeVisible();
    expect(provider.revocations).toBe(1);
  });
}

test('unknown groups do not grant portal roles', async ({ page }) => {
  await mockCognito(page, { groups: ['superuser'] });
  await signIn(page);
  await expect(page.getByRole('alert')).toContainText('needs an employee or engineer role');
  await expect(page.locator('.roles span')).toHaveCount(0);
});

test('desktop and mobile login layouts fit without horizontal scrolling', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 950 });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Sign in with work account' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/login-${width}.png`, fullPage: true });
  }
});


function fixture(status='transferred_to_human', assignee: string | null=null) {
  return {id:'22222222-2222-4222-8222-222222222222',ticket_number:42,
    employee_id:'33333333-3333-4333-8333-333333333333',category:'vpn',description:'VPN disconnects when working remotely.',
    asset_tag:'LAP-42',priority:'medium',status,assigned_engineer_id:assignee,callback_at:null,
    version:1,resolution_summary:null,created_at:'2026-10-13T10:00:00Z',updated_at:'2026-10-13T10:00:00Z'};
}

test('employee sees own workspace and no engineer controls', async ({page})=>{
  await mockCognito(page);
  await page.route('http://localhost:8000/api/tickets?**',r=>r.fulfill({json:{items:[fixture()],next_cursor:null}}));
  await signIn(page);
  await expect(page.getByRole('heading',{name:'My tickets.'})).toBeVisible();
  await page.getByRole('button',{name:'#42',exact:true}).click();
  await expect(page.getByRole('button',{name:'Assign to me'})).toHaveCount(0);
  await expect(page.getByLabel('Record outcome')).toHaveCount(0);
});

test('ticket submission uses no client identity and retries with the same key',async({page})=>{
  await mockCognito(page);
  const bodies: Record<string,unknown>[]=[];
  await page.route('http://localhost:8000/api/tickets',async r=>{
    bodies.push(r.request().postDataJSON());
    if(bodies.length===1) await r.fulfill({status:503,json:{detail:'Try again'}});
    else await r.fulfill({json:fixture('new')});
  });
  await signIn(page);
  await page.getByRole('button',{name:'+ Create ticket',exact:true}).click();
  await page.getByLabel('What’s happening?').fill('Cannot connect to VPN');
  await page.getByLabel('Preferred callback').fill('2030-10-14T14:30');
  await page.getByRole('button',{name:'Submit ticket',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Try again');
  await page.getByRole('button',{name:'Retry submission'}).click();
  await expect(page.getByRole('status')).toContainText('Ticket #42 created');
  expect(bodies).toHaveLength(2);
  expect(bodies[0]).toEqual(bodies[1]);
  expect(bodies[0].callback_at).toBe('2030-10-14T09:00:00.000Z');
  expect(bodies[0]).not.toHaveProperty('employee_id');
  expect(bodies[0]).not.toHaveProperty('priority');
});

test('engineer claims and records an outcome in the same portal',async({page})=>{
  await mockCognito(page,{groups:['engineer','portal_admin']});
  let t=fixture();
  await page.route('http://localhost:8000/api/tickets?**',r=>r.fulfill({json:{items:[t],next_cursor:null}}));
  await page.route(`http://localhost:8000/api/tickets/${t.id}/claim`,r=>{
    expect(r.request().postDataJSON()).toEqual({expected_version:1});
    t={...t,assigned_engineer_id:'11111111-1111-4111-8111-111111111111',version:2};
    return r.fulfill({json:t});
  });
  await page.route(`http://localhost:8000/api/tickets/${t.id}/outcome`,r=>{
    expect(r.request().postDataJSON()).toEqual({expected_version:2,status:'completed',note:'VPN profile corrected and employee confirmed access.'});
    return r.fulfill({json:{...t,status:'completed',version:3,resolution_summary:'VPN profile corrected and employee confirmed access.'}});
  });
  await signIn(page);
  await expect(page.getByRole('heading',{name:'All tickets.'})).toBeVisible();
  await expect(page.getByRole('button',{name:'+ Create ticket',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'#42',exact:true}).click();
  await page.getByRole('button',{name:'Assign to me'}).click();
  await page.getByLabel('Outcome note').fill('VPN profile corrected and employee confirmed access.');
  await page.getByRole('button',{name:'Save outcome'}).click();
  await expect(page.getByRole('status')).toContainText('marked completed');
  await expect(page.getByRole('button',{name:'Save outcome'})).toHaveCount(0);
});

test('assignment conflict refreshes stale details',async({page})=>{
  await mockCognito(page,{groups:['engineer']});
  const t=fixture();
  await page.route('http://localhost:8000/api/tickets?**',r=>r.fulfill({json:{items:[t],next_cursor:null}}));
  await page.route(`http://localhost:8000/api/tickets/${t.id}/claim`,r=>r.fulfill({status:409,json:{detail:'Another engineer has already claimed this ticket'}}));
  await signIn(page); await page.getByRole('button',{name:'#42',exact:true}).click();
  await page.getByRole('button',{name:'Assign to me'}).click();
  await expect(page.getByRole('alert')).toContainText('Another engineer');
  await expect(page.getByRole('button',{name:'Save outcome'})).toHaveCount(0);
});

test('ticket text is escaped and layout works on a phone',async({page})=>{
  await page.setViewportSize({width:390,height:850});
  await mockCognito(page);
  const t={...fixture(),description:'<script>alert("unsafe")</script>'};
  await page.route('http://localhost:8000/api/tickets?**',r=>r.fulfill({json:{items:[t],next_cursor:null}}));
  await signIn(page); await page.getByRole('button',{name:'#42',exact:true}).click();
  await expect(page.locator('.full-description')).toHaveText(t.description);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/tickets-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:'test-results/tickets-desktop.png',fullPage:true});
});
