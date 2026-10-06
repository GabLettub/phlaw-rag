// n8n "Code" node (language: JavaScript, mode: Run Once for All Items).
//
// Input : the JSON that POST /digest returned
//         {case_id, title, gr_no, sections[{heading, paragraphs[]}], sources[]}
// Output: one item with the pieces of Notion's "create a page" request
//         (POST https://api.notion.com/v1/pages):
//           parent, properties, children  the request body, as objects
//           bodyString                    the same body as one JSON string
//         Send bodyString with a "Raw" body (content type
//         application/json). That avoids n8n's JSON-body field, which can
//         turn an object expression into "[object Object]".
//
// Why a Code node: a digest has a different number of paragraphs each
// time, which the Notion node's fixed block list cannot express.
//
// Notion limits (from memory, check developers.notion.com):
// - a rich_text "content" is at most 2,000 characters
// - a request may contain at most 100 child blocks

// Paste your Case Digests database id here (see docs/notion-setup.md).
const DIGESTS_DATABASE_ID = "PASTE_DATABASE_ID_HERE";

const MAX_TEXT = 1800; // stay under Notion's 2,000-character limit
const MAX_BLOCKS = 100;

function text(content, link) {
  const piece = { type: "text", text: { content } };
  if (link) piece.text.link = { url: link };
  return piece;
}

// Split long text at sentence ends so no block exceeds MAX_TEXT. The
// backend already does this for digests; this is a second safety net.
function splitText(value) {
  const pieces = [];
  let current = "";
  for (const sentence of String(value).split(/(?<=[.!?])\s+/)) {
    let rest = sentence;
    while (rest.length > MAX_TEXT) {
      if (current) {
        pieces.push(current);
        current = "";
      }
      pieces.push(rest.slice(0, MAX_TEXT));
      rest = rest.slice(MAX_TEXT);
    }
    if (current && current.length + 1 + rest.length > MAX_TEXT) {
      pieces.push(current);
      current = rest;
    } else {
      current = current ? `${current} ${rest}` : rest;
    }
  }
  if (current) pieces.push(current);
  return pieces;
}

function heading(content) {
  return {
    object: "block",
    type: "heading_2",
    heading_2: { rich_text: [text(content)] },
  };
}

function paragraph(content) {
  return {
    object: "block",
    type: "paragraph",
    paragraph: { rich_text: [text(content)] },
  };
}

function bullet(content, link) {
  return {
    object: "block",
    type: "bulleted_list_item",
    bulleted_list_item: { rich_text: [text(content, link)] },
  };
}

function buildPage(digest) {
  const blocks = [];
  for (const section of digest.sections) {
    if (!section.paragraphs.length) continue;
    blocks.push(heading(section.heading));
    for (const para of section.paragraphs) {
      for (const piece of splitText(para)) blocks.push(paragraph(piece));
    }
  }
  if (digest.sources && digest.sources.length) {
    blocks.push(heading("Sources"));
    for (const source of digest.sources) {
      const label = `[${source.section}] ${source.snippet}`;
      blocks.push(bullet(label.slice(0, MAX_TEXT), source.url));
    }
  }
  if (blocks.length > MAX_BLOCKS) {
    throw new Error(
      `Digest has ${blocks.length} blocks; Notion allows ${MAX_BLOCKS} ` +
        "per request. Append the rest in a second request.",
    );
  }
  const firstUrl = digest.sources && digest.sources[0]
    ? digest.sources[0].url
    : null;
  return {
    parent: { database_id: DIGESTS_DATABASE_ID },
    properties: {
      Title: { title: [text(digest.title)] },
      "Case ID": { rich_text: [text(digest.case_id)] },
      "G.R. No.": { rich_text: [text(digest.gr_no)] },
      "Generated at": { date: { start: new Date().toISOString() } },
      Sources: { url: firstUrl },
    },
    children: blocks,
  };
}

// Inside n8n `$input` exists: return the page body. Outside n8n (a
// plain `node` test) export the function instead.
if (typeof $input !== "undefined") {
  const page = buildPage($input.first().json);
  return [{ json: { ...page, bodyString: JSON.stringify(page) } }];
}
module.exports = { buildPage, splitText };
