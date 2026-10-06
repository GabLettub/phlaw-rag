# Notion setup

Part 1 of the admin pipeline. Do this before [n8n-setup.md](n8n-setup.md).

> Notion's menus change often. Names below are from Notion's and n8n's
> documentation where marked, otherwise from memory (**[Unverified]**).
> If a button has moved, look for the nearest equivalent.

## 1. Create the integration

1. Open <https://www.notion.com/my-integrations> and choose **New
   integration**. Name it `phlaw-rag-n8n`. Type: **Internal**.
2. On the **Capabilities** tab enable: *Read content*, *Update content*,
   *Insert content*. Save. (Per n8n's Notion credential docs.)
3. On the **Secrets** tab copy the **Internal Integration Token**. Treat it
   like a password: it goes into n8n only, never into this repo.

## 2. Create the pages and databases

Create a private page called **PHLaw RAG – Admin** and, inside it, two
**full-page databases** (type `/database` and choose *Table – Full page*, or
the closest option).

### Database 1: Case Queue

| Property | Type | Notes |
|---|---|---|
| Title | Title | e.g. `Oposa v. Factoran` |
| Case ID | Text | **lowercase**, letters, digits and `-` only, e.g. `gr-101083` (the API rejects anything else) |
| G.R. No. | Text | e.g. `G.R. No. 101083` |
| Date | Date | the decision date |
| Topic | Select | free-form |
| Source URL | URL | the lawphil page |
| Status | Select | options: `Queued`, `Processing`, `Indexed`, `Failed` |
| Chunks | Number | filled by n8n |
| Indexed at | Date | filled by n8n |
| Error | Text | filled by n8n on failure |
| Digest | Relation → Case Digests | filled by n8n (workflow B). Create it after Case Digests exists |

### Database 2: Case Digests

| Property | Type |
|---|---|
| Title | Title |
| Case ID | Text |
| G.R. No. | Text |
| Generated at | Date |
| Sources | URL |

The digest text itself goes in the **page body** (headings and paragraphs),
written by n8n. The property names must match exactly:
[`n8n/build-digest-blocks.js`](../n8n/build-digest-blocks.js) writes to
`Title`, `Case ID`, `G.R. No.`, `Generated at` and `Sources`.

## 3. Share the databases with the integration

For **each** database (and the Admin page):

1. Open it, click the **⋯** menu (top right).
2. Under **Connections**, choose **Connect to**, search for
   `phlaw-rag-n8n` and select it. (Per n8n's Notion credential docs.)

Skipping this is the most common failure: the Notion API then answers
"object not found" even though the database exists.

## 4. Find the database ids

Open a database as a full page and copy its address. The id is the 32
characters after the last `/` and before `?v=`:

```
https://www.notion.so/yourname/1a2b3c4d5e6f47a8b9c0d1e2f3a4b5c6?v=...
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

You need the **Case Digests** id for the Code node in workflow B.

## 5. Sample rows for the Case Queue

Add these as rows with Status = `Queued` **only once n8n is running and the
workflow is active** (see [n8n-setup.md](n8n-setup.md)). Add one first and
watch it, then the rest. The six decisions are already indexed, so queueing
them re-indexes the same chunks (safe: ids are stable).

| Title | Case ID | G.R. No. | Date | Topic | Source URL |
|---|---|---|---|---|---|
| Knights of Rizal v. DMCI Homes | gr-213948 | G.R. No. 213948 | 2017-04-25 | Cultural heritage | https://lawphil.net/judjuris/juri2017/apr2017/gr_213948_2017.html |
| MMDA v. Concerned Residents of Manila Bay | gr-171947 | G.R. Nos. 171947-48 | 2008-12-18 | Environment / continuing mandamus | https://lawphil.net/judjuris/juri2008/dec2008/gr_171947_2008.html |
| Pearl & Dean v. Shoemart | gr-148222 | G.R. No. 148222 | 2003-08-15 | Intellectual property | https://lawphil.net/judjuris/juri2003/aug2003/gr_148222_2003.html |
| Ang v. Court of Appeals | gr-182835 | G.R. No. 182835 | 2010-04-20 | Electronic evidence / RA 9262 | https://lawphil.net/judjuris/juri2010/apr2010/gr_182835_2010.html |
| Disini v. Secretary of Justice | gr-203335 | G.R. No. 203335 | 2014-02-18 | Cybercrime / free speech | https://lawphil.net/judjuris/juri2014/feb2014/gr_203335_2014.html |
| Oposa v. Factoran | gr-101083 | G.R. No. 101083 | 1993-07-30 | Environment / intergenerational responsibility | https://lawphil.net/judjuris/juri1993/jul1993/gr_101083_1993.html |

(Dates are the ones in `backend/data/cases.yaml`. The lawphil pages give
April 18, 2017 for Knights of Rizal and February 11, 2014 for Disini.)

## 6. Publishing for the frontend link (optional)

`NEXT_PUBLIC_NOTION_URL` should point to a **read-only public page showing
only the Case Digests**. Do not publish the Admin page: the Case Queue
shows source URLs, statuses and error messages.

1. Open the Case Digests page, then **Share** → **Publish** (or *Share to
   web*) **[Unverified menu names]**.
2. Leave editing and comments off.
3. Copy the link (`https://…notion.site/…`) into `NEXT_PUBLIC_NOTION_URL`.
