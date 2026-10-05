# PHLaw RAG Prototype — Action Plan v2

**Changes from v1:** Notion replaces the n8n Form and the Gmail/Discord step, a `/digest` endpoint feeds Notion digest pages, and the 6 cases are confirmed real.

> **About the code and estimates:** library class names, parameters and menu names come from memory, not a test install, so they're marked **[Unverified]**. Check them against the docs when you install. Time estimates are guesses.

---

## 0. Goal and definition of done

**Goal:** by end of day tomorrow, a public web app where recruiters can ask about **6 landmark Philippine Supreme Court decisions**. Built on **Pinecone + LangChain + Groq (free)**, with an **n8n + Notion** pipeline for adding decisions.

**Done means:**

- [ ] A public Vercel link loads with example questions.
- [ ] Case digests (Facts / Issues / Ruling / Doctrine) come from the actual decision text, with sources shown.
- [ ] Topic search lists the matching cases.
- [ ] Follow-up questions about the current case work.
- [ ] Questions outside the 6 cases get "not in my indexed decisions."
- [ ] A Notion Case Queue row goes `Queued → Processing → Indexed` through n8n.
- [ ] The README has the architecture, stack, eval results, the n8n/Notion section, and a link to the thesis version (v1).

---

## 1. Architecture

```
                 ┌──────────────────────────── Vercel ─────────────────────────────┐
 Recruiter ────▶ │ Next.js chat UI (reused from v1)                                │
                 │ example questions · sources panel · active_case_id · banner     │
                 └───────────────┬─────────────────────────────────────────────────┘
                                 │ POST /chat
                 ┌───────────────▼───────────────────── Render ────────────────────┐
                 │ FastAPI                                                         │
                 │  router: regex fast-path → LLM structured output                │
                 │     digest | search | follow_up | general | out_of_scope        │
                 │  LangChain chains: retriever (metadata filter) → prompt → LLM   │
                 │  /chat  /cases  /health   |  /ingest  /digest  (token-protected)│
                 └──────┬──────────────────────────────┬──────────────────▲────────┘
                        ▼                              ▼                  │
         ┌───────────────────────────┐   ┌─────────────────────────┐      │
         │ Pinecone (Starter, free)  │   │ Groq (free)             │      │
         │ index phlaw / ns decisions│   │ gpt-oss-120b: answers   │      │
         │ hosted multilingual-e5    │   │ gpt-oss-20b: router     │      │
         └───────────────────────────┘   └─────────────────────────┘      │
                                                                          │
   ┌────────────── Notion ───────────────┐      ┌──────── n8n (local Docker) ───────┐
   │ Case Queue  (Status, Chunks, Error) │◀────▶│ Trigger on Queued → /ingest       │
   │ Case Digests (digest pages)         │◀─────│ → update status → /digest → page  │
   └─────────────────────────────────────┘      └───────────────────────────────────┘
```

---

## 2. The 6 cases (all confirmed real)

| case_id | Title | Topic | Source to ingest |
|---|---|---|---|
| `gr-213948` | Knights of Rizal v. DMCI Homes (Apr. 25, 2017) | Cultural heritage | [lawphil](https://lawphil.net/judjuris/juri2017/apr2017/gr_213948_2017.html) |
| `gr-171947` | MMDA v. Concerned Residents of Manila Bay (Dec. 18, 2008) | Environment / continuing mandamus | Find the **2008 decision** on lawphil or the e-Library; the link found earlier is the 2011 resolution |
| `gr-148222` | Pearl & Dean v. Shoemart (Aug. 15, 2003) | Intellectual property | [lawphil](https://lawphil.net/judjuris/juri2003/aug2003/gr_148222_2003.html) |
| `gr-182835` | Ang v. Court of Appeals (Apr. 20, 2010) | Electronic evidence / RA 9262 | [lawphil](https://lawphil.net/judjuris/juri2010/apr2010/gr_182835_2010.html) |
| `gr-203335` | Disini v. Secretary of Justice (Feb. 18, 2014) | Cybercrime / free speech | Find the **Feb. 18 decision**; the lawphil link found is the April resolution. Main decision only. |
| `gr-101083` | Oposa v. Factoran (July 30, 1993) | Environment / intergenerational responsibility | lawphil or the e-Library |

---

## 3. Repo layout (`phlaw-rag`, a new repo)

```
phlaw-rag/
├── backend/
│   ├── app/
│   │   ├── main.py      # FastAPI, CORS, rate limits, endpoints
│   │   ├── config.py    # env vars (pydantic-settings)
│   │   ├── router.py    # regex + LLM intent routing
│   │   ├── chains.py    # digest / search / follow_up / general chains
│   │   ├── store.py     # Pinecone vector store + retriever helpers
│   │   ├── ingest.py    # fetch → clean → chunk → upsert (CLI + /ingest)
│   │   └── prompts.py   # prompts (digest format adapted from v1)
│   ├── data/cases.yaml, data/raw/*.txt, data/cards.json
│   ├── scripts/ingest_all.py, scripts/eval.py
│   ├── eval/questions.json, eval/results.md
│   ├── requirements.txt, .env.example
├── frontend/                       # trimmed copy of v1
├── n8n/ingest.workflow.json, n8n/digest.workflow.json   # credentials removed
├── docs/notion-setup.md, docs/screenshots/
└── README.md
```

---

## 4. Phases

### Phase 0: Accounts and setup (about 30 min)

1. **Create accounts:**
   - Pinecone (Starter) → API key
   - Groq → API key
   - Render, Vercel
   - Notion (an integration token comes in Phase 7)
   - a new GitHub repo, `phlaw-rag`
2. **Check Groq's free limits** for `openai/gpt-oss-120b` and `openai/gpt-oss-20b` in the console (Settings → Limits). Groq shut down `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` for Free/Developer tiers on Aug 16, 2026 and recommends these as replacements (per third-party reports of Groq's deprecation notice). **[Unverified]**
3. **Set up the project:**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install fastapi "uvicorn[standard]" pydantic-settings python-dotenv httpx beautifulsoup4 pyyaml slowapi \
               langchain langchain-pinecone langchain-groq langchain-text-splitters pinecone
   pip freeze > backend/requirements.txt
   ```
4. **Create `backend/.env`.** Add `.env` to `.gitignore` before the first commit, and commit only `.env.example`:
   ```
   PINECONE_API_KEY=
   PINECONE_INDEX=phlaw
   GROQ_API_KEY=
   LLM_MODEL=openai/gpt-oss-120b
   ROUTER_MODEL=openai/gpt-oss-20b
   LLM_REASONING_EFFORT=medium
   ROUTER_REASONING_EFFORT=low
   INGEST_TOKEN=<long random string>
   ALLOWED_ORIGINS=http://localhost:3000
   DAILY_REQUEST_CAP=300
   ```

**Check:** the imports run without errors. If versions conflict, pin `langchain-core` to what `langchain-pinecone` requires.

### Phase 1: Get the decision texts (about 1 hour)

1. **Fill in `data/cases.yaml`** by hand: id, title, G.R. no., date, topic, URL.
2. **Write `ingest.fetch_clean(url)`:**
   - `httpx` + BeautifulSoup to get the main text.
   - Strip navigation and footer text. For e-Library pages, copy v1's `clean_website_headers` and `normalize_text`.
   - Cut everything from "SEPARATE / DISSENTING / CONCURRING OPINION" onward.
3. **Save to `data/raw/<case_id>.txt` and read every file.**

**Check:** 6 files. Each starts with the caption and contains "WHEREFORE" or "SO ORDERED".

### Phase 2: Chunk and index in Pinecone (about 1–1.5 hours)

**Splitter:** `RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)`. That's about 375 tokens per chunk (inference), under e5-large's reported limit of about 500 input tokens. **[Unverified]**

**Metadata on every chunk:**
- `case_id`, `title`, `gr_no`, `date`, `topic`, `url`, `chunk_index`, `text`
- `section`, tagged with regex: `dispositive` (from "WHEREFORE" on), `facts` / `issues` / `ruling` (from headers), otherwise `body`.

**Index:** dense, **1024 dimensions** (e5-large's output size, **[Unverified]**), cosine, serverless `aws/us-east-1`. Namespace: `decisions`.

**Sketch [Unverified]:**

```python
from langchain_pinecone import PineconeEmbeddings, PineconeVectorStore

emb = PineconeEmbeddings(model="multilingual-e5-large")
store = PineconeVectorStore(index_name=INDEX, embedding=emb, namespace="decisions")
store.add_documents(
    docs,
    ids=[f"{d.metadata['case_id']}-{d.metadata['chunk_index']}" for d in docs],
)
```

**Stable IDs** let you re-ingest a case without creating duplicates.

**Case cards:** generate one short summary per case, save them to `data/cards.json`, and **edit all 6 by hand**.

**Check:** the vector count in the Pinecone console looks right. Searching "continuing mandamus" returns `gr-171947`, and "Rizal Monument sightline" returns `gr-213948`.

### Phase 3: FastAPI + LangChain backend (about 3 hours)

**Endpoints:**

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /chat` | public, rate-limited | `{message, history[], active_case_id?}` → `{answer, intent, case_id?, sources[]}` |
| `GET /cases` | public | the 6 cases with their cards |
| `GET /health` | public | `{ok, vectors}` |
| `POST /ingest` | `X-Ingest-Token` | `{url, case_id, title, gr_no, date, topic}` → `{case_id, chunks}` |
| `POST /digest` | `X-Ingest-Token` | `{case_id}` → structured digest JSON for Notion (shape below) |

**`/digest` response:**

```json
{
  "case_id": "gr-101083",
  "title": "...",
  "gr_no": "...",
  "sections": [
    {"heading": "Facts", "paragraphs": ["≤1,800 chars", "..."]},
    {"heading": "Issues", "paragraphs": ["Whether or not ..."]},
    {"heading": "Ruling", "paragraphs": ["..."]},
    {"heading": "Doctrine", "paragraphs": ["..."]}
  ],
  "sources": [{"section": "dispositive", "snippet": "...", "url": "..."}]
}
```

Paragraphs are split to about 1,800 characters because Notion reportedly limits each text block to about 2,000 characters. **[Unverified]**

**Routing:**

1. **Regex first, no LLM call:** a G.R. number or a known case name → `digest`.
2. Otherwise, the **gpt-oss-20b router** (`reasoning_effort="low"`) with structured output: `Intent(kind, case_id)`. **[Unverified: `ChatGroq(...).with_structured_output(Intent)` and how `langchain-groq` passes `reasoning_effort`; fall back to `model_kwargs` if needed]**
3. If `active_case_id` is set and the message reads like a follow-up → `follow_up`.

**Chains:**

| Intent | Retrieval | Output |
|---|---|---|
| `digest` | filter `case_id`, k=12, sorted by `chunk_index`, plus every `dispositive` chunk | Facts / Issues ("Whether or not…") / Ruling / Doctrine |
| `follow_up` | filter `active_case_id`, similarity search on the question, k=6 | a focused answer |
| `search` | k=20 → group by `case_id` → top 3 | case cards + one line each on why it matches |
| `general` | none | a short definition, labeled as general knowledge |
| `out_of_scope` | none | "Not in the 6 decisions I've indexed" + the case list |

`/chat` and `/digest` share one digest chain.

**Grounding rules for every retrieval prompt:**
- "Answer only from the excerpts."
- "If the excerpts don't contain it, say so."
- "Cite the title and G.R. no."

Always return `sources`.

**Limits and security:**
- `slowapi`: about 10 requests/minute per IP, plus `DAILY_REQUEST_CAP`.
- `max_tokens`: about 2,048 for digests, about 512 for the router. gpt-oss models are reasoning models, and reasoning tokens likely count toward the output budget, so a 1,024 cap could cut digests off. (inference)
- Keep only the last 6 messages of history.
- Return a friendly "demo limit reached" message on 429s.
- CORS allows only `ALLOWED_ORIGINS`.
- No debug output in API responses.

**Check:** one `curl` per intent, plus `/ingest` and `/digest` with the token.

### Phase 4: Frontend (about 1–1.5 hours)

1. **Copy from v1:** `page.tsx`, `RichText.tsx`, `components/ui/*`, the Tailwind/shadcn config.
2. **Change:**
   - `NEXT_PUBLIC_API_URL` instead of the hard-coded URL.
   - Send `active_case_id` from the last response with each request.
   - A collapsible **Sources** list under each answer.
   - A banner: "Prototype covering 6 landmark SC decisions · Not legal advice · First message may take ~1 min to wake the server."
   - Example-question chips:
     - "Digest Knights of Rizal v. DMCI"
     - "What is a writ of continuing mandamus?"
     - "Do the Rules on Electronic Evidence apply to criminal cases?" (Ang)
     - "Which provisions of the Cybercrime Act were struck down?" (Disini)
     - "Show me environmental law cases"
     - "Did the Supreme Court rule on the Eat Bulaga trademark?" (out of scope)
3. **Remove** `RatingComponent`, `MetricsDisplay` and the clear-cache call.

### Phase 5: Evaluation (about 45 min)

**`eval/questions.json`, about 15 items:**
- 2 per case (one digest, one specific fact).
- 3 out of scope: Eat Bulaga, "Administrative Circular 24-2024", a click-wrap ruling.

**`scripts/eval.py`** checks the expected `case_id` in sources, expected keywords in the answer, and a decline for the out-of-scope questions. It writes `eval/results.md`.

**In the README, report only the numbers the run actually produced.**

### Phase 6: Deploy (about 1.5 hours; deploy early, then iterate)

**Render (Web Service):**
- Root: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set the env vars; `ALLOWED_ORIGINS` = your Vercel URL.
- **[Unverified]** The free tier sleeps when idle.

**Vercel:** root `frontend`; set `NEXT_PUBLIC_API_URL` to the Render URL.

**Check:** a private browser window, and every example chip works.

### Phase 7: n8n + Notion automation (about 1–1.5 hours core; stretch goal about 1 hour)

**Notion setup (about 15 min):**

1. Create an internal integration and copy its token. **[Unverified: menu names]**
2. Create a page called "PHLaw RAG – Admin" with two databases:

   **Case Queue**

   | Property | Type |
   |---|---|
   | Title | Title |
   | Case ID | Text (e.g. `gr-101083`) |
   | G.R. No. | Text |
   | Date | Date |
   | Topic | Select |
   | Source URL | URL |
   | Status | Select: `Queued` / `Processing` / `Indexed` / `Failed` |
   | Chunks | Number |
   | Indexed at | Date |
   | Error | Text |
   | Digest | Relation → Case Digests |

   **Case Digests:** Title · Case ID · G.R. No. · Generated at · Sources (URL), with the digest text in the page body.

3. **Share the page with the integration.** Skipping this causes "object not found" errors.
4. **Run n8n:**
   ```bash
   docker run -it --rm -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
   ```
   Then add credentials: Notion (the token) and a Header Auth credential (`X-Ingest-Token`).

**Workflow A, ingest (core):**

```
Notion Trigger (Case Queue page added/updated; polls on an interval)
 → IF Status == "Queued"
 → Notion: Status = "Processing"
 → HTTP POST {API}/ingest
 → IF 200
     ✅ Status = "Indexed", Chunks, Indexed at = now
     ❌ Status = "Failed", Error = message
```

**Workflow B, digest page (stretch goal, only after Phase 6 works):**

```
✅ branch of A → HTTP POST {API}/digest
 → Notion: create page in Case Digests (heading block per section, paragraph blocks per paragraph)
 → Notion: set Case Queue → Digest relation
```

- **Optional:** a Discord webhook node on the ❌ branch only, for push alerts.
- **Admin-only:** no public "save to Notion" button.
- **Test:** add the 6 cases as `Queued` rows, watch them reach `Indexed`, then ask the live chatbot about one. Record a GIF.
- **Export** both workflows with credentials removed, to `n8n/`. Write `docs/notion-setup.md` with the schemas above.

### Phase 8: README and polish (about 45 min)

The README should have:

- a pitch line, the live link, a demo GIF
- the architecture diagram, the stack table
- "How retrieval works": chunking, metadata filters, grounding, sources
- the eval table
- the n8n + Notion section, with screenshots of the Case Queue and a digest page (optionally a public read-only Notion link)
- limitations: 6 cases, free tiers, not legal advice
- **v1 (thesis research version)**, linking `phlaw-chatbot`
- how to run locally

---

## 5. Schedule

| Block | Phases | Estimate |
|---|---|---|
| Morning | 0 → 1 → 2 | about 3 hours |
| Midday | 3 | about 3 hours |
| Afternoon | 4 → 6 | about 3 hours |
| Evening | 5 → 7A → 8 → (7B if time) | about 3 hours |

**If you're behind, cut in this order:**

1. Workflow B (Notion digest pages)
2. the Discord alert
3. the `general` intent (route it to `out_of_scope`)
4. LLM-generated case cards (write them by hand)
5. the `search` intent

**Never cut:** sources in answers, the out-of-scope decline, rate limiting, the ingest token, Workflow A.

---

## 6. Risks

| Risk | What to do |
|---|---|
| Groq free limits | gpt-oss-20b router with low reasoning effort, chunked contexts, capped `max_tokens`, daily cap, friendly 429 message |
| Groq model retirement (Llama already retired) | Model names live only in `.env`; check Groq's deprecations page before deploying |
| Library version mismatch | Pin with `pip freeze` on day one and deploy with exactly those versions |
| Messy scraped text | Read every `raw/*.txt`, and remove separate opinions |
| Wrong legal statements | Grounded prompts, sources always shown, banner, out-of-scope eval |
| Notion trigger delay or duplicate runs | Expect polling delay; the `Processing` status plus stable IDs keep re-runs safe |
| Notion text-block size limit | `/digest` splits paragraphs to about 1,800 characters |
| Render cold start | UI notice |
| Leaked keys | `.env` in `.gitignore` from the first commit, tokens on admin endpoints, credentials scrubbed from n8n exports |

---

## 7. Résumé bullets (only the parts that are true after you build it)

- "Built a RAG legal assistant over Philippine Supreme Court decisions with **LangChain**, **Pinecone** (hosted multilingual-e5 embeddings, metadata-filtered retrieval) and **OpenAI gpt-oss-120b via Groq**; every answer cites its source passages."
- "Designed intent routing (regex fast-path plus LLM structured output) for digest, search, follow-up and out-of-scope queries; declined [x/3] questions about nonexistent rulings in evaluation."
- "Automated ingestion with **n8n**, using **Notion** as the content queue and audit log (Queued → Processing → Indexed/Failed), idempotent **Pinecone** upserts, and auto-generated case-digest pages."
- "Rebuilt a thesis system (Django/Qdrant/hybrid BM25 + RRF) into a lightweight deployable stack (FastAPI, Render, Vercel)."

---

## 8. Sources used while preparing this plan

Case verification:

- [Knights of Rizal v. DMCI, G.R. No. 213948 (lawphil)](https://lawphil.net/judjuris/juri2017/apr2017/gr_213948_2017.html) · [e-Library](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/63069)
- [MMDA v. Concerned Residents of Manila Bay, G.R. Nos. 171947-48 (ADB PDF)](https://lpr.adb.org/sites/default/files/2024-05/philippines-mmda-vs-concerned-citizens-of-manila-bay.pdf) · [2011 resolution (chanrobles)](https://www.chanrobles.com/cralaw/2011februarydecisions.php?id=138)
- [Pearl & Dean v. Shoemart, G.R. No. 148222 (lawphil)](https://lawphil.net/judjuris/juri2003/aug2003/gr_148222_2003.html) · [e-Library](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/48090)
- [Ang v. Court of Appeals, G.R. No. 182835 (lawphil)](https://lawphil.net/judjuris/juri2010/apr2010/gr_182835_2010.html) · [e-Library](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/53911)
- [Disini v. Secretary of Justice, G.R. No. 203335 (lawphil, April 2014 resolution)](https://lawphil.net/judjuris/juri2014/apr2014/gr_203335_2014.html) · [Wikipedia](https://en.wikipedia.org/wiki/Disini_v._Secretary_of_Justice)
- [Oposa v. Factoran, G.R. No. 101083 (UMN Human Rights Library PDF)](https://hrlibrary.umn.edu/research/Philippines/Oposa%20v%20Factoran,%20GR%20No.%20101083,%20July%2030,%201993,%20on%20the%20State's%20Responsibility%20To%20Protect%20the%20Right%20To%20Live%20in%20a%20Healthy%20Environment.pdf) · [jur.ph summary](https://jur.ph/jurisprudence/summary/oposa-v-factoran-jr)

Cases dropped as unverifiable:

- [Eat Bulaga: decided by the Court of Appeals, not the SC (Philstar)](https://www.philstar.com/entertainment/2025/01/01/2411156/court-appeals-affirms-tvj-ownership-eat-bulaga-trademark)
- [OCA Circulars 2024 (Circular No. 24-2024 is an unrelated workshop circular)](https://oca.judiciary.gov.ph/oca-circulars-2024/)
- [RA 8792 text (no SC click-wrap ruling found)](https://www.lawphil.net/statutes/repacts/ra2000/ra_8792_2000.html)

Free-tier limits and model availability (third-party summaries; check the official consoles):

- [Groq model deprecations (official)](https://console.groq.com/docs/deprecations)
- [Groq free tier 2026: Llama is gone (third-party)](https://klymentiev.com/blog/groq-pricing)

- [Groq free tier limits](https://theneuralbase.com/groq/learn/beginner/free-tier-limits/)
- [Pinecone metadata size limit (community)](https://community.pinecone.io/t/metadata-size-limit/7171)
- [Pinecone rate limits and quotas](https://fast.io/resources/pinecone-rate-limit/)
