/**
 * Video Hunter shell — header + icon sidebar + tabs.
 * Pages:
 *   • Projects — list + create; selecting one opens its Hunt tab.
 *   • Hunt     — per-project search + AG Grid (keep/reject + Download + Next).
 *   • Settings — admin provider credentials (write-only).
 */
import { useState, useCallback, useRef, useEffect, lazy, Suspense } from 'react';
import {
  Clapperboard, FolderKanban, LogOut, Menu, Search, Settings, SlidersHorizontal,
  User, X, Loader2,
} from 'lucide-react';
import { useApp } from './contexts/AppContext';
import { Login } from './components/Login';
import type { Project } from './types';

const Projects = lazy(() =>
  import('./components/Projects').then((m) => ({ default: m.Projects })),
);
const VideoHunter = lazy(() =>
  import('./components/VideoHunter').then((m) => ({ default: m.VideoHunter })),
);
const AdminSettings = lazy(() =>
  import('./components/AdminSettings').then((m) => ({ default: m.AdminSettings })),
);

const APP_NAME = 'Video Hunter';
const FOOTER_TEXT = '© Video Hunter';

function AppIcon() {
  return (
    <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
      <Clapperboard className="h-5 w-5 text-white" />
    </div>
  );
}

type Tab =
  | { id: 'projects'; type: 'projects'; label: string; pinned: true; refreshKey?: number; icon?: React.ReactNode }
  | { id: `hunt:${number}`; type: 'hunt'; label: string; pinned?: false; refreshKey?: number; icon?: React.ReactNode; project: Project }
  | { id: 'settings'; type: 'settings'; label: string; pinned?: false; refreshKey?: number; icon?: React.ReactNode };

interface NavItem {
  label: string;
  icon: React.ReactNode;
  activeFor: Tab['type'][];
  onClick: () => void;
}

function TabFallback() {
  return (
    <div className="flex-1 flex items-center justify-center bg-app-bg">
      <Loader2 className="w-10 h-10 text-app-accent animate-spin" />
    </div>
  );
}

export default function App() {
  const { session, logout, brightness, setBrightness, fontSize, setFontSize, themeId, setThemeId } = useApp();
  const [isAuthenticated, setIsAuthenticated] = useState(!!session);

  useEffect(() => {
    setIsAuthenticated(!!session);
  }, [session]);

  const [tabs, setTabs] = useState<Tab[]>([
    {
      id: 'projects',
      type: 'projects',
      label: 'Projects',
      pinned: true,
      icon: <FolderKanban className="h-4 w-4" />,
    },
  ]);
  const [activeTabId, setActiveTabId] = useState<Tab['id']>('projects');

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsMenuOpen, setSettingsMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node))
        setSettingsMenuOpen(false);
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node))
        setUserMenuOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const closeAllMenus = useCallback(() => {
    setSidebarOpen(false);
    setSettingsMenuOpen(false);
    setUserMenuOpen(false);
  }, []);

  function openTab(t: Tab) {
    setTabs((prev) => {
      const existing = prev.find((x) => x.id === t.id);
      if (existing) {
        return prev.map((x) => (x.id === t.id ? { ...x, refreshKey: Date.now() } : x));
      }
      // Replace the single settings tab if opening a new one; hunt tabs stack.
      const filtered =
        t.type === 'settings' ? prev.filter((x) => x.type !== 'settings' || x.pinned) : prev;
      return [...filtered, { ...t, refreshKey: Date.now() }];
    });
    setActiveTabId(t.id);
  }

  function closeTab(id: Tab['id']) {
    const tab = tabs.find((t) => t.id === id);
    if (!tab || tab.pinned) return;
    setTabs((prev) => {
      const next = prev.filter((t) => t.id !== id);
      return next.length ? next : [
        {
          id: 'projects',
          type: 'projects',
          label: 'Projects',
          pinned: true,
          icon: <FolderKanban className="h-4 w-4" />,
        },
      ];
    });
    if (activeTabId === id) {
      const rest = tabs.filter((t) => t.id !== id);
      setActiveTabId(rest.length ? rest[rest.length - 1].id : 'projects');
    }
  }

  const openProject = useCallback((p: Project) => {
    openTab({
      id: `hunt:${p.id}` as const,
      type: 'hunt',
      label: `Hunt · ${p.name}`,
      icon: <Search className="h-4 w-4" />,
      project: p,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const NAV: NavItem[] = [
    {
      label: 'Projects',
      icon: <FolderKanban className="h-5 w-5 shrink-0" />,
      activeFor: ['projects', 'hunt'],
      onClick: () => {
        closeAllMenus();
        openTab({
          id: 'projects',
          type: 'projects',
          label: 'Projects',
          pinned: true,
          icon: <FolderKanban className="h-4 w-4" />,
        });
      },
    },
    {
      label: 'Settings',
      icon: <Settings className="h-5 w-5 shrink-0" />,
      activeFor: ['settings'],
      onClick: () => {
        closeAllMenus();
        openTab({
          id: 'settings',
          type: 'settings',
          label: 'Settings',
          icon: <Settings className="h-4 w-4" />,
        });
      },
    },
  ];

  const activeTab = tabs.find((t) => t.id === activeTabId);
  function renderPage() {
    if (!activeTab) return null;
    switch (activeTab.type) {
      case 'projects':
        return (
          <Suspense fallback={<TabFallback />}>
            <Projects key={activeTab.refreshKey} onOpenProject={openProject} />
          </Suspense>
        );
      case 'hunt':
        return (
          <Suspense fallback={<TabFallback />}>
            <VideoHunter key={activeTab.refreshKey} project={activeTab.project} />
          </Suspense>
        );
      case 'settings':
        return (
          <Suspense fallback={<TabFallback />}>
            <AdminSettings key={activeTab.refreshKey} />
          </Suspense>
        );
      default:
        return null;
    }
  }

  if (!isAuthenticated) {
    return <Login onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  const isActive = (n: NavItem) =>
    activeTab ? n.activeFor.includes(activeTab.type) : false;

  return (
    <div className="min-h-screen bg-app-bg flex flex-col" onClick={closeAllMenus}>
      {/* Header */}
      <header
        className="shrink-0 h-12 bg-app-header flex items-center justify-between px-4 text-white shadow-md z-50"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2">
          <AppIcon />
          <span className="font-semibold text-base hidden sm:inline">{APP_NAME}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="relative" ref={settingsRef}>
            <button
              onClick={() => {
                setSettingsMenuOpen((v) => !v);
                setUserMenuOpen(false);
              }}
              className={`p-2.5 rounded hover:bg-white/10 transition-colors ${settingsMenuOpen ? 'bg-white/10' : 'opacity-80'}`}
              title="Appearance"
            >
              <SlidersHorizontal className="h-5 w-5" />
            </button>
            {settingsMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-52 bg-app-sidebar border border-white/10 rounded-lg shadow-xl py-2 z-[100]">
                <div className="px-3 py-1.5 border-b border-white/10">
                  <span className="text-xs font-medium text-white/70">Theme</span>
                  <div className="flex gap-1 mt-1">
                    {(['ocean', 'mist'] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setThemeId(t)}
                        className={`flex-1 py-1.5 rounded text-sm capitalize ${
                          themeId === t ? 'bg-white/20 text-white' : 'text-white/80 hover:bg-white/10'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="px-3 py-1.5 border-b border-white/10">
                  <span className="text-xs font-medium text-white/70">Brightness</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(['light', 'normal', 'dark', 'contrast'] as const).map((b) => (
                      <button
                        key={b}
                        onClick={() => setBrightness(b)}
                        className={`flex-1 min-w-0 py-1.5 rounded text-xs ${
                          brightness === b ? 'bg-white/20 text-white' : 'text-white/80 hover:bg-white/10'
                        }`}
                      >
                        {b}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="px-3 py-1.5">
                  <span className="text-xs font-medium text-white/70">Font size</span>
                  <div className="flex gap-1 mt-1">
                    {(['small', 'normal', 'large'] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setFontSize(f)}
                        className={`flex-1 py-1.5 rounded text-sm capitalize ${
                          fontSize === f ? 'bg-white/20 text-white' : 'text-white/80 hover:bg-white/10'
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => {
                setUserMenuOpen((v) => !v);
                setSettingsMenuOpen(false);
              }}
              className={`p-2.5 rounded hover:bg-white/10 transition-colors ${userMenuOpen ? 'bg-white/10' : 'opacity-80'}`}
              title="User"
            >
              <User className="h-5 w-5" />
            </button>
            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-app-sidebar border border-white/10 rounded-lg shadow-xl py-2 z-[100]">
                <div className="px-3 py-2 border-b border-white/10">
                  <p className="text-sm font-medium text-white truncate">{session?.user_name}</p>
                  <p className="text-xs text-white/70 capitalize">{session?.user_role}</p>
                </div>
                <button
                  onClick={async () => {
                    setUserMenuOpen(false);
                    await logout();
                  }}
                  className="w-full flex items-center justify-center gap-2 py-2 px-3 text-sm text-white/90 hover:bg-app-destructive/30 hover:text-white rounded-b-lg transition-colors"
                >
                  <LogOut className="h-4 w-4" /> Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 flex flex-row min-h-0">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setSidebarOpen((v) => !v);
          }}
          className="md:hidden fixed z-50 min-h-[44px] min-w-[44px] p-3 left-2 bg-app-sidebar rounded-xl shadow-lg border border-app-sidebar-hover"
          style={{ top: 'max(0.5rem, env(safe-area-inset-top, 0px))' }}
        >
          <Menu className="h-6 w-6 text-white" />
        </button>

        <div
          className={`${sidebarOpen ? 'fixed inset-0 z-40 md:relative md:z-auto' : 'hidden md:flex'}
            md:w-[72px] lg:w-20 bg-app-sidebar border-r border-white/10 flex flex-col shrink-0 overflow-visible`}
          onClick={(e) => e.stopPropagation()}
        >
          {sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(false)}
              className="md:hidden absolute min-h-[44px] min-w-[44px] p-3 right-2 bg-app-sidebar rounded-xl"
              style={{ top: 'max(0.5rem, env(safe-area-inset-top, 0px))' }}
            >
              <X className="h-6 w-6 text-white" />
            </button>
          )}

          <nav className="flex-1 p-2 space-y-0.5 overflow-visible">
            {NAV.map((n, i) => (
              <button
                key={i}
                onClick={n.onClick}
                title={n.label}
                className={`w-full flex items-center justify-center p-2.5 rounded transition-all duration-200 text-white ${
                  isActive(n)
                    ? 'bg-app-sidebar-active border-r-[3px] border-r-app-sidebar-indicator'
                    : 'hover:bg-app-sidebar-hover'
                }`}
              >
                {n.icon}
              </button>
            ))}
          </nav>

          <div className="p-2 border-t border-white/10 flex flex-col items-center">
            <p className="text-[9px] text-white/40">{FOOTER_TEXT}</p>
          </div>
        </div>

        <div
          className="flex-1 flex flex-col min-w-0 pt-[52px] md:pt-0"
          onClick={closeAllMenus}
        >
          {/* Tabs bar */}
          <div className="bg-app-tabs-bg border-b border-app-input-border shrink-0">
            <div className="px-2 sm:px-4 py-1.5">
              <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide min-h-[40px]">
                {tabs.map((tab) => (
                  <div
                    key={tab.id}
                    className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-all duration-200 cursor-pointer flex-shrink-0 -mb-px group ${
                      activeTabId === tab.id
                        ? 'border-app-sidebar-indicator text-app-text-primary font-semibold'
                        : 'border-transparent text-app-text-muted hover:text-app-text-primary hover:bg-white/40'
                    }`}
                  >
                    <div
                      className="flex items-center gap-2"
                      onClick={() => {
                        setTabs((prev) =>
                          prev.map((t) => (t.id === tab.id ? { ...t, refreshKey: Date.now() } : t)),
                        );
                        setActiveTabId(tab.id);
                      }}
                    >
                      {tab.icon && <span className="text-slate-600 shrink-0">{tab.icon}</span>}
                      <span className="whitespace-nowrap text-sm">{tab.label}</span>
                    </div>
                    {!tab.pinned && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          closeTab(tab.id);
                        }}
                        className="p-0.5 text-slate-400 hover:bg-red-100 hover:text-red-600 rounded"
                      >
                        <X className="h-2.5 w-2.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-hidden flex flex-col min-h-0 bg-app-bg">{renderPage()}</div>
        </div>
      </div>
    </div>
  );
}
