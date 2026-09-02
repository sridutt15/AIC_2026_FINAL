import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  FileUp,
  Gauge,
  History as HistoryIcon,
  LayoutDashboard,
  Lightbulb,
  ListChecks,
  LogOut,
  Menu,
  MessageSquareQuote,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Table2,
  Target,
  UserRound,
  X,
} from 'lucide-react'
import { checkHealth, checkDatabaseHealth } from './api/health'
import { setSessionExpiredHandler } from './api/authClient'
import { AuthProvider, useAuth } from './context/AuthContext'
import { Badge, Button } from './components/ui'
import UploadPage from './pages/UploadPage'
import ProfilePage from './pages/ProfilePage'
import SemanticContractPage from './pages/SemanticContractPage'
import DataQualityPage from './pages/DataQualityPage'
import CanonicalModelPage from './pages/CanonicalModelPage'
import KpiDashboardPage from './pages/KpiDashboardPage'
import AnomalyPage from './pages/AnomalyPage'
import DriversPage from './pages/DriversPage'
import InsightsPage from './pages/InsightsPage'
import RecommendationsPage from './pages/RecommendationsPage'
import FeedbackPage from './pages/FeedbackPage'
import TelemetryPage from './pages/TelemetryPage'
import HistoryPage from './pages/HistoryPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

type BackendStatus = 'checking' | 'connected' | 'unreachable'
type DbStatus = 'checking' | 'connected' | 'unreachable'
type BootStage = 'server' | 'database' | 'ready' | 'db_failed'
export type PageName =
  | 'Upload'
  | 'Profile'
  | 'Semantic Contract'
  | 'Data Quality'
  | 'Canonical Model'
  | 'KPIs'
  | 'Anomalies'
  | 'Drivers'
  | 'Insights'
  | 'Recommendations'
  | 'Feedback'
  | 'Telemetry'
  | 'History'
  | 'Dashboard'
  | 'Login'
  | 'Register'

const NAV_ITEMS: {
  label: string
  page: PageName
  icon: React.ReactNode
  group: 'pipeline' | 'analysis' | 'ops'
}[] = [
  { label: 'Dashboard', page: 'Dashboard', icon: <LayoutDashboard size={18} />, group: 'ops' },
  { label: 'Upload', page: 'Upload', icon: <FileUp size={18} />, group: 'pipeline' },
  { label: 'Profile', page: 'Profile', icon: <Table2 size={18} />, group: 'pipeline' },
  { label: 'Semantic Contract', page: 'Semantic Contract', icon: <ScrollText size={18} />, group: 'pipeline' },
  { label: 'Data Quality', page: 'Data Quality', icon: <ShieldCheck size={18} />, group: 'pipeline' },
  { label: 'Canonical Model', page: 'Canonical Model', icon: <ListChecks size={18} />, group: 'pipeline' },
  { label: 'KPIs', page: 'KPIs', icon: <Gauge size={18} />, group: 'analysis' },
  { label: 'Anomalies', page: 'Anomalies', icon: <AlertTriangle size={18} />, group: 'analysis' },
  { label: 'Drivers', page: 'Drivers', icon: <BarChart3 size={18} />, group: 'analysis' },
  { label: 'Insights', page: 'Insights', icon: <Lightbulb size={18} />, group: 'analysis' },
  { label: 'Recommendations', page: 'Recommendations', icon: <Target size={18} />, group: 'analysis' },
  { label: 'Feedback', page: 'Feedback', icon: <MessageSquareQuote size={18} />, group: 'ops' },
  { label: 'Telemetry', page: 'Telemetry', icon: <Activity size={18} />, group: 'ops' },
  { label: 'History', page: 'History', icon: <HistoryIcon size={18} />, group: 'ops' },
]

const NAV_GROUPS: { id: 'pipeline' | 'analysis' | 'ops'; label: string }[] = [
  { id: 'pipeline', label: 'Data Pipeline' },
  { id: 'analysis', label: 'Analysis' },
  { id: 'ops', label: 'Operations' },
]

function StatusPill({
  ok,
  checking,
  label,
  message,
}: {
  ok: boolean
  checking: boolean
  label: string
  message?: string
}) {
  if (checking) {
    return (
      <span className="hidden items-center gap-1.5 text-xs font-medium text-slate-400 md:inline-flex">
        <span className="h-2 w-2 animate-pulse-dot rounded-full bg-slate-300" />
        {label}: checking…
      </span>
    )
  }
  return (
    <span
      title={message}
      className={`hidden items-center gap-1.5 text-xs font-semibold md:inline-flex ${
        ok ? 'text-emerald-600' : 'text-red-500'
      }`}
    >
      <span className={ok ? 'pulse-dot' : 'h-2 w-2 rounded-full bg-red-500'} />
      {label}: {ok ? 'Connected' : 'Not reachable'}
    </span>
  )
}

/** Two-stage boot screen: server, then database, with retry on 503. */
function BootScreen({
  stage,
  dbMessage,
  onRetry,
}: {
  stage: BootStage
  dbMessage?: string
  onRetry: () => void
}) {
  return (
    <div className="relative flex h-screen flex-col items-center justify-center gap-5">
      <div className="app-bg" />
      <div className="glass flex flex-col items-center gap-4 rounded-card px-10 py-8">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-500 text-white shadow-lg shadow-accent-500/30">
          <Sparkles size={22} />
        </div>
        <h1 className="text-lg font-extrabold tracking-tight text-slate-900">
          KPI Intelligence-to-Action Engine
        </h1>
        {stage === 'server' && (
          <p className="animate-pulse text-sm text-slate-500">Waking up the server…</p>
        )}
        {stage === 'database' && (
          <p className="animate-pulse text-sm text-slate-500">Connecting to database…</p>
        )}
        {stage === 'db_failed' && (
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm font-medium text-red-600">{dbMessage}</p>
            <Button onClick={onRetry}>Retry</Button>
          </div>
        )}
      </div>
    </div>
  )
}

function SidebarNav({
  page,
  setPage,
  onNavigate,
}: {
  page: PageName
  setPage: (p: PageName) => void
  onNavigate?: () => void
}) {
  return (
    <nav className="flex h-full flex-col gap-5 overflow-y-auto px-3 py-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.id}>
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
            {group.label}
          </p>
          <ul className="space-y-0.5">
            {NAV_ITEMS.filter((i) => i.group === group.id).map((item) => {
              const active = page === item.page
              return (
                <li key={item.label}>
                  <button
                    onClick={() => {
                      setPage(item.page)
                      onNavigate?.()
                    }}
                    className={`relative flex min-h-[44px] w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 ${
                      active
                        ? 'text-accent-700'
                        : 'text-slate-600 hover:bg-white/60 hover:text-slate-900'
                    }`}
                  >
                    {active && (
                      <motion.span
                        layoutId="nav-active-pill"
                        transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                        className="absolute inset-0 rounded-xl bg-accent-50 ring-1 ring-accent-100"
                      />
                    )}
                    <span className="relative z-10 shrink-0">{item.icon}</span>
                    <span className="relative z-10 truncate">{item.label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}

function AppShell() {
  const { user, ready, isGuest, logout, startGuest, exitGuest } = useAuth()
  const [bootStage, setBootStage] = useState<BootStage>('server')
  const [bootSlow, setBootSlow] = useState(false)
  const [dbMessage, setDbMessage] = useState<string | undefined>(undefined)
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking')
  const [dbStatus, setDbStatus] = useState<DbStatus>('checking')
  const [page, setPage] = useState<PageName>('Upload')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const bootTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const runBoot = useCallback(async () => {
    setBootStage('server')
    setBootSlow(false)
    if (bootTimer.current) clearTimeout(bootTimer.current)
    bootTimer.current = setTimeout(() => setBootSlow(true), 3000)
    try {
      await checkHealth()
    } catch {
      setBackendStatus('unreachable')
      return
    }
    setBackendStatus('connected')
    setBootStage('database')
    setBootSlow(false)
    if (bootTimer.current) clearTimeout(bootTimer.current)
    try {
      await checkDatabaseHealth()
      setDbStatus('connected')
      setDbMessage(undefined)
      setBootStage('ready')
    } catch (err) {
      setDbStatus('unreachable')
      setDbMessage(err instanceof Error ? err.message : 'Database unreachable')
      setBootStage('db_failed')
    }
  }, [])

  useEffect(() => {
    void runBoot()
    return () => {
      if (bootTimer.current) clearTimeout(bootTimer.current)
    }
  }, [runBoot])

  useEffect(() => {
    setSessionExpiredHandler(() => {
      void logout()
      setPage('Login')
    })
  }, [logout])

  // Route guard: once session restore settled, no user (and not guest) -> Login.
  const needsLogin = ready && !user && !isGuest && page !== 'Login' && page !== 'Register'
  useEffect(() => {
    if (needsLogin) {
      setPage('Login')
    }
  }, [needsLogin])

  if (bootStage !== 'ready') {
    return (
      <BootScreen
        stage={bootStage}
        dbMessage={bootSlow || bootStage !== 'server' ? dbMessage : undefined}
        onRetry={() => void runBoot()}
      />
    )
  }

  // Login/Register render without the app shell.
  if (page === 'Login' || page === 'Register') {
    return (
      <div className="relative min-h-screen">
        <div className="app-bg" />
        <div className="relative z-10">
          {page === 'Login' ? (
            <LoginPage
              onDone={() => setPage('Upload')}
              onGuest={() => {
                startGuest()
                setPage('Upload')
              }}
            />
          ) : (
            <RegisterPage onDone={() => setPage('Upload')} />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex h-screen flex-col overflow-hidden">
      <div className="app-bg" />

      {/* ---------- Topbar (glass, fixed) ---------- */}
      <header className="glass relative z-30 flex items-center justify-between gap-3 border-b border-white/60 px-4 py-3 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={() => setDrawerOpen(true)}
            className="rounded-xl p-2 text-slate-600 hover:bg-white/70 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-500 text-white shadow-md shadow-accent-500/30">
            <Sparkles size={18} />
          </div>
          <h1 className="hidden truncate text-base font-extrabold tracking-tight text-slate-900 md:block">
            KPI Intelligence-to-Action
          </h1>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2">
          {isGuest ? (
            <>
              <Badge tone="warning" title="Guest data lives in memory only and is never saved">
                Guest Mode — changes won&apos;t be saved
              </Badge>
              <Button variant="secondary" onClick={exitGuest}>
                Exit Guest
              </Button>
            </>
          ) : user ? (
            <>
              <span className="hidden items-center gap-1.5 text-xs font-medium text-slate-500 sm:inline-flex">
                <UserRound size={14} />
                {user.email}
              </span>
              <Button
                variant="ghost"
                onClick={() => {
                  void logout()
                }}
              >
                <LogOut size={15} />
                <span className="hidden sm:inline">Logout</span>
              </Button>
            </>
          ) : null}

          <StatusPill
            ok={backendStatus === 'connected'}
            checking={backendStatus === 'checking'}
            label="Backend"
          />
          <StatusPill
            ok={dbStatus === 'connected'}
            checking={dbStatus === 'checking'}
            label="Database"
            message={dbStatus === 'unreachable' ? dbMessage : undefined}
          />
        </div>
      </header>

      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* ---------- Sidebar (glass, desktop) ---------- */}
        <aside className="glass hidden w-60 shrink-0 border-r border-white/60 lg:block">
          <SidebarNav page={page} setPage={setPage} />
        </aside>

        {/* ---------- Mobile drawer ---------- */}
        <AnimatePresence>
          {drawerOpen && (
            <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
                onClick={() => setDrawerOpen(false)}
                className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm lg:hidden"
              />
              <motion.aside
                initial={{ x: -300 }}
                animate={{ x: 0 }}
                exit={{ x: -300 }}
                transition={{ type: 'spring', stiffness: 380, damping: 34 }}
                className="glass-strong fixed inset-y-0 left-0 z-50 w-72 lg:hidden"
              >
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="absolute right-3 top-3 rounded-xl p-2 text-slate-500 hover:bg-white/70"
                  aria-label="Close navigation"
                >
                  <X size={18} />
                </button>
                <SidebarNav
                  page={page}
                  setPage={setPage}
                  onNavigate={() => setDrawerOpen(false)}
                />
              </motion.aside>
            </>
          )}
        </AnimatePresence>

        {/* ---------- Main content with page transitions ---------- */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={page}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="mx-auto max-w-6xl"
            >
              {page === 'Upload' && <UploadPage />}
              {page === 'Profile' && <ProfilePage />}
              {page === 'Semantic Contract' && <SemanticContractPage />}
              {page === 'Data Quality' && <DataQualityPage />}
              {page === 'Canonical Model' && <CanonicalModelPage />}
              {page === 'KPIs' && <KpiDashboardPage />}
              {page === 'Anomalies' && <AnomalyPage />}
              {page === 'Drivers' && <DriversPage />}
              {page === 'Insights' && <InsightsPage />}
              {page === 'Recommendations' && <RecommendationsPage />}
              {page === 'Feedback' && <FeedbackPage />}
              {page === 'Telemetry' && <TelemetryPage />}
              {page === 'History' && <HistoryPage onNavigate={setPage} />}
              {page === 'Dashboard' && <DashboardPage />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
