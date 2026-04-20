/**
 * Projects page — list existing projects, create a new one, select one to hunt.
 * Selecting a project opens the VideoHunter tab scoped to that project id.
 */
import { useEffect, useMemo, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { FolderPlus, Loader2, Trash2 } from 'lucide-react';
import { api } from '../api';
import type { Project } from '../types';
import { getFontSizeWidthMultiplier } from '../lib/fontSizeStore';

interface Props {
  onOpenProject: (p: Project) => void;
}

export function Projects({ onOpenProject }: Props) {
  const [rows, setRows] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const scale = getFontSizeWidthMultiplier();

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .listProjects()
      .then(setRows)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const p = await api.createProject(name);
      setNewName('');
      setRows((prev) => [p, ...prev]);
      onOpenProject(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  }

  async function onDelete(p: Project) {
    if (!confirm(`Delete project "${p.name}" and all its candidates?`)) return;
    try {
      await api.deleteProject(p.id);
      setRows((prev) => prev.filter((r) => r.id !== p.id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  }

  const columns: ColDef<Project>[] = useMemo(
    () => [
      { field: 'id', headerName: 'ID', width: Math.round(80 * scale) },
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'subject',
        headerName: 'Last subject',
        flex: 1,
        minWidth: 180,
        valueGetter: (p) => p.data?.subject || '—',
      },
      {
        field: 'updated_at',
        headerName: 'Updated',
        width: Math.round(180 * scale),
        valueFormatter: (p) => (p.value ? new Date(p.value).toLocaleString() : ''),
      },
      {
        headerName: 'Actions',
        width: Math.round(200 * scale),
        cellRenderer: (p: ICellRendererParams<Project>) => {
          const proj = p.data!;
          return (
            <div className="flex gap-2 items-center h-full">
              <button
                className="px-3 py-1 rounded bg-theme-tab-active text-white text-sm hover:bg-theme-tab-active-hover"
                onClick={() => onOpenProject(proj)}
              >
                Hunt
              </button>
              <button
                className="p-1.5 rounded text-red-600 hover:bg-red-50"
                onClick={() => onDelete(proj)}
                title="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          );
        },
      },
    ],
    [scale],
  );

  return (
    <div className="page-fill flex-1 flex flex-col min-h-0">
      <div className="page-header px-4 py-3 flex items-center justify-between">
        <h2 className="page-header-title">Projects</h2>
      </div>

      <div className="action-bar px-4 py-3 flex items-center gap-3 flex-wrap bg-white border-b border-gray-200">
        <form onSubmit={onCreate} className="flex items-center gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New project name…"
            className="input-base w-64"
            disabled={creating}
          />
          <button
            type="submit"
            className="btn-primary inline-flex items-center gap-2"
            disabled={creating || !newName.trim()}
          >
            {creating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FolderPlus className="h-4 w-4" />
            )}
            Create project
          </button>
        </form>
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>

      <div className="grid-fill px-4 pb-4 flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full text-theme-text-muted">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <div className="ag-theme-alpine h-full w-full rounded-lg border border-gray-200">
            <AgGridReact<Project>
              rowData={rows}
              columnDefs={columns}
              rowHeight={40}
              headerHeight={40}
              onRowDoubleClicked={(e) => e.data && onOpenProject(e.data)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
