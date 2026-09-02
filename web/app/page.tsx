"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ActionBar, Ledger, ScorePicker } from "@/components/Board";
import { Analysis, ExplainModal, LeaderboardPanel, Rivals, type RivalState } from "@/components/Panels";
import { GoldDiceGame, HORIZON, SCORE, type Action, type Obs } from "@/lib/engine";
import { compareMoves, explain, type Explanation } from "@/lib/explain";
import { recallName, rememberName, submit } from "@/lib/leaderboard";
import { actionLabel, loadModels, type Manifest, type Model } from "@/lib/models";
import { analyze, loadOracle, type GameAnalysis } from "@/lib/oracle";
import { makeRandomness, randomSeed } from "@/lib/rng";

type Phase = "loading" | "setup" | "playing" | "done";
type Mode = "solo" | "uno" | "tres";

const MODE_LABEL: Record<Mode, string> = {
  solo: "Solo",
  uno: "Contra el Campeón",
  tres: "Contra los tres",
};

export default function Page() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [models, setModels] = useState<Model[]>([]);

  const [name, setName] = useState("");
  const [mode, setMode] = useState<Mode>("tres");
  const [coach, setCoach] = useState(true);

  const [seed, setSeed] = useState(0);
  const [version, bump] = useState(0);
  const gameRef = useRef<GoldDiceGame | null>(null);
  const rivalsRef = useRef<RivalState[]>([]);
  const obsLog = useRef<Obs[]>([]);

  const [scoring, setScoring] = useState<number | null>(null);
  const [modal, setModal] = useState<{ title: string; explanation: Explanation } | null>(null);
  const [feedback, setFeedback] = useState<{ text: string; tone: string } | null>(null);
  const [analysis, setAnalysis] = useState<GameAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [boardKey, setBoardKey] = useState(0);

  // ---------------------------------------------------------------- carga
  useEffect(() => {
    loadModels()
      .then(({ manifest, models }) => {
        setManifest(manifest);
        setModels(models);
        setName(recallName());
        setPhase("setup");
      })
      .catch((e) => setError(String(e?.message ?? e)));
  }, []);

  const champion = models[0];

  const chosenModels = useMemo(() => {
    if (mode === "solo") return [];
    if (mode === "uno") return champion ? [champion] : [];
    return models;
  }, [mode, models, champion]);

  // ---------------------------------------------------------------- juego
  const start = useCallback(() => {
    const s = randomSeed();
    setSeed(s);
    gameRef.current = new GoldDiceGame(makeRandomness(s));
    rivalsRef.current = chosenModels.map((model) => ({
      model,
      game: new GoldDiceGame(makeRandomness(s)),
      lastMove: "",
      explanation: null,
    }));
    obsLog.current = [];
    setAnalysis(null);
    setFeedback(null);
    setScoring(null);
    setPhase("playing");
    bump((v) => v + 1);
  }, [chosenModels]);

  const finish = useCallback(async () => {
    const game = gameRef.current;
    if (!game || !manifest) return;
    setPhase("done");
    setAnalyzing(true);
    try {
      const oracle = await loadOracle(manifest.oracle);
      const result = analyze(oracle, obsLog.current, game.history);
      setAnalysis(result);
      if (name.trim()) {
        rememberName(name.trim());
        await submit({
          name: name.trim(),
          score: result.finalScore,
          decision: result.decisionScore,
          luck: result.luck,
          seed,
          mode: MODE_LABEL[mode],
          at: Date.now(),
        });
        setBoardKey((k) => k + 1);
      }
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setAnalyzing(false);
    }
  }, [manifest, name, seed, mode]);

  const play = useCallback(
    (action: Action, amount: number | null) => {
      const game = gameRef.current;
      if (!game || game.done) return;

      const obs = game.obs();
      obsLog.current.push(obs);

      // Lo que hubiera hecho el Campeón en TU posición, calculado antes de jugar.
      if (coach && champion) {
        const ranked = champion.rank(obs);
        const yours = actionLabel(action, amount);
        const theirs = ranked[0].label;
        const played = ranked.find((r) => r.action === action);
        const gap = played ? ranked[0].value - played.value : 0;
        const cmp = compareMoves(yours, theirs, gap);
        setFeedback({ text: cmp.verdict, tone: cmp.tone });
      }

      game.step(action, amount);

      for (const rival of rivalsRef.current) {
        if (rival.game.done) continue;
        const rObs = rival.game.obs();
        const ranked = rival.model.rank(rObs);
        const move = ranked[0];
        rival.lastMove = `turno ${rObs.turn}: ${move.label}`;
        rival.explanation = explain(rObs, ranked);
        rival.game.step(move.action, move.scoreAmount);
      }

      setScoring(null);
      bump((v) => v + 1);
      if (game.done) void finish();
    },
    [coach, champion, finish],
  );

  const onPick = useCallback(
    (action: Action) => {
      const game = gameRef.current;
      if (!game) return;
      if (action === SCORE) {
        setScoring(game.gold);
        return;
      }
      play(action, null);
    },
    [play],
  );

  // ---------------------------------------------------------------- vistas
  if (error) {
    return (
      <main className="shell">
        <div className="panel">
          <div className="panel-body">
            <p style={{ margin: 0, color: "var(--storm)", fontWeight: 700 }}>Algo se rompió</p>
            <p className="note">{error}</p>
          </div>
        </div>
      </main>
    );
  }

  if (phase === "loading") {
    return (
      <main className="shell">
        <p className="note">Cargando los modelos entrenados…</p>
      </main>
    );
  }

  const game = gameRef.current;
  const obs = game?.obs();
  const recommended = coach && champion && obs && !game!.done ? champion.act(obs).action : null;

  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <h1 className="wordmark">
            Gold <em>Dice</em> RL
          </h1>
          <p className="tagline">
            Jugá contra agentes entrenados con aprendizaje por refuerzos — y descubrí, contra la solución
            exacta del juego, cuánto de tu resultado fue decisión y cuánto fue suerte.
          </p>
        </div>
        {manifest && (
          <div className="masthead-right">
            <div className="stat">
              <span className="stat-label">Juego perfecto</span>
              <span className="stat-value num gold" style={{ fontSize: 20 }}>
                {manifest.oracle.mean?.toFixed(0) ?? manifest.optimal.toFixed(0)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Mejor agente</span>
              <span className="stat-value num" style={{ fontSize: 20 }}>
                {champion?.mean.toFixed(0)}
              </span>
            </div>
          </div>
        )}
      </header>

      {phase === "setup" && (
        <div className="grid-main">
          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Empezar</h2>
            </div>
            <div className="panel-body stack" style={{ gap: 16 }}>
              <div className="stack" style={{ gap: 6 }}>
                <label className="stat-label" htmlFor="nombre">
                  Tu nombre (sin cuenta, sin mail)
                </label>
                <input
                  id="nombre"
                  type="text"
                  value={name}
                  maxLength={24}
                  placeholder="Cómo querés aparecer en la tabla"
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="stack" style={{ gap: 6 }}>
                <span className="stat-label">Modo</span>
                <div className="tabs">
                  {(["solo", "uno", "tres"] as Mode[]).map((m) => (
                    <button key={m} className="tab" aria-selected={mode === m} onClick={() => setMode(m)}>
                      {MODE_LABEL[m]}
                    </button>
                  ))}
                </div>
              </div>

              <label className="row" style={{ gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={coach} onChange={(e) => setCoach(e.target.checked)} />
                <span className="note" style={{ margin: 0 }}>
                  Modo aprendizaje: marcar la jugada del Campeón y comparar con la tuya en cada turno.
                </span>
              </label>

              <button className="btn primary" onClick={start} style={{ justifySelf: "start" }}>
                Jugar 30 turnos
              </button>

              <div className="note" style={{ borderTop: "1px solid var(--line-soft)", paddingTop: 12 }}>
                <p style={{ marginTop: 0 }}>
                  <strong>Cómo se juega.</strong> Treinta turnos. Cada turno tirás tus dados y el oro se suma.
                  Con ese oro podés hacer <strong>una sola cosa</strong>: convertirlo en puntos, comprar un
                  dado, mejorar todos los dados, comprar un escudo, o pagar 4 para volver a cobrar el dado más
                  alto el turno que viene.
                </p>
                <p>
                  Después de tu jugada, con probabilidad 15 % cae una <strong>tormenta</strong> y te parte el
                  oro al medio. Los puntos no se tocan: ya están en el banco. Un escudo bloquea una tormenta.
                </p>
                <p style={{ marginBottom: 0 }}>
                  Y el detalle que decide todo: <strong>en el turno 30 no hay tirada después</strong>, así que
                  el oro que no hayas convertido se evapora.
                </p>
              </div>
            </div>
          </div>

          <div className="stack">
            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title">Los rivales</h2>
              </div>
              <div className="panel-body">
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Agente</th>
                      <th>Cómo aprendió</th>
                      <th className="r">Media</th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.map((m) => (
                      <tr key={m.id}>
                        <td style={{ fontWeight: 700 }}>{m.label}</td>
                        <td className="note">{m.algo}</td>
                        <td className="r num">{m.mean.toFixed(0)}</td>
                      </tr>
                    ))}
                    <tr>
                      <td style={{ color: "var(--gold)", fontWeight: 700 }}>Juego perfecto</td>
                      <td className="note">programación dinámica exacta, no aprende</td>
                      <td className="r num gold">{manifest?.oracle.mean?.toFixed(0) ?? "644"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <LeaderboardPanel refreshKey={boardKey} />
          </div>
        </div>
      )}

      {phase === "playing" && game && obs && (
        <div className="grid-main">
          <div className="stack">
            <Ledger game={game} />
            {scoring === null ? (
              <div className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Tu jugada</h2>
                  {recommended !== null && (
                    <span className="pill gold">el Campeón marcaría la opción resaltada</span>
                  )}
                </div>
                <div className="panel-body stack" style={{ gap: 12 }}>
                  <ActionBar
                    obs={obs}
                    valid={game.validActions()}
                    recommended={recommended}
                    onPick={onPick}
                    disabled={game.done}
                  />
                  {feedback && (
                    <p
                      className="note"
                      style={{
                        margin: 0,
                        color:
                          feedback.tone === "same"
                            ? "var(--good)"
                            : feedback.tone === "close"
                              ? "var(--muted)"
                              : "var(--gold)",
                      }}
                    >
                      {feedback.text}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <ScorePicker
                gold={game.gold}
                amount={scoring}
                onChange={setScoring}
                onConfirm={() => play(SCORE, scoring)}
                onCancel={() => setScoring(null)}
              />
            )}
          </div>

          <div className="stack">
            {rivalsRef.current.length > 0 && (
              <Rivals
                rivals={rivalsRef.current}
                yourPoints={game.points}
                onExplain={(r) =>
                  r.explanation && setModal({ title: `${r.model.label} — ${r.lastMove}`, explanation: r.explanation })
                }
              />
            )}
            {champion && !game.done && (
              <div className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Consultá al Campeón</h2>
                </div>
                <div className="panel-body">
                  <button
                    className="btn"
                    onClick={() =>
                      setModal({
                        title: `El Campeón en tu posición — turno ${obs.turn}`,
                        explanation: explain(obs, champion.rank(obs)),
                      })
                    }
                  >
                    ¿Qué harías vos acá?
                  </button>
                  <p className="note" style={{ marginBottom: 0, marginTop: 10 }}>
                    Explica su jugada con los números que realmente calculó. Sin llamadas a ninguna API.
                  </p>
                </div>
              </div>
            )}
            <LeaderboardPanel refreshKey={boardKey} />
          </div>
        </div>
      )}

      {phase === "done" && game && (
        <div className="grid-main">
          <div className="stack">
            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title">Fin de la partida</h2>
                <span className="note" style={{ fontSize: 11 }}>
                  semilla <span className="num">{seed}</span>
                </span>
              </div>
              <div className="panel-body center stack" style={{ gap: 12 }}>
                <div>
                  <span className="stat-label" style={{ display: "block" }}>
                    Puntaje final
                  </span>
                  <span className="mono-lg num gold">{game.points}</span>
                </div>
                <div className="row" style={{ justifyContent: "center", gap: 10 }}>
                  <button className="btn primary" onClick={start}>
                    Jugar otra
                  </button>
                  <button className="btn ghost" onClick={() => setPhase("setup")}>
                    cambiar modo
                  </button>
                </div>
              </div>
            </div>
            {analyzing && <p className="note">Cargando el solver exacto para analizar tu partida…</p>}
            {analysis && <Analysis analysis={analysis} />}
          </div>
          <div className="stack">
            {rivalsRef.current.length > 0 && (
              <Rivals
                rivals={rivalsRef.current}
                yourPoints={game.points}
                onExplain={(r) =>
                  r.explanation && setModal({ title: `${r.model.label} — ${r.lastMove}`, explanation: r.explanation })
                }
              />
            )}
            <LeaderboardPanel refreshKey={boardKey} />
          </div>
        </div>
      )}

      {modal && <ExplainModal title={modal.title} explanation={modal.explanation} onClose={() => setModal(null)} />}

      <footer className="note" style={{ marginTop: 34, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
        Trabajo Práctico 1 — Aprendizaje por Refuerzos, Inteligencia Artificial y Neurociencias (UTDT). Los
        agentes corren enteros en tu navegador; el análisis usa la solución exacta del juego, calculada por
        programación dinámica. <span className="num">{HORIZON}</span> turnos, óptimo teórico{" "}
        <span className="num">642</span> puntos.
      </footer>
    </main>
  );
}
