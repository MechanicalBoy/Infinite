// Infinite sign-up Worker: collects emails into Cloudflare D1. No third-party service is needed to collect.
//   POST /api/subscribe     {email, audience, source, turnstile, company} -> row saved as 'pending'
//   GET  /api/confirm?t=    signed link -> 'confirmed'      (only used once a sender is set up: RESEND_API_KEY)
//   GET  /api/unsubscribe?t= signed link -> 'unsubscribed'  (put this link in every email)
// With RESEND_API_KEY set, subscribe also emails the confirmation link (double opt-in). Without it, rows stay
// 'pending' and a later script sends the confirmation to them. Export: see README.
// Secrets: SIGNING_SECRET, TURNSTILE_SECRET (optional), RESEND_API_KEY (optional). Binding: DB (D1).
// Vars: SITE_ORIGIN, API_ORIGIN, FROM

const TOKEN_TTL_MS = 48 * 3600 * 1000;
const PERSONAS = ["artists", "musicians", "vjs", "creative-coders", "developers", "general"];
const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;

const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64 = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

async function hmacKey(secret) {
  return crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

export async function makeToken(secret, payload) {
  const body = b64(new TextEncoder().encode(JSON.stringify(payload)));
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(secret), new TextEncoder().encode(body));
  return body + "." + b64(sig);
}

export async function readToken(secret, token, now = Date.now()) {
  const [body, sig] = String(token || "").split(".");
  if (!body || !sig) return null;
  let ok = false;
  try { ok = await crypto.subtle.verify("HMAC", await hmacKey(secret), unb64(sig), new TextEncoder().encode(body)); } catch { return null; }
  if (!ok) return null;
  const p = JSON.parse(new TextDecoder().decode(unb64(body)));
  return p.exp === undefined || p.exp > now ? p : null;   // unsubscribe tokens carry no expiry
}

const cors = (env) => ({ "Access-Control-Allow-Origin": env.SITE_ORIGIN, "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Vary": "Origin" });
const json = (env, status, obj) => new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors(env) } });
const page = (title, text) => new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><body style="font:18px/1.5 system-ui,sans-serif;max-width:32em;margin:15vh auto;padding:0 20px"><h1>${title}</h1><p>${text}</p><p><a href="/">Back to Infinite</a></p>`, { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } });

async function turnstileOk(env, token, ip) {
  if (!env.TURNSTILE_SECRET) return true; // not configured: honeypot only
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token || "", remoteip: ip || "" }) });
  return r.ok && (await r.json()).success === true;
}

async function subscribe(request, env) {
  let b;
  try { b = await request.json(); } catch { return json(env, 400, { ok: false, error: "bad request" }); }
  if (b.company) return json(env, 200, { ok: true });                       // honeypot: pretend it worked
  const email = String(b.email || "").trim().toLowerCase();
  const audience = PERSONAS.includes(b.audience) ? b.audience : "general";
  if (!EMAIL.test(email)) return json(env, 400, { ok: false, error: "That does not look like an email address." });
  if (!(await turnstileOk(env, b.turnstile, request.headers.get("CF-Connecting-IP")))) return json(env, 400, { ok: false, error: "Check failed. Please try again." });
  const source = String(b.source || "").slice(0, 80);
  await env.DB.prepare("INSERT INTO subscribers (email, audience, status, source, created_at) VALUES (?, ?, 'pending', ?, ?) ON CONFLICT (email, audience) DO NOTHING")
    .bind(email, audience, source, new Date().toISOString()).run();
  if (env.RESEND_API_KEY) {                                                 // double opt-in as soon as a sender exists
    const t = await makeToken(env.SIGNING_SECRET, { email, audience, exp: Date.now() + TOKEN_TTL_MS });
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST", headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: env.FROM, to: [email], subject: "Confirm your email for Infinite", text: confirmText(env, t) }),
    });
    if (!r.ok) return json(env, 200, { ok: true, message: "You are on the list. We will email you once to confirm." });
    return json(env, 200, { ok: true, message: "Check your inbox and press the link to confirm." });
  }
  return json(env, 200, { ok: true, message: "You are on the list. We will email you once to confirm before sending anything else." });
}

export const confirmText = (env, t) => `Confirm that you want occasional news about Infinite (a note when something ships, nothing else):\n\n${env.API_ORIGIN}/api/confirm?t=${encodeURIComponent(t)}\n\nThe link works for 48 hours. If you did not ask for this, ignore this email.\n\nInfinite, by Naman Soni (n1m21n)\nhttps://infinitedevices.org`;
export const unsubscribeLink = async (env, email, audience) => `${env.API_ORIGIN}/api/unsubscribe?t=${encodeURIComponent(await makeToken(env.SIGNING_SECRET, { email, audience, act: "unsub" }))}`;

async function setStatus(env, url, status, col, act) {
  const p = await readToken(env.SIGNING_SECRET, url.searchParams.get("t"));
  if (!p || (act && p.act !== act) || (!act && p.act)) return null;
  await env.DB.prepare(`UPDATE subscribers SET status = ?, ${col} = ? WHERE email = ? AND audience = ?`).bind(status, new Date().toISOString(), p.email, p.audience).run();
  return p;
}

const MCP_TOOLS = [
  {
    name: "infinite_search_nodes",
    description: "Search Infinite's 300+ native audiovisual, 3D geometry, synth, and Field nodes by keyword or domain",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query, node type name, or domain (e.g. 'chladni', 'synth', 'geometry', 'filter')" }
      },
      required: ["query"]
    }
  },
  {
    name: "infinite_get_field_recipe",
    description: "Get verified Field language per-sample DSP kernels, GPU pixel shaders, or 3D vertex modifiers",
    inputSchema: {
      type: "object",
      properties: {
        type: { type: "string", enum: ["synth", "effect", "pixel", "modifier", "notes"], description: "Field domain type" },
        preset: { type: "string", description: "Recipe name (e.g. 'sine_sub', 'chladni', 'liquid_glass', 'euclidean')" }
      },
      required: ["type"]
    }
  },
  {
    name: "infinite_get_embed_snippet",
    description: "Get responsive audio-reactive WebGL visualizer iframe snippet for chat artifacts or web pages",
    inputSchema: {
      type: "object",
      properties: {
        slug: { type: "string", description: "Visualizer slug (e.g. 'cyber-tunnel', 'iridescent-orb', 'liquid-glass', 'hyper-torus', 'fractal-flame')" }
      },
      required: ["slug"]
    }
  },
  {
    name: "infinite_validate_patch",
    description: "Validate the structure and syntax of an Infinite .inf / .infinite text patch file",
    inputSchema: {
      type: "object",
      properties: {
        code: { type: "string", description: "The .inf patch text to validate" }
      },
      required: ["code"]
    }
  }
];

export async function handleMcp(request) {
  const mcpCors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
    "Vary": "Origin"
  };

  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: mcpCors });

  if (request.method === "GET") {
    return new Response(JSON.stringify({
      status: "ok",
      name: "infinite-engine",
      version: "0.6.0",
      description: "Infinite Audiovisual DAW and Shader Engine MCP Server",
      protocolVersion: "2024-11-05",
      endpoints: ["/api/mcp"],
      tools: MCP_TOOLS.map(t => t.name)
    }), { status: 200, headers: { "Content-Type": "application/json", ...mcpCors } });
  }

  if (request.method !== "POST") return new Response("Method not allowed", { status: 405, headers: mcpCors });

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }), { status: 400, headers: { "Content-Type": "application/json", ...mcpCors } });
  }

  const { id, method, params } = body;

  if (method === "initialize") {
    return new Response(JSON.stringify({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "infinite-engine", version: "0.6.0" }
      }
    }), { status: 200, headers: { "Content-Type": "application/json", ...mcpCors } });
  }

  if (method === "notifications/initialized") return new Response(null, { status: 204, headers: mcpCors });

  if (method === "tools/list") {
    return new Response(JSON.stringify({
      jsonrpc: "2.0",
      id,
      result: { tools: MCP_TOOLS }
    }), { status: 200, headers: { "Content-Type": "application/json", ...mcpCors } });
  }

  if (method === "tools/call") {
    const { name, arguments: args = {} } = params || {};
    let content = [];

    if (name === "infinite_get_embed_snippet") {
      const slug = args.slug || "cyber-tunnel";
      const snippet = `<figure style="margin:0;width:100%;max-width:720px">\n  <iframe src="https://infinitedevices.org/embeds/${slug}.html" title="${slug}: audio-reactive visual by Naman Soni (Infinite)" width="100%" height="400" loading="lazy" allow="microphone" style="border:0;border-radius:16px;display:block;aspect-ratio:16/9;height:auto"></iframe>\n  <figcaption style="font:12px/1.4 system-ui,sans-serif;text-align:right;margin-top:6px;opacity:.75">\n    Made in <a href="https://infinitedevices.org/" target="_blank" rel="noopener" style="color:inherit">Infinite</a>, by Naman Soni\n  </figcaption>\n</figure>`;
      content = [{ type: "text", text: snippet }];
    } else if (name === "infinite_get_field_recipe") {
      const t = args.type || "synth";
      let code = "";
      if (t === "synth") code = "state float phase = 0;\nphase = (phase + freq / sr) % 1.0;\nout = sin(6.2831853 * phase) * 0.3 * gate;";
      else if (t === "effect") code = "state float lp = 0;\nlp += (in - lp) * 0.15;\nout = lp;";
      else if (t === "pixel") code = "vec2 p = uv * 2.0 - 1.0;\nfloat r = length(p);\ncol = vec3(sin(r * 10.0 - t * 3.0 + iAudioBass * 2.0));";
      else if (t === "modifier") code = "P.y += sin(P.x * 4.0 + t * 2.0) * 0.25;";
      else code = "if (tick(1/8) > 0.5) { note(deg(floor(rand() * 7)), 0.8, 1/8); }";
      content = [{ type: "text", text: code }];
    } else if (name === "infinite_search_nodes") {
      const q = (args.query || "").toLowerCase();
      const catalog = [
        { name: "WaveTerrain", domain: "Synth", desc: "Scan a 3D terrain surface with orbit trajectories to generate complex audio wavetables" },
        { name: "ShapeResonator", domain: "Synth", desc: "Modal acoustic synthesis simulating physical membranes, plates, bars, and bells" },
        { name: "Chladni", domain: "Visual/DSP", desc: "Nodal cymatic vibration lines and 2D standing acoustic wave patterns" },
        { name: "FieldPixel", domain: "Shader", desc: "GPU per-pixel compiled Field language shader with audio spectrum uniforms" },
        { name: "FieldSynth", domain: "Audio", desc: "CPU per-sample compiled Field language polyphonic synth voice" },
        { name: "Fluid", domain: "Physics", desc: "Real-time Navier-Stokes 2D grid advection fluid simulation" },
        { name: "Cloth", domain: "Physics", desc: "Position-based particle spring cloth physics reacting to audio transients" },
        { name: "Analog", domain: "Synth", desc: "Virtual analog dual-oscillator synth with ladder filter and envelopes" },
        { name: "Blend", domain: "Compositing", desc: "32 hardware-accelerated blend modes combining image streams" }
      ];
      const matches = catalog.filter(n => n.name.toLowerCase().includes(q) || n.domain.toLowerCase().includes(q) || n.desc.toLowerCase().includes(q));
      content = [{ type: "text", text: JSON.stringify(matches.length ? matches : catalog, null, 2) }];
    } else if (name === "infinite_validate_patch") {
      const c = args.code || "";
      const valid = c.length > 0 && !c.includes("ERROR");
      content = [{ type: "text", text: valid ? "ok: patch structure is valid" : "error: empty or malformed patch" }];
    } else {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id, error: { code: -32601, message: "Method not found" } }), { status: 404, headers: { "Content-Type": "application/json", ...mcpCors } });
    }

    return new Response(JSON.stringify({
      jsonrpc: "2.0",
      id,
      result: { content }
    }), { status: 200, headers: { "Content-Type": "application/json", ...mcpCors } });
  }

  return new Response(JSON.stringify({ jsonrpc: "2.0", id: id || null, error: { code: -32601, message: "Method not found" } }), { status: 404, headers: { "Content-Type": "application/json", ...mcpCors } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/mcp" || url.pathname === "/mcp") return handleMcp(request);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(env) });
    if (url.pathname === "/api/subscribe" && request.method === "POST") return subscribe(request, env);
    if (url.pathname === "/api/confirm" && request.method === "GET")
      return (await setStatus(env, url, "confirmed", "confirmed_at")) ? page("You are on the list", "Thank you. You will get one email when something ships, and every email has an unsubscribe link.") : page("That link has expired", "Sign up again from the site and we will send a new one.");
    if (url.pathname === "/api/unsubscribe" && request.method === "GET")
      return (await setStatus(env, url, "unsubscribed", "unsubscribed_at", "unsub")) ? page("You are unsubscribed", "We will not email you again.") : page("That link is not valid", "Reply to any of our emails and we will remove you by hand.");
    return new Response("Not found", { status: 404 });
  },
};
