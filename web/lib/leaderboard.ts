/**
 * Tabla de posiciones, sin login.
 *
 * Dos rankings, y el segundo es el que importa:
 *
 *   puntaje     lo que sacaste. Incluye la suerte.
 *   decisiones  el porcentaje del óptimo que capturaron tus decisiones, medido
 *               contra el solver exacto. No se puede farmear volviendo a tirar:
 *               una partida con suerte no lo sube.
 *
 * Persistencia: Supabase si están las variables de entorno, y si no
 * `localStorage`. El juego tiene que funcionar recién clonado y sin configurar
 * nada — un leaderboard local es mejor que una pantalla de error.
 */

export interface Entry {
  name: string;
  score: number;
  decision: number;
  luck: number;
  seed: number;
  mode: string;
  at: number;
}

const KEY = "golddice.leaderboard.v1";
const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const isRemote = Boolean(URL && ANON);

function readLocal(): Entry[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as Entry[];
  } catch {
    return [];
  }
}

function writeLocal(entries: Entry[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries.slice(0, 400)));
  } catch {
    /* modo privado, cuota llena: el juego sigue andando igual */
  }
}

export async function submit(entry: Entry): Promise<void> {
  if (isRemote) {
    try {
      const res = await fetch(`${URL}/rest/v1/scores`, {
        method: "POST",
        headers: {
          apikey: ANON!,
          Authorization: `Bearer ${ANON}`,
          "Content-Type": "application/json",
          Prefer: "return=minimal",
        },
        body: JSON.stringify({
          name: entry.name.slice(0, 24),
          score: entry.score,
          decision: entry.decision,
          luck: entry.luck,
          seed: entry.seed,
          mode: entry.mode,
        }),
      });
      if (res.ok) return;
    } catch {
      /* si la red falla, cae al guardado local */
    }
  }
  writeLocal([entry, ...readLocal()]);
}

export async function top(by: "score" | "decision", limit = 12): Promise<Entry[]> {
  if (isRemote) {
    try {
      const res = await fetch(
        `${URL}/rest/v1/scores?select=name,score,decision,luck,seed,mode,created_at&order=${by}.desc&limit=${limit}`,
        { headers: { apikey: ANON!, Authorization: `Bearer ${ANON}` } },
      );
      if (res.ok) {
        const rows = (await res.json()) as (Omit<Entry, "at"> & { created_at: string })[];
        return rows.map((r) => ({ ...r, at: Date.parse(r.created_at) }));
      }
    } catch {
      /* cae al local */
    }
  }
  return readLocal()
    .sort((a, b) => (by === "score" ? b.score - a.score : b.decision - a.decision))
    .slice(0, limit);
}

export function rememberName(name: string) {
  try {
    localStorage.setItem("golddice.name", name);
  } catch {
    /* ignorar */
  }
}

export function recallName(): string {
  try {
    return localStorage.getItem("golddice.name") ?? "";
  } catch {
    return "";
  }
}
