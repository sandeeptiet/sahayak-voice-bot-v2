export interface Me { id: string; name: string; roles: string[]; phone_ready: boolean }
export interface Ticket {
  id: string; ticket_number: number; employee_id: string; category: string;
  description: string; asset_tag: string | null; priority: string; status: string;
  assigned_engineer_id: string | null; callback_at: string | null; version: number;
  resolution_summary: string | null; created_at: string; updated_at: string;
}
export interface TicketPage { items: Ticket[]; next_cursor: number | null }
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export function createApi(token: () => Promise<string>) {
  const origin = import.meta.env.VITE_API_ORIGIN || 'http://localhost:8000';
  return async function request<T>(path: string, body?: unknown): Promise<T> {
    const bearer = await token();
    let response: Response;
    try {
      response = await fetch(`${origin}/api${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        headers: { Authorization: `Bearer ${bearer}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store', signal: AbortSignal.timeout(20000),
      });
    } catch { throw new ApiError(0, 'The ticket service is unavailable. Please try again shortly.'); }
    if (!response.ok) {
      const fallback = response.status === 401 ? 'Your session has expired. Sign out and sign in again.' : 'The request could not be completed. Please try again.';
      const payload = await response.json().catch(() => ({}));
      throw new ApiError(response.status, typeof payload.detail === 'string' ? payload.detail : fallback);
    }
    return response.json();
  };
}
export type Api = ReturnType<typeof createApi>;
