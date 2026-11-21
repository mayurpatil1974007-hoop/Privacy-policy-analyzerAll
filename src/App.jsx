import React, { useState, useRef, useCallback } from 'react'

const SAMPLE_POLICIES = [
  {
    label: 'High Risk (Red)',
    text: 'We may sell or rent your personal information to third-party advertising networks and marketing partners. We collect your real-time GPS location and may retain your data indefinitely for business purposes. We share biometric data including face scans with our partners.'
  },
  {
    label: 'Moderate Risk (Yellow)',
    text: 'We use cookies and analytics tools to improve our service. We share limited data with service providers and only share information with third parties with your explicit consent or as required by law. You can delete your account or opt out in settings.'
  },
  {
    label: 'Safe (Green)',
    text: 'We do not sell your personal data and never share your information with advertisers. We only process account details to provide the service and allow you to delete your data anytime. Location data is never collected.'
  }
]

const MODES = [
  { id: 'url', label: 'Website URL' },
  { id: 'text', label: 'Paste Text' },
  { id: 'pdf', label: 'PDF Upload' },
  { id: 'image', label: 'Photo / OCR' }
]

export default function App() {
  const [mode, setMode] = useState('url')
  const [input, setInput] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [fileName, setFileName] = useState('')
  const fileRef = useRef(null)

  const getLevelStyles = (level) => {
    if (level === 'Red') {
      return {
        card: 'border-red-500/50 bg-gradient-to-br from-red-950/50 via-slate-900/90 to-slate-900',
        badge: 'bg-red-500/20 text-red-300 border-red-500/40',
        text: 'text-red-400',
        bar: 'bg-gradient-to-r from-red-600 to-rose-400',
        dot: 'bg-red-500',
        label: 'RED • HIGH RISK'
      }
    }
    if (level === 'Yellow') {
      return {
        card: 'border-amber-400/50 bg-gradient-to-br from-amber-950/40 via-slate-900/90 to-slate-900',
        badge: 'bg-amber-400/20 text-amber-200 border-amber-400/40',
        text: 'text-amber-300',
        bar: 'bg-gradient-to-r from-amber-500 to-yellow-300',
        dot: 'bg-amber-400',
        label: 'YELLOW • MODERATE RISK'
      }
    }
    return {
      card: 'border-emerald-500/50 bg-gradient-to-br from-emerald-950/40 via-slate-900/90 to-slate-900',
      badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
      text: 'text-emerald-400',
      bar: 'bg-gradient-to-r from-emerald-500 to-teal-300',
      dot: 'bg-emerald-400',
      label: 'GREEN • LOW RISK'
    }
  }

  const extractPdfText = async (file) => {
    const pdfjs = await import('pdfjs-dist')
    pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`
    const arrayBuffer = await file.arrayBuffer()
    const pdf = await pdfjs.getDocument({ data: arrayBuffer }).promise
    let fullText = ''
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const content = await page.getTextContent()
      const strings = content.items.map((item) => item.str)
      fullText += strings.join(' ') + '\n'
    }
    return fullText.trim()
  }

  const extractImageText = async (file) => {
    const Tesseract = (await import('tesseract.js')).default
    setStatus('Running OCR on image…')
    const { data: { text } } = await Tesseract.recognize(file, 'eng', {
      logger: (m) => {
        if (m.status === 'recognizing text') {
          setStatus(`OCR progress: ${Math.round(m.progress * 100)}%`)
        }
      }
    })
    return text.trim()
  }

  const runAnalysis = async (content, sourceMode) => {
    if (!content || content.trim().length < 20) {
      setError('Not enough readable text to analyze. Please provide a longer policy or try another source.')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    setStatus('Running hybrid NLP + AI analysis…')

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: sourceMode === 'url' ? 'url' : 'text',
          content: content.trim()
        })
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Analysis failed')
      setResult(data)
      setStatus('')
    } catch (err) {
      setError(err.message || 'Something went wrong while analyzing.')
      setStatus('')
    } finally {
      setLoading(false)
    }
  }

  const handleAnalyze = async () => {
    setError('')
    if (mode === 'url' || mode === 'text') {
      if (!input.trim()) {
        setError('Please enter a URL or paste policy text.')
        return
      }
      await runAnalysis(input, mode)
      return
    }
    // PDF / Image already extracted into input
    if (!input.trim()) {
      setError('Please upload a file first.')
      return
    }
    await runAnalysis(input, 'text')
  }

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    setError('')
    setResult(null)
    setLoading(true)
    try {
      let text = ''
      if (mode === 'pdf') {
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
          throw new Error('Please select a valid PDF file.')
        }
        setStatus('Extracting text from PDF…')
        text = await extractPdfText(file)
      } else {
        if (!file.type.startsWith('image/')) {
          throw new Error('Please select an image (JPG, PNG, WEBP).')
        }
        text = await extractImageText(file)
      }
      if (!text || text.length < 30) {
        throw new Error('Could not extract enough text from this file. Try a clearer image or different PDF.')
      }
      setInput(text)
      setStatus('Text extracted. Ready to analyze.')
    } catch (err) {
      setError(err.message)
      setInput('')
      setFileName('')
    } finally {
      setLoading(false)
    }
  }

  const handleSample = (sample) => {
    setMode('text')
    setInput(sample.text)
    setFileName('')
    runAnalysis(sample.text, 'text')
  }

  const downloadReport = (format) => {
    if (!result) return
    const lines = []
    lines.push(`# AegisLex AI — Privacy Policy Report`)
    lines.push(``)
    lines.push(`**Verdict:** ${result.verdict}`)
    lines.push(`**Risk Score:** ${result.risk_score} / 100`)
    lines.push(`**Level:** ${result.level}`)
    lines.push(`**Summary:** ${result.summary}`)
    lines.push(``)
    lines.push(`## Key Stats`)
    lines.push(`- Words: ${result.word_count}`)
    lines.push(`- Sentences analyzed: ${result.sentences_analyzed}`)
    lines.push(`- Coverage: ${result.text_coverage_percent}%`)
    lines.push(`- Engine: ${result.engine || 'Hybrid NLP'}`)
    lines.push(``)
    if (result.data_usage?.length) {
      lines.push(`## Where & How Data Is Used`)
      result.data_usage.forEach((d) => {
        lines.push(`### ${d.destination}${d.negated ? ' (Restricted)' : ''}`)
        lines.push(`- Tag: ${d.where_tag}`)
        lines.push(`- Purpose: ${d.purpose}`)
        lines.push(`- Evidence: "${d.evidence}"`)
        lines.push(``)
      })
    }
    if (result.findings?.length) {
      lines.push(`## Risk Findings`)
      result.findings.forEach((f) => {
        lines.push(`### ${f.category} — ${f.status} (weight +${f.weight_added})`)
        lines.push(`${f.message}`)
        lines.push(`Evidence: "${f.evidence}"`)
        lines.push(``)
      })
    }
    if (result.user_advice?.length) {
      lines.push(`## Recommended Actions`)
      result.user_advice.forEach((a) => lines.push(`- ${a}`))
      lines.push(``)
    }
    lines.push(`---`)
    lines.push(result.disclaimer || 'This is not legal advice.')
    lines.push(`Generated by AegisLex AI`)

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `aegislex-report-${result.level.toLowerCase()}-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const styles = result ? getLevelStyles(result.level) : null

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-cyan-950/20 via-slate-950 to-slate-950 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        {/* Header */}
        <header className="text-center mb-10 no-print">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-xs font-semibold tracking-wide mb-4">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
            HYBRID NLP + AI INTELLIGENCE
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight bg-gradient-to-r from-white via-cyan-100 to-cyan-400 bg-clip-text text-transparent">
            AegisLex AI
          </h1>
          <p className="mt-3 text-slate-400 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed">
            Supreme Privacy Policy & Data Intelligence Analyzer. Instant{' '}
            <span className="text-emerald-400 font-semibold">Green</span> /{' '}
            <span className="text-amber-300 font-semibold">Yellow</span> /{' '}
            <span className="text-red-400 font-semibold">Red</span> verdict with full data-flow mapping.
          </p>
        </header>

        {/* Input Card */}
        <section className="bg-slate-900/70 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-5 sm:p-7 shadow-2xl no-print">
          {/* Mode Tabs */}
          <div className="flex flex-wrap gap-2 mb-5">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => {
                  setMode(m.id)
                  setInput('')
                  setFileName('')
                  setResult(null)
                  setError('')
                  setStatus('')
                }}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition ${
                  mode === m.id
                    ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                    : 'bg-slate-800/80 text-slate-400 hover:text-white border border-slate-700/60'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Quick Samples */}
          <div className="flex flex-wrap items-center gap-2 mb-5">
            <span className="text-xs text-slate-500">Quick test:</span>
            {SAMPLE_POLICIES.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleSample(s)}
                className="px-2.5 py-1 rounded-lg bg-slate-800/70 hover:bg-slate-700 border border-slate-700/60 text-[11px] font-medium text-slate-300 transition"
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Input Area */}
          {mode === 'url' && (
            <input
              type="url"
              placeholder="https://example.com/privacy"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="w-full px-4 py-3.5 rounded-2xl bg-slate-950/80 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-2 focus:ring-cyan-500/20 transition"
            />
          )}

          {mode === 'text' && (
            <textarea
              rows={7}
              placeholder="Paste the full privacy policy text here…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="w-full p-4 rounded-2xl bg-slate-950/80 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-2 focus:ring-cyan-500/20 transition resize-y"
            />
          )}

          {(mode === 'pdf' || mode === 'image') && (
            <div className="space-y-3">
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-cyan-500/50 rounded-2xl p-8 text-center cursor-pointer transition bg-slate-950/50"
              >
                <p className="text-slate-300 font-medium">
                  {mode === 'pdf' ? 'Drop PDF or click to select' : 'Drop image or click to select'}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {mode === 'pdf' ? 'PDF text extraction' : 'JPG, PNG, WEBP — OCR powered'}
                </p>
                {fileName && (
                  <p className="mt-3 text-sm text-cyan-400 font-medium">{fileName}</p>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept={mode === 'pdf' ? 'application/pdf' : 'image/*'}
                onChange={handleFile}
                className="hidden"
              />
              {input && (
                <div className="text-xs text-slate-400 bg-slate-950/60 rounded-xl p-3 max-h-32 overflow-y-auto border border-slate-800">
                  <span className="text-slate-500">Extracted preview:</span> {input.slice(0, 280)}…
                </div>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={handleAnalyze}
            disabled={loading}
            className="w-full mt-5 py-3.5 px-6 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 font-bold text-slate-950 shadow-lg shadow-cyan-950/30 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (status || 'Analyzing…') : 'Generate Intelligence Report'}
          </button>

          {error && (
            <div className="mt-4 p-4 rounded-2xl bg-red-950/50 border border-red-500/40 text-red-200 text-sm">
              {error}
            </div>
          )}
          {status && !error && (
            <div className="mt-4 p-3 rounded-xl bg-cyan-950/30 border border-cyan-500/20 text-cyan-300 text-sm">
              {status}
            </div>
          )}
        </section>

        {/* Results */}
        {result && styles && (
          <section className="mt-10 space-y-6">
            {/* Verdict Card */}
            <div className={`border rounded-3xl p-6 sm:p-8 shadow-xl ${styles.card}`}>
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                <div className="space-y-2">
                  <span className={`inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-extrabold tracking-wider border ${styles.badge}`}>
                    <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
                    {styles.label}
                  </span>
                  <h2 className={`text-2xl sm:text-3xl font-extrabold ${styles.text}`}>
                    {result.verdict}
                  </h2>
                  <p className="text-slate-200 text-sm sm:text-base max-w-xl">{result.summary}</p>
                  {result.engine && (
                    <p className="text-xs text-slate-500">Engine: {result.engine}</p>
                  )}
                </div>

                <div className="bg-slate-950/60 border border-slate-800/80 rounded-2xl p-5 min-w-[220px]">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs uppercase tracking-wider text-slate-400">Risk Score</span>
                    <span className="text-3xl font-black text-white">
                      {result.risk_score}
                      <span className="text-xs font-normal text-slate-400"> / 100</span>
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden mt-3">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${styles.bar}`}
                      style={{ width: `${Math.min(100, Math.max(4, result.risk_score))}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-slate-400 mt-3 flex flex-wrap gap-x-2 gap-y-1">
                    <span>{result.word_count} words</span>
                    <span>•</span>
                    <span>{result.sentences_analyzed} sentences</span>
                    <span>•</span>
                    <span>{result.text_coverage_percent}% coverage</span>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button
                      type="button"
                      onClick={() => window.print()}
                      className="flex-1 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold border border-slate-700 transition"
                    >
                      Print PDF
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadReport('md')}
                      className="flex-1 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold border border-slate-700 transition"
                    >
                      Download MD
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Data Usage */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 sm:p-7">
              <h3 className="text-xl font-bold text-cyan-300 mb-1">Where & How Your Data Is Used</h3>
              <p className="text-xs text-slate-400 mb-5">Destinations, purposes and restriction signals detected</p>
              {result.data_usage?.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {result.data_usage.map((item, idx) => (
                    <div key={idx} className="p-5 rounded-2xl bg-slate-950/80 border border-slate-800/80 hover:border-cyan-500/30 transition">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="font-bold text-white text-sm">{item.destination}</h4>
                        {item.negated && (
                          <span className="shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                            Restricted
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-medium text-cyan-400 mt-1">{item.where_tag}</p>
                      <p className="text-xs text-slate-300 mt-2">
                        <span className="text-slate-500">Purpose:</span> {item.purpose}
                      </p>
                      <p className="text-xs text-slate-500 mt-3 pt-2 border-t border-slate-800 italic">
                        "{item.evidence}"
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No clear data-destination categories matched.</p>
              )}
            </div>

            {/* Findings */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 sm:p-7">
              <h3 className="text-xl font-bold text-white mb-4">NLP & AI Risk Findings</h3>
              {result.findings?.length > 0 ? (
                <div className="space-y-3">
                  {result.findings.map((f, i) => (
                    <div key={i} className="p-4 sm:p-5 rounded-2xl bg-slate-950/80 border border-slate-800/80">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-amber-400">{f.category}</span>
                        <span className="text-xs font-semibold px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-slate-300">
                          {f.status} • +{f.weight_added}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-white mt-2">{f.message}</p>
                      <p className="text-xs text-slate-400 mt-3 bg-slate-900/80 border border-slate-800 p-3 rounded-xl">
                        <span className="font-semibold text-slate-300">Evidence: </span>"{f.evidence}"
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-emerald-400">No high-risk pattern matches found.</p>
              )}
            </div>

            {/* Advice */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 sm:p-7">
              <h3 className="text-lg font-bold text-white mb-3">Recommended Next Steps</h3>
              <ul className="list-disc list-inside space-y-2 text-sm text-slate-300">
                {result.user_advice?.map((tip, idx) => (
                  <li key={idx}>{tip}</li>
                ))}
              </ul>
              <p className="text-xs text-slate-500 mt-5 pt-4 border-t border-slate-800">
                {result.disclaimer}
              </p>
            </div>
          </section>
        )}

        <footer className="mt-16 text-center text-xs text-slate-600 no-print">
          AegisLex AI • Hybrid NLP + AI Privacy Intelligence • Not legal advice
        </footer>
      </div>
    </div>
  )
}
