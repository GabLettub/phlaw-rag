# n8n setup

Part 2 of the admin pipeline. Do [notion-setup.md](notion-setup.md) first.

```
Notion Case Queue ──(new row)──▶ n8n ──▶ POST /ingest ──▶ Pinecone
        ▲                          │
        └──── Status / Chunks / Error written back
                                   └──▶ POST /digest ──▶ Notion Case Digests page
```

> Written from n8n's docs where marked, otherwise from memory
> (**[Unverified]**). Node settings move between n8n versions. When a
> field is not where this says, use the node's own labels.

## 0. What the API expects

| Call | Header | Body | Success |
|---|---|---|---|
| `POST {API}/ingest` | `X-Ingest-Token: <INGEST_TOKEN>` | `{url, case_id, title, gr_no, date, topic}` | `{case_id, chunks}` |
| `POST {API}/digest` | same | `{case_id}` | digest JSON (sections, sources) |
| `GET {API}/health` | none | none | `{ok, vectors}` |

Failure responses: `401` bad token, `422` bad input (for example an
uppercase `case_id`, or a `date` longer than 20 characters), `502` the
source URL could not be fetched, `429` a rate limit.

`{API}` is your Render URL. n8n runs directly on your machine (not in a
container), so `http://localhost:8000` also works while your own
`uvicorn` is running. Prefer the Render URL for the demo, since that is the
backend the public app uses; if you use it, keep the wake-up node (below),
because the free tier sleeps when idle.

## 1. Run n8n

n8n is installed and started with `npx`, so no Docker and no n8n.cloud
account are needed. It needs Node.js 24 or newer (n8n 2.x requires it;
check with `node -v`).

```bash
npx n8n
```

The first run downloads n8n, which takes a few minutes. When it prints that
the editor is ready, open <http://localhost:5678> and create the owner
account. That account is local to your machine, not an n8n.cloud account.

- **Your data** (workflows and credentials) is stored in `~/.n8n`, so it
  survives restarts. Stop n8n with Ctrl+C and start it again with
  `npx n8n`.
- **It only works while it is running.** The Notion trigger **polls**, so
  n8n needs no public address, but a new Case Queue row is picked up only
  while `npx n8n` is up and the workflow is active.
- **Port in use?** `npx n8n` listens on 5678. Stop whatever else uses it, or
  set `N8N_PORT=5679` before the command **[Unverified variable name]**.
- n8n 2.x may label the *Activate* switch as *Publish*; use whichever the
  editor shows.

## 2. Credentials

In n8n: **Credentials → Create credential**.

1. **Notion API**: paste the Internal Integration Token from the Notion
   setup. (n8n's docs call the field *Internal Integration Secret*.)
2. **Header Auth** (this form has two different "names"):
   - the **Name** field inside the form is the HTTP *header* name. Type
     exactly `X-Ingest-Token`, because the backend looks for that header;
   - the **Value** field is your backend `INGEST_TOKEN`;
   - the credential's own title (shown at the top of the window and in the
     credentials list) is only a label for you. Call it
     `phlaw ingest token`. It is never sent anywhere. You pick the
     credential by this label in the HTTP Request node.

## 3. Workflow A: ingest (core)

Create a workflow named `phlaw ingest`. Add these nodes in order.

| # | Node | Settings |
|---|---|---|
| 1 | **Notion Trigger** | Event **Page added to database** (n8n also offers *Page updated in database*). Database: pick **Case Queue**. Poll every minute while testing. |
| 2 | **HTTP Request** (wake-up) | `GET {API}/health`. Timeout `120000` ms. Render's free tier sleeps and can take about a minute to wake; this absorbs it. |
| 3 | **Notion** | Resource **Database Page**, operation **Update**. Page: the trigger's page id. Set **Status** = `Processing`. |
| 4 | **HTTP Request** (ingest) | Method `POST`, URL `{API}/ingest`. Authentication **Generic credential type → Header Auth** → `phlaw ingest token`. Body: JSON (below). Timeout `180000` ms. Settings tab → **On Error** → *Continue (using error output)* **[Unverified name]**. |
| 5a | **Notion** (success) | Database Page → Update the same page: **Status** = `Indexed`, **Chunks** = `{{ $json.chunks }}`, **Indexed at** = `{{ $now }}`. Connect to node 4's *success* output. |
| 5b | **Notion** (failure) | Database Page → Update: **Status** = `Failed`, **Error** = the error message. Connect to node 4's *error* output. |

**Body for node 4.** With *Simplify* on, the trigger's output uses the
Notion property names as they are (checked against a real run): `id`,
`Title`, `Case ID`, `G.R. No.`, `Source URL`, `Topic`, `Status`, and
`Date.start`. You can drag them from the Input panel, or use these
expressions. Names with a space or dot need the `['…']` form.

| Body field | Expression |
|---|---|
| `url` | `{{ $('Notion Trigger').item.json['Source URL'] }}` |
| `case_id` | `{{ $('Notion Trigger').item.json['Case ID'] }}` |
| `title` | `{{ $('Notion Trigger').item.json.Title }}` |
| `gr_no` | `{{ $('Notion Trigger').item.json['G.R. No.'] }}` |
| `date` | `{{ String($('Notion Trigger').item.json.Date.start).slice(0, 10) }}` |
| `topic` | `{{ $('Notion Trigger').item.json.Topic }}` |

In the HTTP Request node set **Body Content Type** to **JSON** and **Specify
Body** to **Using Fields Below**, then add one name/value row per field with
the value switched to *Expression*. n8n builds the JSON object itself, so
nothing can come out as invalid JSON.

If you prefer **Using JSON**, write plain JSON text with each expression
inside double quotes (this works while no value contains a double quote or
line break):

```
{
  "url": "{{ $('Notion Trigger').item.json['Source URL'] }}",
  "case_id": "{{ $('Notion Trigger').item.json['Case ID'] }}",
  "title": "{{ $('Notion Trigger').item.json.Title }}",
  "gr_no": "{{ $('Notion Trigger').item.json['G.R. No.'] }}",
  "date": "{{ String($('Notion Trigger').item.json.Date.start).slice(0, 10) }}",
  "topic": "{{ $('Notion Trigger').item.json.Topic }}"
}
```

Do **not** put an object expression (`{{ { url: ... } }}`) or
`JSON.stringify(...)` in the JSON body: tried in practice, these produced
"The value in the 'JSON Body' field is not valid JSON" or a body the API
rejects as "not a valid dictionary".

Property names differ by node: the **trigger** gives the plain Notion names
above, while the **Notion node's output** (for example after a status update)
uses `property_` names such as `property_case_id` and `property_source_url`.
Use `$('Notion Trigger')` as shown and you always get the plain names.

Two traps:
- The body's `url` must be the **decision link** (the `Source URL` column,
  `https://lawphil.net/...`), not the `url` field that Notion adds to a page,
  which is the Notion page's own address.
- `date` must be 20 characters or fewer, so a full timestamp fails with a
  422. The `.slice(0, 10)` above keeps `YYYY-MM-DD`.
- The **page id** for the Notion update nodes is the trigger's `id`:
  `{{ $('Notion Trigger').item.json.id }}`. Do not drag `Status` or another
  property into that field; Notion then reports "page_id should be a valid
  uuid". For the status updates use **Update** (not **Get**) and, under
  Properties, pick the **Status** key and a value from its Select list.

**Test it** before moving on: add one row with Status `Queued`, click
**Execute workflow** on the trigger (or wait for the poll) and watch each
node. Then try a failure on purpose: a row with a nonsense Source URL should
end as `Failed` with the error text. Seeing both paths work is the point of
the demo.

When it works, switch the workflow to **Active** (top right; newer versions
may call this *Publish*).

## 4. Workflow B: digest page (stretch goal)

Do this only after workflow A works. Workflow B is a **separate workflow**
that workflow A calls after a successful ingest.

**Prerequisites in Notion** (see [notion-setup.md](notion-setup.md))
- A **Case Digests** database with the properties `Title` (title), `Case ID`
  (text), `G.R. No.` (text), `Generated at` (date) and `Sources` (URL). The
  names must match exactly.
- That database is **connected to your integration** (⋯ → Connections).
- Its **database id** (32 characters in the address, before `?v=`).
- In **Case Queue**, a `Digest` property of type Relation pointing to Case
  Digests, **one-way** (do not show it on the Case Digests side).

### 4a. In workflow A: call workflow B

Add an **Execute Workflow** node (named *Execute Sub-workflow* in newer n8n)
after **Notion (success)**, so the row is already `Indexed` when B starts.
Choose workflow B from the list and pass two values **[Unverified labels]**:

| Field | Value |
|---|---|
| `case_id` | `{{ $('Notion Trigger').item.json['Case ID'] }}` |
| `queue_page_id` | `{{ $('Notion Trigger').item.json.id }}` |

Type each expression on one line with nothing after it (a stray newline
breaks Notion ids). While testing, leave *Wait for sub-workflow completion*
on, so an error in B shows up in A's run.

### 4b. Workflow B: the nodes

| # | Node | Settings |
|---|---|---|
| 1 | **When Executed by Another Workflow** | Input data mode: *Accept all data* **[Unverified label]**. |
| 2 | **HTTP Request** (digest) | `POST {API}/digest`, Header Auth credential, Body Content Type **JSON**, Specify Body **Using Fields Below**, one field `case_id` = `{{ $json.case_id }}`. Options: Timeout `180000`. Settings: **Retry On Fail**, 3 tries, wait `45000` ms (Groq's free tier rate-limits long calls). |
| 3 | **Code** | Language JavaScript, *Run Once for All Items*. Paste [`n8n/build-digest-blocks.js`](../n8n/build-digest-blocks.js) and set `DIGESTS_DATABASE_ID` at the top. |
| 4 | **HTTP Request** (create page) | `POST https://api.notion.com/v1/pages`. Authentication: **Predefined credential type → Notion API**. Send Headers: `Notion-Version` = `2022-06-28` **[Unverified: check the current version at developers.notion.com]**. Send Body on, Body Content Type **Raw**, Content Type `application/json`, Body = `{{ $json.bodyString }}`. |
| 5 | **Notion** (link) | Database Page → **Update**. Page **By ID**, Expression: `{{ $('When Executed by Another Workflow').item.json.queue_page_id }}`. Property **Digest** (Relation): the new page's id, `{{ $('HTTP Request (create page)').item.json.id }}` (use your node's real name) **[Unverified field label]**. |

Why raw HTTP and a Raw body for node 4: a digest has a variable number of
paragraphs, so the Notion node's fixed block list cannot express it, and
n8n's JSON-body field can turn an object into `[object Object]`. The Code
node builds the exact request, splits text under Notion's 2,000-character
limit, and stops with a clear error if a digest would exceed 100 blocks. A
Raw body sends its string unchanged.

### 4c. Test B on its own first

Run workflow B by itself with sample input: in node 1 use *Set mock data* to
provide `{"case_id": "gr-213948", "queue_page_id": "<that row's page id>"}`.
Check, in order, that node 2 returns `sections`, node 3 returns `children`
and `bodyString`, node 4 returns a page `id`, and a new page appears in Case
Digests. Then run workflow A with a `Queued` row.

**Known limits.** Running B twice for the same case creates a second digest
page; nothing deduplicates them. Digests are written by a language model, so
read them before publishing the Notion page.

## 5. The test that goes in the README

1. With the workflow active, add the six cases as `Queued` rows (one first).
2. Watch each reach `Indexed` and, if workflow B is on, get a digest page.
3. Ask the live chatbot about one of them.
4. Take screenshots: the Case Queue with statuses, and a digest page.
   Record them in `docs/screenshots/` and add them to the README section.

## 6. Export for the repo

In each workflow: **⋯ → Download**. Save as `n8n/ingest.workflow.json` and
`n8n/digest.workflow.json`. n8n normally exports credential *references*
(names and ids), not the secrets **[Unverified]**, but check before you
commit:

```bash
grep -n -i -E "secret_|ntn_|X-Ingest-Token|api.notion|bearer" n8n/*.workflow.json
```

and search for your actual `INGEST_TOKEN` value as well. Then update the
README's "Status: designed, not yet built" note.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Notion node: "object not found" | The database is not shared with the integration (Notion setup step 3) |
| `/ingest` returns 401 | Header Auth credential name or value is wrong |
| `/ingest` returns 422 "Field required" | A body field is missing or empty; check all six in the node's input |
| `/ingest` returns 422 "Input should be a valid dictionary or object" | The body is not a JSON object: *Body Content Type* is not **JSON** (form or raw text), or the JSON was encoded twice (for example `JSON.stringify` inside a JSON body **[Unverified]**). Use Body Content Type **JSON** with **Using Fields Below** |
| `/ingest` returns 422 about `case_id` or `date` | `case_id` has uppercase letters, or `date` is longer than 20 characters |
| `/ingest` returns 502 | The Source URL cannot be fetched |
| Timeout on the first call | Render was asleep; the wake-up node and a long timeout handle it |
| `503` with an HTML page titled "Render - Application loading" | Render was still waking up. Turn on **Settings → Retry On Fail** (about 5 tries, 15 s apart) on the wake-up node and (about 3 tries, 20 s apart) on the ingest node. Run the whole workflow, not a single node, so the wake-up runs first |
| Trigger fires late | It polls; expect a delay of up to the poll interval |
| Same row processed twice | Re-runs are safe (stable chunk ids), but check the trigger is not set to *Page updated* without an `IF Status == Queued` check |
