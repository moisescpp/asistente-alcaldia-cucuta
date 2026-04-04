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

function App() {
  const [view, setView] = useState('ciudadania')
  const [tramites, setTramites] = useState([])
  const [loadingTramites, setLoadingTramites] = useState(true)
  const [tramitesError, setTramitesError] = useState('')
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

  useEffect(() => {
    refreshTramites()
  }, [])

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
      setConsulta(await response.json())
    } catch (error) {
      setConsultaError(error instanceof Error ? error.message : 'Ocurrio un error al consultar el asistente.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleInputChange(event) {
    const { name, value } = event.target
    setFormData((current) => ({ ...current, [name]: value }))
  }

  function handleResetForm() {
    setEditingId(null)
    setFormData(EMPTY_FORM)
    setAdminError('')
    setAdminMessage('')
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
    setAdminError('')
    setAdminMessage(`Editando "${tramite.nombre}".`)
    setView('admin')
  }

  async function handleAdminSubmit(event) {
    event.preventDefault()
    const payload = normalizePayload(formData)
    if (!payload.nombre || !payload.slug) {
      setAdminError('Nombre y slug son obligatorios.')
      return
    }

    setIsSaving(true)
    setAdminError('')
    setAdminMessage('')
    const endpoint = editingId ? `${API_URL}/admin/tramites/${editingId}` : `${API_URL}/admin/tramites`
    const method = editingId ? 'PUT' : 'POST'

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        throw new Error(editingId ? 'No fue posible actualizar el tramite.' : 'No fue posible crear el tramite.')
      }

      const savedTramite = await response.json()
      await refreshTramites()
      setAdminMessage(editingId ? `Tramite "${savedTramite.nombre}" actualizado.` : `Tramite "${savedTramite.nombre}" creado.`)
      handleResetForm()
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
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-8 px-4 py-8 lg:px-8">
        <header className="overflow-hidden rounded-[2rem] border border-white/70 bg-white/75 p-6 shadow-[0_25px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <span className="inline-flex w-fit rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                Iteracion 2 en construccion
              </span>
              <div className="space-y-3">
                <h1 className="max-w-3xl text-4xl font-black tracking-tight text-slate-950 md:text-5xl">
                  Asistente de tramites estrella para rentas e impuestos
                </h1>
                <p className="max-w-3xl text-base leading-7 text-slate-600 md:text-lg">
                  Ya tenemos consulta ciudadana y una primera vista administrativa conectadas al backend real.
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

        <nav className="flex flex-wrap gap-3">
          <ViewButton active={view === 'ciudadania'} onClick={() => setView('ciudadania')}>
            Vista ciudadana
          </ViewButton>
          <ViewButton active={view === 'admin'} onClick={() => setView('admin')}>
            Panel administrativo
          </ViewButton>
        </nav>

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
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Endpoint actual</p>
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
                    <button type="submit" disabled={isSubmitting} className="inline-flex items-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
                      {isSubmitting ? 'Consultando...' : 'Consultar asistente'}
                    </button>
                    <button type="button" onClick={() => setQuestion(DEFAULT_QUESTION)} className="inline-flex items-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50">
                      Usar ejemplo
                    </button>
                  </div>
                </form>

                {consultaError ? <Message tone="error">{consultaError}</Message> : null}
              </div>

              <ConsultaResult consulta={consulta} />
            </section>

            <aside className="space-y-6">
              <TramitesPanel tramites={tramites} loadingTramites={loadingTramites} tramitesError={tramitesError} />
              <Callout />
            </aside>
          </div>
        ) : (
          <div className="grid gap-8 lg:grid-cols-[1.05fr_1fr]">
            <section className="rounded-[2rem] border border-slate-200/70 bg-white/85 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Panel administrativo inicial</p>
                  <h2 className="mt-2 text-3xl font-bold text-slate-950">Gestion de tramites estrella</h2>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Endpoints usados</p>
                  <p className="text-sm font-semibold text-slate-700">POST / PUT / DELETE</p>
                </div>
              </div>

              <form className="mt-8 grid gap-4 md:grid-cols-2" onSubmit={handleAdminSubmit}>
                <Field label="Nombre" required><input className={inputClassName} name="nombre" value={formData.nombre} onChange={handleInputChange} /></Field>
                <Field label="Slug" required><input className={inputClassName} name="slug" value={formData.slug} onChange={handleInputChange} /></Field>
                <Field label="Dependencia"><input className={inputClassName} name="dependencia" value={formData.dependencia} onChange={handleInputChange} /></Field>
                <Field label="Fuente oficial"><input className={inputClassName} name="fuente_url" value={formData.fuente_url} onChange={handleInputChange} /></Field>
                <Field label="Costo"><input className={inputClassName} name="costo" value={formData.costo} onChange={handleInputChange} /></Field>
                <Field label="Horario"><input className={inputClassName} name="horario" value={formData.horario} onChange={handleInputChange} /></Field>
                <Field className="md:col-span-2" label="Descripcion"><textarea className={`${inputClassName} min-h-28`} name="descripcion" value={formData.descripcion} onChange={handleInputChange} /></Field>
                <Field className="md:col-span-2" label="Requisitos"><textarea className={`${inputClassName} min-h-28`} name="requisitos" value={formData.requisitos} onChange={handleInputChange} /></Field>

                <div className="md:col-span-2">
                  <div className="flex flex-wrap items-center gap-3">
                    <button type="submit" disabled={isSaving} className="inline-flex items-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
                      {isSaving ? 'Guardando...' : editingId ? 'Actualizar tramite' : 'Crear tramite'}
                    </button>
                    <button type="button" onClick={handleResetForm} className="inline-flex items-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50">
                      Limpiar formulario
                    </button>
                  </div>

                  {adminMessage ? <Message tone="success">{adminMessage}</Message> : null}
                  {adminError ? <Message tone="error">{adminError}</Message> : null}
                </div>
              </form>
            </section>

            <aside className="rounded-[2rem] border border-slate-200/70 bg-white/85 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
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
            </aside>
          </div>
        )}
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

function ConsultaResult({ consulta }) {
  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-slate-950 p-6 text-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-300">Respuesta actual</p>
          <h3 className="mt-2 text-2xl font-bold">Resultado de la consulta</h3>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300">MVP conectado al backend</span>
      </div>

      {consulta ? (
        <div className="mt-6 space-y-6">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-300">Pregunta enviada</p>
            <p className="mt-2 text-lg font-medium text-white">{consulta.pregunta}</p>
          </div>
          <div className="rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">Respuesta del asistente</p>
            <p className="mt-3 text-base leading-7 text-emerald-50">{consulta.respuesta}</p>
          </div>
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
              </article>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-6 rounded-3xl border border-dashed border-white/20 bg-white/5 p-8 text-center text-slate-300">
          La respuesta aparecera aqui cuando envies una consulta al asistente.
        </div>
      )}
    </div>
  )
}

function TramitesPanel({ tramites, loadingTramites, tramitesError }) {
  if (loadingTramites) return <LoadingPanel title="Base de consulta disponible" />
  if (tramitesError) return <Message tone="error">{tramitesError}</Message>
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
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => onEdit(tramite)} className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-white">Editar</button>
              <button type="button" onClick={() => onDelete(tramite)} disabled={deletingId === tramite.id} className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60">
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

function Callout() {
  return (
    <div className="rounded-[2rem] border border-slate-200/70 bg-[linear-gradient(135deg,#0f172a_0%,#1f2937_50%,#1a4334_100%)] p-6 text-white shadow-[0_25px_80px_-45px_rgba(15,23,42,0.7)]">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-200">Siguiente paso tecnico</p>
      <h2 className="mt-2 text-2xl font-bold">Embeddings y retrieval semantico</h2>
      <p className="mt-4 text-sm leading-6 text-slate-200">
        Ya tenemos consulta textual y panel administrativo inicial. El siguiente salto sera usar <code>embedding_vector</code> para retrieval semantico real.
      </p>
    </div>
  )
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
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    slate: 'border-slate-200 bg-slate-100 text-slate-800',
  }
  return (
    <div className={`rounded-3xl border px-4 py-4 ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-70">{label}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
    </div>
  )
}

function ViewButton({ active, children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-5 py-3 text-sm font-semibold transition ${active ? 'bg-slate-950 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'}`}
    >
      {children}
    </button>
  )
}

function Field({ label, children, className = '', required = false }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label} {required ? <span className="text-rose-500">*</span> : null}
      </span>
      {children}
    </label>
  )
}

export default App
