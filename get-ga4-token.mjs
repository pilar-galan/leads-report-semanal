#!/usr/bin/env node
/**
 * get-ga4-token.mjs
 * ─────────────────────────────────────────────────────────────────────────
 * Obtiene un REFRESH TOKEN de Google (GA4 + Search Console) ejecutándose una
 * sola vez en tu ordenador. No necesita ningún paquete de npm: usa solo los
 * módulos integrados de Node.js.
 *
 * USO
 *   1. Crea un archivo .env.local en esta misma carpeta con estas dos líneas:
 *
 *        GSC_CLIENT_ID=tu-client-id.apps.googleusercontent.com
 *        GSC_CLIENT_SECRET=tu-client-secret
 *
 *   2. Ejecuta:   node get-ga4-token.mjs
 *   3. Se abrirá tu navegador. Autoriza con la cuenta de Google que tenga
 *      acceso a la propiedad GA4 (y a Search Console).
 *   4. La terminal mostrará el REFRESH TOKEN. Cópialo y guárdalo como secreto
 *      (p. ej. GA4_REFRESH_TOKEN en GitHub Actions).
 *
 * Requisito: el cliente OAuth debe ser de tipo "Aplicación de escritorio"
 * (Desktop app), que permite el redirect a http://localhost con cualquier
 * puerto sin configuración adicional.
 * ─────────────────────────────────────────────────────────────────────────
 */

import http from "node:http";
import https from "node:https";
import crypto from "node:crypto";
import { readFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { URL, URLSearchParams } from "node:url";

// ── Scopes solicitados (lectura) ─────────────────────────────────────────
// GA4 (Analytics Data API) + Search Console. Un único refresh token sirve
// para ambos. Quita el que no necesites.
const SCOPES = [
  "https://www.googleapis.com/auth/analytics.readonly",
  "https://www.googleapis.com/auth/webmasters.readonly",
];

const REDIRECT_PORT = 5858;
const REDIRECT_URI = `http://localhost:${REDIRECT_PORT}`;

// ── Carga de credenciales desde .env.local ───────────────────────────────
function loadEnvLocal() {
  let raw;
  try {
    raw = readFileSync(new URL(".env.local", import.meta.url), "utf8");
  } catch {
    return;
  }
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = val;
  }
}

loadEnvLocal();

const CLIENT_ID = process.env.GSC_CLIENT_ID;
const CLIENT_SECRET = process.env.GSC_CLIENT_SECRET;

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error(
    "\n❌ Faltan credenciales. Crea un archivo .env.local junto a este script con:\n\n" +
      "   GSC_CLIENT_ID=...\n" +
      "   GSC_CLIENT_SECRET=...\n"
  );
  process.exit(1);
}

// ── PKCE (recomendado para clientes de escritorio) ───────────────────────
function base64url(buf) {
  return buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
const codeVerifier = base64url(crypto.randomBytes(32));
const codeChallenge = base64url(crypto.createHash("sha256").update(codeVerifier).digest());
const state = base64url(crypto.randomBytes(16));

// ── URL de consentimiento ────────────────────────────────────────────────
const authUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
authUrl.search = new URLSearchParams({
  client_id: CLIENT_ID,
  redirect_uri: REDIRECT_URI,
  response_type: "code",
  scope: SCOPES.join(" "),
  access_type: "offline",
  prompt: "consent", // fuerza la entrega del refresh_token
  include_granted_scopes: "true",
  state,
  code_challenge: codeChallenge,
  code_challenge_method: "S256",
}).toString();

// ── Abre el navegador (con fallback a copiar/pegar manual) ───────────────
function openBrowser(url) {
  const cmd =
    process.platform === "darwin"
      ? "open"
      : process.platform === "win32"
      ? "cmd"
      : "xdg-open";
  const args = process.platform === "win32" ? ["/c", "start", "", url] : [url];
  try {
    const child = spawn(cmd, args, { stdio: "ignore", detached: true });
    child.on("error", () => {});
    child.unref();
  } catch {
    /* fallback: el usuario copia la URL manualmente */
  }
}

// ── Intercambio de código por tokens ─────────────────────────────────────
function exchangeCode(code) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      code,
      code_verifier: codeVerifier,
      grant_type: "authorization_code",
      redirect_uri: REDIRECT_URI,
    }).toString();

    const req = https.request(
      "https://oauth2.googleapis.com/token",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => {
          try {
            const json = JSON.parse(data);
            if (res.statusCode !== 200) {
              reject(new Error(`${res.statusCode}: ${data}`));
            } else {
              resolve(json);
            }
          } catch (e) {
            reject(new Error(`Respuesta no válida: ${data}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

// ── Servidor local que captura el callback ───────────────────────────────
const server = http.createServer(async (req, res) => {
  const reqUrl = new URL(req.url, REDIRECT_URI);
  if (reqUrl.pathname !== "/") {
    res.writeHead(404).end();
    return;
  }

  const err = reqUrl.searchParams.get("error");
  const code = reqUrl.searchParams.get("code");
  const returnedState = reqUrl.searchParams.get("state");

  const reply = (msg) => {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(
      `<!doctype html><meta charset="utf-8"><body style="font-family:system-ui;background:#0a0618;color:#f0edff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h2>${msg}</h2><p style="color:#7b76a0">Ya puedes cerrar esta pestaña y volver a la terminal.</p></div></body>`
    );
  };

  if (err) {
    reply("❌ Autorización cancelada");
    console.error(`\n❌ Error de autorización: ${err}`);
    server.close();
    process.exit(1);
  }

  if (returnedState !== state) {
    reply("❌ Estado no válido (posible CSRF)");
    console.error("\n❌ El parámetro 'state' no coincide. Abortando.");
    server.close();
    process.exit(1);
  }

  if (!code) {
    reply("⏳ Esperando código de autorización…");
    return;
  }

  try {
    const tokens = await exchangeCode(code);
    reply("✅ ¡Listo! Refresh token generado.");
    console.log("\n────────────────────────────────────────────────────────");
    if (tokens.refresh_token) {
      console.log("✅ REFRESH TOKEN (guárdalo como secreto):\n");
      console.log(tokens.refresh_token);
    } else {
      console.log(
        "⚠️  No se devolvió refresh_token. Esto ocurre si ya autorizaste antes.\n" +
          "    Revoca el acceso en https://myaccount.google.com/permissions\n" +
          "    y vuelve a ejecutar el script."
      );
    }
    console.log("\nScopes concedidos: " + (tokens.scope || "(desconocido)"));
    console.log("────────────────────────────────────────────────────────\n");
  } catch (e) {
    reply("❌ Error al intercambiar el código");
    console.error("\n❌ Error al obtener el token:\n" + e.message);
    server.close();
    process.exit(1);
  }

  server.close();
  process.exit(0);
});

server.listen(REDIRECT_PORT, () => {
  console.log("\n🔑 Autorización de Google (GA4 + Search Console)\n");
  console.log("Abriendo el navegador… Si no se abre solo, copia y pega esta URL:\n");
  console.log(authUrl.toString() + "\n");
  openBrowser(authUrl.toString());
});
