/**
 * Login — exact same look/feel as buildingsmanager.
 * Replace the icon and title text for each project.
 */
import { useState, FormEvent } from 'react';
import { Clapperboard, Loader2, AlertCircle } from 'lucide-react';
import { useApp } from '../contexts/AppContext';

interface LoginProps {
  onLoginSuccess: () => void;
}

export function Login({ onLoginSuccess }: LoginProps) {
  const { login } = useApp();
  const [username,     setUsername]     = useState('');
  const [password,     setPassword]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(username.trim(), password);
      if (result.success) { onLoginSuccess(); return; }
      setError(result.error ?? 'Login failed.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-theme-content px-4">
      <div className="max-w-md w-full">

        {/* ── Logo + title ── */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-theme-tab-active rounded-2xl shadow-lg mb-4">
            <Clapperboard className="w-12 h-12 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-theme-text-primary mb-2">Video Hunter</h1>
          <p className="text-theme-text-muted">Sign in to continue</p>
        </div>

        {/* ── Card ── */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-theme-card-border">
          <form onSubmit={handleSubmit} className="space-y-6">

            {/* Username */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-theme-text-primary mb-2">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                disabled={loading}
                autoComplete="username"
                placeholder="Enter username"
                className="input-base"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-theme-text-primary mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  autoComplete="current-password"
                  placeholder="Enter password"
                  className="input-base"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  tabIndex={-1}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-theme-text-muted hover:text-theme-text-primary text-sm focus:outline-none"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <span className="flex-1 whitespace-pre-line">{error}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full py-3 px-4 bg-theme-tab-active hover:bg-theme-tab-active-hover text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none flex items-center justify-center gap-2"
            >
              {loading
                ? <><Loader2 className="w-5 h-5 animate-spin" /><span>Signing in…</span></>
                : <span>Sign In</span>
              }
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-theme-text-muted mt-6">
          Video Hunter © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  );
}
