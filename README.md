# AegisLex AI — Supreme Privacy Policy & Data Intelligence Analyzer

Production-ready hybrid **NLP + AI** privacy policy analyzer.

## Features

- **Website URL Scan** — multi-strategy fetch + clean text extraction
- **Paste Text** — large editor + instant Red / Yellow / Green samples
- **PDF Upload** — client-side text extraction (pdf.js)
- **Photo / Screenshot OCR** — client-side Tesseract.js
- **Hybrid Engine** — Deterministic NLP always runs; AI enrichment when `OPENAI_API_KEY` or `XAI_API_KEY` is set
- **Rich Report** — Verdict card, data-flow map, findings with evidence, actionable advice
- **Download** — Markdown report + Print-to-PDF
- **Premium dark SaaS UI** — glassmorphism, risk-colored accents, fully responsive

## Deploy on Vercel (Clean)

1. Create a new GitHub repository
2. Upload **all files** from this project (keep folder structure)
3. Go to [vercel.com](https://vercel.com) → **New Project** → Import the repo
4. Framework Preset: **Vite**
5. Build Command: `npm run build`
6. Output Directory: `dist`
7. (Optional) Add Environment Variables:
   - `OPENAI_API_KEY` or `XAI_API_KEY` for AI enrichment
8. Click **Deploy**

The app works even without any AI key (pure NLP fallback).

## Local Development

```bash
npm install
npm run dev
```

Open http://localhost:5173

## Project Structure

```
aegislex/
├── api/
│   └── analyze.py          # Python serverless (NLP + optional AI)
├── src/
│   ├── App.jsx             # Full UI
│   ├── index.css
│   └── main.jsx
├── public/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── requirements.txt
├── vercel.json
└── README.md
```

## Environment Variables (Optional)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI GPT enrichment |
| `XAI_API_KEY` | xAI Grok enrichment |

If neither is set, the app uses pure deterministic NLP and never crashes.

## Tech Stack

- React 18 + Vite 5 + Tailwind CSS 3
- Python serverless (Vercel)
- pdf.js + Tesseract.js (client-side)
- Hybrid NLP pattern engine + optional LLM

---

Built for reliable production deployment. No black screens. No build errors.
