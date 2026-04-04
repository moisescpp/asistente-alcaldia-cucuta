import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

const DEFAULT_QUESTION = 'Quiero informacion sobre impuesto predial'

function App() {
  const [tramites, setTramites] = useState([])
  const [loadingTramites, setLoadingTramites] = useState(true)
  const [tramitesError, setTramitesError] = useState('')

  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [consulta, setConsulta] = useState(null)
  const [consultaError, setConsultaError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let ignore = false

    async function loadTramites() {
      setLoadingTramites(true)
      setTramitesError('')

      try {
        const response = await fetch(`${API_URL}/tramites`)

        if (!response.ok) {
          throw new Error('No fue posible cargar los tramites activos.')
        }

        const data = await response.json()

        if (!ignore) {
          setTramites(data)
        }
      } catch (error) {
        if (!ignore) {
          setTramitesError(
            error instanceof Error
              ? error.message
              : 'Ocurrio un error al consultar los tramites.',
          )
        }
      } finally {
        if (!ignore) {
          setLoadingTramites(false)
        }
      }
    }

    loadTramites()

    return () => {
      ignore = true
    }
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()

    const trimmedQuestion = question.trim()
    if (!trimmedQuestion) {
      setConsultaError('Escribe una pregunta antes de consultar.')
      return
    }

    setConsultaError('')
    setIsSubmitting(true)

    try {
      const response = await fetch(`${API_URL}/consulta`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify({
          pregunta: trimmedQuestion,
        }),
      })

      if (!response.ok) {
        throw new Error('No fue posible procesar la consulta.')
      }

      const data = await response.json()
      setConsulta(data)
    } catch (error) {
      setConsultaError(
        error instanceof Error
          ? error.message
          : 'Ocurrio un error al consultar el asistente.',
      )
    } finally {
      setIsSubmitting(false)
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
                  Esta interfaz ya consulta el backend del proyecto y muestra una
                  primera version funcional del asistente para orientar a los
                  ciudadanos sobre tramites estrella.
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <MetricCard label="API" value="Activa" tone="emerald" />
              <MetricCard
                label="Tramites cargados"
                value={loadingTramites ? '...' : String(tramites.length)}
                tone="amber"
              />
            </div>
          </div>
        </header>

        <main className="grid gap-8 lg:grid-cols-[1.5fr_1fr]">
          <section className="space-y-6">
            <div className="rounded-[2rem] border border-slate-200/70 bg-white/80 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
              <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Consulta del asistente
                  </p>
                  <h2 className="mt-2 text-2xl font-bold text-slate-950">
                    Pregunta por un tramite
                  </h2>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                    Endpoint actual
                  </p>
                  <p className="text-sm font-semibold text-slate-700">
                    POST /api/consulta
                  </p>
                </div>
              </div>

              <form className="space-y-4" onSubmit={handleSubmit}>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Escribe tu consulta
                  </span>
                  <textarea
                    className="min-h-32 w-full rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 text-base text-slate-800 outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ejemplo: Quiero informacion sobre impuesto predial"
                  />
                </label>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex items-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                  >
                    {isSubmitting ? 'Consultando...' : 'Consultar asistente'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setQuestion(DEFAULT_QUESTION)}
                    className="inline-flex items-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                  >
                    Usar ejemplo
                  </button>
                </div>
              </form>

              {consultaError ? (
                <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {consultaError}
                </p>
              ) : null}
            </div>

            <div className="rounded-[2rem] border border-slate-200/70 bg-slate-950 p-6 text-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-300">
                    Respuesta actual
                  </p>
                  <h3 className="mt-2 text-2xl font-bold">
                    Resultado de la consulta
                  </h3>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300">
                  MVP conectado al backend
                </span>
              </div>

              {consulta ? (
                <div className="mt-6 space-y-6">
                  <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-300">
                      Pregunta enviada
                    </p>
                    <p className="mt-2 text-lg font-medium text-white">
                      {consulta.pregunta}
                    </p>
                  </div>

                  <div className="rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">
                      Respuesta del asistente
                    </p>
                    <p className="mt-3 text-base leading-7 text-emerald-50">
                      {consulta.respuesta}
                    </p>
                  </div>

                  <div>
                    <div className="mb-4 flex items-center justify-between gap-4">
                      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">
                        Tramites relacionados
                      </p>
                      <p className="text-sm text-slate-300">
                        {consulta.total_resultados} coincidencia(s)
                      </p>
                    </div>

                    <div className="grid gap-4">
                      {consulta.tramites_relacionados.map((tramite) => (
                        <article
                          key={tramite.id}
                          className="rounded-3xl border border-white/10 bg-white/5 p-5"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <h4 className="text-lg font-semibold text-white">
                                {tramite.nombre}
                              </h4>
                              <p className="mt-2 text-sm text-slate-300">
                                {tramite.dependencia}
                              </p>
                            </div>
                            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-300">
                              ID {tramite.id}
                            </span>
                          </div>

                          {tramite.fuente_url ? (
                            <a
                              href={tramite.fuente_url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-4 inline-flex text-sm font-semibold text-emerald-300 transition hover:text-emerald-200"
                            >
                              Ver fuente oficial
                            </a>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-3xl border border-dashed border-white/20 bg-white/5 p-8 text-center text-slate-300">
                  La respuesta aparecera aqui cuando envies una consulta al
                  asistente.
                </div>
              )}
            </div>
          </section>

          <aside className="space-y-6">
            <div className="rounded-[2rem] border border-slate-200/70 bg-white/80 p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] backdrop-blur">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                Tramites activos
              </p>
              <h2 className="mt-2 text-2xl font-bold text-slate-950">
                Base de consulta disponible
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                Este bloque consume <span className="font-semibold">GET /api/tramites</span>{' '}
                y muestra la base activa con la que hoy trabaja el asistente.
              </p>

              {loadingTramites ? (
                <div className="mt-6 space-y-3">
                  {[1, 2, 3].map((item) => (
                    <div
                      key={item}
                      className="h-20 animate-pulse rounded-3xl bg-slate-100"
                    />
                  ))}
                </div>
              ) : null}

              {tramitesError ? (
                <p className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {tramitesError}
                </p>
              ) : null}

              {!loadingTramites && !tramitesError ? (
                <div className="mt-6 grid gap-4">
                  {tramites.map((tramite) => (
                    <article
                      key={tramite.id}
                      className="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 transition hover:-translate-y-0.5 hover:border-emerald-200 hover:bg-white"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-base font-semibold text-slate-900">
                            {tramite.nombre}
                          </h3>
                          <p className="mt-2 text-sm text-slate-600">
                            {tramite.dependencia}
                          </p>
                        </div>
                        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                          ID {tramite.id}
                        </span>
                      </div>

                      <p className="mt-4 text-sm leading-6 text-slate-600">
                        {tramite.descripcion || 'Sin descripcion disponible.'}
                      </p>
                    </article>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="rounded-[2rem] border border-slate-200/70 bg-[linear-gradient(135deg,#0f172a_0%,#1f2937_50%,#1a4334_100%)] p-6 text-white shadow-[0_25px_80px_-45px_rgba(15,23,42,0.7)]">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-200">
                Siguiente paso tecnico
              </p>
              <h2 className="mt-2 text-2xl font-bold">
                Preparar embeddings y retrieval semantico
              </h2>
              <p className="mt-4 text-sm leading-6 text-slate-200">
                Esta vista ya consume la API real. El siguiente salto de valor
                sera reemplazar la coincidencia textual por una recuperacion
                basada en embeddings guardados en <code>embedding_vector</code>.
              </p>
            </div>
          </aside>
        </main>
      </div>
    </div>
  )
}

function MetricCard({ label, value, tone }) {
  const tones = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
  }

  return (
    <div className={`rounded-3xl border px-4 py-4 ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-70">
        {label}
      </p>
      <p className="mt-2 text-2xl font-black">{value}</p>
    </div>
  )
}

export default App
