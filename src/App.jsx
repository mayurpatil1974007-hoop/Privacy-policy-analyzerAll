import React, { useState, useRef } from 'react'

const MODES = [
  { id: 'url', label: 'Website URL' },
  { id: 'text', label: 'Paste Text' },
  { id: 'pdf', label: 'PDF / File Upload' },
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
        card: 'border-red-200 bg-gradient-to-br from-red-50/90 via-white to-rose-50/60',
        badge: 'bg-red-100 text-red-700 border-red-200',
        text: 'text-red-700',
        bar: 'bg-gradient-to-r from-red-600 to-rose-500',
        dot: 'bg-red-600',
        label: 'RED • HIGH RISK'
      }
    }
    if (level === 'Yellow') {
      return {
        card: 'border-amber-200 bg-gradient-to-br from-amber-50/90 via-white to-yellow-50/60',
        badge: 'bg-amber-100 text-amber-800 border-amber-200',
        text: 'text-amber-700',
        bar: 'bg-gradient-to-r from-amber-500 to-yellow-400',
        dot: 'bg-amber-500',
        label: 'YELLOW • MODERATE RISK'
      }
    }
    return {
      card: 'border-emerald-200 bg-gradient-to-br from-emerald-50/90 via-white to-teal-50/60',
      badge: 'bg-emerald-100 text-emerald-700 border-emerald-200',
      text: 'text-emerald-700',
      bar: 'bg-gradient-to-r from-emerald-600 to-teal-500',
      dot: 'bg-emerald-600',
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

  const extractTextFile = async (file) => {
    const raw = await file.text()
    if (file.name.toLowerCase().endsWith('.html') || file.type === 'text/html') {
      const doc = new DOMParser().parseFromString(raw, 'text/html')
      doc.querySelectorAll('script, style, noscript').forEach((el) => el.remove())
      return (doc.body?.textContent || '').replace(/\s+/g, ' ').trim()
    }
    return raw.trim()
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
      const lower = file.name.toLowerCase()
      if (mode === 'pdf') {
        if (file.type === 'application/pdf' || lower.endsWith('.pdf')) {
          setStatus('Extracting text from PDF…')
          text = await extractPdfText(file)
        } else if (
          file.type.startsWith('text/') ||
          lower.endsWith('.txt') ||
          lower.endsWith('.md') ||
          lower.endsWith('.html')
        ) {
          setStatus('Reading text from file…')
          text = await extractTextFile(file)
        } else {
          throw new Error('Please select a PDF, TXT, MD, or HTML file.')
        }
      } else {
        if (!file.type.startsWith('image/')) {
          throw new Error('Please select an image (JPG, PNG, WEBP).')
        }
        text = await extractImageText(file)
      }
      if (!text || text.length < 30) {
        throw new Error('Could not extract enough text from this file. Try pasting text or a clearer file.')
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

  const handleDownloadPdf = () => {
    const prevTitle = document.title
    if (result) {
      document.title = `Privacy-Policy-Report-${result.level}-${result.risk_score}`
    }
    window.print()
    setTimeout(() => {
      document.title = prevTitle
    }, 500)
  }

  const switchMode = (nextMode) => {
    setMode(nextMode)
    setInput('')
    setFileName('')
    setResult(null)
    setError('')
    setStatus('')
  }

  const styles = result ? getLevelStyles(result.level) : null

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-100/80 text-slate-900 print:bg-white">
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: #ffffff !important; }
        }
      `}</style>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12 print:py-4">
        {/* Header */}
        <header className="text-center mb-10 no-print">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-sky-50 border border-sky-200/80 text-sky-700 text-xs font-semibold tracking-wide mb-4 shadow-2xs">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse" />
            HYBRID NLP + AI INTELLIGENCE
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-900">
            Privacy Policy Analyzer
          </h1>
          <p className="mt-3 text-slate-600 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed">
            Clear privacy policy & data intelligence analyzer. Instant{' '}
            <span className="text-emerald-700 font-semibold">Green</span> /{' '}
            <span className="text-amber-700 font-semibold">Yellow</span> /{' '}
            <span className="text-red-700 font-semibold">Red</span> verdict with full data-flow mapping.
          </p>
        </header>

        {/* Input Card */}
        <section className="bg-white border border-slate-200/90 rounded-3xl p-5 sm:p-7 shadow-xl shadow-slate-200/50 no-print">
          {/* Mode Tabs */}
          <div className="flex flex-wrap gap-2 mb-6">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => switchMode(m.id)}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer ${
                  mode === m.id
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70 border border-slate-200/70'
                }`}
              >
                {m.label}
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
              className="w-full px-4 py-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-500/10 transition"
            />
          )}

          {mode === 'text' && (
            <textarea
              rows={7}
              placeholder="Paste the full privacy policy text here…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="w-full p-4 rounded-2xl bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-500/10 transition resize-y"
            />
          )}

          {(mode === 'pdf' || mode === 'image') && (
            <div className="space-y-3">
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-slate-300 hover:border-sky-500 rounded-2xl p-8 text-center cursor-pointer transition bg-slate-50/80 hover:bg-sky-50/40"
              >
                <p className="text-slate-800 font-semibold">
                  {mode === 'pdf' ? 'Drop PDF / text file or click to select' : 'Drop image or click to select'}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {mode === 'pdf' ? 'PDF, TXT, MD, or HTML text extraction' : 'JPG, PNG, WEBP — OCR powered'}
                </p>
                {fileName && (
                  <p className="mt-3 text-sm text-sky-700 font-semibold">{fileName}</p>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept={mode === 'pdf' ? '.pdf,.txt,.md,.html,application/pdf,text/*' : 'image/*'}
                onChange={handleFile}
                className="hidden"
              />
              {input && (
                <div className="text-xs text-slate-600 bg-slate-50 rounded-xl p-3 max-h-32 overflow-y-auto border border-slate-200">
                  <span className="font-semibold text-slate-700">Extracted preview:</span> {input.slice(0, 280)}…
                </div>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={handleAnalyze}
            disabled={loading}
            className="w-full mt-5 py-3.5 px-6 rounded-2xl bg-slate-900 hover:bg-slate-800 font-bold text-white shadow-lg shadow-slate-900/10 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (status || 'Analyzing…') : 'Generate Intelligence Report'}
          </button>

          {error && (
            <div className="mt-4 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm font-medium space-y-2.5">
              <p>{error}</p>
              {mode === 'url' && (
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => switchMode('text')}
                    className="px-3 py-1.5 rounded-lg bg-white hover:bg-red-100/60 text-red-800 text-xs font-semibold border border-red-200 transition cursor-pointer"
                  >
                    Paste Policy Text Instead
                  </button>
                  <button
                    type="button"
                    onClick={() => switchMode('pdf')}
                    className="px-3 py-1.5 rounded-lg bg-white hover:bg-red-100/60 text-red-800 text-xs font-semibold border border-red-200 transition cursor-pointer"
                  >
                    Upload PDF / File Instead
                  </button>
                </div>
              )}
            </div>
          )}
          {status && !error && (
            <div className="mt-4 p-3 rounded-xl bg-sky-50 border border-sky-200 text-sky-800 text-sm font-medium">
              {status}
            </div>
          )}
        </section>

        {/* Results */}
        {result && styles && (
          <section className="mt-10 space-y-6">
            {/* Verdict Card */}
            <div className={`border rounded-3xl p-6 sm:p-8 shadow-lg shadow-slate-200/50 print:shadow-none ${styles.card}`}>
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                <div className="space-y-2">
                  <span className={`inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-extrabold tracking-wider border ${styles.badge}`}>
                    <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
                    {styles.label}
                  </span>
                  <h2 className={`text-2xl sm:text-3xl font-extrabold ${styles.text}`}>
                    {result.verdict}
                  </h2>
                  <p className="text-slate-700 text-sm sm:text-base max-w-xl leading-relaxed">{result.summary}</p>
                  {result.engine && (
                    <p className="text-xs text-slate-500">Engine: {result.engine}</p>
                  )}
                </div>

                <div className="bg-white/90 border border-slate-200/90 rounded-2xl p-5 min-w-[220px] shadow-xs">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Risk Score</span>
                    <span className="text-3xl font-black text-slate-900">
                      {result.risk_score}
                      <span className="text-xs font-normal text-slate-500"> / 100</span>
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden mt-3">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${styles.bar}`}
                      style={{ width: `${Math.min(100, Math.max(4, result.risk_score))}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-slate-500 mt-3 flex flex-wrap gap-x-2 gap-y-1">
                    <span>{result.word_count} words</span>
                    <span>•</span>
                    <span>{result.sentences_analyzed} sentences</span>
                    <span>•</span>
                    <span>{result.text_coverage_percent}% coverage</span>
                  </div>
                  <div className="mt-4 no-print">
                    <button
                      type="button"
                      onClick={handleDownloadPdf}
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition cursor-pointer"
                    >
                      Download PDF
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Data Usage */}
            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-7 shadow-sm print:shadow-none">
              <h3 className="text-xl font-bold text-slate-900 mb-1">Where & How Your Data Is Used</h3>
              <p className="text-xs text-slate-500 mb-5">Destinations, purposes and restriction signals detected</p>
              {result.data_usage?.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {result.data_usage.map((item, idx) => (
                    <div key={idx} className="p-5 rounded-2xl bg-slate-50/80 border border-slate-200/80 hover:border-sky-300 transition">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="font-bold text-slate-900 text-sm">{item.destination}</h4>
                        {item.negated && (
                          <span className="shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
                            Restricted
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-semibold text-sky-700 mt-1">{item.where_tag}</p>
                      <p className="text-xs text-slate-700 mt-2">
                        <span className="font-semibold text-slate-500">Purpose:</span> {item.purpose}
                      </p>
                      <p className="text-xs text-slate-500 mt-3 pt-2 border-t border-slate-200 italic">
                        "{item.evidence}"
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No clear data-destination categories matched.</p>
              )}
            </div>

            {/* Findings */}
            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-7 shadow-sm print:shadow-none">
              <h3 className="text-xl font-bold text-slate-900 mb-4">NLP & AI Risk Findings</h3>
              {result.findings?.length > 0 ? (
                <div className="space-y-3">
                  {result.findings.map((f, i) => (
                    <div key={i} className="p-4 sm:p-5 rounded-2xl bg-slate-50/80 border border-slate-200/80">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-amber-700">{f.category}</span>
                        <span className="text-xs font-semibold px-3 py-1 rounded-full bg-white border border-slate-200 text-slate-700">
                          {f.status} • +{f.weight_added}
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-slate-900 mt-2">{f.message}</p>
                      <p className="text-xs text-slate-600 mt-3 bg-white border border-slate-200 p-3 rounded-xl">
                        <span className="font-semibold text-slate-800">Evidence: </span>"{f.evidence}"
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-emerald-700 font-medium">No high-risk pattern matches found.</p>
              )}
            </div>

            {/* Advice */}
            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-7 shadow-sm print:shadow-none">
              <h3 className="text-lg font-bold text-slate-900 mb-3">Recommended Next Steps</h3>
              <ul className="list-disc list-inside space-y-2 text-sm text-slate-700">
                {result.user_advice?.map((tip, idx) => (
                  <li key={idx}>{tip}</li>
                ))}
              </ul>
              <p className="text-xs text-slate-500 mt-5 pt-4 border-t border-slate-200">
                {result.disclaimer}
              </p>
            </div>
          </section>
        )}

        <footer className="mt-16 text-center text-xs text-slate-500 no-print">
          Privacy Policy Analyzer • Hybrid NLP + AI Privacy Intelligence • Not legal advice
        </footer>
      </div>
    </div>
  )
}
