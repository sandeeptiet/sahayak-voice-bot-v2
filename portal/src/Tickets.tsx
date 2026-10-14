import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, type Api, type Me, type Ticket, type TicketPage } from './api';

const categories: Record<string, string> = {account_access:'Account access',network:'Network',vpn:'VPN',microsoft_365:'Microsoft 365',hardware:'Hardware',software:'Software',other:'Other'};
const states: Record<string, string> = {new:'New',in_progress:'In progress',transferred_to_human:'Needs human support',completed:'Completed',failed:'Failed',cancelled:'Cancelled'};
const stamp = (value: string) => new Intl.DateTimeFormat('en-IN', {dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kolkata'}).format(new Date(value));

export function Tickets({ api }: { api: Api }) {
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<Ticket[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [note, setNote] = useState('');
  const [outcome, setOutcome] = useState('completed');
  const [draft, setDraft] = useState({category:'vpn',description:'',asset_tag:'',callback_at:''});
  const requestKey = useRef(crypto.randomUUID());
  const pendingCreate = useRef<Record<string, unknown> | null>(null);
  const generation = useRef(0);
  const engineer = me?.roles.includes('engineer') ?? false;

  async function load(status = filter, before?: number) {
    const current = ++generation.current;
    setLoading(true); setError('');
    try {
      const profile = await api<Me>('/me');
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (before) params.set('before', String(before));
      const page = await api<TicketPage>(`/tickets?${params}`);
      if (current !== generation.current) return;
      setMe(profile); setItems(old => before ? [...old, ...page.items] : page.items); setCursor(page.next_cursor);
    } catch (e) {
      if (current === generation.current) {
        setError(e instanceof Error ? e.message : 'Unable to load tickets.');
        if (e instanceof ApiError && [401,403].includes(e.status)) { setMe(null); setItems([]); setSelected(null); }
      }
    } finally { if (current === generation.current) setLoading(false); }
  }
  useEffect(() => { void load(filter); return () => { generation.current++; }; }, [filter]);

  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
    // Freeze the submission on an uncertain network result; retries use the same key/body.
    pendingCreate.current ??= {
      ...draft, asset_tag: draft.asset_tag || null,
      callback_at: draft.callback_at ? new Date(`${draft.callback_at}:00+05:30`).toISOString() : null,
      request_key: requestKey.current,
    };
      const result = await api<Ticket>('/tickets', pendingCreate.current);
      pendingCreate.current = null; requestKey.current = crypto.randomUUID();
      setDraft({category:'vpn',description:'',asset_tag:'',callback_at:''}); setCreating(false);
      setNotice(`Ticket #${result.ticket_number} created. The call request is queued; automated calling is not active yet.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to create ticket.');
      if (e instanceof ApiError && [400,401,403,422].includes(e.status)) pendingCreate.current = null;
    } finally { setBusy(false); }
  }

  async function change(ticket: Ticket, action: 'claim' | 'outcome') {
    setBusy(true); setError(''); setNotice('');
    try {
      const value = await api<Ticket>(`/tickets/${ticket.id}/${action}`, {
        expected_version: ticket.version, ...(action === 'outcome' ? {status:outcome,note} : {}),
      });
      setSelected(value); setNote('');
      setNotice(action === 'claim' ? `Ticket #${value.ticket_number} is assigned to you.` : `Ticket #${value.ticket_number} marked ${states[value.status].toLowerCase()}.`);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) { await load(); setSelected(null); }
      setError(e instanceof Error ? e.message : 'Unable to update ticket.');
    } finally { setBusy(false); }
  }

  return <section className="workspace" aria-labelledby="tickets-title">
    <div className="workspace-heading"><div><span className="eyebrow">YOUR SUPPORT WORKSPACE</span><h1 id="tickets-title">{engineer ? 'All tickets' : 'My tickets'}<span className="accent">.</span></h1><p>{engineer ? 'Review requests and pick up tickets that need human support.' : 'Create a request and keep track of your IT support.'}</p></div>
      {me?.roles.includes('employee') && <button className="primary new-ticket" disabled={busy || creating} onClick={() => {setCreating(true); setSelected(null);}}>+ Create ticket</button>}
    </div>
    {me && <p className="signed-as">Welcome, {me.name}. <span>Times shown in India Standard Time.</span></p>}
    {error && <div className="notice error" role="alert">{error}</div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    {creating && <form className="ticket-form" onSubmit={create} aria-label="Create ticket">
      <h2>How can we help?</h2>
      {!me?.phone_ready && <div className="notice">Ask your administrator to confirm your callback number before submitting.</div>}
      <fieldset disabled={busy || !!pendingCreate.current}>
        <label>Category<select value={draft.category} onChange={e=>setDraft({...draft,category:e.target.value})}>{Object.entries(categories).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
        <label>What’s happening?<textarea required maxLength={10000} rows={4} value={draft.description} onChange={e=>setDraft({...draft,description:e.target.value})} placeholder="Describe the issue and anything you’ve already tried." /></label>
        <div className="form-row"><label>Asset tag <span>(optional)</span><input maxLength={100} value={draft.asset_tag} onChange={e=>setDraft({...draft,asset_tag:e.target.value})} /></label>
        <label>Preferred callback <span>(optional, IST)</span><input type="datetime-local" value={draft.callback_at} onChange={e=>setDraft({...draft,callback_at:e.target.value})}/></label></div>
      </fieldset>
      {pendingCreate.current && !busy && <p className="help">The last submission could not be confirmed. Retry below to avoid creating a duplicate.</p>}
      <div className="form-actions"><button className="primary" disabled={busy || !me?.phone_ready}>{busy ? 'Submitting…' : pendingCreate.current ? 'Retry submission' : 'Submit ticket'}</button><button type="button" className="quiet-button" disabled={busy || !!pendingCreate.current} onClick={()=>setCreating(false)}>Cancel</button></div>
    </form>}
    <div className="list-toolbar"><label>Show<select value={filter} disabled={busy} onChange={e=>{setFilter(e.target.value);setSelected(null);}}><option value="">All statuses</option>{Object.entries(states).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><button className="quiet-button" disabled={loading || busy} onClick={()=>{setSelected(null);void load();}}>Refresh ↻</button></div>
    {loading && <p role="status">Loading tickets…</p>}
    {!loading && !error && items.length === 0 && <div className="empty-state"><h2>{filter ? 'No tickets with this status.' : 'No tickets yet.'}</h2><p>{engineer ? 'Requests will appear here as employees submit them.' : 'Your support requests will appear here.'}</p></div>}
    {items.length > 0 && <div className="table-wrap"><table><thead><tr><th>Ticket</th><th>Issue</th><th>Status</th><th>Priority</th><th>Assigned to</th><th>Created</th></tr></thead><tbody>{items.map(t=><tr key={t.id} className={selected?.id===t.id ? 'selected-row':''}>
      <td><button className="ticket-link" onClick={()=>{setSelected(t);setNote('');setCreating(false);}}>#{t.ticket_number}</button></td><td><strong>{categories[t.category]}</strong><span className="issue-excerpt">{t.description}</span></td><td><span className={`status-pill ${t.status}`}>{states[t.status]}</span></td><td className="priority">{t.priority}</td><td>{t.assigned_engineer_id===me?.id?'You':t.assigned_engineer_id?'Engineer':'Unassigned'}</td><td className="date-cell">{stamp(t.created_at)}</td>
    </tr>)}</tbody></table></div>}
    {cursor && <button className="quiet-button load-more" disabled={loading || busy} onClick={()=>void load(filter,cursor)}>Load more tickets</button>}
    {selected && <section className="ticket-detail" aria-labelledby="detail-title">
      <div className="detail-heading"><h2 id="detail-title">Ticket #{selected.ticket_number}</h2><button className="quiet-button" onClick={()=>setSelected(null)}>Close</button></div>
      <p className="full-description">{selected.description}</p>
      {selected.asset_tag && <p>Asset: {selected.asset_tag}</p>}
      {selected.callback_at && <p>Preferred callback: {stamp(selected.callback_at)}</p>}
      {selected.resolution_summary && <div className="notice"><strong>Outcome</strong><p>{selected.resolution_summary}</p></div>}
      {engineer && selected.status==='transferred_to_human' && !selected.assigned_engineer_id && <button className="primary new-ticket" disabled={busy} onClick={()=>void change(selected,'claim')}>Assign to me</button>}
      {engineer && selected.status==='transferred_to_human' && selected.assigned_engineer_id===me?.id && <form onSubmit={e=>{e.preventDefault();void change(selected,'outcome');}} aria-label="Record outcome">
        <label>Outcome<select value={outcome} onChange={e=>setOutcome(e.target.value)}><option value="completed">Completed</option><option value="failed">Failed</option></select></label>
        <label>Outcome note<textarea required maxLength={5000} rows={3} value={note} onChange={e=>setNote(e.target.value)} placeholder="Explain what was tried and the result." /></label>
        <button className="primary new-ticket" disabled={busy || !note.trim()}>Save outcome</button>
      </form>}
    </section>}
    <p className="workspace-foot">Sahayak pilot · Automated calling is not active yet.</p>
  </section>;
}
