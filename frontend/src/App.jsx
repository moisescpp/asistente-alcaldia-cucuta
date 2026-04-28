import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
const DEFAULT_QUESTION = 'Quiero informacion sobre impuesto predial'
const FALLBACK_QUICK_QUESTIONS = [
  'Consulta por impuesto predial',
  'Consulta por generacion de paz y salvo',
  'Consulta por devolucion de pagos en exceso',
  'Consulta por industria y comercio',
]
const ADMIN_TOKEN_STORAGE_KEY = 'admin-access-token'
const ADMIN_SESSION_EXPIRES_AT_STORAGE_KEY = 'admin-session-expires-at'
const ADMIN_WORKSPACE_STORAGE_KEY = 'admin-workspace-state'
const EMPTY_FORM = {
  nombre: '',
  slug: '',
  descripcion: '',
  requisitos: '',
  costo: '',
  horario: '',
  dependencia: '',
  fuente_url: '',
}

const inputClassName =
  'w-full rounded-3xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-800 outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100'
const EMPTY_ADMIN_ERRORS = {
  nombre: '',
  slug: '',
  dependencia: '',
  descripcion: '',
  requisitos: '',
  fuente_url: '',
}
const FRONTEND_GENERIC_DESCRIPTION_PATTERNS = [
  'consulta orientativa',
  'tramite de prueba',
  'sin descripcion',
  'no hay descripcion',
]
const EMPTY_ADMIN_WORKSPACE = {
  formData: EMPTY_FORM,
  editingId: null,
  slugTouched: false,
  adminSearch: '',
  adminDependency: 'todas',
}

function App() {
  const storedAdminWorkspace = readStoredAdminWorkspace()
  const storedAdminSessionExpiresAt = readStoredAdminSessionExpiresAt()
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') return 'light'
    return window.localStorage.getItem('app-theme') ?? 'light'
  })
  const [view, setView] = useState('ciudadania')
  const [tramites, setTramites] = useState([])
  const [loadingTramites, setLoadingTramites] = useState(true)
  const [tramitesError, setTramitesError] = useState('')
  const [consultaLogs, setConsultaLogs] = useState([])
  const [loadingConsultaLogs, setLoadingConsultaLogs] = useState(false)
  const [consultaLogsError, setConsultaLogsError] = useState('')
  const [hasLoadedConsultaLogs, setHasLoadedConsultaLogs] = useState(false)
  const [consultaLogsStale, setConsultaLogsStale] = useState(false)
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [consulta, setConsulta] = useState(null)
  const [consultaError, setConsultaError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formData, setFormData] = useState(storedAdminWorkspace.formData)
  const [editingId, setEditingId] = useState(storedAdminWorkspace.editingId)
  const [adminError, setAdminError] = useState('')
  const [adminMessage, setAdminMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [adminFieldErrors, setAdminFieldErrors] = useState(EMPTY_ADMIN_ERRORS)
  const [slugTouched, setSlugTouched] = useState(storedAdminWorkspace.slugTouched)
  const [adminSearch, setAdminSearch] = useState(storedAdminWorkspace.adminSearch)
  const [adminDependency, setAdminDependency] = useState(storedAdminWorkspace.adminDependency)
  const [adminToken, setAdminToken] = useState(() => {
    if (typeof window === 'undefined') return ''
    return window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? ''
  })
  const [adminSessionExpiresAt, setAdminSessionExpiresAt] = useState(storedAdminSessionExpiresAt)
  const [adminTimeRemainingSeconds, setAdminTimeRemainingSeconds] = useState(() =>
    getRemainingSeconds(storedAdminSessionExpiresAt),
  )
  const [adminPin, setAdminPin] = useState('')
  const [adminAuthError, setAdminAuthError] = useState('')
  const [adminAuthBusy, setAdminAuthBusy] = useState(false)
  const [adminAuthenticated, setAdminAuthenticated] = useState(false)
  const [adminSessionChecked, setAdminSessionChecked] = useState(() => {
    if (typeof window === 'undefined') return true
    return !(window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? '')
  })

  const isDarkTheme = theme === 'dark'
  const dependencyOptions = buildDependencyOptions(tramites)
  const normalizedAdminSearch = normalizeLooseText(adminSearch)
  const filteredTramites = tramites.filter((tramite) => {
    const dependencyLabel = getCanonicalDependencyLabel(tramite.dependencia, dependencyOptions)
    const searchableText = normalizeLooseText(
      [tramite.nombre, tramite.descripcion, dependencyLabel].filter(Boolean).join(' '),
    )
    const matchesSearch =
      !normalizedAdminSearch || searchableText.includes(normalizedAdminSearch)
    const matchesDependency = adminDependency === 'todas' || dependencyLabel === adminDependency
    return matchesSearch && matchesDependency
  })
  const hasActiveAdminFilters = Boolean(normalizedAdminSearch) || adminDependency !== 'todas'
  const qualitySummary = summarizeTramiteQuality(tramites)
  const weakestTramites = selectWeakestTramites(tramites)
  const catalogAttention = buildCatalogAttention(consultaLogs, tramites)
  const quickQuestions = buildQuickQuestions(tramites)
  const hasRestorableAdminWorkspace = hasStoredAdminWorkspace({
    formData,
    editingId,
    adminSearch,
    adminDependency,
  })
  const draftQualityReport = assessFrontendTramiteQuality({
    ...formData,
    dependencia: normalizeDependencySelection(formData.dependencia, dependencyOptions),
  })

  useEffect(() => {
    refreshTramites()
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('app-theme', theme)
  }, [theme])

  useEffect(() => {
    if (
      view !== 'admin' ||
      !adminAuthenticated ||
      (hasLoadedConsultaLogs && !consultaLogsStale)
    ) {
      return
    }

    let isCancelled = false

    async function loadAdminLogs() {
      setLoadingConsultaLogs(true)
      setConsultaLogsError('')
      try {
        const response = await fetch(`${API_URL}/admin/consultas`, {
          headers: { Authorization: `Bearer ${adminToken}` },
        })

        if (response.status === 401) {
          clearAdminSession('La sesion administrativa expiro. Vuelve a ingresar tu PIN.')
          throw new Error('La sesion administrativa expiro. Vuelve a ingresar tu PIN.')
        }

        if (!response.ok) {
          throw new Error('No fue posible cargar la actividad reciente del asistente.')
        }

        const data = await response.json()
        if (isCancelled) return
        setConsultaLogs(data)
        setHasLoadedConsultaLogs(true)
        setConsultaLogsStale(false)
      } catch (error) {
        if (isCancelled) return
        setConsultaLogsError(
          error instanceof Error
            ? error.message
            : 'Ocurrio un error al consultar la actividad del asistente.',
        )
      } finally {
        if (!isCancelled) {
          setLoadingConsultaLogs(false)
        }
      }
    }

    loadAdminLogs()

    return () => {
      isCancelled = true
    }
  }, [view, adminAuthenticated, hasLoadedConsultaLogs, consultaLogsStale, adminToken])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (adminToken) {
      window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminToken)
      return
    }
    window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
  }, [adminToken])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (adminSessionExpiresAt) {
      window.sessionStorage.setItem(
        ADMIN_SESSION_EXPIRES_AT_STORAGE_KEY,
        String(adminSessionExpiresAt),
      )
      return
    }
    window.sessionStorage.removeItem(ADMIN_SESSION_EXPIRES_AT_STORAGE_KEY)
  }, [adminSessionExpiresAt])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const snapshot = {
      formData,
      editingId,
      slugTouched,
      adminSearch,
      adminDependency,
    }
    window.sessionStorage.setItem(ADMIN_WORKSPACE_STORAGE_KEY, JSON.stringify(snapshot))
  }, [formData, editingId, slugTouched, adminSearch, adminDependency])

  useEffect(() => {
    if (!adminToken || !adminSessionExpiresAt) {
      setAdminTimeRemainingSeconds(0)
      return
    }

    const updateRemaining = () => {
      const remaining = getRemainingSeconds(adminSessionExpiresAt)
      setAdminTimeRemainingSeconds(remaining)
      if (remaining <= 0) {
        clearAdminSession(
          'La sesion administrativa expiro. Tu borrador quedo guardado para retomarlo al volver a ingresar el PIN.',
        )
      }
    }

    updateRemaining()
    const timerId = window.setInterval(updateRemaining, 1000)

    return () => {
      window.clearInterval(timerId)
    }
  }, [adminToken, adminSessionExpiresAt])

  useEffect(() => {
    if (!adminToken) {
      setAdminAuthenticated(false)
      setAdminSessionChecked(true)
      return
    }

    let isCancelled = false

    async function checkAdminSession() {
      setAdminSessionChecked(false)
      try {
        const response = await fetch(`${API_URL}/admin/session`, {
          headers: { Authorization: `Bearer ${adminToken}` },
        })

        if (response.status === 401) {
          if (!isCancelled) {
            clearAdminSession('La sesion administrativa expiro. Vuelve a ingresar tu PIN.')
          }
          return
        }

        if (!response.ok) {
          throw new Error('No fue posible validar la sesion administrativa.')
        }

        const data = await response.json()

        if (!isCancelled) {
          setAdminAuthenticated(true)
          setAdminAuthError('')
          setAdminSessionExpiresAt(resolveSessionExpiryTimestamp(data))
        }
      } catch {
        if (!isCancelled) {
          clearAdminSession('No fue posible validar el acceso privado del panel admin.')
        }
      } finally {
        if (!isCancelled) {
          setAdminSessionChecked(true)
        }
      }
    }

    checkAdminSession()

    return () => {
      isCancelled = true
    }
  }, [adminToken])

  async function refreshTramites() {
    setLoadingTramites(true)
    setTramitesError('')
    try {
      const response = await fetch(`${API_URL}/tramites`)
      if (!response.ok) throw new Error('No fue posible cargar los tramites activos.')
      setTramites(await response.json())
    } catch (error) {
      setTramitesError(error instanceof Error ? error.message : 'Ocurrio un error al consultar los tramites.')
    } finally {
      setLoadingTramites(false)
    }
  }

  function openAdminView() {
    setView('admin')
    setAdminAuthError('')
  }

  function clearAdminSession(message = '') {
    setAdminToken('')
    setAdminSessionExpiresAt(null)
    setAdminTimeRemainingSeconds(0)
    setAdminAuthenticated(false)
    setAdminSessionChecked(true)
    setAdminPin('')
    setConsultaLogs([])
    setHasLoadedConsultaLogs(false)
    setConsultaLogsStale(false)
    setAdminMessage('')
    if (message) {
      setAdminAuthError(message)
    }
  }

  async function fetchAdmin(endpoint, options = {}, tokenOverride = adminToken) {
    if (!tokenOverride) {
      throw new Error('Debes ingresar el PIN administrativo para continuar.')
    }

    const headers = {
      ...(options.headers ?? {}),
      Authorization: `Bearer ${tokenOverride}`,
    }

    const response = await fetch(endpoint, {
      ...options,
      headers,
    })

    if (response.status === 401) {
      clearAdminSession('La sesion administrativa expiro. Vuelve a ingresar tu PIN.')
      throw new Error('La sesion administrativa expiro. Vuelve a ingresar tu PIN.')
    }

    return response
  }

  async function handleAdminUnlock(event) {
    event.preventDefault()
    const cleanedPin = adminPin.trim()
    if (!cleanedPin) {
      setAdminAuthError('Ingresa el PIN administrativo para abrir este apartado privado.')
      return
    }

    setAdminAuthBusy(true)
    setAdminAuthError('')
    try {
      const response = await fetch(`${API_URL}/admin/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ pin: cleanedPin }),
      })

      const data = await response.json().catch(() => null)
      if (!response.ok) {
        throw new Error(data?.detail || 'No fue posible abrir la sesion administrativa.')
      }

      setAdminToken(data.access_token)
      setAdminSessionExpiresAt(resolveSessionExpiryTimestamp(data))
      setAdminTimeRemainingSeconds(data.expires_in_seconds ?? 0)
      setAdminAuthenticated(true)
      setAdminSessionChecked(true)
      setAdminPin('')
      setAdminMessage(
        hasRestorableAdminWorkspace
          ? 'Acceso privado habilitado. Recuperamos tu contexto administrativo para que sigas donde ibas.'
          : 'Acceso privado habilitado para el panel administrativo.',
      )
      setAdminError('')
      await refreshConsultaLogs(data.access_token)
    } catch (error) {
      setAdminAuthError(
        error instanceof Error ? error.message : 'No fue posible abrir la sesion administrativa.',
      )
    } finally {
      setAdminAuthBusy(false)
    }
  }

  function handleAdminLogout() {
    clearAdminSession('')
    setAdminMessage('Sesion administrativa cerrada.')
    setAdminError('')
  }

  async function refreshConsultaLogs(tokenOverride = adminToken) {
    if (!tokenOverride) {
      setLoadingConsultaLogs(false)
      return
    }

    setLoadingConsultaLogs(true)
    setConsultaLogsError('')
    try {
      const response = await fetchAdmin(`${API_URL}/admin/consultas`, {}, tokenOverride)
      if (!response.ok) throw new Error('No fue posible cargar la actividad reciente del asistente.')
      setConsultaLogs(await response.json())
      setHasLoadedConsultaLogs(true)
      setConsultaLogsStale(false)
    } catch (error) {
      setConsultaLogsError(
        error instanceof Error
          ? error.message
          : 'Ocurrio un error al consultar la actividad del asistente.',
      )
    } finally {
      setLoadingConsultaLogs(false)
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const pregunta = question.trim()
    if (!pregunta) {
      setConsultaError('Escribe una pregunta antes de consultar.')
      return
    }

    setConsultaError('')
    setIsSubmitting(true)
    try {
      const response = await fetch(`${API_URL}/consulta`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ pregunta }),
      })
      if (!response.ok) throw new Error('No fue posible procesar la consulta.')
      const result = await response.json()
      setConsulta(result)
      setConsultaLogsStale(true)
    } catch (error) {
      setConsultaError(error instanceof Error ? error.message : 'Ocurrio un error al consultar el asistente.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleInputChange(event) {
    const { name, value } = event.target

    if (name === 'slug') {
      setSlugTouched(true)
    }

    setFormData((current) => {
      const nextState = { ...current, [name]: value }

      if (name === 'nombre' && !slugTouched && !editingId) {
        nextState.slug = slugify(value)
      }

      return nextState
    })

    if (name in EMPTY_ADMIN_ERRORS) {
      setAdminFieldErrors((current) => ({
        ...current,
        [name]: '',
      }))
    }
  }

  function handleResetForm(clearFeedback = true) {
    setEditingId(null)
    setFormData(EMPTY_FORM)
    setAdminFieldErrors(EMPTY_ADMIN_ERRORS)
    setSlugTouched(false)
    if (clearFeedback) {
      setAdminError('')
      setAdminMessage('')
    }
  }

  function handleEdit(tramite) {
    setEditingId(tramite.id)
    setFormData({
      nombre: tramite.nombre ?? '',
      slug: tramite.slug ?? '',
      descripcion: tramite.descripcion ?? '',
      requisitos: tramite.requisitos ?? '',
      costo: tramite.costo ?? '',
      horario: tramite.horario ?? '',
      dependencia: tramite.dependencia ?? '',
      fuente_url: tramite.fuente_url ?? '',
    })
    setAdminFieldErrors(EMPTY_ADMIN_ERRORS)
    setSlugTouched(true)
    setAdminError('')
    setAdminMessage(`Editando "${tramite.nombre}".`)
    setView('admin')
  }

  async function handleAdminSubmit(event) {
    event.preventDefault()
    const payload = normalizePayload(formData)
    payload.dependencia = normalizeDependencySelection(payload.dependencia, dependencyOptions)
    const nextFieldErrors = validateAdminForm(payload)

    if (hasAdminErrors(nextFieldErrors)) {
      setAdminFieldErrors(nextFieldErrors)
      setAdminError('Revisa los campos marcados antes de guardar.')
      return
    }

    setIsSaving(true)
    setAdminError('')
    setAdminMessage('')
    setAdminFieldErrors(EMPTY_ADMIN_ERRORS)
    const endpoint = editingId ? `${API_URL}/admin/tramites/${editingId}` : `${API_URL}/admin/tramites`
    const method = editingId ? 'PUT' : 'POST'

    try {
      const response = await fetchAdmin(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        throw new Error(
          errorData?.detail ||
            (editingId
              ? 'No fue posible actualizar el tramite.'
              : 'No fue posible crear el tramite.'),
        )
      }

      const savedTramite = await response.json()
      await refreshTramites()
      setAdminMessage(
        editingId
          ? `Tramite "${savedTramite.nombre}" actualizado.`
          : `Tramite "${savedTramite.nombre}" creado o reactivado correctamente.`,
      )
      handleResetForm(false)
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : 'Ocurrio un error al guardar el tramite.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(tramite) {
    setDeletingId(tramite.id)
    setAdminError('')
    setAdminMessage('')
    try {
      const response = await fetchAdmin(`${API_URL}/admin/tramites/${tramite.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('No fue posible desactivar el tramite.')
      await refreshTramites()
      if (editingId === tramite.id) handleResetForm()
      setAdminMessage(`Tramite "${tramite.nombre}" desactivado.`)
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : 'Ocurrio un error al desactivar el tramite.')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div
      className={`min-h-screen transition-colors ${
        isDarkTheme
          ? 'bg-[radial-gradient(circle_at_top,#0f172a_0%,#111827_45%,#020617_100%)] text-slate-100'
          : 'bg-[radial-gradient(circle_at_top,#f8f4ea_0%,#eef5f3_45%,#dfe8ea_100%)] text-slate-900'
      }`}
    >
      <div className="mx-auto flex min-h-screen w-full max-w-[1680px] flex-col gap-8 px-4 py-8 lg:px-8 xl:px-10">
        <a
          href="#contenido-principal"
          className="skip-link rounded-full bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-lg"
        >
          Saltar al contenido principal
        </a>

        <header
          className={`overflow-hidden rounded-[2rem] border p-6 shadow-[0_25px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur transition-colors ${
            isDarkTheme ? 'border-slate-700/70 bg-slate-900/80' : 'border-white/70 bg-white/75'
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={openAdminView}
                aria-label="Abrir panel administrativo"
                className={`inline-flex items-center gap-3 rounded-2xl border px-4 py-3 transition ${
                  isDarkTheme
                    ? 'border-slate-700 bg-slate-950/80 hover:border-slate-500 hover:bg-slate-950'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <svg
                  viewBox="0 0 24 24"
                  className={`h-7 w-7 ${isDarkTheme ? 'text-slate-100' : 'text-slate-700'}`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 20a6 6 0 0 0-12 0" />
                  <circle cx="12" cy="8" r="4" />
                </svg>
                <span className="text-left">
                  <span className={`block text-[11px] font-semibold uppercase tracking-[0.18em] ${
                    isDarkTheme ? 'text-slate-400' : 'text-slate-500'
                  }`}>
                    Acceso privado
                  </span>
                  <span className={`block text-sm font-semibold ${
                    isDarkTheme ? 'text-slate-100' : 'text-slate-800'
                  }`}>
                    Panel admin
                  </span>
                </span>
              </button>
              {view === 'admin' ? (
                <button
                  type="button"
                  onClick={() => setView('ciudadania')}
                  className={`inline-flex items-center rounded-full border px-4 py-2 text-sm font-semibold transition ${
                    isDarkTheme
                      ? 'border-slate-600 bg-slate-950/70 text-slate-100 hover:border-slate-400 hover:bg-slate-900'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'
                  }`}
                >
                  Volver a consulta
                </button>
              ) : null}
            </div>

            <button
              type="button"
              onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
              className={`inline-flex items-center rounded-full border px-4 py-2 text-sm font-semibold transition ${
                isDarkTheme
                  ? 'border-amber-300/30 bg-amber-300/10 text-amber-100 hover:bg-amber-300/20'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'
              }`}
            >
              {isDarkTheme ? 'Modo claro' : 'Modo oscuro'}
            </button>
          </div>

          <div className="mt-6 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <span className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] ${
                isDarkTheme
                  ? 'border-emerald-300/30 bg-emerald-300/10 text-emerald-100'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-700'
              }`}>
                Iteracion 4 en fortalecimiento
              </span>
              <div className="flex items-start gap-4">
                <div className={`hidden rounded-3xl border p-3 sm:block ${
                  isDarkTheme ? 'border-slate-700 bg-slate-950/70' : 'border-slate-200 bg-white'
                }`}>
                  <img
                    src="/logo-alcaldia.png"
                    alt="Logo Alcaldia de Cucuta"
                    className="h-14 w-14 object-contain"
                  />
                </div>
                <div className="space-y-3">
                  <h1 className={`max-w-3xl text-4xl font-black tracking-tight md:text-5xl ${isDarkTheme ? 'text-white' : 'text-slate-950'}`}>
                    Asistente de tramites para rentas e impuestos
                  </h1>
                  <p className={`max-w-3xl text-base leading-7 md:text-lg ${isDarkTheme ? 'text-slate-300' : 'text-slate-600'}`}>
                    Estamos dejando el sistema mas claro para ciudadania y mas confiable para consultas reales sobre tramites tributarios de la Alcaldia de Cucuta.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard label="API" value="Activa" tone="emerald" />
              <MetricCard label="Tramites activos" value={loadingTramites ? '...' : String(tramites.length)} tone="amber" />
              <MetricCard label="Vista" value={view === 'ciudadania' ? 'Consulta' : 'Admin'} tone="slate" />
            </div>
          </div>
        </header>

        <main id="contenido-principal" className="flex-1">
          {view === 'ciudadania' ? (
            <div className="grid gap-8 lg:grid-cols-[1.5fr_1fr]">
              <section className="space-y-6">
                <div className="rounded-[2rem] border border-slate-200/70 bg-white/80 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
                  <div className="mb-6 flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Consulta del asistente</p>
                      <h2 className="mt-2 text-2xl font-bold text-slate-950">Pregunta por un tramite</h2>
                    </div>
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-right">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Canal ciudadano</p>
                      <p className="text-sm font-semibold text-emerald-900">Consulta guiada</p>
                    </div>
                  </div>

                  <form className="space-y-4" onSubmit={handleSubmit}>
                    <label className="block">
                      <span className="mb-2 block text-sm font-medium text-slate-700">Escribe tu consulta</span>
                      <textarea
                        className="min-h-32 w-full rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 text-base text-slate-800 outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100"
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        placeholder="Ejemplo: Quiero informacion sobre impuesto predial"
                      />
                    </label>

                    <div className="flex flex-wrap items-center gap-3">
                      <button type="submit" disabled={isSubmitting} className="inline-flex w-full items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400 sm:w-auto">
                        {isSubmitting ? 'Consultando...' : 'Consultar asistente'}
                      </button>
                      <button type="button" onClick={() => setQuestion(DEFAULT_QUESTION)} className="inline-flex w-full items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 sm:w-auto">
                        Usar ejemplo
                      </button>
                    </div>

                    <div className="space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Preguntas rapidas
                      </p>
                      <div className="flex flex-wrap gap-3">
                        {quickQuestions.map((quickQuestion) => (
                          <button
                            key={quickQuestion}
                            type="button"
                            onClick={() => setQuestion(quickQuestion)}
                            className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-100"
                          >
                            {quickQuestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  </form>

                  {consultaError ? <Message tone="error">{consultaError}</Message> : null}
                </div>

                <ConsultaResult
                  consulta={consulta}
                  isSubmitting={isSubmitting}
                  onUseSuggestion={setQuestion}
                  quickQuestions={quickQuestions}
                />
              </section>

              <aside className="space-y-6">
                <TramitesPanel tramites={tramites} loadingTramites={loadingTramites} tramitesError={tramitesError} />
                <Callout />
              </aside>
            </div>
          ) : !adminSessionChecked ? (
            <LoadingPanel title="Validando acceso privado" />
          ) : !adminAuthenticated ? (
            <AdminAccessPanel
              pin={adminPin}
              onPinChange={setAdminPin}
              onSubmit={handleAdminUnlock}
              isBusy={adminAuthBusy}
              error={adminAuthError}
              hasRestorableWorkspace={hasRestorableAdminWorkspace}
            />
          ) : (
            <div className="grid gap-8 xl:grid-cols-[minmax(0,1.02fr)_minmax(0,1fr)]">
              <section className="rounded-[2rem] border border-slate-200/70 bg-white/85 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Panel administrativo</p>
                    <h2 className="mt-2 text-3xl font-bold text-slate-950">Gestion de tramites estrella</h2>
                    <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                      Este formulario ya crea y actualiza tramites reales. En esta fase lo usamos para mantener coherencia entre la base administrativa y la experiencia de consulta ciudadana.
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-3">
                    <div className={`rounded-2xl border px-4 py-3 text-right ${getSessionToneClassName(adminTimeRemainingSeconds).panel}`}>
                      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${getSessionToneClassName(adminTimeRemainingSeconds).eyebrow}`}>
                        Sesion privada
                      </p>
                      <p className={`text-sm font-semibold ${getSessionToneClassName(adminTimeRemainingSeconds).label}`}>
                        {formatSessionCountdown(adminTimeRemainingSeconds)}
                      </p>
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/70">
                        <div
                          className={`h-full rounded-full transition-all ${getSessionToneClassName(adminTimeRemainingSeconds).bar}`}
                          style={{ width: `${getSessionProgress(adminTimeRemainingSeconds)}%` }}
                        />
                      </div>
                      <p className={`mt-2 text-[11px] font-medium ${getSessionToneClassName(adminTimeRemainingSeconds).hint}`}>
                        Si expira, conservamos tu borrador y filtros para retomarlos al reingresar.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleAdminLogout}
                      className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                    >
                      Cerrar acceso privado
                    </button>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                    editingId
                      ? 'border border-amber-200 bg-amber-50 text-amber-700'
                      : 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                  }`}>
                    {editingId ? 'Modo edicion' : 'Nuevo tramite'}
                  </span>
                  <span className="text-sm text-slate-500">
                    Los campos con <span className="font-semibold text-rose-500">*</span> son obligatorios.
                  </span>
                  {hasRestorableAdminWorkspace ? (
                    <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
                      Contexto recuperable activo
                    </span>
                  ) : null}
                </div>

                <form className="mt-8 grid gap-4 md:grid-cols-2" onSubmit={handleAdminSubmit}>
                  <Field label="Nombre" required error={adminFieldErrors.nombre}>
                    <input className={fieldClassName(adminFieldErrors.nombre)} name="nombre" value={formData.nombre} onChange={handleInputChange} />
                  </Field>
                  <Field label="Slug" required hint="Si no lo escribes manualmente, se genera a partir del nombre." error={adminFieldErrors.slug}>
                    <input className={fieldClassName(adminFieldErrors.slug)} name="slug" value={formData.slug} onChange={handleInputChange} />
                  </Field>
                  <Field
                    label="Dependencia"
                    required
                    hint={
                      dependencyOptions.length
                        ? 'Puedes elegir una dependencia existente o escribir una nueva.'
                        : 'Escribe la dependencia responsable del tramite.'
                    }
                    error={adminFieldErrors.dependencia}
                  >
                    <input
                      list="dependency-options"
                      className={fieldClassName(adminFieldErrors.dependencia)}
                      name="dependencia"
                      value={formData.dependencia}
                      onChange={handleInputChange}
                      placeholder="Selecciona o escribe una dependencia"
                    />
                  </Field>
                  <Field label="Fuente oficial" hint="Opcional. Usa una URL completa con http o https." error={adminFieldErrors.fuente_url}>
                    <input className={fieldClassName(adminFieldErrors.fuente_url)} name="fuente_url" value={formData.fuente_url} onChange={handleInputChange} />
                  </Field>
                  <Field label="Costo"><input className={inputClassName} name="costo" value={formData.costo} onChange={handleInputChange} /></Field>
                  <Field label="Horario"><input className={inputClassName} name="horario" value={formData.horario} onChange={handleInputChange} /></Field>
                  <Field className="md:col-span-2" label="Descripcion" error={adminFieldErrors.descripcion}><textarea className={fieldClassName(adminFieldErrors.descripcion) + ' min-h-28'} name="descripcion" value={formData.descripcion} onChange={handleInputChange} /></Field>
                  <Field className="md:col-span-2" label="Requisitos" error={adminFieldErrors.requisitos}><textarea className={fieldClassName(adminFieldErrors.requisitos) + ' min-h-28'} name="requisitos" value={formData.requisitos} onChange={handleInputChange} /></Field>
                  <div className="md:col-span-2 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Calidad semantica del borrador</p>
                        <p className="mt-2 text-sm text-slate-700">
                          Nivel actual: <span className={`font-semibold ${qualityToneClassName(draftQualityReport.level)}`}>{humanizeQualityLevel(draftQualityReport.level)}</span>
                        </p>
                      </div>
                      <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-600">
                        Score {draftQualityReport.score}
                      </span>
                    </div>
                    {draftQualityReport.alerts.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {draftQualityReport.alerts.slice(0, 4).map((alert) => (
                          <span key={alert} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
                            {alert}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-sm text-emerald-700">El tramite ya tiene una base bastante buena para consultas ciudadanas.</p>
                    )}
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                      Accion sugerida: <span className="font-medium text-slate-800">{draftQualityReport.recommendedAction}</span>
                    </p>
                  </div>
                  <div className="md:col-span-2">
                    <div className="flex flex-wrap items-center gap-3">
                      <button type="submit" disabled={isSaving} className="inline-flex w-full items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400 sm:w-auto">
                        {isSaving ? 'Guardando...' : editingId ? 'Actualizar tramite' : 'Crear tramite'}
                      </button>
                      <button type="button" onClick={handleResetForm} className="inline-flex w-full items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 sm:w-auto">
                        Limpiar formulario
                      </button>
                    </div>

                    {adminMessage ? <Message tone="success">{adminMessage}</Message> : null}
                    {adminError ? <Message tone="error">{adminError}</Message> : null}
                  </div>
                </form>

                {dependencyOptions.length ? (
                  <datalist id="dependency-options">
                    {dependencyOptions.map((dependency) => (
                      <option key={dependency} value={dependency} />
                    ))}
                  </datalist>
                ) : null}
              </section>

              <section className="rounded-[2rem] border border-slate-200/70 bg-white/85 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
                <div className="mb-6 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Inventario activo</p>
                    <h3 className="mt-2 text-2xl font-bold text-slate-950">Tramites disponibles</h3>
                  </div>
                  <button type="button" onClick={refreshTramites} className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50">
                    Actualizar lista
                  </button>
                </div>

                <div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                  <label className="block">
                    <span className="mb-2 block text-sm font-medium text-slate-700">Buscar tramite</span>
                    <input
                      className={inputClassName}
                      value={adminSearch}
                      onChange={(event) => setAdminSearch(event.target.value)}
                      placeholder="Nombre, descripcion o dependencia"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-2 block text-sm font-medium text-slate-700">Filtrar por dependencia</span>
                    <select
                      className={inputClassName}
                      value={adminDependency}
                      onChange={(event) => setAdminDependency(event.target.value)}
                    >
                      <option value="todas">Todas las dependencias</option>
                      {dependencyOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="mb-6 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
                  <p>
                    Mostrando {filteredTramites.length} de {tramites.length} tramite(s) activos.
                  </p>
                  <div className="flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-rose-700">
                      Criticos {qualitySummary.critical}
                    </span>
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-amber-700">
                      En riesgo {qualitySummary.warning}
                    </span>
                    <span className="rounded-full border border-rose-200 bg-white px-3 py-1 text-rose-700">
                      Fuera de foco {qualitySummary.outOfScope}
                    </span>
                    <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-sky-700">
                      Con impacto real {catalogAttention.items.length}
                    </span>
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700">
                      Fuertes {qualitySummary.strong}
                    </span>
                  </div>
                  {hasActiveAdminFilters ? (
                    <button
                      type="button"
                      onClick={() => {
                        setAdminSearch('')
                        setAdminDependency('todas')
                      }}
                      className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                    >
                      Limpiar filtros
                    </button>
                  ) : null}
                </div>

                {weakestTramites.length ? (
                  <div className="mb-6 rounded-3xl border border-amber-200 bg-[linear-gradient(180deg,#fff8eb_0%,#fffdf8_100%)] p-5 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">
                          Tramites que requieren atencion
                        </p>
                        <h4 className="mt-2 text-lg font-semibold text-slate-950">
                          Prioridad para fortalecer el catalogo
                        </h4>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                          Aqui juntamos los tramites mas fragiles o fuera de foco. Si mejoramos descripcion, requisitos o fuente oficial, el asistente respondera con mas precision y menos desvio.
                        </p>
                      </div>
                      <span className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-800">
                        {weakestTramites.length} foco(s)
                      </span>
                    </div>

                    <div className="mt-4 grid gap-3 xl:grid-cols-3">
                      {weakestTramites.map(({ tramite, report }) => (
                        <article key={`weak-${tramite.id}`} className="rounded-3xl border border-amber-200 bg-white px-4 py-4">
                          {(() => {
                            const signal = catalogAttention.byId.get(tramite.id)
                            return (
                              <>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                              report.scopeStatus === 'fuera_de_foco'
                                ? 'border-rose-200 bg-rose-50 text-rose-700'
                                : report.level === 'critico'
                                  ? 'border-rose-200 bg-rose-50 text-rose-700'
                                  : 'border-amber-200 bg-amber-50 text-amber-700'
                            }`}>
                              {humanizeQualityLevel(report.level)} · {report.score}
                            </span>
                            <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                              ID {tramite.id}
                            </span>
                          </div>
                          <h5 className="mt-3 text-sm font-semibold leading-6 text-slate-950">
                            {tramite.nombre}
                          </h5>
                          <p className="mt-2 text-xs leading-5 text-slate-500">
                            {cleanDependencyLabel(tramite.dependencia)}
                          </p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${scopeBadgeClassName(report.scopeStatus)}`}>
                              {humanizeScopeStatus(report.scopeStatus)}
                            </span>
                          </div>
                          {report.alerts.length ? (
                            <ul className="mt-3 space-y-2">
                              {report.alerts.slice(0, 2).map((alert) => (
                                <li key={`${tramite.id}-${alert}`} className="text-sm leading-6 text-slate-600">
                                  {alert}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                          {signal ? (
                            <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">
                                Impacto real en preguntas
                              </p>
                              <p className="mt-2 text-sm leading-6 text-rose-900">
                                {signal.hits} senal(es) recientes. Ejemplo: "{signal.example}".
                              </p>
                            </div>
                          ) : null}
                          <p className="mt-3 text-sm leading-6 text-slate-700">
                            {report.recommendedAction}
                          </p>
                              </>
                            )
                          })()}
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}

                <TramitesAdminList
                  tramites={filteredTramites}
                  loadingTramites={loadingTramites}
                  tramitesError={tramitesError}
                  editingId={editingId}
                  deletingId={deletingId}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  hasActiveFilters={hasActiveAdminFilters}
                  catalogAttentionById={catalogAttention.byId}
                />
              </section>

              <ConsultaActivityPanel
                logs={consultaLogs}
                tramites={tramites}
                loading={loadingConsultaLogs || (!hasLoadedConsultaLogs && !consultaLogsError)}
                error={consultaLogsError}
                onRefresh={refreshConsultaLogs}
                className="xl:col-span-2"
              />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function normalizePayload(data) {
  return Object.fromEntries(
    Object.entries({ ...data, activo: true }).map(([key, value]) => [
      key,
      typeof value === 'string' ? value.trim() : value,
    ]),
  )
}

function validateAdminForm(payload) {
  const errors = { ...EMPTY_ADMIN_ERRORS }

  if (!payload.nombre) {
    errors.nombre = 'Ingresa el nombre del tramite.'
  }

  if (!payload.slug) {
    errors.slug = 'Ingresa o genera un slug para el tramite.'
  } else if (!/^[a-z0-9-]+$/.test(payload.slug)) {
    errors.slug = 'El slug solo debe contener minusculas, numeros y guiones.'
  }

  if (!payload.dependencia) {
    errors.dependencia = 'Indica la dependencia responsable.'
  }

  const qualityReport = assessFrontendTramiteQuality(payload)
  if (qualityReport.blockingIssues.some((issue) => issue.includes('descripcion'))) {
    errors.descripcion = 'Describe el tramite con mas contexto ciudadano y menos frases genericas.'
  }

  if (qualityReport.blockingIssues.some((issue) => issue.includes('requisitos'))) {
    errors.requisitos = 'Detalla requisitos reales; evita dejar este campo demasiado corto.'
  }

  if (payload.fuente_url && !isValidUrl(payload.fuente_url)) {
    errors.fuente_url = 'La fuente oficial debe ser una URL valida con http o https.'
  }

  return errors
}

function hasAdminErrors(errors) {
  return Object.values(errors).some(Boolean)
}

function normalizeLooseText(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
}

function frontendWordCount(value) {
  return normalizeLooseText(value)
    .split(' ')
    .filter(Boolean).length
}

function assessFrontendTramiteQuality(tramite) {
  const description = String(tramite.descripcion ?? '')
  const requirements = String(tramite.requisitos ?? '')
  const sourceUrl = String(tramite.fuente_url ?? '')
  const dependency = String(tramite.dependencia ?? '')
  const normalizedDescription = normalizeLooseText(description)
  const descriptionWords = frontendWordCount(description)
  const requirementWords = frontendWordCount(requirements)

  let score = Number.isFinite(tramite.semantic_quality_score)
    ? tramite.semantic_quality_score
    : 100
  const alerts = Array.isArray(tramite.semantic_quality_alerts)
    ? [...tramite.semantic_quality_alerts]
    : []
  const blockingIssues = []

  if (descriptionWords === 0) {
    score -= 40
    alerts.push('Falta una descripcion clara del tramite.')
    blockingIssues.push('descripcion vacia')
  } else if (descriptionWords < 12) {
    score -= 24
    alerts.push('La descripcion es demasiado corta para preguntas ciudadanas.')
    blockingIssues.push('descripcion corta')
  } else if (descriptionWords < 20) {
    score -= 10
    alerts.push('La descripcion puede ser mas especifica.')
  }

  const hasGenericPattern = FRONTEND_GENERIC_DESCRIPTION_PATTERNS.some((pattern) =>
    normalizedDescription.includes(pattern),
  )
  const hasWeakPrefixedDescription =
    descriptionWords < 12 &&
    (normalizedDescription.startsWith('tramite para ') ||
      normalizedDescription.startsWith('proceso para '))

  if (hasGenericPattern || hasWeakPrefixedDescription) {
    score -= 18
    alerts.push('La descripcion sigue sonando generica.')
    blockingIssues.push('descripcion generica')
  }

  if (requirementWords === 0) {
    score -= 14
    alerts.push('Faltan requisitos del tramite.')
    blockingIssues.push('requisitos vacios')
  } else if (requirementWords < 6) {
    score -= 8
    alerts.push('Los requisitos son muy cortos y pueden perder contexto.')
    blockingIssues.push('requisitos cortos')
  }

  if (!sourceUrl.trim()) {
    score -= 8
    alerts.push('Falta la fuente oficial.')
  }

  if (!dependency.trim()) {
    score -= 6
    alerts.push('Falta la dependencia responsable.')
  }

  const finalScore = Math.max(Math.min(score, 100), 0)
  const level =
    finalScore >= 85
      ? 'fuerte'
      : finalScore >= 70
        ? 'estable'
        : finalScore >= 55
          ? 'en_riesgo'
          : 'critico'

  return {
    score: finalScore,
    level,
    alerts: [...new Set(alerts)].slice(0, 5),
    blockingIssues: [...new Set(blockingIssues)],
    scopeStatus: dependency.trim() ? 'tributario' : 'sin_contexto',
    recommendedAction:
      dependency.trim()
        ? 'Refuerza descripcion, requisitos y fuente oficial si quieres mejorar la interpretacion ciudadana.'
        : 'Completa la dependencia y el contexto tributario para clasificar mejor este tramite.',
  }
}

function getTramiteQualitySnapshot(tramite) {
  const hasBackendQuality =
    Number.isFinite(tramite.semantic_quality_score) &&
    typeof tramite.semantic_quality_level === 'string' &&
    tramite.semantic_quality_level.length > 0

  if (hasBackendQuality) {
    return {
      score: tramite.semantic_quality_score,
      level: tramite.semantic_quality_level,
      alerts: Array.isArray(tramite.semantic_quality_alerts)
        ? [...tramite.semantic_quality_alerts]
        : [],
      blockingIssues: [],
      scopeStatus: tramite.semantic_scope_status ?? inferScopeStatusFromAlerts(tramite.semantic_quality_alerts),
      recommendedAction: tramite.semantic_recommended_action ?? '',
    }
  }

  return assessFrontendTramiteQuality(tramite)
}

function summarizeTramiteQuality(tramites) {
  return tramites.reduce(
    (summary, tramite) => {
      const report = getTramiteQualitySnapshot(tramite)
      if (report.level === 'critico') summary.critical += 1
      else if (report.level === 'en_riesgo') summary.warning += 1
      else summary.strong += 1
      if (report.scopeStatus === 'fuera_de_foco') summary.outOfScope += 1
      return summary
    },
    { critical: 0, warning: 0, strong: 0, outOfScope: 0 },
  )
}

function selectWeakestTramites(tramites) {
  return [...tramites]
    .map((tramite) => ({
      tramite,
      report: getTramiteQualitySnapshot(tramite),
    }))
    .filter(
      ({ report }) =>
        report.level === 'critico' ||
        report.level === 'en_riesgo' ||
        report.scopeStatus === 'fuera_de_foco',
    )
    .sort((left, right) => {
      if (left.report.scopeStatus !== right.report.scopeStatus) {
        return left.report.scopeStatus === 'fuera_de_foco' ? -1 : 1
      }
      if (left.report.score !== right.report.score) return left.report.score - right.report.score
      return left.tramite.nombre.localeCompare(right.tramite.nombre, 'es-CO', {
        sensitivity: 'base',
      })
    })
    .slice(0, 3)
}

function humanizeQualityLevel(level) {
  const labels = {
    fuerte: 'Fuerte',
    estable: 'Estable',
    en_riesgo: 'En riesgo',
    critico: 'Critico',
    sin_datos: 'Sin datos',
  }
  return labels[level] ?? level
}

function qualityToneClassName(level) {
  if (level === 'fuerte') return 'text-emerald-700'
  if (level === 'estable') return 'text-sky-700'
  if (level === 'en_riesgo') return 'text-amber-700'
  return 'text-rose-700'
}

function inferScopeStatusFromAlerts(alerts) {
  if (!Array.isArray(alerts)) return 'sin_datos'
  return alerts.some((alert) => String(alert).includes('rentas e impuestos'))
    ? 'fuera_de_foco'
    : 'tributario'
}

function humanizeScopeStatus(scopeStatus) {
  const labels = {
    tributario: 'En foco tributario',
    fuera_de_foco: 'Fuera de foco',
    sin_contexto: 'Falta contexto',
    sin_datos: 'Sin clasificar',
  }
  return labels[scopeStatus] ?? scopeStatus
}

function scopeBadgeClassName(scopeStatus) {
  if (scopeStatus === 'fuera_de_foco') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (scopeStatus === 'sin_contexto') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

function buildQuickQuestions(tramites) {
  const prioritizedMatchers = [
    'predial',
    'paz y salvo',
    'industria y comercio',
    'espectaculos',
    'devolucion',
    'alumbrado',
  ]
  const availableLabels = new Map()

  tramites.forEach((tramite) => {
    const normalizedName = normalizeLooseText(tramite.nombre)
    const label = `Consulta por ${tramite.nombre}`
    if (!availableLabels.has(normalizedName)) {
      availableLabels.set(normalizedName, label)
    }
  })

  const prioritizedLabels = prioritizedMatchers.flatMap((matcher) =>
    Array.from(availableLabels.entries())
      .filter(([normalizedName]) => normalizedName.includes(matcher))
      .map(([, label]) => label),
  )

  const mergedLabels = [...prioritizedLabels, ...availableLabels.values()]
  const uniqueLabels = [...new Set(mergedLabels)].slice(0, 4)

  return uniqueLabels.length ? uniqueLabels : FALLBACK_QUICK_QUESTIONS
}

function cleanDependencyLabel(value) {
  return String(value ?? '').trim().replace(/\s+/g, ' ')
}

function buildDependencyOptions(tramites) {
  const dependencyMap = new Map()

  tramites.forEach((tramite) => {
    const label = cleanDependencyLabel(tramite.dependencia)
    if (!label) return

    const key = normalizeLooseText(label)
    if (!dependencyMap.has(key)) {
      dependencyMap.set(key, label)
    }
  })

  return Array.from(dependencyMap.values()).sort((left, right) =>
    left.localeCompare(right, 'es-CO', { sensitivity: 'base' }),
  )
}

function normalizeDependencySelection(value, dependencyOptions) {
  const cleanedValue = cleanDependencyLabel(value)
  if (!cleanedValue) return ''

  const normalizedValue = normalizeLooseText(cleanedValue)
  const existingDependency = dependencyOptions.find(
    (option) => normalizeLooseText(option) === normalizedValue,
  )

  return existingDependency ?? cleanedValue
}

function getCanonicalDependencyLabel(value, dependencyOptions) {
  return normalizeDependencySelection(value, dependencyOptions)
}

function slugify(value) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

function isValidUrl(value) {
  try {
    const parsedUrl = new URL(value)
    return parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:'
  } catch {
    return false
  }
}

function fieldClassName(hasError) {
  return `${inputClassName} ${
    hasError
      ? 'border-rose-300 bg-rose-50 focus:border-rose-400 focus:ring-rose-100'
      : ''
  }`
}

function getLogDateKey(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function extractAvailableLogDates(logs) {
  const dateMap = new Map()

  logs.forEach((log) => {
    const key = getLogDateKey(log.created_at)
    if (!key) return

    const current = dateMap.get(key)
    if (current) {
      current.count += 1
      return
    }

    dateMap.set(key, {
      key,
      count: 1,
    })
  })

  return Array.from(dateMap.values()).sort((left, right) => right.key.localeCompare(left.key))
}

function formatSelectedDateLabel(dateKey) {
  if (!dateKey) return 'Fecha no disponible'

  const date = new Date(`${dateKey}T12:00:00`)
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible'

  return new Intl.DateTimeFormat('es-CO', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

function ConsultaResult({ consulta, isSubmitting, onUseSuggestion, quickQuestions }) {
  const statusConfig = getConsultaStatusConfig(consulta?.mensaje_estado)
  const summaryText = consulta ? extractSummaryText(consulta.respuesta) : ''
  const orientationText = compactOrientationText(summaryText)
  const isNoMatch = consulta?.mensaje_estado === 'Sin coincidencias en la base actual'
  const isTooGeneral = consulta?.mensaje_estado === 'Consulta demasiado general'
  const allMatches = consulta
    ? [
        ...(consulta.tramite_principal ? [consulta.tramite_principal] : []),
        ...(consulta.tramites_relacionados ?? []),
      ]
    : []
  const [selectedMatchId, setSelectedMatchId] = useState(null)
  const defaultMatchId =
    consulta?.tramite_principal?.id ?? consulta?.tramites_relacionados?.[0]?.id ?? null
  const activeMatchId = allMatches.some((tramite) => tramite.id === selectedMatchId)
    ? selectedMatchId
    : defaultMatchId

  const activeMatch =
    allMatches.find((tramite) => tramite.id === activeMatchId) ??
    consulta?.tramite_principal ??
    consulta?.tramites_relacionados?.[0] ??
    null
  const secondaryMatches = activeMatch
    ? allMatches.filter((tramite) => tramite.id !== activeMatch.id)
    : allMatches
  const isViewingAlternative =
    Boolean(activeMatch && consulta?.tramite_principal) &&
    activeMatch.id !== consulta.tramite_principal.id
  const missingFields = activeMatch
    ? [
        !activeMatch.descripcion ? 'Descripcion' : null,
        !activeMatch.requisitos ? 'Requisitos' : null,
        !activeMatch.costo ? 'Costo' : null,
        !activeMatch.horario ? 'Horario' : null,
        !activeMatch.fuente_url ? 'Fuente oficial' : null,
      ].filter(Boolean)
    : []

  return (
    <section className="rounded-[2rem] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(248,250,252,0.96)_100%)] p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-700">Respuesta del asistente</p>
          <h3 className="mt-2 text-2xl font-bold text-slate-950">Resultado de la consulta</h3>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Primero ves la guia esencial y luego los datos de apoyo del tramite.
          </p>
        </div>
        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700 shadow-sm">
          Consulta asistida
        </span>
      </div>

      {isSubmitting ? (
        <div className="mt-6 space-y-4">
          <div className="h-6 w-40 animate-pulse rounded-full bg-slate-200" />
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
            <div className="h-4 w-32 animate-pulse rounded-full bg-slate-200" />
            <div className="mt-4 h-4 w-full animate-pulse rounded-full bg-slate-200" />
            <div className="mt-3 h-4 w-5/6 animate-pulse rounded-full bg-slate-200" />
          </div>
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
            <div className="h-4 w-36 animate-pulse rounded-full bg-slate-200" />
            <div className="mt-4 h-4 w-full animate-pulse rounded-full bg-slate-200" />
            <div className="mt-3 h-4 w-4/5 animate-pulse rounded-full bg-slate-200" />
          </div>
        </div>
      ) : consulta ? (
        <div className="mt-6 space-y-6">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.45fr)_minmax(15rem,0.75fr)_minmax(8.5rem,0.4fr)]">
            <ResultMetricCard label="Pregunta" className="bg-[linear-gradient(135deg,#ffffff_0%,#f8fafc_100%)]">
              <p className="text-base font-semibold leading-7 text-slate-950">{consulta.pregunta}</p>
            </ResultMetricCard>

            <ResultMetricCard label="Estado" className="bg-white">
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusConfig.badgeClassName}`}>
                {consulta.mensaje_estado}
              </span>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {consulta.mensaje_estado === 'Coincidencias semanticas encontradas'
                  ? 'El asistente encontro una ruta suficientemente confiable.'
                  : consulta.mensaje_estado === 'Consulta demasiado general'
                    ? 'Necesita una pista mas concreta para responder mejor.'
                    : 'Te muestra caminos cercanos para continuar sin perder el hilo.'}
              </p>
            </ResultMetricCard>

            <ResultMetricCard label="Resultados" className="bg-white">
              <p className="text-4xl font-black tracking-tight text-slate-950">{consulta.total_resultados}</p>
              <p className="mt-1 text-sm text-slate-500">
                {consulta.total_resultados === 1 ? 'resultado util' : 'resultados detectados'}
              </p>
            </ResultMetricCard>
          </div>

          <div className={`relative overflow-hidden rounded-3xl border p-5 ${statusConfig.panelClassName}`}>
            <div className="pointer-events-none absolute inset-y-4 left-4 w-1 rounded-full bg-white/80" />
            <div className="pl-4">
              <p className={`text-xs uppercase tracking-[0.2em] ${statusConfig.labelClassName}`}>Orientacion inmediata</p>
              <p className="mt-2 text-[15px] leading-7 text-slate-800">{orientationText}</p>
            </div>
          </div>

          {activeMatch ? (
            <article className="rounded-[1.9rem] border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#fbfdff_100%)] p-5 shadow-[0_12px_45px_-35px_rgba(15,23,42,0.35)]">
              <div className="flex flex-wrap items-start justify-between gap-4 rounded-[1.6rem] border border-slate-100 bg-[linear-gradient(135deg,#f8fafc_0%,#f1f5f9_100%)] px-5 py-5">
                <div className="max-w-3xl">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    {isViewingAlternative ? 'Coincidencia seleccionada' : 'Tramite principal'}
                  </p>
                  <h4 className="mt-2 text-2xl font-bold leading-tight text-slate-950">
                    {activeMatch.nombre}
                  </h4>
                  <p className="mt-3 inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-sm font-medium text-slate-600 shadow-sm">
                    {cleanDependencyLabel(activeMatch.dependencia)}
                  </p>
                  {isViewingAlternative ? (
                    <p className="mt-3 text-sm leading-6 text-slate-500">
                      Estas viendo otra coincidencia relacionada con la misma consulta. Puedes volver a la principal desde la lista superior.
                    </p>
                  ) : null}
                </div>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-500 shadow-sm">
                  ID {activeMatch.id}
                </span>
              </div>

              <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.78fr)]">
                <div className="grid gap-4">
                  {activeMatch.descripcion ? (
                    <div className="order-2 lg:order-1">
                      <DetailCard
                        label="Descripcion del tramite"
                        value={activeMatch.descripcion}
                        tone="slate"
                      />
                    </div>
                  ) : null}

                  {activeMatch.requisitos ? (
                    <div className="order-1 lg:order-2">
                      <DetailCard
                        label="Requisitos clave"
                        value={activeMatch.requisitos}
                        tone="sky"
                        asList
                      />
                    </div>
                  ) : null}

                  {!activeMatch.descripcion && !activeMatch.requisitos ? (
                    <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-5">
                      <p className="text-sm leading-6 text-slate-600">
                        Este tramite existe en la base, pero todavia no tiene detalle suficiente para mostrar una ficha mas completa.
                      </p>
                    </div>
                  ) : null}
                </div>

                <aside className="space-y-4">
                  {activeMatch.fuente_url ? (
                    <div className="rounded-3xl border border-emerald-200 bg-[linear-gradient(180deg,#ecfdf5_0%,#f8fffb_100%)] p-5 shadow-sm">
                      <p className="text-xs uppercase tracking-[0.18em] text-emerald-700">Validacion oficial</p>
                      <p className="mt-2 text-sm leading-6 text-emerald-900">
                        Revisa la fuente institucional para confirmar el tramite o continuar la gestion.
                      </p>
                      <a
                        href={activeMatch.fuente_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-4 inline-flex items-center rounded-full border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 transition hover:border-emerald-400 hover:bg-emerald-50"
                      >
                        Ir a la fuente oficial
                      </a>
                    </div>
                  ) : null}

                  {activeMatch.costo || activeMatch.horario ? (
                    <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Datos de apoyo</p>
                      <div className="mt-3 space-y-3">
                        {activeMatch.costo ? (
                          <CompactInfoRow
                            label="Costo"
                            value={activeMatch.costo}
                            accent="amber"
                          />
                        ) : null}
                        {activeMatch.horario ? (
                          <CompactInfoRow
                            label="Horario"
                            value={activeMatch.horario}
                            accent="slate"
                          />
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  {missingFields.length ? (
                    <div className="rounded-3xl border border-amber-200 bg-amber-50 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-amber-700">Informacion pendiente</p>
                      <p className="mt-2 text-sm leading-6 text-amber-900">
                        Aun no hay datos registrados para: {missingFields.join(', ')}.
                      </p>
                    </div>
                  ) : null}
                </aside>
              </div>
            </article>
          ) : null}

          {!activeMatch && consulta ? (
            <StateActionPanel
              mode={isTooGeneral ? 'ambigua' : isNoMatch ? 'sin_coincidencia' : 'informativa'}
            />
          ) : null}

          {secondaryMatches.length ? (
            <div className="rounded-3xl border border-slate-200 bg-white/80 p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    Otras coincidencias disponibles
                  </p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Aqui ves opciones cercanas en version resumida. Si quieres revisar otra, usa el boton y reemplazamos la ficha visible.
                  </p>
                </div>
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {secondaryMatches.length} opcion{secondaryMatches.length > 1 ? 'es' : ''}
                </span>
              </div>

              <div className="mt-4 space-y-3">
                {secondaryMatches.map((match, index) => {
                  const isPrimary =
                    consulta.tramite_principal && match.id === consulta.tramite_principal.id

                  return (
                    <div
                      key={match.id}
                      className="rounded-3xl border border-slate-200 bg-slate-50/80 px-4 py-4 text-left transition"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                                isPrimary
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-slate-200 text-slate-700'
                              }`}
                            >
                              {isPrimary ? 'Principal' : `Opcion ${index + 1}`}
                            </span>
                          </div>

                          <h5 className="mt-3 text-sm font-semibold leading-6 text-slate-950">
                            {match.nombre}
                          </h5>
                          <p className="mt-1 text-xs leading-5 text-slate-500">
                            {cleanDependencyLabel(match.dependencia)}
                          </p>
                          {match.descripcion ? (
                            <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">
                              {match.descripcion}
                            </p>
                          ) : null}
                        </div>

                        <div className="flex flex-none items-center">
                          <button
                            type="button"
                            onClick={() => setSelectedMatchId(match.id)}
                            className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-100"
                          >
                            Ver mas informacion
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : null}

          {consulta.sugerencias?.length ? (
            <div className={`rounded-3xl border p-5 ${
              isTooGeneral
                ? 'border-amber-200 bg-amber-50/70'
                : isNoMatch
                  ? 'border-sky-200 bg-sky-50/70'
                  : 'border-slate-200 bg-slate-50'
            }`}>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                {isTooGeneral
                  ? 'Sugerencias para precisar la consulta'
                  : isNoMatch
                    ? 'Rutas sugeridas para seguir buscando'
                    : 'Sugerencias para continuar'}
              </p>
              <p className="mt-3 text-sm font-medium text-slate-700">
                Elige una ruta y la usamos de inmediato.
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {isTooGeneral
                  ? 'Tu pregunta necesita una pista más concreta. Estas opciones te ayudan a aterrizar la intención y llegar más rápido al trámite correcto.'
                  : isNoMatch
                    ? 'No hubo una coincidencia suficientemente confiable, pero estas consultas cercanas pueden ayudarte a llegar al tramite correcto.'
                    : 'Si quieres afinar la consulta o revisar otra ruta cercana, puedes usar una de estas preguntas.'}
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                {consulta.sugerencias.map((sugerencia) => (
                  <button
                    key={sugerencia}
                    type="button"
                    onClick={() => onUseSuggestion(sugerencia)}
                    className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-50"
                  >
                    {sugerencia}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {consulta.tramites_relacionados.length && !consulta.tramite_principal ? (
            <div>
              <p className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                {isTooGeneral ? 'Opciones cercanas para precisar' : 'Coincidencias cercanas detectadas'}
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                {consulta.tramites_relacionados.map((tramite) => (
                  <article key={tramite.id} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_10px_35px_-30px_rgba(15,23,42,0.35)]">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h4 className="text-lg font-semibold text-slate-950">{tramite.nombre}</h4>
                        <p className="mt-2 text-sm text-slate-600">
                          {cleanDependencyLabel(tramite.dependencia)}
                        </p>
                      </div>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-500">
                        ID {tramite.id}
                      </span>
                    </div>
                    {tramite.descripcion ? (
                      <p className="mt-4 text-sm leading-6 text-slate-600">{tramite.descripcion}</p>
                    ) : null}
                    {!consulta.tramite_principal ? (
                      <button
                        type="button"
                        onClick={() => onUseSuggestion(`Consulta por ${tramite.nombre}`)}
                        className="mt-4 inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-100"
                      >
                        Usar esta opcion
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-slate-600">
          La respuesta aparecera aqui cuando envies una consulta al asistente.
          <p className="mt-3 text-sm leading-6 text-slate-500">
            Puedes empezar con una pregunta concreta sobre un impuesto, un tramite o una gestion tributaria.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            {quickQuestions.slice(0, 3).map((quickQuestion) => (
              <button
                key={quickQuestion}
                type="button"
                onClick={() => onUseSuggestion(quickQuestion)}
                className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-50"
              >
                {quickQuestion}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function DetailCardBase({ label, value, tone = 'slate', asList = false }) {
  const tones = {
    slate: 'border-slate-200 bg-white',
    sky: 'border-sky-200 bg-sky-50/55',
  }

  const segments = formatDetailSegments(value, asList)

  return (
    <div className={`rounded-3xl border p-5 shadow-sm ${tones[tone] ?? tones.slate}`}>
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      {segments.length > 1 ? (
        <ul className="mt-4 space-y-3">
          {segments.map((segment) => (
            <li key={`${label}-${segment.slice(0, 24)}`} className="flex items-start gap-3 text-sm leading-6 text-slate-800">
              <span className="mt-2 h-2 w-2 flex-none rounded-full bg-emerald-500" />
              <span>{segment}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-7 text-slate-800">{segments[0] ?? value}</p>
      )}
    </div>
  )
}

function DetailCard({ label, value, tone, asList }) {
  return <DetailCardBase label={label} value={value} tone={tone} asList={asList} />
}

function ResultMetricCard({ label, children, className = '' }) {
  return (
    <div className={`flex h-full flex-col justify-between rounded-3xl border border-slate-200 p-4 shadow-sm ${className}`}>
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function CompactInfoRow({ label, value, accent = 'slate' }) {
  const accents = {
    amber: 'bg-amber-100/80 text-amber-900',
    slate: 'bg-slate-200/80 text-slate-700',
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
          <p className="mt-1 text-sm font-medium leading-6 text-slate-800">{value}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${accents[accent] ?? accents.slate}`}>
          {label}
        </span>
      </div>
    </div>
  )
}

function StateActionPanel({ mode }) {
  const content = {
    ambigua: {
      badge: 'Consulta demasiado general',
      badgeClassName: 'border-amber-200 bg-amber-50 text-amber-700',
      title: 'Necesitamos una pista mas especifica',
      description:
        'Todavia no conviene mostrar una ficha completa porque la consulta puede apuntar a varios tramites distintos.',
      promptGuide: 'Prueba una estructura corta como: impuesto + gestion + contexto.',
      promptExample: 'Ejemplo: requisitos para paz y salvo predial',
      tips: [
        'Menciona el impuesto o tramite concreto que necesitas.',
        'Agrega una pista como predial, paz y salvo, industria y comercio o devolucion.',
        'Usa una de las sugerencias rapidas para aterrizar la intencion.',
      ],
    },
    sin_coincidencia: {
      badge: 'Sin coincidencia suficiente',
      badgeClassName: 'border-sky-200 bg-sky-50 text-sky-700',
      title: 'No encontramos un tramite confiable todavia',
      description:
        'Preferimos no inventar una respuesta. Abajo te dejamos rutas cercanas para que llegues al tramite correcto con menos ensayo y error.',
      promptGuide: 'Reformula la consulta con el nombre del impuesto o la gestion esperada.',
      promptExample: 'Ejemplo: devolucion de pagos en exceso del impuesto predial',
      tips: [
        'Prueba una consulta mas concreta o enfocada en el impuesto.',
        'Usa las sugerencias disponibles para acercarte al catalogo actual.',
        'Si el tramite es nuevo, conviene revisar si su descripcion quedo demasiado corta.',
      ],
    },
    informativa: {
      badge: 'Consulta en revision',
      badgeClassName: 'border-slate-200 bg-slate-50 text-slate-700',
      title: 'Estamos guiando la siguiente accion',
      description:
        'Todavia no hay una ficha principal visible, pero abajo tienes opciones cercanas para continuar la consulta.',
      promptGuide: '',
      promptExample: '',
      tips: [],
    },
  }

  const current = content[mode] ?? content.informativa

  return (
    <div className="rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] p-5 shadow-sm">
      <div>
        <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${current.badgeClassName}`}>
          {current.badge}
        </span>
        <h4 className="mt-3 text-xl font-semibold text-slate-950">{current.title}</h4>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{current.description}</p>
      </div>

      {current.promptGuide ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Como reformular mejor
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-700">{current.promptGuide}</p>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-900">{current.promptExample}</p>
        </div>
      ) : null}

      {current.tips.length ? (
        <ul className="mt-4 grid gap-3 md:grid-cols-3">
          {current.tips.map((tip, index) => (
            <li key={tip} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-700">
              <span className="mb-2 inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-xs font-semibold text-slate-500">
                {index + 1}
              </span>
              <p>{tip}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function formatDetailSegments(value, asList = false) {
  const text = String(value ?? '').replace(/\r/g, '').trim()
  if (!text) return []

  if (!asList) {
    const paragraphs = text
      .split('\n')
      .map((segment) => segment.trim())
      .filter(Boolean)

    return paragraphs.length ? paragraphs : [text]
  }

  const normalized = text
    .replace(/\n+/g, '\n')
    .replace(/\s+[•·]\s+/g, '\n')
    .replace(/\s+-\s+/g, '\n')

  const segments = normalized
    .split('\n')
    .map((segment) => segment.replace(/^\d+[).:-]?\s*/, '').trim())
    .filter(Boolean)

  return segments.length ? segments : [text]
}

function compactOrientationText(value) {
  const normalized = String(value ?? '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalized) {
    return 'Todavia no hay una orientacion disponible para esta consulta.'
  }

  const sentences = normalized
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean)

  const compact = sentences.slice(0, 2).join(' ')

  if (compact.length <= 220) {
    return compact
  }

  return `${compact.slice(0, 217).trimEnd()}...`
}

function TramitesPanel({ tramites, loadingTramites, tramitesError }) {
  const dependencyOptions = buildDependencyOptions(tramites)
  if (loadingTramites) return <LoadingPanel title="Base de consulta disponible" />
  if (tramitesError) return <Message tone="error">{tramitesError}</Message>
  if (!tramites.length) {
    return (
      <EmptyPanel
        title="Base de consulta disponible"
        body="Todavia no hay tramites activos cargados para consulta ciudadana."
      />
    )
  }
  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-white/80 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Tramites activos</p>
      <h2 className="mt-2 text-2xl font-bold text-slate-950">Base de consulta disponible</h2>
      <div className="mt-6 grid gap-4">
        {tramites.map((tramite) => (
          <article key={tramite.id} className="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900">{tramite.nombre}</h3>
                <p className="mt-2 text-sm text-slate-600">
                  {getCanonicalDependencyLabel(tramite.dependencia, dependencyOptions)}
                </p>
              </div>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ID {tramite.id}</span>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{tramite.descripcion || 'Sin descripcion disponible.'}</p>
          </article>
        ))}
      </div>
    </div>
  )
}

function TramitesAdminList({
  tramites,
  loadingTramites,
  tramitesError,
  editingId,
  deletingId,
  onEdit,
  onDelete,
  hasActiveFilters,
  catalogAttentionById,
}) {
  const dependencyOptions = buildDependencyOptions(tramites)
  if (loadingTramites) return <LoadingPanel title="Tramites disponibles" />
  if (tramitesError) return <Message tone="error">{tramitesError}</Message>
  if (!tramites.length) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
        <p className="text-base font-semibold text-slate-700">
          {hasActiveFilters ? 'No hay tramites para los filtros actuales.' : 'No hay tramites activos registrados.'}
        </p>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          {hasActiveFilters
            ? 'Prueba otra combinacion de busqueda o dependencia para seguir revisando la base administrativa.'
            : 'Usa el formulario de la izquierda para crear el primer tramite estrella y comenzar a poblar la base administrativa.'}
        </p>
      </div>
    )
  }
  return (
    <div className="grid gap-4">
        {tramites.map((tramite) => (
          <article key={tramite.id} className={`rounded-3xl border px-5 py-5 ${editingId === tramite.id ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50'}`}>
            {(() => {
            const qualityReport = getTramiteQualitySnapshot(tramite)
            const catalogSignal = catalogAttentionById?.get(tramite.id)
              return (
                <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-lg font-semibold text-slate-900">{tramite.nombre}</h4>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ID {tramite.id}</span>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                  qualityReport.level === 'fuerte'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : qualityReport.level === 'estable'
                      ? 'border-sky-200 bg-sky-50 text-sky-700'
                      : qualityReport.level === 'en_riesgo'
                        ? 'border-amber-200 bg-amber-50 text-amber-700'
                        : 'border-rose-200 bg-rose-50 text-rose-700'
                }`}>
                  {humanizeQualityLevel(qualityReport.level)} - {qualityReport.score}
                </span>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${scopeBadgeClassName(qualityReport.scopeStatus)}`}>
                  {humanizeScopeStatus(qualityReport.scopeStatus)}
                </span>
                {catalogSignal ? (
                  <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-rose-700">
                    Impacto real {catalogSignal.hits}
                  </span>
                ) : null}
              </div>
              <p className="text-sm text-slate-600">
                {getCanonicalDependencyLabel(tramite.dependencia, dependencyOptions)}
              </p>
            </div>
            <div className="flex w-full flex-wrap gap-2 sm:w-auto">
              <button type="button" onClick={() => onEdit(tramite)} className="inline-flex flex-1 items-center justify-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-white sm:flex-none">Editar</button>
              <button type="button" onClick={() => onDelete(tramite)} disabled={deletingId === tramite.id} className="inline-flex flex-1 items-center justify-center rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none">
                {deletingId === tramite.id ? 'Desactivando...' : 'Desactivar'}
              </button>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">{tramite.descripcion || 'Sin descripcion disponible.'}</p>
          {qualityReport.alerts.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {qualityReport.alerts.slice(0, 3).map((alert) => (
                <span key={alert} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600">
                  {alert}
                </span>
              ))}
            </div>
          ) : null}
          {catalogSignal ? (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">
                Senal desde preguntas reales
              </p>
              <p className="mt-2 text-sm leading-6 text-rose-900">
                {catalogSignal.headline}
              </p>
              <p className="mt-2 text-sm leading-6 text-rose-800">
                Ejemplo: "{catalogSignal.example}"
              </p>
            </div>
          ) : null}
          <p className="mt-4 text-sm leading-6 text-slate-600">
            Accion sugerida: <span className="font-medium text-slate-800">{qualityReport.recommendedAction}</span>
          </p>
              </>
            )
          })()}
        </article>
      ))}
    </div>
  )
}

function ConsultaActivityPanel({ logs, tramites, loading, error, onRefresh, className = '' }) {
  const [expandedLogId, setExpandedLogId] = useState(null)
  const [statusFilter, setStatusFilter] = useState('todas')
  const [showAllLogs, setShowAllLogs] = useState(false)
  const [selectedLogDate, setSelectedLogDate] = useState('')
  const availableLogDates = extractAvailableLogDates(logs)
  const effectiveSelectedLogDate = availableLogDates.some((option) => option.key === selectedLogDate)
    ? selectedLogDate
    : availableLogDates[0]?.key ?? ''

  const dateScopedLogs = effectiveSelectedLogDate
    ? logs.filter((log) => getLogDateKey(log.created_at) === effectiveSelectedLogDate)
    : logs
  const stats = dateScopedLogs.reduce(
    (summary, log) => {
      if (isPositiveLogStatus(log.mensaje_estado)) summary.positivas += 1
      else if (isAmbiguousLogStatus(log.mensaje_estado)) summary.ambiguas += 1
      else if (isNoMatchLogStatus(log.mensaje_estado)) summary.sinCoincidencia += 1
      return summary
    },
    { positivas: 0, ambiguas: 0, sinCoincidencia: 0 },
  )
  const filteredLogs = dateScopedLogs.filter((log) => matchesLogFilter(log, statusFilter))
  const visibleLogs = showAllLogs ? filteredLogs : filteredLogs.slice(0, 4)
  const groupedVisibleLogs = groupLogsByDate(visibleLogs)
  const problematicPatterns = buildProblematicPatterns(dateScopedLogs)
  const questionInsights = buildQuestionInsights(dateScopedLogs, tramites)
  const catalogAttention = buildCatalogAttention(dateScopedLogs, tramites)
  const totalQuestionsInView = dateScopedLogs.length || 1
  const questionInsightSeries = [
    {
      key: 'wellDetailed',
      label: 'Bien detalladas',
      value: questionInsights.wellDetailed,
      tone: 'emerald',
      description: 'Preguntas con contexto suficiente que el asistente resolvio bien.',
      example: questionInsights.examples.wellDetailed,
    },
    {
      key: 'tooGeneral',
      label: 'Muy generales',
      value: questionInsights.tooGeneral,
      tone: 'amber',
      description: 'Consultas amplias que necesitan una pista mas concreta del ciudadano.',
      example: questionInsights.examples.tooGeneral,
    },
    {
      key: 'possibleDescriptionGap',
      label: 'Posible falta de descripcion',
      value: questionInsights.possibleDescriptionGap,
      tone: 'rose',
      description: 'Preguntas razonables que no lograron una respuesta clara y conviene revisar contra el catalogo.',
      example: questionInsights.examples.possibleDescriptionGap,
    },
    {
      key: 'shortQuestions',
      label: 'Preguntas cortas',
      value: questionInsights.shortQuestions,
      tone: 'slate',
      description: 'Mensajes muy breves que suelen requerir apoyo de sugerencias o desambiguacion.',
      example: questionInsights.examples.shortQuestions,
    },
  ]
  const statusSeries = [
    { key: 'positivas', label: 'Positivas', value: stats.positivas, tone: 'emerald' },
    { key: 'ambiguas', label: 'Ambiguas', value: stats.ambiguas, tone: 'amber' },
    { key: 'sinCoincidencia', label: 'Sin coincidencia', value: stats.sinCoincidencia, tone: 'slate' },
  ]
  const filters = [
    { id: 'todas', label: 'Todas', count: dateScopedLogs.length },
    { id: 'positivas', label: 'Positivas', count: stats.positivas },
    { id: 'ambiguas', label: 'Ambiguas', count: stats.ambiguas },
    { id: 'sin_coincidencia', label: 'Sin coincidencia', count: stats.sinCoincidencia },
  ]

  return (
    <section className={`rounded-[2rem] border border-slate-200/70 bg-white/85 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur ${className}`}>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Actividad del asistente</p>
          <h3 className="mt-2 text-2xl font-bold text-slate-950">Consultas recientes</h3>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Esta vista nos ayuda a observar preguntas reales, detectar ambiguedades y confirmar si el sistema esta respondiendo con el tramite correcto.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            Actualizar actividad
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedLogDate(availableLogDates[0]?.key ?? '')
              setStatusFilter('todas')
              setShowAllLogs(false)
              setExpandedLogId(null)
            }}
            className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            Ir al ultimo dia con actividad
          </button>
        </div>
      </div>

      {!loading && !error && logs.length ? (
        <div className="mb-6 rounded-3xl border border-slate-200 bg-slate-50 p-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">
                Seleccionar fecha de consulta
              </span>
              <input
                type="date"
                className={inputClassName}
                value={effectiveSelectedLogDate}
                onChange={(event) => {
                  setSelectedLogDate(event.target.value)
                  setShowAllLogs(false)
                  setExpandedLogId(null)
                }}
              />
            </label>

            <div className="rounded-3xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Dia seleccionado
              </p>
              <h4 className="mt-2 text-lg font-semibold text-slate-950">
                {effectiveSelectedLogDate ? formatSelectedDateLabel(effectiveSelectedLogDate) : 'Sin fecha seleccionada'}
              </h4>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {dateScopedLogs.length
                  ? `Hay ${dateScopedLogs.length} consulta(s) registradas en esta fecha antes de aplicar el filtro por estado.`
                  : 'No hubo consultas registradas en esta fecha. Puedes elegir otro dia para revisar actividad real.'}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && !error && logs.length && catalogAttention.items.length ? (
        <div className="mb-6 rounded-3xl border border-rose-200 bg-[linear-gradient(180deg,#fff5f5_0%,#fffdfd_100%)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-700">
                Tramites que estas preguntas estan golpeando
              </p>
              <h4 className="mt-2 text-lg font-semibold text-slate-950">
                Revisiones sugeridas por actividad real
              </h4>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-600">
              Si una pregunta es razonable y aun asi termina ambigua o sin coincidencia, aqui te mostramos el tramite que mas conviene reforzar primero.
            </p>
          </div>

          <div className="mt-4 grid gap-3 xl:grid-cols-3">
            {catalogAttention.items.map((item) => (
              <article key={`attention-${item.tramite.id}`} className="rounded-3xl border border-rose-200 bg-white px-4 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">
                    {item.hits} senal(es)
                  </span>
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${scopeBadgeClassName(item.report.scopeStatus)}`}>
                    {humanizeScopeStatus(item.report.scopeStatus)}
                  </span>
                </div>
                <h5 className="mt-3 text-sm font-semibold leading-6 text-slate-950">
                  {item.tramite.nombre}
                </h5>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {cleanDependencyLabel(item.tramite.dependencia)}
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-700">{item.headline}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Ejemplo: "{item.example}"
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-800">
                  Accion sugerida: <span className="font-medium">{item.recommendedAction}</span>
                </p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {!loading && !error && logs.length ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <MetricCard label="Positivas" value={String(stats.positivas)} tone="emerald" />
          <MetricCard label="Ambiguas" value={String(stats.ambiguas)} tone="amber" />
          <MetricCard label="Sin coincidencia" value={String(stats.sinCoincidencia)} tone="slate" />
        </div>
      ) : null}

      {!loading && !error && logs.length ? (
        <div className="mb-6 rounded-3xl border border-slate-200 bg-slate-50 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Estadisticas de preguntas
              </p>
              <h4 className="mt-2 text-lg font-semibold text-slate-950">
                Como estan preguntando los ciudadanos
              </h4>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-500">
              Aqui separamos preguntas bien detalladas, consultas generales y casos donde una pregunta razonable sigue sin respuesta clara, porque eso suele apuntar a una descripcion debil del tramite.
            </p>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <QuestionInsightChart
              total={totalQuestionsInView}
              title="Distribucion visual del dia"
              description="Esta barra resume de forma grafica como se repartieron las preguntas segun su nivel de claridad."
              items={questionInsightSeries}
            />

            <div className="grid gap-3 xl:grid-cols-2">
              {questionInsightSeries.map((item) => (
                <QuestionInsightCard
                  key={item.key}
                  title={item.label}
                  value={item.value}
                  tone={item.tone}
                  description={item.description}
                  example={item.example}
                  total={totalQuestionsInView}
                />
              ))}
            </div>
          </div>

          <div className="mt-4">
            <QuestionInsightChart
              total={totalQuestionsInView}
              title="Estado de respuesta del asistente"
              description="Asi se repartieron los resultados entre respuestas positivas, consultas ambiguas y casos sin coincidencia."
              items={statusSeries}
              compact
            />
          </div>
        </div>
      ) : null}

      {loading ? <LoadingPanel title="Consultas recientes" /> : null}
      {!loading && error ? <Message tone="error">{error}</Message> : null}
      {!loading && !error && !logs.length ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <p className="text-base font-semibold text-slate-700">Aun no hay actividad registrada.</p>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            Las consultas realizadas por los ciudadanos comenzaran a verse aqui para apoyar el seguimiento del sistema.
          </p>
        </div>
      ) : null}

      {!loading && !error && logs.length ? (
        <div className="space-y-5">
          {problematicPatterns.length ? (
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Patrones problematicos
                  </p>
                  <h4 className="mt-2 text-lg font-semibold text-slate-950">
                    Consultas que conviene revisar primero
                  </h4>
                </div>
                <p className="text-sm text-slate-500">
                  Priorizamos ambiguedades, no coincidencias y repeticiones con riesgo real.
                </p>
              </div>

              <div className="mt-4 grid gap-3 xl:grid-cols-3">
                {problematicPatterns.map((pattern) => (
                  <div key={pattern.key} className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold leading-6 text-slate-900">{pattern.display}</p>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        {pattern.count}
                      </span>
                    </div>
                    <p className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-500">
                      {pattern.lastStatus}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            {filters.map((filter) => (
              <button
                key={filter.id}
                type="button"
                onClick={() => {
                  setStatusFilter(filter.id)
                  setShowAllLogs(false)
                  setExpandedLogId(null)
                }}
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition ${
                  statusFilter === filter.id
                    ? 'border-slate-950 bg-slate-950 text-white'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'
                }`}
              >
                <span>{filter.label}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs ${statusFilter === filter.id ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-500'}`}>
                  {filter.count}
                </span>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
            <p>Mostrando {filteredLogs.length} consulta(s) para el filtro actual.</p>
            <p>Despliega una tarjeta para ver la pregunta, el resumen y las opciones sugeridas.</p>
          </div>

          <div className="space-y-5">
            {groupedVisibleLogs.map((group) => (
              <section key={group.key} className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Fecha de consulta
                    </p>
                    <h5 className="mt-2 text-lg font-semibold text-slate-950">{group.label}</h5>
                  </div>
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {group.logs.length} consulta(s)
                  </span>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  {group.logs.map((log) => {
                    const statusConfig = getConsultaLogStatusConfig(log.mensaje_estado)
                    const isExpanded = expandedLogId === log.id
                    return (
                      <article key={log.id} className="rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#f8fafc_55%,#f1f5f9_100%)] px-5 py-5">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div className="space-y-3">
                            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusConfig.badgeClassName}`}>
                              {log.mensaje_estado}
                            </span>
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                                Tramite principal detectado
                              </p>
                              <h4 className="mt-2 text-lg font-semibold leading-7 text-slate-950">
                                {log.tramite_principal_nombre || 'Sin tramite principal'}
                              </h4>
                            </div>
                          </div>

                          <div className="flex flex-col items-start gap-3 sm:items-end">
                            <div className="text-right text-xs uppercase tracking-[0.18em] text-slate-500">
                              <p>{formatLogTime(log.created_at)}</p>
                              <p className={`mt-2 inline-flex rounded-full border px-3 py-1 ${originBadgeClassName(log.origen_respuesta)}`}>
                                {humanizeResponseOrigin(log.origen_respuesta)}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                              className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-100"
                            >
                              {isExpanded ? 'Ocultar detalle' : 'Ver pregunta'}
                            </button>
                          </div>
                        </div>

                        <div className="mt-5 flex flex-wrap gap-3">
                          <LogPill label="Resultados" value={String(log.total_resultados)} />
                          <LogPill
                            label="Origen"
                            value={humanizeResponseOrigin(log.origen_respuesta)}
                            toneClassName={originPillClassName(log.origen_respuesta)}
                            hint={describeResponseOrigin(log.origen_respuesta)}
                          />
                          <LogPill label="Estado" value={shortStatusLabel(log.mensaje_estado)} />
                        </div>

                        {isExpanded ? (
                          <div className="mt-5 space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
                            <div>
                              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                                Pregunta realizada por el ciudadano
                              </p>
                              <p className="mt-3 text-sm font-medium leading-7 text-slate-900">
                                {log.pregunta}
                              </p>
                            </div>

                            {log.resumen_respuesta ? (
                              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                                  Resumen entregado por el asistente
                                </p>
                                <p className="mt-3 text-sm leading-7 text-slate-700">
                                  {log.resumen_respuesta}
                                </p>
                              </div>
                            ) : null}

                            {log.tramites_relacionados?.length ? (
                              <div>
                                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                                  Tramites relacionados mostrados
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  {log.tramites_relacionados.map((tramiteRelacionado) => (
                                    <span
                                      key={`${log.id}-tramite-${tramiteRelacionado}`}
                                      className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700"
                                    >
                                      {tramiteRelacionado}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}

                            {log.sugerencias?.length ? (
                              <div>
                                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                                  Sugerencias mostradas al ciudadano
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  {log.sugerencias.map((sugerencia) => (
                                    <span
                                      key={`${log.id}-sugerencia-${sugerencia}`}
                                      className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700"
                                    >
                                      {sugerencia}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>

          {filteredLogs.length > 4 ? (
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Navegacion de consultas
                  </p>
                  <p className="mt-2 text-sm text-slate-700">
                    {showAllLogs
                      ? `Estas viendo las ${filteredLogs.length} consultas del filtro actual.`
                      : `Estas viendo 4 de ${filteredLogs.length} consultas del filtro actual.`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAllLogs((current) => !current)}
                  className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-100"
                >
                  {showAllLogs ? 'Mostrar solo 4' : `Ver ${filteredLogs.length - 4} mas`}
                </button>
              </div>
            </div>
          ) : null}

          {!filteredLogs.length ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
              <p className="text-base font-semibold text-slate-700">
                {dateScopedLogs.length
                  ? 'No hay consultas para este filtro.'
                  : 'No hubo consultas en la fecha seleccionada.'}
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-500">
                {dateScopedLogs.length
                  ? 'Prueba con otro estado para seguir revisando el comportamiento del asistente.'
                  : 'Cambia la fecha en el calendario para revisar otro dia con actividad.'}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function LogPill({ label, value, hint = '', toneClassName = '' }) {
  return (
    <div className={`min-w-[11rem] rounded-2xl border border-slate-200 bg-white px-4 py-3 ${toneClassName}`}>
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-slate-800">{value}</p>
      {hint ? <p className="mt-1 text-xs leading-5 text-slate-500">{hint}</p> : null}
    </div>
  )
}

function QuestionInsightChart({ title, description, items, total, compact = false }) {
  return (
    <section className={`rounded-3xl border border-slate-200 bg-white ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            {title}
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
          {total} preguntas
        </span>
      </div>

      <div className="mt-4 overflow-hidden rounded-full border border-slate-200 bg-slate-100">
        <div className={`flex ${compact ? 'h-4' : 'h-5'}`}>
          {items.map((item) => (
            <div
              key={item.key}
              className={chartSegmentClassName(item.tone)}
              style={{ width: `${calculateInsightPercent(item.value, total)}%` }}
              title={`${item.label}: ${item.value}`}
            />
          ))}
        </div>
      </div>

      <div className={`mt-4 grid gap-3 ${compact ? 'md:grid-cols-3' : 'sm:grid-cols-2'}`}>
        {items.map((item) => (
          <div key={`legend-${item.key}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className={`h-3 w-3 rounded-full ${chartDotClassName(item.tone)}`} />
                <span className="text-sm font-semibold text-slate-800">{item.label}</span>
              </div>
              <span className="text-sm font-black text-slate-950">{item.value}</span>
            </div>
            <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">
              {calculateInsightPercent(item.value, total)}% del total
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}

function QuestionInsightCard({ title, value, description, example, tone, total }) {
  const tones = {
    emerald: {
      card: 'border-emerald-200 bg-white',
      badge: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      progress: 'bg-emerald-500',
    },
    amber: {
      card: 'border-amber-200 bg-white',
      badge: 'border-amber-200 bg-amber-50 text-amber-700',
      progress: 'bg-amber-500',
    },
    rose: {
      card: 'border-rose-200 bg-white',
      badge: 'border-rose-200 bg-rose-50 text-rose-700',
      progress: 'bg-rose-500',
    },
    slate: {
      card: 'border-slate-200 bg-white',
      badge: 'border-slate-200 bg-slate-50 text-slate-700',
      progress: 'bg-slate-500',
    },
  }

  const styles = tones[tone] ?? tones.slate

  return (
    <article className={`rounded-3xl border p-4 ${styles.card}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            {title}
          </p>
          <p className="mt-3 text-3xl font-black text-slate-950">{value}</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${styles.badge}`}>
          {calculateInsightPercent(value, total)}%
        </span>
      </div>
      <div className="mt-4 overflow-hidden rounded-full border border-slate-200 bg-slate-100">
        <div
          className={`h-3 rounded-full ${styles.progress}`}
          style={{ width: `${calculateInsightPercent(value, total)}%` }}
        />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
      {example ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Ejemplo reciente
          </p>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-800">{example}</p>
        </div>
      ) : (
        <p className="mt-4 text-xs leading-5 text-slate-500">
          Todavia no hay un ejemplo reciente en esta fecha.
        </p>
      )}
    </article>
  )
}

function calculateInsightPercent(value, total) {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

function chartSegmentClassName(tone) {
  if (tone === 'emerald') return 'bg-emerald-500'
  if (tone === 'amber') return 'bg-amber-500'
  if (tone === 'rose') return 'bg-rose-500'
  return 'bg-slate-500'
}

function chartDotClassName(tone) {
  if (tone === 'emerald') return 'bg-emerald-500'
  if (tone === 'amber') return 'bg-amber-500'
  if (tone === 'rose') return 'bg-rose-500'
  return 'bg-slate-500'
}

function AdminAccessPanel({
  pin,
  onPinChange,
  onSubmit,
  isBusy,
  error,
  hasRestorableWorkspace,
}) {
  return (
    <section className="mx-auto max-w-3xl rounded-[2rem] border border-slate-200/70 bg-white/85 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Acceso administrativo privado</p>
          <h2 className="mt-2 text-3xl font-bold text-slate-950">Desbloquea el panel interno</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Este apartado ya no es solo visual: para crear, editar, desactivar tramites o revisar actividad interna necesitamos una sesion privada valida.
          </p>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-right">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Proteccion activa</p>
          <p className="text-sm font-semibold text-emerald-900">PIN + sesion temporal</p>
        </div>
      </div>

      {hasRestorableWorkspace ? (
        <div className="mt-6 rounded-3xl border border-sky-200 bg-sky-50 px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">
            Borrador protegido
          </p>
          <p className="mt-2 text-sm leading-6 text-sky-900">
            Conservamos tu formulario, filtros y modo de edicion. Cuando abras de nuevo el panel privado retomaras exactamente donde ibas.
          </p>
        </div>
      ) : null}

      <form className="mt-8 space-y-4" onSubmit={onSubmit}>
        <Field
          label="PIN administrativo"
          required
          hint="Usamos una sesion privada temporal para que el acceso interno no quede expuesto."
          error={error}
        >
          <input
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            className={fieldClassName(error)}
            value={pin}
            onChange={(event) => onPinChange(event.target.value)}
            placeholder="Ingresa el PIN del panel admin"
          />
        </Field>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={isBusy}
            className="inline-flex w-full items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400 sm:w-auto"
          >
            {isBusy ? 'Validando acceso...' : 'Abrir panel privado'}
          </button>
          <span className="text-sm text-slate-500">
            Solo despues de validar el PIN se habilitan los endpoints administrativos.
          </span>
        </div>
      </form>
    </section>
  )
}

function LoadingPanel({ title }) {
  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-white/80 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">{title}</p>
      <div className="mt-6 space-y-3">
        {[1, 2, 3].map((item) => <div key={item} className="h-20 animate-pulse rounded-3xl bg-slate-100" />)}
      </div>
    </div>
  )
}

function EmptyPanel({ title, body }) {
  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-white/80 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">{title}</p>
      <div className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
        <p className="text-base font-semibold text-slate-700">Sin informacion disponible</p>
        <p className="mt-3 text-sm leading-6 text-slate-500">{body}</p>
      </div>
    </div>
  )
}

function readStoredAdminSessionExpiresAt() {
  if (typeof window === 'undefined') return null

  const rawValue = window.sessionStorage.getItem(ADMIN_SESSION_EXPIRES_AT_STORAGE_KEY)
  if (!rawValue) return null

  const parsedValue = Number(rawValue)
  if (!Number.isFinite(parsedValue) || parsedValue <= 0) return null

  return parsedValue
}

function readStoredAdminWorkspace() {
  if (typeof window === 'undefined') return EMPTY_ADMIN_WORKSPACE

  const rawValue = window.sessionStorage.getItem(ADMIN_WORKSPACE_STORAGE_KEY)
  if (!rawValue) return EMPTY_ADMIN_WORKSPACE

  try {
    const parsed = JSON.parse(rawValue)
    return {
      formData: {
        ...EMPTY_FORM,
        ...(parsed?.formData ?? {}),
      },
      editingId: Number.isInteger(parsed?.editingId) ? parsed.editingId : null,
      slugTouched: Boolean(parsed?.slugTouched),
      adminSearch: typeof parsed?.adminSearch === 'string' ? parsed.adminSearch : '',
      adminDependency:
        typeof parsed?.adminDependency === 'string' && parsed.adminDependency
          ? parsed.adminDependency
          : 'todas',
    }
  } catch {
    return EMPTY_ADMIN_WORKSPACE
  }
}

function hasStoredAdminWorkspace({ formData, editingId, adminSearch, adminDependency }) {
  const hasMeaningfulFormData = Object.values(formData ?? {}).some((value) =>
    typeof value === 'string' ? value.trim() : Boolean(value),
  )

  return (
    hasMeaningfulFormData ||
    Boolean(editingId) ||
    Boolean((adminSearch ?? '').trim()) ||
    adminDependency !== 'todas'
  )
}

function resolveSessionExpiryTimestamp(sessionPayload) {
  if (sessionPayload?.expires_at) {
    return Number(sessionPayload.expires_at) * 1000
  }

  if (sessionPayload?.expires_in_seconds) {
    return Date.now() + Number(sessionPayload.expires_in_seconds) * 1000
  }

  return null
}

function getRemainingSeconds(expiresAt) {
  if (!expiresAt) return 0
  return Math.max(Math.ceil((expiresAt - Date.now()) / 1000), 0)
}

function formatSessionCountdown(remainingSeconds) {
  if (!remainingSeconds) return 'Sesion expirada'

  const minutes = Math.floor(remainingSeconds / 60)
  const seconds = remainingSeconds % 60
  return `Tiempo restante ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function getSessionProgress(remainingSeconds) {
  const trialWindowSeconds = 5 * 60
  return Math.max(Math.min((remainingSeconds / trialWindowSeconds) * 100, 100), 0)
}

function getSessionToneClassName(remainingSeconds) {
  if (remainingSeconds <= 60) {
    return {
      panel: 'border-rose-200 bg-rose-50',
      eyebrow: 'text-rose-700',
      label: 'text-rose-900',
      bar: 'bg-rose-500',
      hint: 'text-rose-700',
    }
  }

  if (remainingSeconds <= 180) {
    return {
      panel: 'border-amber-200 bg-amber-50',
      eyebrow: 'text-amber-700',
      label: 'text-amber-900',
      bar: 'bg-amber-500',
      hint: 'text-amber-700',
    }
  }

  return {
    panel: 'border-emerald-200 bg-emerald-50',
    eyebrow: 'text-emerald-700',
    label: 'text-emerald-900',
    bar: 'bg-emerald-500',
    hint: 'text-emerald-700',
  }
}

function Callout() {
  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-[linear-gradient(135deg,#0f172a_0%,#1f2937_50%,#1a4334_100%)] p-6 text-white shadow-[0_25px_80px_-45px_rgba(15,23,42,0.7)]">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-200">Foco actual</p>
      <h2 className="mt-2 text-2xl font-bold">Claridad, precision y experiencia</h2>
      <p className="mt-4 text-sm leading-6 text-slate-200">
        La arquitectura RAG ya funciona; ahora estamos puliendo la forma en que se muestran los resultados, la desambiguacion de consultas y la experiencia del ciudadano.
      </p>
    </div>
  )
}

function formatLogDate(value) {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Fecha no disponible'
  }

  return new Intl.DateTimeFormat('es-CO', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

function formatLogTime(value) {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Hora no disponible'
  }

  return new Intl.DateTimeFormat('es-CO', {
    timeStyle: 'short',
  }).format(date)
}

function humanizeResponseOrigin(origin) {
  const mapping = {
    semantica: 'Recuperacion semantica',
    textual: 'Respaldo textual',
    clarificacion: 'Solicitud de precision',
    sin_coincidencias: 'Sin coincidencia suficiente',
    desconocido: 'Origen no identificado',
  }

  return mapping[origin] ?? origin
}

function describeResponseOrigin(origin) {
  const mapping = {
    semantica: 'Entendio la intencion por contexto y similitud semantica.',
    textual: 'Gano una coincidencia mas literal del catalogo.',
    clarificacion: 'La consulta era amplia y el sistema prefirio pedir precision.',
    sin_coincidencias: 'No encontro una ruta lo bastante confiable para responder.',
    desconocido: 'Conviene revisar este caso porque no quedo clasificado.',
  }

  return mapping[origin] ?? 'Origen sin descripcion disponible.'
}

function originPillClassName(origin) {
  if (origin === 'semantica') return 'border-emerald-200 bg-emerald-50/70'
  if (origin === 'textual') return 'border-sky-200 bg-sky-50/70'
  if (origin === 'clarificacion') return 'border-amber-200 bg-amber-50/70'
  if (origin === 'sin_coincidencias') return 'border-slate-200 bg-slate-50'
  return 'border-rose-200 bg-rose-50/70'
}

function originBadgeClassName(origin) {
  if (origin === 'semantica') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (origin === 'textual') return 'border-sky-200 bg-sky-50 text-sky-700'
  if (origin === 'clarificacion') return 'border-amber-200 bg-amber-50 text-amber-700'
  if (origin === 'sin_coincidencias') return 'border-slate-200 bg-slate-100 text-slate-700'
  return 'border-rose-200 bg-rose-50 text-rose-700'
}

function shortStatusLabel(messageStatus) {
  const mapping = {
    'Coincidencias semanticas encontradas': 'Coincidencia valida',
    'Coincidencias encontradas': 'Coincidencia valida',
    'Consulta demasiado general': 'Falta precision',
    'Sin coincidencias en la base actual': 'Sin coincidencia',
  }

  return mapping[messageStatus] ?? messageStatus
}

function matchesLogFilter(log, filter) {
  if (filter === 'todas') return true
  if (filter === 'positivas') return isPositiveLogStatus(log.mensaje_estado)
  if (filter === 'ambiguas') return isAmbiguousLogStatus(log.mensaje_estado)
  if (filter === 'sin_coincidencia') return isNoMatchLogStatus(log.mensaje_estado)
  return true
}

function buildProblematicPatterns(logs) {
  const counts = new Map()

  logs.forEach((log) => {
    const normalizedQuestion = normalizePatternQuestion(log.pregunta)
    const severity = getPatternSeverity(log)
    const current = counts.get(normalizedQuestion)

    if (current) {
      current.count += 1
      current.lastStatus = shortStatusLabel(log.mensaje_estado)
      current.severity += severity
      return
    }

    counts.set(normalizedQuestion, {
      key: normalizedQuestion,
      display: log.pregunta,
      count: 1,
      lastStatus: shortStatusLabel(log.mensaje_estado),
      severity,
    })
  })

  return Array.from(counts.values())
    .filter((pattern) => pattern.severity > 1 || pattern.count > 1)
    .sort((left, right) => {
      if (right.severity !== left.severity) return right.severity - left.severity
      return right.count - left.count
    })
    .slice(0, 3)
}

function buildQuestionInsights(logs, tramites = []) {
  const summary = {
    wellDetailed: 0,
    tooGeneral: 0,
    possibleDescriptionGap: 0,
    shortQuestions: 0,
    examples: {
      wellDetailed: '',
      tooGeneral: '',
      possibleDescriptionGap: '',
      shortQuestions: '',
    },
  }

  logs.forEach((log) => {
    const wordCount = countQuestionWords(log.pregunta)
    const normalizedQuestion = (log.pregunta ?? '').trim()
    const isPositive = isPositiveLogStatus(log.mensaje_estado)
    const isGeneral = isAmbiguousLogStatus(log.mensaje_estado)
    const isNoMatch = isNoMatchLogStatus(log.mensaje_estado)
    const isWellDetailedQuestion = wordCount >= 5
    const isShortQuestion = wordCount > 0 && wordCount <= 2

    if (isPositive && isWellDetailedQuestion) {
      summary.wellDetailed += 1
      if (!summary.examples.wellDetailed) {
        summary.examples.wellDetailed = normalizedQuestion
      }
    }

    if (isGeneral) {
      summary.tooGeneral += 1
      if (!summary.examples.tooGeneral) {
        summary.examples.tooGeneral = normalizedQuestion
      }
    }

    const likelyCatalogCandidates = findLikelyTramitesForQuestion(normalizedQuestion, tramites)
    const canBlameCatalog = likelyCatalogCandidates.some((candidate) => candidate.score >= 2)

    if ((isNoMatch || isGeneral) && wordCount >= 4 && canBlameCatalog) {
      summary.possibleDescriptionGap += 1
      if (!summary.examples.possibleDescriptionGap) {
        summary.examples.possibleDescriptionGap = normalizedQuestion
      }
    }

    if (isShortQuestion) {
      summary.shortQuestions += 1
      if (!summary.examples.shortQuestions) {
        summary.examples.shortQuestions = normalizedQuestion
      }
    }
  })

  return summary
}

function countQuestionWords(question) {
  return (question ?? '')
    .trim()
    .split(/\s+/)
    .filter(Boolean).length
}

function buildCatalogAttention(logs, tramites) {
  const attentionById = new Map()

  logs.forEach((log) => {
    if (!isCatalogAttentionLog(log)) return

    const candidates = findLikelyTramitesForQuestion(log.pregunta, tramites)
      .filter((candidate) => candidate.score >= 2)
      .slice(0, 3)

    candidates.forEach((candidate, index) => {
      const current = attentionById.get(candidate.tramite.id)
      const weight = index === 0 ? 2 : 1

      if (current) {
        current.hits += weight
        if (isNoMatchLogStatus(log.mensaje_estado)) current.noMatchCount += 1
        if (isAmbiguousLogStatus(log.mensaje_estado)) current.ambiguityCount += 1
        if (countQuestionWords(log.pregunta) >= 5) current.detailedMissCount += 1
        return
      }

      attentionById.set(candidate.tramite.id, {
        tramite: candidate.tramite,
        report: getTramiteQualitySnapshot(candidate.tramite),
        hits: weight,
        noMatchCount: isNoMatchLogStatus(log.mensaje_estado) ? 1 : 0,
        ambiguityCount: isAmbiguousLogStatus(log.mensaje_estado) ? 1 : 0,
        detailedMissCount: countQuestionWords(log.pregunta) >= 5 ? 1 : 0,
        example: log.pregunta,
      })
    })
  })

  const items = Array.from(attentionById.values())
    .map((item) => {
      const likelyCause =
        item.report.scopeStatus === 'fuera_de_foco'
          ? 'fuera_de_foco'
          : item.report.level === 'critico' || item.report.level === 'en_riesgo'
            ? 'catalogo_debil'
            : item.noMatchCount >= item.ambiguityCount
              ? 'falta_de_precision_del_catalogo'
              : 'necesita_mas_claves_ciudadanas'

      return {
        ...item,
        likelyCause,
        headline: buildCatalogAttentionHeadline(item, likelyCause),
        recommendedAction: buildCatalogAttentionAction(item, likelyCause),
      }
    })
    .sort((left, right) => {
      if (right.hits !== left.hits) return right.hits - left.hits
      if (right.detailedMissCount !== left.detailedMissCount) {
        return right.detailedMissCount - left.detailedMissCount
      }
      if (left.report.score !== right.report.score) return left.report.score - right.report.score
      return left.tramite.nombre.localeCompare(right.tramite.nombre, 'es-CO', {
        sensitivity: 'base',
      })
    })

  const byId = new Map(items.map((item) => [item.tramite.id, item]))

  return {
    items: items.slice(0, 4),
    byId,
  }
}

function isCatalogAttentionLog(log) {
  const isProblematicStatus =
    isNoMatchLogStatus(log.mensaje_estado) ||
    isAmbiguousLogStatus(log.mensaje_estado)

  return isProblematicStatus && countQuestionWords(log.pregunta) >= 4
}

function isPositiveLogStatus(messageStatus) {
  return (
    messageStatus === 'Coincidencias semanticas encontradas' ||
    messageStatus === 'Coincidencias encontradas'
  )
}

function isAmbiguousLogStatus(messageStatus) {
  return messageStatus === 'Consulta demasiado general'
}

function isNoMatchLogStatus(messageStatus) {
  return messageStatus === 'Sin coincidencias en la base actual'
}

function findLikelyTramitesForQuestion(question, tramites) {
  const questionTokens = extractMeaningfulTokens(question)

  return tramites
    .map((tramite) => {
      const source = [
        tramite.nombre,
        tramite.descripcion,
        tramite.requisitos,
        tramite.dependencia,
      ]
        .filter(Boolean)
        .join(' ')
      const catalogTokens = extractMeaningfulTokens(source)
      const overlap = questionTokens.filter((token) => catalogTokens.includes(token))
      const score = new Set(overlap).size

      return {
        tramite,
        score,
      }
    })
    .filter((candidate) => candidate.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score
      return left.tramite.nombre.localeCompare(right.tramite.nombre, 'es-CO', {
        sensitivity: 'base',
      })
    })
}

function extractMeaningfulTokens(value) {
  const stopwords = new Set([
    'al',
    'algo',
    'ante',
    'aqui',
    'con',
    'como',
    'cual',
    'cuanto',
    'de',
    'del',
    'desde',
    'donde',
    'el',
    'en',
    'es',
    'esta',
    'este',
    'hay',
    'hoy',
    'impuesto',
    'la',
    'las',
    'lo',
    'los',
    'mas',
    'mi',
    'necesito',
    'para',
    'pero',
    'por',
    'que',
    'quiero',
    'se',
    'ser',
    'sin',
    'sobre',
    'tengo',
    'tramite',
    'una',
    'uno',
    'uso',
    'ver',
    'ya',
  ])

  return normalizeLooseText(value)
    .split(/\s+/)
    .map((token) => token.replace(/[^a-z0-9-]/g, '').trim())
    .filter((token) => token.length >= 4 && !stopwords.has(token))
}

function buildCatalogAttentionHeadline(item, likelyCause) {
  if (likelyCause === 'fuera_de_foco') {
    return 'Las preguntas reales lo estan tocando, pero su contexto se ve fuera del foco tributario de Hacienda.'
  }

  if (likelyCause === 'catalogo_debil') {
    return 'Las preguntas ciudadanas ya lo estan rozando y la ficha todavia necesita mas contexto para responder con firmeza.'
  }

  if (likelyCause === 'falta_de_precision_del_catalogo') {
    return 'La gente pregunta con bastante contexto, pero el catalogo aun no devuelve una coincidencia suficientemente clara.'
  }

  return 'Las preguntas se acercan a este tramite, pero todavia hace falta mas lenguaje ciudadano para conectar mejor la intencion.'
}

function buildCatalogAttentionAction(item, likelyCause) {
  if (likelyCause === 'fuera_de_foco') {
    return 'Revisa si este tramite debe seguir en el panel de Hacienda o si conviene moverlo a otro catalogo institucional.'
  }

  if (likelyCause === 'catalogo_debil') {
    return 'Fortalece descripcion, requisitos y fuente oficial con lenguaje ciudadano parecido al ejemplo detectado.'
  }

  if (likelyCause === 'falta_de_precision_del_catalogo') {
    return 'Agrega a la descripcion palabras y escenarios reales de la consulta ciudadana para reducir los casos sin coincidencia.'
  }

  return 'Refuerza la descripcion con sinonimos ciudadanos y ejemplos de uso para que el asistente reconozca mejor la intencion.'
}

function normalizePatternQuestion(question) {
  return question
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function groupLogsByDate(logs) {
  const groups = new Map()

  logs.forEach((log) => {
    const key = getLogDateKey(log.created_at) || 'fecha-no-disponible'
    const currentGroup = groups.get(key)

    if (currentGroup) {
      currentGroup.logs.push(log)
      return
    }

    groups.set(key, {
      key,
      label: formatLogDate(log.created_at),
      logs: [log],
    })
  })

  return Array.from(groups.values())
}

function getPatternSeverity(log) {
  if (isAmbiguousLogStatus(log.mensaje_estado)) return 3
  if (isNoMatchLogStatus(log.mensaje_estado)) return 4
  if (log.total_resultados > 1) return 2
  return 0
}

function extractSummaryText(responseText) {
  if (!responseText) {
    return 'Todavia no hay una respuesta disponible para esta consulta.'
  }

  const [summary] = responseText.split('\n\nTramite principal:')
  return summary.trim() || responseText
}

function getConsultaStatusConfig(messageStatus) {
  if (messageStatus === 'Consulta demasiado general') {
    return {
      badgeClassName: 'border-amber-200 bg-amber-50 text-amber-700',
      panelClassName: 'border-amber-200 bg-amber-50',
      labelClassName: 'text-amber-700',
      panelLabel: 'Necesitamos mas precision',
    }
  }

  if (messageStatus === 'Sin coincidencias en la base actual') {
    return {
      badgeClassName: 'border-rose-200 bg-rose-50 text-rose-700',
      panelClassName: 'border-rose-200 bg-rose-50',
      labelClassName: 'text-rose-700',
      panelLabel: 'Sin coincidencia suficiente',
    }
  }

  return {
    badgeClassName: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    panelClassName: 'border-emerald-200 bg-emerald-50',
    labelClassName: 'text-emerald-700',
    panelLabel: 'Orientacion del asistente',
  }
}

function getConsultaLogStatusConfig(messageStatus) {
  if (isPositiveLogStatus(messageStatus)) {
    return {
      badgeClassName: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    }
  }

  if (isAmbiguousLogStatus(messageStatus)) {
    return {
      badgeClassName: 'border-amber-200 bg-amber-50 text-amber-700',
    }
  }

  return {
    badgeClassName: 'border-slate-200 bg-slate-100 text-slate-700',
  }
}

function Message({ children, tone }) {
  const tones = {
    error: 'mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700',
    success: 'mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700',
  }
  return <p className={tones[tone]}>{children}</p>
}

function MetricCard({ label, value, tone }) {
  const tones = {
    emerald: {
      card: 'border-emerald-200 bg-emerald-50 text-emerald-950',
      label: 'text-emerald-900',
      value: 'text-emerald-950',
    },
    amber: {
      card: 'border-amber-200 bg-amber-50 text-amber-950',
      label: 'text-amber-900',
      value: 'text-amber-950',
    },
    slate: {
      card: 'border-slate-200 bg-slate-100 text-slate-950',
      label: 'text-slate-800',
      value: 'text-slate-950',
    },
  }

  const styles = tones[tone]

  return (
    <div className={`rounded-3xl border px-4 py-4 ${styles.card}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${styles.label}`}>{label}</p>
      <p className={`mt-2 text-2xl font-black ${styles.value}`}>{value}</p>
    </div>
  )
}

function Field({
  label,
  children,
  className = '',
  required = false,
  hint = '',
  error = '',
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label} {required ? <span className="text-rose-500">*</span> : null}
      </span>
      {children}
      {hint ? <span className="mt-2 block text-xs text-slate-500">{hint}</span> : null}
      {error ? <span className="mt-2 block text-xs font-medium text-rose-600">{error}</span> : null}
    </label>
  )
}

export default App
