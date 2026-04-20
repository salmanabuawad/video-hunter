import type { AppConfigStatus, Project, SearchBatch, Session, VideoRow } from './types';

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...init,
    headers: { ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') msg = body.detail;
      else if (Array.isArray(body?.detail))
        msg = body.detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join('; ');
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function downloadUrl(videoId: number) {
  return `${BASE}/api/videos/${videoId}/download`;
}

export const api = {
  async login(username: string, password: string) {
    return request<{
      ok: boolean;
      token: string;
      expires_at: string;
      user: { id: number; username: string; role: string };
    }>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  },

  async logout() {
    return request('/api/auth/logout', { method: 'POST' });
  },

  async me(): Promise<Session> {
    const u = await request<{ id: number; username: string; role: string }>('/api/auth/me');
    return { user_id: u.id, user_name: u.username, user_role: u.role, token: '' };
  },

  listProjects: () => request<Project[]>('/api/projects'),

  createProject: (name: string) =>
    request<Project>('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  getProject: (id: number) => request<Project>(`/api/projects/${id}`),

  deleteProject: (id: number) => request<void>(`/api/projects/${id}`, { method: 'DELETE' }),

  startSearch: (projectId: number, subject: string, provider: 'youtube' | 'facebook') =>
    request<SearchBatch>(`/api/projects/${projectId}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, provider }),
    }),

  nextBatch: (projectId: number) =>
    request<SearchBatch>(`/api/projects/${projectId}/search/next`, { method: 'POST' }),

  decideVideo: (videoId: number, decision: 'keep' | 'reject' | 'candidate') =>
    request<VideoRow>(`/api/videos/${videoId}/decide`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision }),
    }),

  listKept: (projectId: number) => request<VideoRow[]>(`/api/projects/${projectId}/kept`),

  adminConfigStatus: () => request<AppConfigStatus>('/api/admin/config/status'),

  saveAdminConfig: (body: {
    youtube_api_key?: string;
    facebook_cookies?: string;
    facebook_email?: string;
    facebook_password?: string;
  }) =>
    request<AppConfigStatus>('/api/admin/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
};
