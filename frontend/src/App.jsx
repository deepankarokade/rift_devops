import { useState, useEffect, useRef } from 'react'
import { supabase } from './supabase'
import './App.css'

// API Base URL - uses environment variable for production deployment
const API_URL = (import.meta.env.VITE_API_URL || window.location.origin).replace(/\/$/, '')

// ============== API Service ==============
const api = {
  // Get system status
  async getStatus() {
    try {
      const res = await fetch(`${API_URL}/api/status`)
      if (!res.ok) throw new Error('API unavailable')
      return res.json().catch(() => ({}))
    } catch {
      return { status: 'Autonomous Agent Active', active_nodes: 142, uptime: 99.99, region: 'US-EAST-1' }
    }
  },

  // Get dashboard stats
  async getStats() {
    try {
      const res = await fetch(`${API_URL}/api/stats`)
      if (!res.ok) throw new Error('API unavailable')
      return res.json().catch(() => ({}))
    } catch {
      return { active_deployments: 0, ai_confidence: 0, error_rate: 0, infra_cost: 0, success_rate: 100, total_runs: 0, completed_runs: 0, failed_runs: 0 }
    }
  },

  // Get recent actions
  async getActions() {
    try {
      const res = await fetch(`${API_URL}/api/actions`)
      if (!res.ok) throw new Error('API unavailable')
      return res.json().catch(() => [])
    } catch {
      return []
    }
  },

  // Get latency data
  async getLatency() {
    try {
      const res = await fetch(`${API_URL}/api/latency`)
      if (!res.ok) throw new Error('API unavailable')
      return res.json().catch(() => ({ regions: [] }))
    } catch {
      return { regions: [] }
    }
  },

  // Create and start a new pipeline run
  async createRun(repoUrl, branch = 'main', teamName = '', leaderName = '') {
    const res = await fetch(`${API_URL}/api/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        repo_url: repoUrl,
        branch,
        team_name: teamName,
        leader_name: leaderName
      })
    })
    if (!res.ok) {
      let message = 'Failed to start pipeline'
      try {
        const data = await res.json()
        message = data?.detail || data?.message || message
      } catch {
        // Ignore parse errors and use fallback message
      }
      throw new Error(message)
    }
    return res.json()
  },

  // Get all runs
  async getRuns() {
    try {
      const res = await fetch(`${API_URL}/api/runs`)
      if (!res.ok) throw new Error('API unavailable')
      return res.json().catch(() => [])
    } catch {
      return []
    }
  },

  // Get specific run
  async getRun(runId) {
    const res = await fetch(`${API_URL}/api/runs/${runId}`)
    return res.json()
  },

  // Get run status
  async getRunStatus(runId) {
    const res = await fetch(`${API_URL}/api/runs/${runId}/status`)
    if (!res.ok) throw new Error('Failed to fetch pipeline status')
    return res.json()
  }
}

// ============== WebSocket Hook ==============
function useWebSocket(runId) {
  const [updates, setUpdates] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!runId) return

    // Connect to WebSocket
    const wsProtocol = API_URL.startsWith('https') ? 'wss' : 'ws'
    const wsUrl = `${wsProtocol}://${API_URL.replace(/^https?:\/\//, '')}/ws`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      // Subscribe to run updates
      ws.send(JSON.stringify({ type: 'subscribe', run_id: runId }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setUpdates(prev => [...prev, data])
      } catch (e) {
        console.error('WebSocket message error:', e)
      }
    }

    ws.onclose = () => {
      setConnected(false)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      ws.close()
    }
  }, [runId])

  return { updates, connected }
}

// ============== Main App Component ==============
function App() {
  const [session, setSession] = useState(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // Dashboard state
  const [systemStatus, setSystemStatus] = useState(null)
  const [stats, setStats] = useState(null)
  const [recentActions, setRecentActions] = useState([])
  const [latencyData, setLatencyData] = useState([])
  const [activeView, setActiveView] = useState('overview')
  const [searchQuery, setSearchQuery] = useState('')

  // Pipeline state
  const [repoUrl, setRepoUrl] = useState('')
  const [teamName, setTeamName] = useState('')
  const [leaderName, setLeaderName] = useState('')
  const [currentRun, setCurrentRun] = useState(null)
  const [runProgress, setRunProgress] = useState(null)
  const [pipelineLogs, setPipelineLogs] = useState([])
  const [pipelineRuns, setPipelineRuns] = useState([])
  const [isRunning, setIsRunning] = useState(false)

  // WebSocket for real-time updates
  const { updates, connected } = useWebSocket(currentRun?.id)

  // Process WebSocket updates
  useEffect(() => {
    if (updates.length > 0) {
      const latest = updates[updates.length - 1]

      if (latest.type === 'pipeline_update') {
        setRunProgress({
          status: latest.status,
          progress: latest.progress,
          current_step: latest.current_step,
          iteration: latest.iteration,
          failures_detected: latest.failures_detected || [],
          fixes_applied: latest.fixes_applied || [],
        })
        setPipelineLogs(latest.logs || [])
      } else if (latest.type === 'pipeline_complete') {
        setIsRunning(false)
        if (Array.isArray(latest.logs) && latest.logs.length > 0) {
          setPipelineLogs(latest.logs)
        }
        setRunProgress({
          status: latest.status,
          ci_status: latest.ci_status,
          progress: latest.progress,
          current_step: latest.current_step,
          score: latest.score,
          total_time_seconds: latest.total_time_seconds,
          total_failures: latest.total_failures,
          total_fixes: latest.total_fixes,
        })
        setCurrentRun(prev => (prev ? {
          ...prev,
          status: latest.status,
          ci_status: latest.ci_status,
          total_time_seconds: latest.total_time_seconds,
          total_failures: latest.total_failures,
          total_fixes: latest.total_fixes
        } : prev))
      } else if (latest.type === 'pipeline_error') {
        setIsRunning(false)
        setRunProgress({
          status: 'FAILED',
          current_step: latest.error,
        })
      }
    }
  }, [updates])

  // Poll run status as a fallback to avoid UI stalls if WebSocket events are missed
  useEffect(() => {
    if (!currentRun?.id || !isRunning) return

    let cancelled = false

    const syncRunStatus = async () => {
      try {
        const status = await api.getRunStatus(currentRun.id)
        if (cancelled || !status) return

        setRunProgress(prev => ({
          ...prev,
          status: status.status || prev?.status,
          ci_status: status.ci_status || prev?.ci_status,
          progress: status.progress ?? prev?.progress ?? 0,
          current_step: status.current_step || prev?.current_step || 'Initializing pipeline...',
          iteration: status.iteration ?? prev?.iteration,
          failures_detected: status.failures_detected || prev?.failures_detected || [],
          fixes_applied: status.fixes_applied || prev?.fixes_applied || [],
        }))

        if (Array.isArray(status.logs) && status.logs.length > 0) {
          setPipelineLogs(status.logs)
        }

        if (status.status === 'COMPLETED' || status.status === 'FAILED') {
          setIsRunning(false)
          try {
            const finalRun = await api.getRun(currentRun.id)
            if (!cancelled && finalRun) {
              setCurrentRun(finalRun)
              setRunProgress(prev => ({
                ...prev,
                status: finalRun.status,
                ci_status: finalRun.ci_status,
                progress: finalRun.progress ?? 100,
                current_step: finalRun.current_step,
                score: finalRun.score,
                total_time_seconds: finalRun.total_time_seconds,
                total_failures: finalRun.total_failures,
                total_fixes: finalRun.total_fixes,
              }))
              setPipelineLogs(finalRun.logs || status.logs || [])
            }
          } catch {
            // Ignore final-run fetch failures; status endpoint already has terminal state
          }
        }
      } catch {
        // Keep polling; temporary network failures should not stop progress tracking
      }
    }

    syncRunStatus()
    const interval = setInterval(syncRunStatus, 3000)

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [currentRun?.id, isRunning])

  // Auth check
  useEffect(() => {
    // Check if Supabase is configured
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
    const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

    // If Supabase is not configured, run in demo mode (bypass auth)
    if (!supabaseUrl || !supabaseAnonKey || supabaseUrl === 'https://example.supabase.co') {
      setSession({ user: { email: 'demo@example.com' } })
      return
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setSession(session)
      } else {
        // No session, try to use demo mode
        setSession({ user: { email: 'demo@example.com' } })
      }
    }).catch(() => {
      // If auth fails, use demo mode
      setSession({ user: { email: 'demo@example.com' } })
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setSession(session)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  // Fetch dashboard data
  useEffect(() => {
    if (session) {
      fetchDashboardData()
      const interval = setInterval(fetchDashboardData, 5000)
      return () => clearInterval(interval)
    }
  }, [session])

  const fetchDashboardData = async () => {
    try {
      const [statusData, statsData, actionsData, latency, runsData] = await Promise.all([
        api.getStatus(),
        api.getStats(),
        api.getActions(),
        api.getLatency(),
        api.getRuns()
      ])

      setSystemStatus(statusData)
      setStats(statsData)
      setRecentActions(actionsData)
      setLatencyData(latency.regions || [])
      setPipelineRuns(runsData || [])
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err)
      // Use mock data
      setSystemStatus({ status: 'Autonomous Agent Active', active_nodes: 142, uptime: 99.99, region: 'US-EAST-1' })
      setStats({ active_deployments: 12, ai_confidence: 98.4, error_rate: 0.02, infra_cost: 2450 })
      setLatencyData([
        { name: 'US-EAST-1', latency: 12, percentage: 85 },
        { name: 'EU-WEST-1', latency: 42, percentage: 45 },
        { name: 'AP-SOUTH-1', latency: 68, percentage: 30 }
      ])
      setRecentActions([
        { id: '1', type: 'Kubernetes Auto-scaled', description: 'Traffic spike detected in US-West cluster.', timestamp: new Date().toISOString(), status: 'success' },
        { id: '2', type: 'Security Vulnerability Patched', description: 'Identified CVE-2024-5120 in base image.', timestamp: new Date().toISOString(), status: 'success' },
        { id: '3', type: 'Node Health Remediation', description: 'Node i-0a2f1b unresponsive. Restarted.', timestamp: new Date().toISOString(), status: 'success' }
      ])
      setPipelineRuns([])
    }
  }

  // Auth handlers
  const handleSignUp = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) setError(error.message)
    else setMessage('Check your email for verification!')
    setLoading(false)
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    setLoading(false)
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin }
    })
    if (error) setError(error.message)
    setLoading(false)
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  const normalizeBranchSegment = (value) =>
    value
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')

  const buildBranchName = (team, leader) => {
    const teamSegment = normalizeBranchSegment(team)
    const leaderSegment = normalizeBranchSegment(leader)
    if (teamSegment && leaderSegment) return `${teamSegment}_${leaderSegment}_AI_Fix`
    return 'TEAM_LEADER_AI_Fix'
  }

  const formatTotalTime = (seconds = 0) => {
    const value = Number(seconds || 0)
    if (value < 60) return `${value}s`
    const mins = Math.floor(value / 60)
    const secs = value % 60
    return `${mins}m ${secs}s`
  }

  // Pipeline handlers
  const handleStartPipeline = async (e) => {
    e.preventDefault()
    if (!repoUrl || !teamName || !leaderName) return

    setLoading(true)
    setError('')
    try {
      const branchName = buildBranchName(teamName, leaderName)
      const run = await api.createRun(repoUrl, branchName, teamName, leaderName)
      setCurrentRun(run)
      setIsRunning(true)
      setPipelineLogs(run.logs || [])
      setRunProgress({
        status: run.status,
        ci_status: run.ci_status || 'UNKNOWN',
        progress: 0,
        current_step: run.current_step
      })
    } catch (err) {
      setError('Failed to start pipeline: ' + err.message)
    }
    setLoading(false)
  }

  const formatTimeAgo = (date) => {
    const diff = Date.now() - new Date(date)
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (minutes < 60) return `${minutes} min ago`
    if (hours < 24) return `${hours} hours ago`
    return `${Math.floor(hours / 24)} days ago`
  }

  const parseTerminalLogLine = (line) => {
    const raw = String(line ?? '')
    const timestampMatch = raw.match(/^\[(.*?)\]\s*/)
    const timestamp = timestampMatch ? `[${timestampMatch[1]}]` : `[${new Date().toLocaleTimeString()}]`
    const rest = timestampMatch ? raw.slice(timestampMatch[0].length) : raw

    const levelMatch = rest.match(/^\[(SUCCESS|INFO|NEURAL|ERROR)\]\s*/i)
    const level = levelMatch ? levelMatch[1].toUpperCase() : 'INFO'
    const message = levelMatch ? rest.slice(levelMatch[0].length) : rest

    return { timestamp, level, message: message || raw }
  }

  const createdBranch = buildBranchName(teamName, leaderName)
  const terminalRunStatus = (runProgress?.status || currentRun?.status || '').toUpperCase()
  const runFailureMessage = terminalRunStatus === 'FAILED'
    ? (runProgress?.current_step || currentRun?.current_step || 'Analysis failed. Check logs for details.')
    : ''
  const summary = currentRun ? {
    repoUrl: currentRun.repo_url || repoUrl,
    teamName: currentRun.team_name || teamName,
    leaderName: currentRun.leader_name || leaderName,
    branch: currentRun.branch || createdBranch,
    totalFailures: runProgress?.total_failures ?? currentRun.total_failures ?? 0,
    totalFixes: runProgress?.total_fixes ?? currentRun.total_fixes ?? 0,
    totalTimeSeconds: runProgress?.total_time_seconds ?? currentRun.total_time_seconds ?? 0,
    ciStatus: (runProgress?.ci_status || currentRun.ci_status || (terminalRunStatus === 'COMPLETED' ? 'PASSED' : terminalRunStatus) || 'UNKNOWN').toUpperCase(),
    finalBadge: terminalRunStatus === 'FAILED' ? 'FAILED' : 'PASSED'
  } : null

  // Login Screen
  if (!session) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="logo-container">
              <span className="material-symbols-outlined logo-icon">bolt</span>
            </div>
            <h1>NEURAL OPS</h1>
            <p className="login-subtitle">DevOps AI Command Center</p>
          </div>

          {message && <div className="message success">{message}</div>}
          {error && <div className="message error">{error}</div>}

          <form onSubmit={handleLogin}>
            <div className="form-group">
              <input type="email" placeholder="Your email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="form-group">
              <input type="password" placeholder="Your password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <div className="button-group">
              <button type="submit" disabled={loading} className="btn-primary">
                {loading ? 'Loading...' : 'Sign In'}
              </button>
              <button onClick={handleSignUp} disabled={loading} type="button" className="btn-secondary">
                Sign Up
              </button>
            </div>
          </form>

          <div className="divider"><span>or</span></div>

          <button onClick={handleGoogleLogin} disabled={loading} className="btn-google">
            <span className="material-symbols-outlined">account_circle</span>
            Sign in with Google
          </button>
        </div>
      </div>
    )
  }

  // Dashboard
  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-icon-container">
            <span className="material-symbols-outlined">bolt</span>
          </div>
          <span className="logo-text">NEURAL OPS</span>
        </div>

        <nav className="sidebar-nav">
          <a className={`nav-item ${activeView === 'overview' ? 'active' : ''}`} onClick={() => setActiveView('overview')}>
            <span className="material-symbols-outlined">grid_view</span>
            <span>Overview</span>
          </a>
          <a className={`nav-item ${activeView === 'pipelines' ? 'active' : ''}`} onClick={() => setActiveView('pipelines')}>
            <span className="material-symbols-outlined">account_tree</span>
            <span>Pipelines</span>
          </a>
          <a className={`nav-item ${activeView === 'health' ? 'active' : ''}`} onClick={() => setActiveView('health')}>
            <span className="material-symbols-outlined">analytics</span>
            <span>Agent Health</span>
          </a>
          <a className={`nav-item ${activeView === 'infra' ? 'active' : ''}`} onClick={() => setActiveView('infra')}>
            <span className="material-symbols-outlined">database</span>
            <span>Infrastructure</span>
          </a>
          <a className={`nav-item ${activeView === 'settings' ? 'active' : ''}`} onClick={() => setActiveView('settings')}>
            <span className="material-symbols-outlined">settings</span>
            <span>Settings</span>
          </a>
        </nav>

        <div className="sidebar-footer">
          <div className="node-region glass-card">
            <p className="label">NODE REGION</p>
            <div className="region-info">
              <div className="pulse-dot"></div>
              <span>{systemStatus?.region || 'US-EAST-1'}</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Header */}
        <header className="header glass-card">
          <div className="search-container">
            <span className="material-symbols-outlined search-icon">search</span>
            <input type="text" placeholder="Search clusters, logs, or neural tasks..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>

          <div className="header-right">
            <div className="status-badge">
              <span className="pulse-dot"></span>
              <span>System Online</span>
            </div>

            <div className="user-section">
              <div className="user-info">
                <p className="user-name">{session.user.email?.split('@')[0] || 'User'}</p>
                <p className="user-role">Lead DevOps</p>
              </div>
              <div className="user-avatar gradient-border">
                <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuCUFEICIRiQt-xfmhFErOalZfpNEIsrsLvkUVVzvojPooI94j1iwt3fbPro4x3lzHtjVmTx-8bH2egXXQJeD01NW9d9gD18Ypww0bM92ZjS2VeCN_8JUatWCCDUBM0-ALui4CJOpOSZh5Y8ahE2xyTgHATsd4hSfNjhZ24LrZWEBO2f34SuWdYGcsU_mUlz_S9sW76bejnH30iCGjf8tuKr8nMw6ePe1avfTaE7sNV9QNsAhAdrRaR8byOoxb-xF-r-QDtkzT51clg" alt="User" />
              </div>
              <button onClick={handleLogout} className="logout-btn">
                <span className="material-symbols-outlined">logout</span>
              </button>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="dashboard-content">
          {/* Hero Section */}
          <section className="gradient-border neon-shadow-blue">
            <div className="hero-card">
              <div className="hero-bg-effect"></div>
              <div className="hero-content">
                <div className="hero-text">
                  <div className="hero-title">
                    <span className="material-symbols-outlined hero-icon">verified_user</span>
                    <h2>Autonomous Agent Active</h2>
                  </div>
                  <p className="hero-description">
                    Neural engine is currently monitoring <span className="highlight-primary">{systemStatus?.active_nodes || 142} nodes</span> across 3 global regions. Uptime remains optimal at <span className="highlight-white">{systemStatus?.uptime || 99.99}%</span>.
                  </p>
                  <div className="hero-buttons">
                    <button className="btn-primary" onClick={handleStartPipeline} disabled={loading || isRunning || !repoUrl || !teamName || !leaderName}>
                      <span className="material-symbols-outlined">play_arrow</span>
                      {isRunning ? 'Analyzing...' : 'Analyze Repository'}
                    </button>
                    <button className="btn-outline">
                      <span className="material-symbols-outlined">visibility</span>
                      Cluster Map
                    </button>
                  </div>
                </div>
                <div className="hero-stats glass-card">
                  <div className="uptime-display">
                    <div className="uptime-value">{systemStatus?.uptime || 99.9}<span className="uptime-unit">%</span></div>
                    <div className="uptime-label">REAL-TIME UPTIME</div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="run-input-section glass-card">
            <div className="run-input-header">
              <h3>Input Section</h3>
              <span className="pipeline-branch-preview">{createdBranch}</span>
            </div>
            <form className="run-input-form" onSubmit={handleStartPipeline}>
              <div className="form-group">
                <label>GitHub Repository URL</label>
                <input
                  type="text"
                  placeholder="https://github.com/deepankarokade/rift-agent-test-repo.git"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Team Name</label>
                <input
                  type="text"
                  placeholder="RIFT ORGANISERS"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Team Leader Name</label>
                <input
                  type="text"
                  placeholder="Saiyam Kumar"
                  value={leaderName}
                  onChange={(e) => setLeaderName(e.target.value)}
                  required
                />
              </div>
              <div className="run-input-actions">
                <button type="submit" className="btn-primary" disabled={loading || isRunning}>
                  {isRunning ? 'Running Agent...' : 'Analyze Repository'}
                </button>
                {(loading || isRunning) && <span className="run-loading-indicator">Agent is running...</span>}
              </div>
            </form>
          </section>

          {/* Stats Grid */}
          <section className="stats-grid">
            <div className="stat-card glass-card">
              <div className="stat-header">
                <div className="stat-icon primary"><span className="material-symbols-outlined">rocket_launch</span></div>
                <div className="pulse-dot"></div>
              </div>
              <h3 className="stat-label">Active Deployments</h3>
              <div className="stat-value">{stats?.active_deployments || 12} <span className="stat-change">+2 Today</span></div>
            </div>

            <div className="stat-card glass-card">
              <div className="stat-header">
                <div className="stat-icon secondary"><span className="material-symbols-outlined">psychology</span></div>
                <span className="stat-badge secondary">+0.5%</span>
              </div>
              <h3 className="stat-label">AI Confidence</h3>
              <div className="stat-value confidence">
                <div className="circular-progress">
                  <svg viewBox="0 0 36 36">
                    <circle className="circular-bg" cx="18" cy="18" r="16" />
                    <circle className="circular-progress-bar" cx="18" cy="18" r="16" strokeDasharray={`${stats?.ai_confidence || 98.4}, 100`} />
                  </svg>
                  <span className="progress-text">{stats?.ai_confidence || 98}%</span>
                </div>
                <div className="confidence-value">{stats?.ai_confidence || 98.4}<span className="unit secondary">%</span></div>
              </div>
            </div>

            <div className="stat-card glass-card">
              <div className="stat-header">
                <div className="stat-icon success"><span className="material-symbols-outlined">analytics</span></div>
                <span className="stat-badge success">-12%</span>
              </div>
              <h3 className="stat-label">Error Rates</h3>
              <div className="stat-value">{stats?.error_rate || 0.02}<span className="unit success">%</span></div>
              <div className="progress-bar"><div className="progress-fill success"></div></div>
            </div>

            <div className="stat-card glass-card">
              <div className="stat-header">
                <div className="stat-icon primary"><span className="material-symbols-outlined">payments</span></div>
                <span className="stat-badge primary">Optimal</span>
              </div>
              <h3 className="stat-label">Infra Monthly Cost</h3>
              <div className="stat-value">${stats?.infra_cost || 2450} <span className="stat-sub">est.</span></div>
            </div>
          </section>

          {/* Pipeline Progress (when running) */}
          {isRunning && runProgress && (
            <section className="pipeline-progress">
              <div className="progress-card glass-card">
                <div className="progress-header">
                  <h3>
                    <span className="material-symbols-outlined">autorenew</span>
                    Pipeline Running
                  </h3>
                  <div className="progress-status">
                    <span className="pulse-dot"></span>
                    {runProgress.status}
                  </div>
                </div>

                <div className="progress-bar-container">
                  <div className="progress-bar-fill" style={{ width: `${runProgress.progress}%` }}></div>
                </div>

                <div className="progress-info">
                  <span className="progress-step">{runProgress.current_step}</span>
                  <span className="progress-percent">{Math.round(runProgress.progress)}%</span>
                </div>

                {runProgress.iteration && (
                  <div className="iteration-info">
                    <span>Iteration: {runProgress.iteration}</span>
                  </div>
                )}

                {runProgress.failures_detected?.length > 0 && (
                  <div className="failures-detected">
                    <h4>Failures Detected ({runProgress.failures_detected.length})</h4>
                    {runProgress.failures_detected.map((f, i) => (
                      <div key={i} className="failure-item">
                        <span className="file">{f.file}:{f.line}</span>
                        <span className="type">{f.type}</span>
                        <span className="message">{f.message}</span>
                      </div>
                    ))}
                  </div>
                )}

                {runProgress.fixes_applied?.length > 0 && (
                  <div className="fixes-applied">
                    <h4>Fixes Applied ({runProgress.fixes_applied.length})</h4>
                    {runProgress.fixes_applied.map((f, i) => (
                      <div key={i} className="fix-item">
                        <span className="file">{f.file}:{f.line}</span>
                        <span className="type success">{f.type}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Run Summary Card */}
          {summary && !isRunning && (terminalRunStatus === 'COMPLETED' || terminalRunStatus === 'FAILED') && (
            <section className="pipeline-results">
              <div className="results-card glass-card">
                <div className="results-header run-summary-header">
                  <h3>Run Summary</h3>
                  <span className={`summary-status-badge ${summary.finalBadge === 'PASSED' ? 'passed' : 'failed'}`}>
                    {summary.finalBadge}
                  </span>
                </div>

                <div className="run-summary-grid">
                  <div className="result-item">
                    <span className="result-label">Repository URL</span>
                    <span className="result-value summary-text">{summary.repoUrl || '-'}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Team Name</span>
                    <span className="result-value summary-text">{summary.teamName || '-'}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Team Leader</span>
                    <span className="result-value summary-text">{summary.leaderName || '-'}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Branch Created</span>
                    <span className="result-value summary-text">{summary.branch || '-'}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Total Failures</span>
                    <span className="result-value">{summary.totalFailures}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Total Fixes</span>
                    <span className="result-value success">{summary.totalFixes}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Total Time Taken</span>
                    <span className="result-value">{formatTotalTime(summary.totalTimeSeconds)}</span>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Pipeline Failure Details */}
          {!isRunning && runFailureMessage && (
            <section className="pipeline-failure">
              <div className="failure-card glass-card">
                <div className="failure-header">
                  <span className="material-symbols-outlined">error</span>
                  <h3>Analysis Failed</h3>
                </div>
                <p className="failure-text">{runFailureMessage}</p>
                <p className="failure-meta">
                  Status: {terminalRunStatus} | CI: {(runProgress?.ci_status || currentRun?.ci_status || 'UNKNOWN').toUpperCase()}
                </p>
              </div>
            </section>
          )}

          {/* Main Content Grid - Only show for overview */}
          {activeView === 'overview' && (
            <section className="content-grid">
              {/* Actions Section */}
              <div className="actions-section">
                <div className="section-header">
                  <h3><span className="material-symbols-outlined">dynamic_feed</span>Recent AI Actions</h3>
                  <a href="#" className="view-all">View All</a>
                </div>

                {recentActions.map((action) => (
                  <div key={action.id} className={`action-card ${action.status === 'success' ? 'primary' : action.status === 'error' ? 'secondary' : 'success'}`}>
                    <div className="action-icon">
                      {action.type.includes('Kubernetes') && <span className="material-symbols-outlined">compress</span>}
                      {action.type.includes('Security') && <span className="material-symbols-outlined">security</span>}
                      {action.type.includes('Node') && <span className="material-symbols-outlined">dns</span>}
                      {!action.type.includes('Kubernetes') && !action.type.includes('Security') && !action.type.includes('Node') && <span className="material-symbols-outlined">auto_fix_high</span>}
                    </div>
                    <div className="action-content">
                      <div className="action-header">
                        <h4>{action.type}</h4>
                        <span className="action-time">{formatTimeAgo(action.timestamp)}</span>
                      </div>
                      <p className="action-description">"{action.description}"</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Right Column */}
              <div className="right-column">
                <div className="latency-card glass-card">
                  <h3>Latency Distribution</h3>
                  <div className="latency-list">
                    {latencyData.map((region) => (
                      <div key={region.name} className="latency-item">
                        <div className="latency-header">
                          <span className="region-name">{region.name}</span>
                          <span className={`latency-value ${region.name.includes('WEST') ? 'secondary' : 'primary'}`}>{region.latency}ms</span>
                        </div>
                        <div className="latency-bar">
                          <div className={`latency-fill ${region.name.includes('WEST') ? 'secondary' : 'primary'}`} style={{ width: `${region.percentage}%` }}></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="scan-card glass-card">
                  <h3>Neural Scan</h3>
                  <p className="scan-status">Scanning for infrastructure drifts...</p>
                  <div className="scan-animation">
                    <div className="scanner">
                      <div className="scanner-ring"></div>
                      <span className="material-symbols-outlined">hub</span>
                    </div>
                  </div>
                  <button className="btn-outline full-width" onClick={handleStartPipeline} disabled={loading || isRunning || !repoUrl || !teamName || !leaderName}>Run Scan</button>
                </div>
              </div>
            </section>
          )}

          {/* Pipelines View */}
          {activeView === 'pipelines' && (
            <section className="pipelines-view">
              <div className="view-header">
                <h2><span className="material-symbols-outlined">account_tree</span>Pipeline Runs</h2>
                <button className="btn-primary" onClick={handleStartPipeline} disabled={loading || isRunning || !repoUrl || !teamName || !leaderName}>
                  <span className="material-symbols-outlined">add</span>
                  Analyze Repository
                </button>
              </div>
              <div className="pipeline-list glass-card">
                {pipelineRuns.length === 0 ? (
                  <div className="empty-state">
                    <span className="material-symbols-outlined">inbox</span>
                    <p>No pipeline runs yet. Start your first pipeline!</p>
                  </div>
                ) : (
                  pipelineRuns.map((run) => (
                    <div key={run.id} className="pipeline-item">
                      <div className="pipeline-info">
                        <span className="pipeline-repo">{run.repo_url}</span>
                        <span className="pipeline-branch">{run.branch}</span>
                      </div>
                      <div className={`pipeline-status ${run.status.toLowerCase()}`}>
                        {run.status}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>
          )}

          {/* Health View */}
          {activeView === 'health' && (
            <section className="health-view">
              <div className="view-header">
                <h2><span className="material-symbols-outlined">analytics</span>Agent Health</h2>
              </div>
              <div className="health-grid">
                <div className="health-card glass-card">
                  <h3>System Status</h3>
                  <div className="health-status healthy">
                    <span className="material-symbols-outlined">check_circle</span>
                    <span>All Systems Operational</span>
                  </div>
                </div>
                <div className="health-card glass-card">
                  <h3>Active Agents</h3>
                  <div className="health-stat">{systemStatus?.active_nodes || 142}</div>
                </div>
                <div className="health-card glass-card">
                  <h3>Uptime</h3>
                  <div className="health-stat">{systemStatus?.uptime || 99.99}%</div>
                </div>
              </div>
            </section>
          )}

          {/* Infrastructure View */}
          {activeView === 'infra' && (
            <section className="infra-view">
              <div className="view-header">
                <h2><span className="material-symbols-outlined">database</span>Infrastructure</h2>
              </div>
              <div className="infra-grid">
                <div className="infra-card glass-card">
                  <h3>Region</h3>
                  <p>{systemStatus?.region || 'US-EAST-1'}</p>
                </div>
                <div className="infra-card glass-card">
                  <h3>Active Deployments</h3>
                  <p>{stats?.active_deployments || 0}</p>
                </div>
                <div className="infra-card glass-card">
                  <h3>Total Runs</h3>
                  <p>{stats?.total_runs || 0}</p>
                </div>
              </div>
            </section>
          )}

          {/* Settings View */}
          {activeView === 'settings' && (
            <section className="settings-view">
              <div className="view-header">
                <h2><span className="material-symbols-outlined">settings</span>Settings</h2>
              </div>
              <div className="settings-card glass-card">
                <h3>API Configuration</h3>
                <div className="setting-item">
                  <label>API URL</label>
                  <input type="text" value={API_URL} readOnly />
                </div>
                <div className="setting-item">
                  <label>WebSocket</label>
                  <input type="text" value={`${API_URL.replace(/^http/, 'ws')}/ws`} readOnly />
                </div>
              </div>
            </section>
          )}
        </div>

        {/* Terminal */}
        <footer className="terminal">
          <div className="terminal-header">
            <div className="terminal-info">
              <span className="material-symbols-outlined">terminal</span>
              <span>Neural Console v4.2.0</span>
              <span className="connection-status">
                <span className="dot success"></span>
                {connected ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>
            <div className="terminal-actions">
              <button><span className="material-symbols-outlined">close_fullscreen</span></button>
              <button><span className="material-symbols-outlined">settings_ethernet</span></button>
            </div>
          </div>
          <div className="terminal-content">
            {(pipelineLogs.length > 0 ? pipelineLogs : [
              '[14:22:01] [INFO] AI Agent initializing neural pattern matching',
              '[14:22:05] [INFO] Monitoring ingress traffic peaks...',
              '[14:23:12] [SUCCESS] Node synchronization complete',
              '[14:24:45] [NEURAL] Predictive model suggests 15% increase',
              '[14:25:01] [INFO] Pre-warming pods...'
            ]).map((log, i) => (
              <div key={i} className="log-line">
                {(() => {
                  const parsed = parseTerminalLogLine(log)
                  const levelClass =
                    parsed.level === 'SUCCESS' ? 'success' :
                      parsed.level === 'NEURAL' ? 'neural' :
                        parsed.level === 'ERROR' ? 'error' : 'info'
                  return (
                    <>
                      <span className="log-time">{parsed.timestamp}</span>
                      <span className={`log-level ${levelClass}`}>[{parsed.level}]</span>
                      <span>{parsed.message}</span>
                    </>
                  )
                })()}
              </div>
            ))}
            <div className="log-line cursor-line">
              <span className="log-time">[{new Date().toLocaleTimeString()}]</span>
              <span className="cursor pulse">_</span>
            </div>
          </div>
        </footer>
      </main>

      {/* Map Background */}
      <div className="map-background">
        <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuDZWV8kV-Ro00q49u2TiSzh8oiFh8Y2mvSAlLsyD0N_vKNhZ-JPzSNMJsyxrv02XalFf0XfV5iDJ0UvR-kazN8W12LJO2u2Dgadg1Tm3ZAcltB2CBOUVGbvLE-XfpvidbPEOh6ipDDJ-BD2cDGU7R3lvKfVEk6TRzwWaQJpmDDDp5JpxfPhXWJt-qk06nwRDOtICiD69byNzSmO-FCMAnioSrCngxY9_-LqFxU8sDv0eZ8aBcEjUX_WdRSwqdV_bcZruesINU3JzSw" alt="" />
      </div>
    </div>
  )
}

export default App
