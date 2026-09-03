const KEY = "gold-dice:leaderboard:v1";

function redisConfig() {
  return {
    url: process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL,
    token: process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN
  };
}

async function command(parts) {
  const cfg = redisConfig();
  if (!cfg.url || !cfg.token) throw new Error("Redis is not configured");
  const response = await fetch(cfg.url + "/" + parts.map(encodeURIComponent).join("/"), {
    headers: { Authorization: "Bearer " + cfg.token },
    cache: "no-store"
  });
  if (!response.ok) throw new Error("Redis request failed");
  const body = await response.json();
  if (body.error) throw new Error(body.error);
  return body.result;
}

function cleanName(value) {
  return String(value || "Anónimo")
    .replace(/[<>\u0000-\u001f\u007f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 20) || "Anónimo";
}

function integer(value, min, max) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= min && parsed <= max ? parsed : null;
}

function decimal(value, min, max) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max
    ? Math.round(parsed * 10) / 10 : null;
}

async function clientHash(req) {
  const ip = String(req.headers["x-forwarded-for"] || "unknown").split(",")[0].trim();
  const bytes = new TextEncoder().encode(ip + ":gold-dice");
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Buffer.from(digest).toString("hex").slice(0, 20);
}

async function rateLimited(req) {
  const bucket = "gold-dice:rate:" + await clientHash(req) + ":" + Math.floor(Date.now() / 60000);
  const count = await command(["INCR", bucket]);
  if (count === 1) await command(["EXPIRE", bucket, "90"]);
  return count > 6;
}

function headers(res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("X-Content-Type-Options", "nosniff");
}

module.exports = async function handler(req, res) {
  headers(res);
  try {
    if (req.method === "GET") {
      const raw = await command(["ZREVRANGE", KEY, "0", "49", "WITHSCORES"]);
      const scores = [];
      for (let i = 0; i < raw.length; i += 2) {
        try {
          const entry = JSON.parse(raw[i]);
          entry.puntaje = Number(raw[i + 1]);
          scores.push(entry);
        } catch (_) { /* Ignorar una fila dañada sin romper el ranking. */ }
      }
      return res.status(200).json({ scores });
    }

    if (req.method !== "POST") {
      res.setHeader("Allow", "GET, POST");
      return res.status(405).json({ error: "Método no permitido" });
    }
    if (await rateLimited(req)) return res.status(429).json({ error: "Demasiados resultados seguidos" });

    const body = req.body || {};
    const puntaje = integer(body.puntaje, 0, 5000);
    const semilla = integer(body.semilla, 0, 0xffffff);
    const nota = decimal(body.nota, 0, 100);
    const suerte = decimal(body.suerte, -5000, 5000);
    if (puntaje === null || semilla === null || nota === null || suerte === null) {
      return res.status(400).json({ error: "Resultado inválido" });
    }

    const entry = {
      id: crypto.randomUUID(),
      nombre: cleanName(body.nombre),
      nota,
      suerte,
      semilla,
      cuando: Date.now()
    };
    await command(["ZADD", KEY, String(puntaje), JSON.stringify(entry)]);
    return res.status(201).json({ saved: true });
  } catch (error) {
    console.error("leaderboard", error.message);
    return res.status(503).json({ error: "El ranking global no está disponible" });
  }
};
