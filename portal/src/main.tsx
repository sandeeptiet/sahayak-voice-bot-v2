import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { readConfig } from './config';
import { createAuth, type Identity } from './auth';
import './styles.css';
import './tickets.css';
import { createApi } from './api';
import { Tickets } from './Tickets';

let auth: ReturnType<typeof createAuth> | undefined;
let setupError = '';
try {
  const config = readConfig(import.meta.env);
  if (window.location.origin !== config.origin) {
    throw new Error(`Open the portal at ${config.origin} so sign-in returns to the correct address.`);
  }
  auth = createAuth(config);
} catch (error) {
  setupError = error instanceof Error ? error.message : 'Portal configuration is incomplete.';
}
const isCallback = window.location.pathname === '/auth/callback';
const callbackUrl = window.location.href;
// Remove codes and provider errors before rendering or loading any other content.
if (isCallback) window.history.replaceState({}, '', '/');

const api = createApi(async () => {
  if (!auth) throw new Error('Sign-in is not configured');
  return auth.accessToken();
});

function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [busy, setBusy] = useState(isCallback && !!auth);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!isCallback || !auth) return;
    let active = true;
    auth.complete(callbackUrl).then(user => {
      if (active) setIdentity(user);
    }).catch((error: Error) => {
      if (active) setMessage(error.message);
    }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!identity) return;
    const expire = () => {
      if (Date.now() < identity.expiresAt) return;
      setIdentity(null);
      setMessage('Your session has expired. Sign in again to continue.');
      void auth?.expire();
    };
    const timer = window.setTimeout(expire, Math.max(0, identity.expiresAt - Date.now()));
    window.addEventListener('focus', expire);
    document.addEventListener('visibilitychange', expire);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('focus', expire);
      document.removeEventListener('visibilitychange', expire);
    };
  }, [identity]);

  async function signIn() {
    setMessage(''); setBusy(true);
    try { await auth?.login(); }
    catch { setMessage('Sign-in is unavailable right now. Please try again.'); setBusy(false); }
  }
  async function signOut() {
    setIdentity(null); setBusy(true); setMessage('');
    try { await auth?.logout(); }
    catch { setMessage('You are signed out of this portal. Close the browser to finish signing out.'); setBusy(false); }
  }

  return <div className="page">
    <header>
      <a className="brand" href="/" aria-label="Sahayak home"><span className="brand-mark">s</span>Sahayak<span className="brand-dot">.</span></a>
      <span className="header-label">YOUR IT SUPPORT SPACE</span>
      {identity ? <button className="quiet-button" onClick={signOut}>Sign out <span aria-hidden="true">↗</span></button> : <span className="pilot">Employee pilot</span>}
    </header>
    {identity ? <Tickets api={api} /> : <main>
      <section className="intro" aria-labelledby="intro-title">
        <div className="eyebrow"><span /> A LITTLE HELP. A BETTER WORKDAY.</div>
        <h1 id="intro-title">IT trouble?<br />Let's work<br />through it<span className="accent">.</span></h1>
        <p className="lede">A place to ask for help, follow your requests, and get back to what you do best.</p>
        <div className="journey">
          <div><span className="step">01</span><p><strong>Tell us what’s happening</strong><span>Describe the issue in your own words.</span></p></div>
          <div><span className="step">02</span><p><strong>Get the right support</strong><span>Guided help, with a human when needed.</span></p></div>
          <div><span className="step">03</span><p><strong>Keep everything in view</strong><span>Your updates and outcomes, in one place.</span></p></div>
        </div>
        <p className="intro-foot">Less time troubleshooting. More time moving forward.</p>
      </section>
      <section className="entry" aria-labelledby="entry-title">
        <div className="entry-top"><span className="small-label">SAHAYAK PORTAL</span><span className="small-label">01 / SIGN IN</span></div>
        <div className="card">
          <div className="card-icon" aria-hidden="true">↗</div>
          <span className="eyebrow dark">GOOD TO HAVE YOU HERE</span>
          <h2 id="entry-title">Your workday, supported.</h2>
            <p className="card-copy">Sign in with your work account to access Sahayak.</p>
            {setupError && <div className="notice" role="alert"><strong>One setup step remains</strong><p>{setupError}</p></div>}
            {message && <div className="notice error" role="alert">{message}</div>}
            <button className="primary" disabled={busy || !!setupError} onClick={signIn}>{busy ? 'Connecting…' : 'Sign in with work account'}<span aria-hidden="true">↗</span></button>
            <p className="secure-note">You’ll continue to your organization’s secure sign-in page.</p>
          <div className="card-divider" />
          <p className="help">Need access?<br /><strong>Contact your IT administrator.</strong></p>
        </div>
        <div className="bottom-note"><span aria-hidden="true">✳</span><p>Built around people.<br /><strong>Backed by your support team.</strong></p></div>
      </section>
    </main>}
    <footer><span>SAHAYAK / WORKPLACE SUPPORT</span><span>Internal employee portal</span></footer>
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
