"use client";

import {
  ACTION_NAMES,
  BUY_DICE,
  BUY_SHIELD,
  HORIZON,
  PASS,
  SCORE,
  SHIELD_COST,
  STORE_BEST_DIE,
  STORE_DIE_COST,
  UPGRADE,
  newDiceCost,
  upgradeCost,
  type Action,
  type GoldDiceGame,
  type Obs,
  type TurnRecord,
} from "@/lib/engine";

export function TurnStrip({ history, turn }: { history: TurnRecord[]; turn: number }) {
  return (
    <div className="turnstrip" aria-label={`Turno ${turn} de ${HORIZON}`}>
      {Array.from({ length: HORIZON }, (_, i) => {
        const t = i + 1;
        const rec = history[i];
        const cls = rec?.storm && !rec.stormBlocked ? "storm" : t === turn ? "now" : t < turn ? "past" : "";
        return <div key={t} className={`tick ${cls}`} title={`Turno ${t}`} />;
      })}
    </div>
  );
}

export function Dice({ raw, bonus }: { raw: number[]; bonus: number }) {
  const best = raw.length ? Math.max(...raw) : 0;
  let bestUsed = false;
  return (
    <div className="tray">
      {raw.map((v, i) => {
        const isBest = v === best && !bestUsed && (bestUsed = true);
        return (
          <div key={i} className={`die num ${isBest ? "best" : ""}`}>
            {v + bonus}
            {bonus > 0 && <span className="die-bonus">+{bonus}</span>}
          </div>
        );
      })}
      {raw.length === 0 && <span className="note">sin tirada</span>}
    </div>
  );
}

const ACTION_ORDER: Action[] = [SCORE, STORE_BEST_DIE, BUY_DICE, UPGRADE, BUY_SHIELD, PASS];

export function costOf(action: Action, obs: Obs): string {
  switch (action) {
    case SCORE:
      return obs.gold > 0 ? `convertís oro en puntos` : "no tenés oro";
    case BUY_DICE:
      return `cuesta ${newDiceCost(obs.numDice)} · ${obs.numDice} → ${obs.numDice + 1} dados`;
    case UPGRADE:
      return `cuesta ${upgradeCost(obs.diceBonus)} · +1 a todos los dados`;
    case BUY_SHIELD:
      return `cuesta ${SHIELD_COST} · bloquea una tormenta`;
    case STORE_BEST_DIE:
      return `cuesta ${STORE_DIE_COST} · cobrás ${obs.rollMax} otra vez`;
    case PASS:
      return "guardás el oro para después";
  }
}

export function ActionBar({
  obs,
  valid,
  recommended,
  onPick,
  disabled,
}: {
  obs: Obs;
  valid: Action[];
  recommended: Action | null;
  onPick: (a: Action) => void;
  disabled: boolean;
}) {
  return (
    <div className="actions">
      {ACTION_ORDER.map((a) => (
        <button
          key={a}
          className={`action ${recommended === a ? "recommended" : ""}`}
          disabled={disabled || !valid.includes(a)}
          onClick={() => onPick(a)}
        >
          <span className="action-name">{ACTION_NAMES[a]}</span>
          <span className="action-cost">{costOf(a, obs)}</span>
        </button>
      ))}
    </div>
  );
}

export function ScorePicker({
  gold,
  amount,
  onChange,
  onConfirm,
  onCancel,
}: {
  gold: number;
  amount: number;
  onChange: (v: number) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="panel" style={{ marginTop: 10 }}>
      <div className="panel-body stack" style={{ gap: 10 }}>
        <div className="row spread">
          <span className="note">
            ¿Cuánto oro convertís en puntos? Lo que dejes queda expuesto a la tormenta.
          </span>
          <span className="num stat-value gold">{amount}</span>
        </div>
        <input
          type="range"
          min={0}
          max={gold}
          value={amount}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ width: "100%" }}
        />
        <div className="row spread">
          <div className="row" style={{ gap: 6 }}>
            <button className="btn tiny" onClick={() => onChange(gold)}>
              todo
            </button>
            <button className="btn tiny" onClick={() => onChange(Math.floor(gold / 2))}>
              mitad
            </button>
            <button className="btn tiny" onClick={() => onChange(0)}>
              nada
            </button>
          </div>
          <div className="row" style={{ gap: 6 }}>
            <button className="btn ghost tiny" onClick={onCancel}>
              cancelar
            </button>
            <button className="btn primary" onClick={onConfirm}>
              puntuar {amount}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Ledger({ game }: { game: GoldDiceGame }) {
  const last = game.history[game.history.length - 1];
  return (
    <div className={`panel ${last?.storm && !last.stormBlocked ? "storm-flash" : ""}`}>
      <div className="panel-head">
        <h2 className="panel-title">Tu libro</h2>
        <div className="row" style={{ gap: 8 }}>
          <span className="pill">
            turno <span className="num">{Math.min(game.turn, HORIZON)}</span>/30
          </span>
          {game.shields > 0 && <span className="pill good">escudos {game.shields}</span>}
          {last?.storm && (
            <span className={`pill ${last.stormBlocked ? "good" : "storm"}`}>
              {last.stormBlocked ? "tormenta bloqueada" : `tormenta −${last.goldLostToStorm}`}
            </span>
          )}
        </div>
      </div>
      <div className="panel-body stack" style={{ gap: 14 }}>
        <TurnStrip history={game.history} turn={game.turn} />
        <div className="row" style={{ gap: 30 }}>
          <div className="stat">
            <span className="stat-label">Puntos</span>
            <span className="stat-value num">{game.points}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Oro</span>
            <span className="stat-value num gold">{game.gold}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Motor</span>
            <span className="stat-value num" style={{ fontSize: 19 }}>
              {game.numDice}d +{game.diceBonus}
            </span>
            <span className="stat-sub num">
              {(game.numDice * (3.5 + game.diceBonus)).toFixed(1)} oro/turno
            </span>
          </div>
        </div>
        <div>
          <span className="stat-label" style={{ display: "block", marginBottom: 7 }}>
            Tirada del turno
          </span>
          <Dice raw={game.rawRoll} bonus={game.diceBonus} />
        </div>
      </div>
    </div>
  );
}
