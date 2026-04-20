/**
 * VideoHunter — per-project search page:
 *   subject + provider selector → 10-row AG Grid of candidates
 *   Per row: keep / reject radio + Download link (visible once backend has
 *   finished the yt-dlp pull; otherwise says "downloading…").
 *   "Next" button purges non-kept rows on the server (rows + files) and
 *   fetches the next 10 from the same query.
 */
import { useEffect, useMemo, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import {
  CheckCircle2, ChevronRight, Download, Loader2, Search as SearchIcon, XCircle,
} from 'lucide-react';
import { api, downloadUrl } from '../api';
import type { Project, VideoRow } from '../types';
import { getFontSizeWidthMultiplier } from '../lib/fontSizeStore';

interface Props {
  project: Project;
}

function fmtDuration(sec: number) {
  if (!sec || sec <= 0) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h > 0
    ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    : `${m}:${s.toString().padStart(2, '0')}`;
}

function fmtCount(n: number) {
  if (!n) return '';
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

export function VideoHunter({ project }: Props) {
  const [subject, setSubject] = useState(project.subject || '');
  const [provider, setProvider] = useState<'youtube' | 'facebook'>('youtube');
  const [rows, setRows] = useState<VideoRow[]>([]);
  const [kept, setKept] = useState<VideoRow[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scale = getFontSizeWidthMultiplier();

  // Load the kept pile for this project on mount so the lower grid shows
  // every video the user has kept across all past searches, not just this
  // session's keeps.
  useEffect(() => {
    api
      .listKept(project.id)
      .then(setKept)
      .catch(() => {
        /* non-fatal — lower grid stays empty until the user keeps something */
      });
  }, [project.id]);

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault();
    const q = subject.trim();
    if (!q) return;
    setBusy('search');
    setError(null);
    try {
      const res = await api.startSearch(project.id, q, provider);
      setRows(res.batch);
      setHasMore(res.has_more);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Search failed');
    } finally {
      setBusy(null);
    }
  }

  async function onNext() {
    setBusy('next');
    setError(null);
    try {
      const res = await api.nextBatch(project.id);
      setRows(res.batch);
      setHasMore(res.has_more);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Next failed');
    } finally {
      setBusy(null);
    }
  }

  async function setDecision(row: VideoRow, decision: 'keep' | 'rejected' | 'candidate') {
    const wasKept = row.state === 'keep';
    const willBeKept = decision === 'keep';
    const optimistic: VideoRow = { ...row, state: decision };

    // Optimistic move between grids:
    //   - Keep click on a candidate: yank out of top grid, prepend to kept.
    //   - Un-keep click on a kept row: yank out of kept, push back on top as candidate.
    //   - Anything else (candidate ↔ rejected): stays in the top grid.
    if (!wasKept && willBeKept) {
      setRows((rs) => rs.filter((r) => r.id !== row.id));
      setKept((ks) => [optimistic, ...ks.filter((k) => k.id !== row.id)]);
    } else if (wasKept && !willBeKept) {
      setKept((ks) => ks.filter((k) => k.id !== row.id));
      setRows((rs) => [...rs.filter((r) => r.id !== row.id), optimistic]);
    } else {
      setRows((rs) => rs.map((r) => (r.id === row.id ? optimistic : r)));
    }

    try {
      const updated = await api.decideVideo(row.id, decision);
      // Sync authoritative row into whichever grid it now belongs to.
      if (updated.state === 'keep') {
        setKept((ks) => ks.map((k) => (k.id === updated.id ? updated : k)));
      } else {
        setRows((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
      }
    } catch (e: unknown) {
      // Revert: drop from both and re-insert in the original grid with original state.
      setRows((rs) => rs.filter((r) => r.id !== row.id));
      setKept((ks) => ks.filter((k) => k.id !== row.id));
      if (wasKept) {
        setKept((ks) => [row, ...ks]);
      } else {
        setRows((rs) => [...rs, row]);
      }
      setError(e instanceof Error ? e.message : 'Decision failed');
    }
  }

  const columns: ColDef<VideoRow>[] = useMemo(
    () => [
      {
        headerName: '',
        width: Math.round(130 * scale),
        cellRenderer: (p: ICellRendererParams<VideoRow>) => {
          const r = p.data!;
          return r.thumbnail_url ? (
            <img
              src={r.thumbnail_url}
              alt=""
              className="h-full w-full object-cover rounded"
              loading="lazy"
            />
          ) : (
            <div className="h-full w-full bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs">
              no thumb
            </div>
          );
        },
      },
      {
        field: 'title',
        headerName: 'Title',
        flex: 2,
        minWidth: 240,
        cellRenderer: (p: ICellRendererParams<VideoRow>) => (
          <a
            href={p.data?.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-theme-tab-active hover:underline"
          >
            {p.data?.title}
          </a>
        ),
      },
      {
        field: 'channel',
        headerName: 'Channel',
        width: Math.round(160 * scale),
      },
      {
        field: 'duration_sec',
        headerName: 'Duration',
        width: Math.round(110 * scale),
        valueFormatter: (p) => fmtDuration(p.value as number),
      },
      {
        field: 'view_count',
        headerName: 'Views',
        width: Math.round(100 * scale),
        valueFormatter: (p) => fmtCount(p.value as number),
      },
      {
        field: 'provider',
        headerName: 'Source',
        width: Math.round(110 * scale),
      },
      {
        headerName: 'Decision',
        width: Math.round(200 * scale),
        cellRenderer: (p: ICellRendererParams<VideoRow>) => {
          const r = p.data!;
          return (
            <div className="flex items-center gap-1 h-full">
              <button
                type="button"
                onClick={() =>
                  setDecision(r, r.state === 'keep' ? 'candidate' : 'keep')
                }
                className={`px-2 py-1 rounded text-sm inline-flex items-center gap-1 border ${
                  r.state === 'keep'
                    ? 'bg-green-600 text-white border-green-600'
                    : 'bg-white text-green-700 border-green-600 hover:bg-green-50'
                }`}
                title="Keep (survives the Next button)"
              >
                <CheckCircle2 className="h-4 w-4" /> Keep
              </button>
              <button
                type="button"
                onClick={() =>
                  setDecision(r, r.state === 'rejected' ? 'candidate' : 'rejected')
                }
                className={`px-2 py-1 rounded text-sm inline-flex items-center gap-1 border ${
                  r.state === 'rejected'
                    ? 'bg-red-600 text-white border-red-600'
                    : 'bg-white text-red-700 border-red-600 hover:bg-red-50'
                }`}
                title="Reject"
              >
                <XCircle className="h-4 w-4" />
              </button>
            </div>
          );
        },
      },
      {
        headerName: 'Download',
        width: Math.round(170 * scale),
        cellRenderer: (p: ICellRendererParams<VideoRow>) => {
          const r = p.data!;
          const cached = r.has_local_file;
          // Stub candidates carry synthetic IDs that don't exist on the
          // provider — yt-dlp will always 404. Suppress the button so we
          // don't offer a broken action.
          const isStub =
            /^stub\d/i.test(r.provider_video_id) ||
            (r.provider === 'facebook' && r.provider_video_id.length > 15);
          if (isStub && !cached) {
            return (
              <span className="text-xs text-theme-text-muted italic h-full inline-flex items-center">
                stub — paste a real API key
              </span>
            );
          }
          return (
            <a
              href={downloadUrl(r.id)}
              download
              className="inline-flex items-center gap-1 text-theme-tab-active hover:underline text-sm"
              title={cached ? 'Stream the cached file' : 'Fetches the file from the provider on demand (may take 10–60s)'}
            >
              <Download className="h-4 w-4" /> {cached ? 'Download' : 'Fetch + download'}
            </a>
          );
        },
      },
    ],
    [scale],
  );

  return (
    <div className="page-fill flex-1 flex flex-col min-h-0">
      <div className="page-header px-4 py-3">
        <h2 className="page-header-title">
          Hunt · <span className="opacity-80">{project.name}</span>
        </h2>
      </div>

      <div className="px-4 py-3 flex flex-wrap items-center gap-3 bg-white border-b border-gray-200">
        <form onSubmit={runSearch} className="flex items-center gap-2 flex-wrap">
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject to search for…"
            className="input-base w-72"
            disabled={busy !== null}
          />
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as 'youtube' | 'facebook')}
            className="input-base w-40"
            disabled={busy !== null}
          >
            <option value="youtube">YouTube</option>
            <option value="facebook">Facebook</option>
          </select>
          <button
            type="submit"
            disabled={busy !== null || !subject.trim()}
            className="btn btn-primary btn-md inline-flex items-center gap-2 !bg-blue-600 !text-white hover:!bg-blue-700 disabled:!bg-gray-400"
          >
            {busy === 'search' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SearchIcon className="h-4 w-4" />
            )}
            Search
          </button>
        </form>
        <div className="flex-1" />
        <button
          type="button"
          onClick={onNext}
          disabled={busy !== null || !hasMore || rows.length === 0}
          className="btn btn-primary btn-md inline-flex items-center gap-2 !bg-blue-600 !text-white hover:!bg-blue-700 disabled:!bg-gray-400 disabled:opacity-60"
          title="Discard un-kept candidates and fetch the next 10"
        >
          {busy === 'next' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          Next 10
        </button>
      </div>

      {error && (
        <div className="px-4 py-2 text-sm text-red-700 bg-red-50 border-b border-red-200">
          {error}
        </div>
      )}

      <div className="px-4 pb-4 flex-1 min-h-0 flex flex-col gap-3">
        {/* ── Candidates (unreviewed + rejected) ────────────────────── */}
        <div className="flex-[3] min-h-0 flex flex-col">
          <div className="flex items-center justify-between px-1 py-1">
            <h3 className="text-sm font-semibold text-theme-text-primary">
              Candidates
              <span className="ml-2 text-xs text-theme-text-muted font-normal">
                ({rows.length}) — Reject or take no action, then click Next to discard.
              </span>
            </h3>
          </div>
          <div className="ag-theme-alpine flex-1 min-h-0 w-full rounded-lg border border-gray-200">
            <AgGridReact<VideoRow>
              rowData={rows}
              columnDefs={columns}
              rowHeight={88}
              headerHeight={40}
              getRowId={(p) => String(p.data.id)}
              noRowsOverlayComponent={() => (
                <div className="text-theme-text-muted italic">
                  Enter a subject and click Search.
                </div>
              )}
            />
          </div>
        </div>

        {/* ── Kept (survives Next + persists across searches) ───────── */}
        <div className="flex-[2] min-h-[180px] flex flex-col">
          <div className="flex items-center justify-between px-1 py-1">
            <h3 className="text-sm font-semibold text-theme-text-primary">
              Kept
              <span className="ml-2 text-xs text-theme-text-muted font-normal">
                ({kept.length}) — survives Next. Click Keep again to move back to Candidates.
              </span>
            </h3>
          </div>
          <div className="ag-theme-alpine flex-1 min-h-0 w-full rounded-lg border border-green-300 bg-green-50/30">
            <AgGridReact<VideoRow>
              rowData={kept}
              columnDefs={columns}
              rowHeight={88}
              headerHeight={40}
              getRowId={(p) => String(p.data.id)}
              noRowsOverlayComponent={() => (
                <div className="text-theme-text-muted italic">
                  No kept videos yet — click the green Keep button on a candidate.
                </div>
              )}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
