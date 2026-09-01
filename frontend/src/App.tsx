import { useCallback, useEffect, useRef, useState } from 'react'
import { checkHealth, checkDatabaseHealth } from './api/health'
import { listPersonas } from './api/persona'
import { setSessionExpiredHandler } from './api/authClient'
import { PersonaContext } from './context/PersonaContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import type { Persona } from './types'
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
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

type BackendStatus = 'checking' | 'connected' | 'unreachable'
type DbStatus = 'checking' | 'connected' | 'unreachable'
type BootStage = 'server' | 'database' | 'ready' | 'db_failed'
type PageName =
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
  | 'Dashboard'
  | 'Login'
  | 'Register'

const NAV_ITEMS: { label: string; enabled: boolean; page?: PageName }[] = [
  { label: 'Upload', enabled: true, page: 'Upload' },
  { label: 'Profile', enabled: true, page: 'Profile' },
  { label: 'Semantic Contract', enabled: true, page: 'Semantic Contract' },
  { label: 'Data Quality', enabled: true, page: 'Data Quality' },
  { label: 'Canonical Model', enabled: true, page: 'Canonical Model' },
  { label: 'KPIs', enabled: true, page: 'KPIs' },
  { label: 'Anomalies', enabled: true, page: 'Anomalies' },
  { label: 'Drivers', enabled: true, page: 'Drivers' },
  { label: 'Insights', enabled: true, page: 'Insights' },
  { label: 'Recommendations', enabled: true, page: 'Recommendations' },
  { label: 'Feedback', enabled: true, page: 'Feedback' },
  { label: 'Telemetry', enabled: true, page: 'Telemetry' },
  { label: 'Dashboard', enabled: true, page: 'Dashboard' },
]

function BackendBadge({ status }: { status: BackendStatus }) {
  if (status === 'checking') {
    return <span className="text-sm text-gray-400">Backend: Checking…</span>
  }
  if (status === 'connected') {
    return <span className="text-sm font-medium text-green-600">Backend: Connected</span>
  }
  return <span className="text-sm font-medium text-red-600">Backend: Not reachable</span>
}

function DatabaseBadge({ status, message }: { status: DbStatus; message?: string }) {
  if (status === 'checking') {
    return <span className="text-sm text-gray-400">Database: Checking…</span>
  }
  if (status === 'connected') {
    return (
      <span className="text-sm font-medium text-green-600">Database: Connected (Supabase)</span>
    )
  }
  return (
    <span
      className="text-sm font-medium text-red-600"
      title={message ?? 'Database temporarily unavailable'}
    >
      Database: Not reachable{message ? ` — ${message}` : ''}
    </span>
  )
}

function PersonaSwitcher({
  personas,
  persona,
  setPersona,
}: {
  personas: Persona[]
  persona: Persona | null
  setPersona: (p: Persona | null) => void
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-500">
      <span className="font-medium text-gray-600">View as:</span>
      <select
        value={persona?.persona_id ?? ''}
        onChange={(e) => {
          const selected = personas.find((p) => p.persona_id === e.target.value) ?? null
          setPersona(selected)
        }}
        className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none"
      >
        <option value="">Unrestricted</option>
        {personas.map((p) => (
          <option key={p.persona_id} value={p.persona_id}>
            {p.name}
          </option>
        ))}
      </select>
      {persona && (
        <span
          className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
          title={persona.access.description ?? ''}
        >
          {persona.name}
        </span>
      )}
    </label>
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
    <div className="flex h-screen flex-col items-center justify-center gap-4 bg-gray-50">
      <h1 className="text-lg font-semibold text-gray-900">KPI Intelligence-to-Action Engine</h1>
      {stage === 'server' && (
        <p className="animate-pulse text-sm text-gray-500">Waking up the server…</p>
      )}
      {stage === 'database' && (
        <p className="animate-pulse text-sm text-gray-500">Connecting to database…</p>
      )}
      {stage === 'db_failed' && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm font-medium text-red-600">{dbMessage}</p>
          <button
            onClick={onRetry}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Retry
          </button>
        </div>
      )}
    </div>
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
  const { user, ready, logout } = useAuth()
  const [bootStage, setBootStage] = useState<BootStage>('server')
  const [bootSlow, setBootSlow] = useState(false)
  const [dbMessage, setDbMessage] = useState<string | undefined>(undefined)
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking')
  const [dbStatus, setDbStatus] = useState<DbStatus>('checking')
  const [page, setPage] = useState<PageName>('Dashboard')
  const [personas, setPersonas] = useState<Persona[]>([])
  const [persona, setPersona] = useState<Persona | null>(null)
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
      return // stay on "Waking up the server…" until it responds
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

  // Two-stage boot on first load.
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

  // Load personas once the app content is shown.
  useEffect(() => {
    if (bootStage === 'ready') {
      listPersonas()
        .then(setPersonas)
        .catch(() => setPersonas([]))
    }
  }, [bootStage])

  // Route guard: once session restore settled, no user -> Login page.
  const needsLogin = ready && !user && page !== 'Login' && page !== 'Register'
  useEffect(() => {
    if (needsLogin) {
      setPage('Login')
    }
  }, [needsLogin])

  // Two-stage boot gate: nothing renders until server + database are up.
  if (bootStage !== 'ready') {
    return (
      <BootScreen
        stage={bootStage}
        dbMessage={bootSlow || bootStage !== 'server' ? dbMessage : undefined}
        onRetry={() => void runBoot()}
      />
    )
  }

  return (
    <PersonaContext.Provider value={{ persona, personas, setPersona }}>
      <div className="flex h-screen flex-col bg-gray-50">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
          <h1 className="text-lg font-semibold text-gray-900">
            KPI Intelligence-to-Action Engine
          </h1>
          <div className="flex items-center gap-6">
            <PersonaSwitcher personas={personas} persona={persona} setPersona={setPersona} />
            {user ? (
              <>
                <span className="text-sm font-medium text-gray-700">
                  Logged in as {user.email}
                </span>
                <button
                  onClick={() => {
                    void logout()
                  }}
                  className="rounded-md border border-gray-300 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Logout
                </button>
              </>
            ) : (
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setPage('Login')}
                  className="text-sm font-medium text-indigo-600 hover:underline"
                >
                  Login
                </button>
                <button
                  onClick={() => setPage('Register')}
                  className="text-sm font-medium text-indigo-600 hover:underline"
                >
                  Register
                </button>
              </div>
            )}
            <BackendBadge status={backendStatus} />
            <DatabaseBadge status={dbStatus} message={dbMessage} />
          </div>
        </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-60 shrink-0 border-r border-gray-200 bg-white py-4">
          <nav>
            <ul>
              {NAV_ITEMS.map((item) => (
                <li key={item.label}>
                  {item.enabled ? (
                    <button
                      onClick={() => setPage(item.page!)}
                      className={`block w-full px-6 py-2 text-left text-sm ${
                        page === item.page
                          ? 'bg-indigo-50 font-medium text-indigo-700'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {item.label}
                    </button>
                  ) : (
                    <span
                      className="block cursor-not-allowed select-none px-6 py-2 text-sm text-gray-400"
                      aria-disabled="true"
                      title="Coming in a later phase"
                    >
                      {item.label}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
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
          {page === 'Dashboard' && <DashboardPage />}
          {page === 'Login' && <LoginPage onDone={() => setPage('Dashboard')} />}
          {page === 'Register' && <RegisterPage onDone={() => setPage('Dashboard')} />}
        </main>
      </div>
      </div>
    </PersonaContext.Provider>
  )
}
