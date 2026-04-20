# UI Base — React + AG Grid + Tailwind Starter

A production-ready frontend template with a complete theme system, AG Grid integration, sidebar navigation, font-size controls, and login screen. Copy this project as the starting point for any new app.

---

## Stack

| Package | Version | Purpose |
|---|---|---|
| React | 18 | UI framework |
| TypeScript | 5 | Type safety |
| Vite | 5 | Build tool / dev server |
| Tailwind CSS | 3 | Utility-first styling |
| AG Grid Community | 34 | Data grid |
| Lucide React | 0.344 | Icons |

---

## Quick Start

```bash
cd ui-base
npm install
npm run dev       # → http://localhost:5174
npm run build     # production build → dist/
```

Default login: **admin / admin** (or any non-empty username + password).

---

## Project Structure

```
ui-base/
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── package.json
└── src/
    ├── main.tsx                   # App entry — provider stack
    ├── App.tsx                    # Shell: Header + Sidebar + content area
    ├── index.css                  # ALL styles: themes, brightness, font-size, AG Grid, components
    ├── contexts/
    │   ├── ThemeContext.tsx        # ocean / mist theme + brightness
    │   ├── FontSizeContext.tsx     # small / normal / large font size
    │   └── AuthContext.tsx         # login / logout session
    ├── lib/
    │   └── fontSizeStore.ts        # Global store — AG Grid column width scaling
    └── components/
        ├── Login.tsx               # Login card + top-left accessibility bar
        ├── Header.tsx              # App header (settings menu, user menu)
        ├── Sidebar.tsx             # Nav with submenus, badges, active stripe
        └── SampleGrid.tsx          # AG Grid demo page
```

---

## Theme System

### Two themes

| Token | Ocean (default) | Mist |
|---|---|---|
| Header | Dark blue `#2E62A2` | White |
| Sidebar | Teal `#2F4D52` | Slate `#475569` |
| Accent | Blue `#2196F3` | Sky `#0EA5E9` |

Switch at runtime:
```tsx
const { setThemeId } = useTheme();
setThemeId('mist');   // or 'ocean'
// Persisted to localStorage('app-theme')
```

### Four brightness levels

`light` → `normal` (default) → `dark` → `contrast` (WCAG AA)

```tsx
const { setBrightness } = useTheme();
setBrightness('contrast');
// Persisted to localStorage('app-brightness')
```

### How it works

CSS variables are declared on `:root` and overridden by `[data-theme]` / `[data-brightness]` attributes on `<html>`. Tailwind maps them via `tailwind.config.js`:

```css
/* index.css */
:root, [data-theme="ocean"] {
  --theme-header: 46 98 162;
  --theme-accent: 33 150 243;
  /* ... */
}
```

```js
// tailwind.config.js
'theme-accent': 'rgb(var(--theme-accent) / <alpha-value>)',
```

```tsx
// Usage in components
<button className="bg-theme-accent text-white hover:bg-theme-accent-hover">
```

### Adding a new theme

1. Add a new `[data-theme="myTheme"]` block in `src/index.css` with all variables.
2. Add `'myTheme'` to the `ThemeId` type in `ThemeContext.tsx`.
3. Add it to the theme toggle in `Header.tsx` and `Login.tsx`.

---

## Font Size System

Three levels: `small` (13px) · `normal` (17px, default) · `large` (22px)

AG Grid automatically scales row height, header height, and cell padding with the font size level.

```tsx
const { setFontSize } = useFontSize();
setFontSize('large');
// Persisted to localStorage('app-font-size')
```

For AG Grid **column widths** that should scale with font size:
```ts
import { getFontSizeWidthMultiplier } from '../lib/fontSizeStore';

const colDef = {
  width: Math.round(120 * getFontSizeWidthMultiplier()),
};
```

---

## Layout System

All layout utilities are plain CSS classes in `index.css`. No page ever scrolls at the document level — only internal panels/grids scroll.

```
┌─────────────────────────── app-shell (100vh, flex column) ─────────────────────────────┐
│  Header (fixed height 48px)                                                             │
├──────────────┬──────────────────────────────────────────────────────────────────────────┤
│              │                                                                          │
│  app-sidebar │  app-content (flex column, overflow hidden)                              │
│  (flex col,  │  ┌──────────────────────────────────────────────────────────────────┐   │
│   overflow   │  │  page-fill (flex column, fills all space)                        │   │
│   hidden)    │  │  ┌──────────────────────────────────────────────────────────┐    │   │
│              │  │  │  page-header (strip)                                     │    │   │
│              │  │  ├──────────────────────────────────────────────────────────┤    │   │
│              │  │  │  action-bar (toolbar)                                    │    │   │
│              │  │  ├──────────────────────────────────────────────────────────┤    │   │
│              │  │  │  grid-fill  ← AG Grid fills remaining height exactly     │    │   │
│              │  │  └──────────────────────────────────────────────────────────┘    │   │
│              │  └──────────────────────────────────────────────────────────────────┘   │
└──────────────┴──────────────────────────────────────────────────────────────────────────┘
```

| Class | Purpose |
|---|---|
| `app-shell` | Root `100vh` flex column, `overflow: hidden` |
| `app-body` | Flex row below header, fills rest of shell |
| `app-sidebar` | Sidebar column, scrolls internally |
| `app-content` | Main area, flex column, `overflow: hidden` |
| `page-fill` | A page — fills `app-content` completely |
| `page-body-scroll` | Scrollable page body (for form/detail pages) |
| `grid-fill` | AG Grid wrapper — fills remaining space in page |

---

## Sidebar Navigation

```tsx
// App.tsx
const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard /> },
  {
    id: 'data', label: 'Data', icon: <Table2 />,
    children: [
      { id: 'grid',    label: 'Grid View', icon: <Table2 /> },
      { id: 'reports', label: 'Reports',   icon: <FileText /> },
    ],
  },
  { id: 'users', label: 'Users', icon: <Users />, badge: 12 },
];

<Sidebar items={NAV_ITEMS} activeId={activeId} onSelect={setActiveId} />
```

- Submenus auto-expand when a child is active.
- `badge` prop shows a count pill.
- `disabled` prop grays out and blocks click.

---

## AG Grid

Configured globally in `index.css` under `.ag-theme-alpine`. Colors follow the active theme automatically via CSS variables.

Minimal page:
```tsx
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
ModuleRegistry.registerModules([AllCommunityModule]);

function MyPage() {
  return (
    <div className="page-fill">
      <div className="page-header px-4 py-3">
        <h2 className="page-header-title">My Grid</h2>
      </div>
      <div className="grid-fill px-4 pb-4">
        <div className="ag-theme-alpine h-full w-full rounded-lg border border-gray-200">
          <AgGridReact rowData={rows} columnDefs={cols} />
        </div>
      </div>
    </div>
  );
}
```

---

## Auth

`AuthContext.tsx` exposes `{ user, login, logout }`. Replace the stub in `login()` with a real API call:

```ts
const login = async (username, password) => {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) return { success: false, error: 'Invalid credentials.' };
  const { user, token } = await res.json();
  localStorage.setItem('app-session', JSON.stringify(user));
  localStorage.setItem('app-token', token);
  setUser(user);
  return { success: true };
};
```

---

## Component Classes (from index.css)

| Class | Usage |
|---|---|
| `page-header` | Blue strip at top of each page |
| `page-header-title` | White bold title inside page-header |
| `action-bar` | Gray toolbar with white bordered buttons |
| `btn-primary` | Accent-colored filled button |
| `btn-danger` | Red filled button |
| `btn-ghost` | Transparent accent-colored button |
| `btn-action` | Icon + label stacked (toolbar buttons) |
| `input-base` | Standard text input with focus ring |
| `label-base` | Form field label |
| `tooltip-content` | Floating tooltip box |
| `animate-slide-in` | Slide from right animation (modals, panels) |

---

## Adding a New Page

1. Create `src/components/MyPage.tsx`:
```tsx
export function MyPage() {
  return (
    <div className="page-fill">
      <div className="page-header px-4 py-3">
        <h2 className="page-header-title">My Page</h2>
      </div>
      <div className="page-body-scroll p-4">
        {/* content */}
      </div>
    </div>
  );
}
```

2. Add to `NAV_ITEMS` in `App.tsx`:
```tsx
{ id: 'my-page', label: 'My Page', icon: <Star /> }
```

3. Render it in `renderPage()`:
```tsx
if (activeId === 'my-page') return <MyPage />;
```

---

## RTL Support

To switch to RTL (e.g. Hebrew/Arabic):

1. `index.html` → `<html lang="he" dir="rtl">`
2. `index.css` AG Grid cells already have `direction: rtl` commented examples — uncomment them.
3. Tailwind: use `rtl:` variants or set `direction: rtl` on `.app-shell`.

---

## Environment / API Base URL

Set `VITE_API_BASE_URL` in a `.env` file:
```
VITE_API_BASE_URL=https://api.myapp.com
```

Read it anywhere:
```ts
const BASE = import.meta.env.VITE_API_BASE_URL ?? '';
fetch(`${BASE}/api/users`);
```
