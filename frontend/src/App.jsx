import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
const DEFAULT_QUESTION = 'Quiero informacion sobre impuesto predial'
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
  fuente_url: '',
}

function App() {
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
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [editingId, setEditingId] = useState(null)
  const [adminError, setAdminError] = useState('')
  const [adminMessage, setAdminMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [adminFieldErrors, setAdminFieldErrors] = useState(EMPTY_ADMIN_ERRORS)
  const [slugTouched, setSlugTouched] = useState(false)

  useEffect(() => {
    refreshTramites()
  }, [])

  useEffect(() => {
    if (view === 'admin' && (!hasLoadedConsultaLogs || consultaLogsStale)) {
      refreshConsultaLogs()
    }
  }, [view, hasLoadedConsultaLogs, consultaLogsStale])

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

  async function refreshConsultaLogs() {
    setLoadingConsultaLogs(true)
    setConsultaLogsError('')
    try {
      const response = await fetch(`${API_URL}/admin/consultas`)
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
      const response = await fetch(endpoint, {
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
      const response = await fetch(`${API_URL}/admin/tramites/${tramite.id}`, { method: 'DELETE' })
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
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f8f4ea_0%,#eef5f3_45%,#dfe8ea_100%)] text-slate-900">
      <div className="mx-auto flex min-h-screen w-full max-w-[1680px] flex-col gap-8 px-4 py-8 lg:px-8 xl:px-10">
        <header className="overflow-hidden rounded-[2rem] border border-white/70 bg-white/75 p-6 shadow-[0_25px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <span className="inline-flex w-fit rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                Iteracion 4 en optimizacion
              </span>
              <div className="space-y-3">
                <h1 className="max-w-3xl text-4xl font-black tracking-tight text-slate-950 md:text-5xl">
                  Asistente de tramites estrella para rentas e impuestos
                </h1>
                <p className="max-w-3xl text-base leading-7 text-slate-600 md:text-lg">
                  El sistema ya cuenta con consulta semantica, respuestas RAG y panel administrativo; ahora estamos afinando claridad, precision y experiencia de uso.
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard label="API" value="Activa" tone="emerald" />
              <MetricCard label="Tramites activos" value={loadingTramites ? '...' : String(tramites.length)} tone="amber" />
              <MetricCard label="Vista" value={view === 'ciudadania' ? 'Consulta' : 'Admin'} tone="slate" />
            </div>
          </div>
        </header>

        <nav className="flex flex-wrap gap-3" aria-label="Cambiar vista del sistema">
          <ViewButton active={view === 'ciudadania'} onClick={() => setView('ciudadania')}>
            Vista ciudadana
          </ViewButton>
          <ViewButton active={view === 'admin'} onClick={() => setView('admin')}>
            Panel administrativo
          </ViewButton>
        </nav>

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
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Endpoint actual</p>
                      <p className="text-sm font-semibold text-slate-700">POST /api/consulta</p>
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
                  </form>

                  {consultaError ? <Message tone="error">{consultaError}</Message> : null}
                </div>

                <ConsultaResult consulta={consulta} isSubmitting={isSubmitting} onUseSuggestion={setQuestion} />
              </section>

              <aside className="space-y-6">
                <TramitesPanel tramites={tramites} loadingTramites={loadingTramites} tramitesError={tramitesError} />
                <Callout />
              </aside>
            </div>
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
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Endpoints usados</p>
                    <p className="text-sm font-semibold text-slate-700">POST / PUT / DELETE</p>
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
                </div>

                <form className="mt-8 grid gap-4 md:grid-cols-2" onSubmit={handleAdminSubmit}>
                  <Field label="Nombre" required error={adminFieldErrors.nombre}>
                    <input className={fieldClassName(adminFieldErrors.nombre)} name="nombre" value={formData.nombre} onChange={handleInputChange} />
                  </Field>
                  <Field label="Slug" required hint="Si no lo escribes manualmente, se genera a partir del nombre." error={adminFieldErrors.slug}>
                    <input className={fieldClassName(adminFieldErrors.slug)} name="slug" value={formData.slug} onChange={handleInputChange} />
                  </Field>
                  <Field label="Dependencia" required error={adminFieldErrors.dependencia}>
                    <input className={fieldClassName(adminFieldErrors.dependencia)} name="dependencia" value={formData.dependencia} onChange={handleInputChange} />
                  </Field>
                  <Field label="Fuente oficial" hint="Opcional. Usa una URL completa con http o https." error={adminFieldErrors.fuente_url}>
                    <input className={fieldClassName(adminFieldErrors.fuente_url)} name="fuente_url" value={formData.fuente_url} onChange={handleInputChange} />
                  </Field>
                  <Field label="Costo"><input className={inputClassName} name="costo" value={formData.costo} onChange={handleInputChange} /></Field>
                  <Field label="Horario"><input className={inputClassName} name="horario" value={formData.horario} onChange={handleInputChange} /></Field>
                  <Field className="md:col-span-2" label="Descripcion"><textarea className={`${inputClassName} min-h-28`} name="descripcion" value={formData.descripcion} onChange={handleInputChange} /></Field>
                  <Field className="md:col-span-2" label="Requisitos"><textarea className={`${inputClassName} min-h-28`} name="requisitos" value={formData.requisitos} onChange={handleInputChange} /></Field>
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

                <TramitesAdminList
                  tramites={tramites}
                  loadingTramites={loadingTramites}
                  tramitesError={tramitesError}
                  editingId={editingId}
                  deletingId={deletingId}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              </section>

              <ConsultaActivityPanel
                logs={consultaLogs}
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

  if (payload.fuente_url && !isValidUrl(payload.fuente_url)) {
    errors.fuente_url = 'La fuente oficial debe ser una URL valida con http o https.'
  }

  return errors
}

function hasAdminErrors(errors) {
  return Object.values(errors).some(Boolean)
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

function ConsultaResult({ consulta, isSubmitting, onUseSuggestion }) {
  const statusConfig = getConsultaStatusConfig(consulta?.mensaje_estado)
  const summaryText = consulta ? extractSummaryText(consulta.respuesta) : ''
  const availableFields = consulta?.tramite_principal
    ? [
        { label: 'Descripcion', value: consulta.tramite_principal.descripcion },
        { label: 'Requisitos', value: consulta.tramite_principal.requisitos },
        { label: 'Costo', value: consulta.tramite_principal.costo },
        { label: 'Horario', value: consulta.tramite_principal.horario },
      ].filter((item) => item.value)
    : []
  const missingFields = consulta?.tramite_principal
    ? [
        !consulta.tramite_principal.descripcion ? 'Descripcion' : null,
        !consulta.tramite_principal.requisitos ? 'Requisitos' : null,
        !consulta.tramite_principal.costo ? 'Costo' : null,
        !consulta.tramite_principal.horario ? 'Horario' : null,
        !consulta.tramite_principal.fuente_url ? 'Fuente oficial' : null,
      ].filter(Boolean)
    : []

  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-slate-950 p-6 text-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-300">Respuesta actual</p>
          <h3 className="mt-2 text-2xl font-bold">Resultado de la consulta</h3>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300">RAG conectado al backend</span>
      </div>

      {isSubmitting ? (
        <div className="mt-6 space-y-4">
          <div className="h-6 w-40 animate-pulse rounded-full bg-white/10" />
          <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <div className="h-4 w-32 animate-pulse rounded-full bg-white/10" />
            <div className="mt-4 h-4 w-full animate-pulse rounded-full bg-white/10" />
            <div className="mt-3 h-4 w-5/6 animate-pulse rounded-full bg-white/10" />
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <div className="h-4 w-36 animate-pulse rounded-full bg-white/10" />
            <div className="mt-4 h-4 w-full animate-pulse rounded-full bg-white/10" />
            <div className="mt-3 h-4 w-4/5 animate-pulse rounded-full bg-white/10" />
          </div>
        </div>
      ) : consulta ? (
        <div className="mt-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusConfig.badgeClassName}`}>
              {consulta.mensaje_estado}
            </span>
            <span className="text-sm text-slate-300">
              {consulta.total_resultados} coincidencia(s)
            </span>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-300">Pregunta enviada</p>
            <p className="mt-2 text-lg font-medium text-white">{consulta.pregunta}</p>
          </div>

          <div className={`rounded-3xl border p-5 ${statusConfig.panelClassName}`}>
            <p className={`text-xs uppercase tracking-[0.2em] ${statusConfig.labelClassName}`}>{statusConfig.panelLabel}</p>
            <p className="mt-3 text-base leading-7 text-white">{summaryText}</p>
          </div>

          {consulta.sugerencias?.length ? (
            <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-300">
                Sugerencias para continuar
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                {consulta.sugerencias.map((sugerencia) => (
                  <button
                    key={sugerencia}
                    type="button"
                    onClick={() => onUseSuggestion(sugerencia)}
                    className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:border-emerald-300 hover:bg-emerald-400/20"
                  >
                    {sugerencia}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {consulta.tramite_principal ? (
            <article className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-300">
                    Tramite principal
                  </p>
                  <h4 className="mt-2 text-xl font-semibold text-white">
                    {consulta.tramite_principal.nombre}
                  </h4>
                  <p className="mt-2 text-sm text-slate-300">
                    {consulta.tramite_principal.dependencia}
                  </p>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-300">
                  ID {consulta.tramite_principal.id}
                </span>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {availableFields.length ? (
                  availableFields.map((field) => (
                    <DetailCard key={field.label} label={field.label} value={field.value} />
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 p-4 md:col-span-2">
                    <p className="text-sm leading-6 text-slate-300">
                      Este tramite existe en la base, pero todavia no tiene detalles ampliados para mostrar en esta vista.
                    </p>
                  </div>
                )}
              </div>

              {missingFields.length ? (
                <div className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-amber-200">Informacion pendiente</p>
                  <p className="mt-2 text-sm leading-6 text-amber-50">
                    Aun no hay datos registrados para: {missingFields.join(', ')}.
                  </p>
                </div>
              ) : null}

              {consulta.tramite_principal.fuente_url ? (
                <a
                  href={consulta.tramite_principal.fuente_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-5 inline-flex text-sm font-semibold text-emerald-300 transition hover:text-emerald-200"
                >
                  Ver fuente oficial
                </a>
              ) : null}
            </article>
          ) : null}

          {consulta.tramites_relacionados.length ? (
            <div>
              <p className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">
                {consulta.tramite_principal ? 'Tramites relacionados' : 'Opciones cercanas para precisar'}
              </p>
              <div className="grid gap-4">
                {consulta.tramites_relacionados.map((tramite) => (
                  <article key={tramite.id} className="rounded-3xl border border-white/10 bg-white/5 p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h4 className="text-lg font-semibold text-white">{tramite.nombre}</h4>
                        <p className="mt-2 text-sm text-slate-300">{tramite.dependencia}</p>
                      </div>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-300">ID {tramite.id}</span>
                    </div>
                    {!consulta.tramite_principal ? (
                      <button
                        type="button"
                        onClick={() => onUseSuggestion(`Consulta por ${tramite.nombre}`)}
                        className="mt-4 inline-flex items-center rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:border-emerald-300 hover:bg-emerald-400/20"
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
        <div className="mt-6 rounded-3xl border border-dashed border-white/20 bg-white/5 p-8 text-center text-slate-300">
          La respuesta aparecera aqui cuando envies una consulta al asistente.
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Puedes empezar con una pregunta sobre impuesto predial, facilidades
            de pago o devolucion de pagos en exceso.
          </p>
        </div>
      )}
    </div>
  )
}

function DetailCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-300">{label}</p>
      <p className="mt-2 text-sm leading-6 text-white">{value}</p>
    </div>
  )
}

function TramitesPanel({ tramites, loadingTramites, tramitesError }) {
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
                <p className="mt-2 text-sm text-slate-600">{tramite.dependencia}</p>
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

function TramitesAdminList({ tramites, loadingTramites, tramitesError, editingId, deletingId, onEdit, onDelete }) {
  if (loadingTramites) return <LoadingPanel title="Tramites disponibles" />
  if (tramitesError) return <Message tone="error">{tramitesError}</Message>
  if (!tramites.length) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
        <p className="text-base font-semibold text-slate-700">
          No hay tramites activos registrados.
        </p>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          Usa el formulario de la izquierda para crear el primer tramite
          estrella y comenzar a poblar la base administrativa.
        </p>
      </div>
    )
  }
  return (
    <div className="grid gap-4">
      {tramites.map((tramite) => (
        <article key={tramite.id} className={`rounded-3xl border px-5 py-5 ${editingId === tramite.id ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50'}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-lg font-semibold text-slate-900">{tramite.nombre}</h4>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ID {tramite.id}</span>
              </div>
              <p className="text-sm text-slate-600">{tramite.dependencia}</p>
            </div>
            <div className="flex w-full flex-wrap gap-2 sm:w-auto">
              <button type="button" onClick={() => onEdit(tramite)} className="inline-flex flex-1 items-center justify-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-white sm:flex-none">Editar</button>
              <button type="button" onClick={() => onDelete(tramite)} disabled={deletingId === tramite.id} className="inline-flex flex-1 items-center justify-center rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none">
                {deletingId === tramite.id ? 'Desactivando...' : 'Desactivar'}
              </button>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">{tramite.descripcion || 'Sin descripcion disponible.'}</p>
        </article>
      ))}
    </div>
  )
}

function ConsultaActivityPanel({ logs, loading, error, onRefresh, className = '' }) {
  const [expandedLogId, setExpandedLogId] = useState(null)
  const [statusFilter, setStatusFilter] = useState('todas')
  const [showAllLogs, setShowAllLogs] = useState(false)
  const stats = logs.reduce(
    (summary, log) => {
      if (log.mensaje_estado === 'Coincidencias semanticas encontradas') summary.positivas += 1
      else if (log.mensaje_estado === 'Consulta demasiado general') summary.ambiguas += 1
      else summary.sinCoincidencia += 1
      return summary
    },
    { positivas: 0, ambiguas: 0, sinCoincidencia: 0 },
  )
  const filteredLogs = logs.filter((log) => matchesLogFilter(log, statusFilter))
  const visibleLogs = showAllLogs ? filteredLogs : filteredLogs.slice(0, 4)
  const groupedVisibleLogs = groupLogsByDate(visibleLogs)
  const problematicPatterns = buildProblematicPatterns(logs)
  const filters = [
    { id: 'todas', label: 'Todas', count: logs.length },
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
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
        >
          Actualizar actividad
        </button>
      </div>

      {!loading && !error && logs.length ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <MetricCard label="Positivas" value={String(stats.positivas)} tone="emerald" />
          <MetricCard label="Ambiguas" value={String(stats.ambiguas)} tone="amber" />
          <MetricCard label="Sin coincidencia" value={String(stats.sinCoincidencia)} tone="slate" />
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
            <p>Despliega una tarjeta para ver la pregunta exacta del ciudadano.</p>
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
                              <p className="mt-2">{humanizeResponseOrigin(log.origen_respuesta)}</p>
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
                          <LogPill label="Origen" value={humanizeResponseOrigin(log.origen_respuesta)} />
                          <LogPill label="Estado" value={shortStatusLabel(log.mensaje_estado)} />
                        </div>

                        {isExpanded ? (
                          <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                              Pregunta realizada por el ciudadano
                            </p>
                            <p className="mt-3 text-sm font-medium leading-7 text-slate-900">
                              {log.pregunta}
                            </p>
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
              <p className="text-base font-semibold text-slate-700">No hay consultas para este filtro.</p>
              <p className="mt-3 text-sm leading-6 text-slate-500">
                Prueba con otro estado para seguir revisando el comportamiento del asistente.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function LogPill({ label, value }) {
  return (
    <div className="min-w-[11rem] rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-slate-800">{value}</p>
    </div>
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

function shortStatusLabel(messageStatus) {
  const mapping = {
    'Coincidencias semanticas encontradas': 'Coincidencia valida',
    'Consulta demasiado general': 'Falta precision',
    'Sin coincidencias en la base actual': 'Sin coincidencia',
  }

  return mapping[messageStatus] ?? messageStatus
}

function matchesLogFilter(log, filter) {
  if (filter === 'todas') return true
  if (filter === 'positivas') return log.mensaje_estado === 'Coincidencias semanticas encontradas'
  if (filter === 'ambiguas') return log.mensaje_estado === 'Consulta demasiado general'
  if (filter === 'sin_coincidencia') return log.mensaje_estado === 'Sin coincidencias en la base actual'
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
    const date = new Date(log.created_at)
    const key = Number.isNaN(date.getTime()) ? 'fecha-no-disponible' : date.toISOString().slice(0, 10)
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
  if (log.mensaje_estado === 'Consulta demasiado general') return 3
  if (log.mensaje_estado === 'Sin coincidencias en la base actual') return 4
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
      badgeClassName: 'border-amber-300/30 bg-amber-300/10 text-amber-200',
      panelClassName: 'border-amber-300/30 bg-amber-300/10',
      labelClassName: 'text-amber-200',
      panelLabel: 'Necesitamos mas precision',
    }
  }

  if (messageStatus === 'Sin coincidencias en la base actual') {
    return {
      badgeClassName: 'border-rose-300/30 bg-rose-300/10 text-rose-200',
      panelClassName: 'border-rose-300/30 bg-rose-300/10',
      labelClassName: 'text-rose-200',
      panelLabel: 'Sin coincidencia suficiente',
    }
  }

  return {
    badgeClassName: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
    panelClassName: 'border-emerald-400/20 bg-emerald-400/10',
    labelClassName: 'text-emerald-200',
    panelLabel: 'Orientacion del asistente',
  }
}

function getConsultaLogStatusConfig(messageStatus) {
  if (messageStatus === 'Coincidencias semanticas encontradas') {
    return {
      badgeClassName: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    }
  }

  if (messageStatus === 'Consulta demasiado general') {
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

function ViewButton({ active, children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-5 py-3 text-sm font-semibold transition ${active ? 'bg-slate-950 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'}`}
    >
      {children}
    </button>
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
