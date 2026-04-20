/**
 * Admin Settings — provider credentials stored in the server DB
 * (table `app_config`). Keys are write-only: saved values are never echoed
 * back to the browser. Empty inputs leave the stored value untouched.
 */
import { FormEvent, useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../api';
import type { AppConfigStatus } from '../types';

export function AdminSettings() {
  const [status, setStatus] = useState<AppConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [ytKey, setYtKey] = useState('');
  const [fbCookies, setFbCookies] = useState('');
  const [fbEmail, setFbEmail] = useState('');
  const [fbPassword, setFbPassword] = useState('');

  useEffect(() => {
    api
      .adminConfigStatus()
      .then((s) => {
        setStatus(s);
        setFbEmail(s.facebook_email || '');
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const res = await api.saveAdminConfig({
        youtube_api_key: ytKey.trim() || undefined,
        facebook_cookies: fbCookies.trim() || undefined,
        facebook_email: fbEmail.trim() || undefined,
        facebook_password: fbPassword.trim() || undefined,
      });
      setStatus(res);
      setYtKey('');
      setFbCookies('');
      setFbPassword('');
      setMessage('Saved. Credentials live in the server database only.');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-fill flex-1 flex flex-col min-h-0">
      <div className="page-header px-4 py-3">
        <h2 className="page-header-title">Admin · Provider credentials</h2>
      </div>

      <div className="page-body-scroll p-6 max-w-2xl">
        {loading && (
          <div className="flex items-center gap-2 text-theme-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading status…
          </div>
        )}

        {status && (
          <div className="mb-6 grid grid-cols-2 gap-3">
            <StatusChip label="YouTube API key" on={status.youtube_configured} />
            <StatusChip label="Facebook session cookies" on={status.facebook_configured} />
            <StatusChip
              label={
                status.facebook_email
                  ? `Facebook email · ${status.facebook_email}`
                  : 'Facebook email'
              }
              on={status.facebook_email_configured}
            />
            <StatusChip
              label="Facebook password"
              on={status.facebook_password_configured}
            />
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-theme-text-primary mb-2">
              YouTube Data API v3 key
            </label>
            <input
              type="password"
              className="input-base"
              value={ytKey}
              onChange={(e) => setYtKey(e.target.value)}
              autoComplete="off"
              placeholder={
                status?.youtube_configured
                  ? '••••••••  (saved — enter a new key to replace)'
                  : 'AIzaSy...'
              }
              disabled={saving}
            />
            <p className="mt-1 text-xs text-theme-text-muted">
              From <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer" className="underline">Google Cloud Console</a>.
              Leave empty to keep the current key.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-theme-text-primary mb-2">
              Facebook session cookies
            </label>
            <textarea
              className="input-base font-mono text-xs h-24"
              value={fbCookies}
              onChange={(e) => setFbCookies(e.target.value)}
              placeholder={
                status?.facebook_configured
                  ? '••••••••  (saved — paste a fresh Cookie header to replace)'
                  : 'c_user=...; xs=...; datr=...; fr=...'
              }
              disabled={saving}
            />
            <p className="mt-1 text-xs text-theme-text-muted">
              Paste the raw <code className="font-mono">Cookie</code> header from a logged-in
              facebook.com session (DevTools → Network → any request → Request Headers → Cookie).
              Keep this rotated — FB may challenge or ban accounts used for scraping.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-theme-text-primary mb-2">
                Facebook email
              </label>
              <input
                type="email"
                className="input-base"
                value={fbEmail}
                onChange={(e) => setFbEmail(e.target.value)}
                placeholder="name@example.com"
                disabled={saving}
              />
              <p className="mt-1 text-xs text-theme-text-muted">
                Account used to harvest the session cookies above. Not a secret;
                shown back here so you know which login is wired.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-theme-text-primary mb-2">
                Facebook password
              </label>
              <input
                type="password"
                autoComplete="new-password"
                className="input-base"
                value={fbPassword}
                onChange={(e) => setFbPassword(e.target.value)}
                placeholder={
                  status?.facebook_password_configured
                    ? '••••••••  (saved — type a new one to replace)'
                    : 'Your Facebook password'
                }
                disabled={saving}
              />
              <p className="mt-1 text-xs text-theme-text-muted">
                Stored in the server DB only. Used to re-establish the session
                automatically when the cookies above expire.
              </p>
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          {message && (
            <div className="flex items-start gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{message}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={saving || (!ytKey.trim() && !fbCookies.trim())}
            className="btn btn-primary btn-md inline-flex items-center gap-2"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Save credentials
          </button>
        </form>
      </div>
    </div>
  );
}

function StatusChip({ label, on }: { label: string; on: boolean }) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
        on
          ? 'bg-green-50 border-green-200 text-green-800'
          : 'bg-gray-50 border-gray-200 text-gray-600'
      }`}
    >
      <span
        className={`inline-block w-2.5 h-2.5 rounded-full ${on ? 'bg-green-500' : 'bg-gray-400'}`}
      />
      <span className="flex-1">{label}</span>
      <span className="font-medium">{on ? 'configured' : 'not set'}</span>
    </div>
  );
}
