"use client";

import { useEffect, useState } from "react";

import { HORIZON, type GoldDiceGame } from "@/lib/engine";
import type { Explanation } from "@/lib/explain";
import type { Model } from "@/lib/models";
import type { GameAnalysis } from "@/lib/oracle";
import { top, type Entry } from "@/lib/leaderboard";

export interface RivalState {
  model: Model;
  game: GoldDiceGame;
  lastMove: string;
  explanation: Explanation | null;
}

export function Rivals({
  rivals,
  yourPoints,
  onExplain,
}: {
  rivals: RivalState[];
  yourPoints: number;
  onExplain: (r: RivalState) => void;
}) {
  const leader = Math.max(yourPoints, ...rivals.map((r) => r.game.points));
  return (
    <div className="panel">
      <div className="panel-head">
        <h2 className="panel-title">La mesa</h2>
        <span className="note" style={{ fontSize: 11 }}>
          mismos dados, mismas tormentas
        </span>
      </div>
      <div className="panel-body">
        <div className="rivals">
          <div className={`rival you ${yourPoints === leader ? "leading" : ""}`}>
            <span className="rival-name">Vos</span>
            <span className="rival-algo">humano</span>
            <span className="rival-score num">{yourPoints}</span>
          </div>
          {rivals.map((r) => (
            <div key={r.model.id} className={`rival ${r.game.points === leader ? "leading" : ""}`}>
              <span className="rival-name">{r.model.label}</span>
              <span className="rival-algo">
                {r.model.algo} · {r.model.mean.toFixed(0)} de media
              </span>
              <span className="rival-score num">{r.game.points}</span>
              {r.lastMove && (
                <span className="rival-move">
                  <span>{r.lastMove}</span>
                  <button className="help" title="¿Por qué?" onClick={() => onExplain(r)}>
                    ?
                  </button>
                </span>
              )}
            </div>
          ))}
        </div>
        <p className="note" style={{ marginTop: 12, marginBottom: 0 }}>
          Todos ven la <strong>misma tirada</strong> y la <strong>misma tormenta</strong> cada turno. La
          diferencia de puntaje no tiene nada de suerte adentro: son las decisiones.
        </p>
      </div>
    </div>
  );
}

export function ExplainModal({
  title,
  explanation,
  onClose,
}: {
  title: string;
  explanation: Explanation;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="panel modal" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h2 className="panel-title">{title}</h2>
          <button className="btn ghost tiny" onClick={onClose}>
            cerrar
          </button>
        </div>
        <div className="panel-body stack" style={{ gap: 12 }}>
          <p style={{ margin: 0, fontWeight: 700, fontSize: 16, color: "var(--gold)" }}>
            {explanation.headline}
          </p>
          {explanation.reasons.map((r, i) => (
            <p key={i} className="note" style={{ margin: 0 }}>
              {r}
            </p>
          ))}
          {explanation.runnerUp && (
            <p className="note" style={{ margin: 0, borderTop: "1px solid var(--line-soft)", paddingTop: 10 }}>
              {explanation.runnerUp}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function Analysis({ analysis }: { analysis: GameAnalysis }) {
  const luckPositive = analysis.luck >= 0;
  const maxRegret = Math.max(1, ...analysis.turns.map((t) => t.regret));
  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-head">
          <h2 className="panel-title">Habilidad y suerte</h2>
          <span className="note" style={{ fontSize: 11 }}>
            contra la solución exacta del juego
          </span>
        </div>
        <div className="panel-body stack" style={{ gap: 16 }}>
          <div className="row" style={{ gap: 34 }}>
            <div className="stat">
              <span className="stat-label">Tu puntaje</span>
              <span className="stat-value num">{analysis.finalScore}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Calidad de decisiones</span>
              <span className="stat-value num gold">{analysis.decisionScore.toFixed(1)}%</span>
              <span className="stat-sub">del óptimo teórico</span>
            </div>
            <div className="stat">
              <span className="stat-label">Suerte</span>
              <span
                className="stat-value num"
                style={{ color: luckPositive ? "var(--good)" : "var(--storm)" }}
              >
                {luckPositive ? "+" : ""}
                {analysis.luck.toFixed(0)}
              </span>
              <span className="stat-sub">{luckPositive ? "el azar te favoreció" : "el azar te castigó"}</span>
            </div>
          </div>

          <p className="note" style={{ margin: 0 }}>
            La partida que jugaste valía <strong className="num">{analysis.skill.toFixed(0)}</strong> puntos
            esperados: el óptimo es <span className="num">{analysis.optimal.toFixed(0)}</span> y tus decisiones
            regalaron <span className="num">{analysis.totalRegret.toFixed(0)}</span>. Sacaste{" "}
            <strong className="num">{analysis.finalScore}</strong>, así que el azar puso{" "}
            <strong className="num">
              {luckPositive ? "+" : ""}
              {analysis.luck.toFixed(0)}
            </strong>
            . Las dos cosas suman tu resultado, exacto.
          </p>

          <div>
            <span className="stat-label" style={{ display: "block", marginBottom: 6 }}>
              Puntos perdidos por turno
            </span>
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${HORIZON}, 1fr)`, gap: 2, alignItems: "end", height: 56 }}>
              {analysis.turns.map((t) => (
                <div
                  key={t.turn}
                  title={`Turno ${t.turn}: ${t.regret.toFixed(1)} puntos`}
                  style={{
                    height: `${Math.max(2, (t.regret / maxRegret) * 100)}%`,
                    background: t.regret > 0.5 ? "var(--storm)" : "var(--line)",
                    borderRadius: 1,
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2 className="panel-title">Tus tres jugadas más caras</h2>
        </div>
        <div className="panel-body">
          <table className="ledger">
            <thead>
              <tr>
                <th className="r">Turno</th>
                <th>Jugaste</th>
                <th>Convenía</th>
                <th className="r">Costo</th>
              </tr>
            </thead>
            <tbody>
              {analysis.worst.map((t) => (
                <tr key={t.turn}>
                  <td className="r num">{t.turn}</td>
                  <td>{t.played}</td>
                  <td style={{ color: "var(--gold)" }}>{t.bestLabel}</td>
                  <td className="r num">−{t.regret.toFixed(1)}</td>
                </tr>
              ))}
              {analysis.worst.every((t) => t.regret < 0.05) && (
                <tr>
                  <td colSpan={4} className="note">
                    Ninguna jugada perdió nada medible. Partida impecable.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function LeaderboardPanel({ refreshKey }: { refreshKey: number }) {
  const [by, setBy] = useState<"decision" | "score">("decision");
  const [rows, setRows] = useState<Entry[]>([]);

  useEffect(() => {
    let alive = true;
    top(by).then((r) => alive && setRows(r));
    return () => {
      alive = false;
    };
  }, [by, refreshKey]);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2 className="panel-title">Tabla</h2>
        <div className="tabs">
          <button className="tab" aria-selected={by === "decision"} onClick={() => setBy("decision")}>
            decisiones
          </button>
          <button className="tab" aria-selected={by === "score"} onClick={() => setBy("score")}>
            puntaje
          </button>
        </div>
      </div>
      <div className="panel-body">
        {rows.length === 0 ? (
          <p className="note" style={{ margin: 0 }}>
            Todavía no jugó nadie. Sé el primero.
          </p>
        ) : (
          <table className="ledger">
            <thead>
              <tr>
                <th className="r">#</th>
                <th>Nombre</th>
                <th className="r">Decisiones</th>
                <th className="r">Puntaje</th>
                <th className="r">Suerte</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.name}-${r.at}-${i}`}>
                  <td className="r num" style={{ color: "var(--faint)" }}>
                    {i + 1}
                  </td>
                  <td>{r.name}</td>
                  <td className="r num" style={{ color: by === "decision" ? "var(--gold)" : undefined }}>
                    {r.decision.toFixed(1)}%
                  </td>
                  <td className="r num">{r.score}</td>
                  <td className="r num" style={{ color: r.luck >= 0 ? "var(--good)" : "var(--storm)" }}>
                    {r.luck >= 0 ? "+" : ""}
                    {r.luck.toFixed(0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="note" style={{ marginTop: 12, marginBottom: 0 }}>
          El ranking por <strong>decisiones</strong> no se puede farmear volviendo a tirar: mide qué
          porcentaje del óptimo capturaron tus jugadas, no cuánta suerte tuviste.
        </p>
      </div>
    </div>
  );
}
