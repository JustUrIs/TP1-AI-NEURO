# Gold Dice RL — el juego

Gold Dice RL jugable en el navegador, contra los agentes entrenados para el TP.
Al terminar la partida se analiza contra la solución exacta del juego y se
separa cuánto de tu resultado fue decisión y cuánto fue suerte.

## Correrlo

```bash
npm install
npm run dev          # http://localhost:3000
```

```bash
npm run verify       # typecheck + motor + políticas (ver abajo)
npm run build
```

## Deploy en Vercel

Importás el repo, ponés `web/` como root directory y listo: no hay backend, no
hay variables obligatorias. Los modelos son archivos estáticos en
`public/models/`.

## Leaderboard

Sin login: ponés un nombre y jugás. Dos rankings — **puntaje** (incluye la
suerte) y **decisiones** (el porcentaje del óptimo que capturaron tus jugadas,
medido contra el solver exacto). El segundo no se puede farmear volviendo a
tirar.

Sin configurar nada, el leaderboard guarda en `localStorage` y es local a cada
navegador. Para que sea compartido, creá un proyecto en Supabase con esta tabla:

```sql
create table public.scores (
  id         bigserial primary key,
  name       text        not null check (char_length(name) between 1 and 24),
  score      integer     not null check (score between 0 and 5000),
  decision   real        not null check (decision between -100 and 100),
  luck       real        not null,
  seed       bigint      not null,
  mode       text        not null,
  created_at timestamptz not null default now()
);

alter table public.scores enable row level security;

-- Cualquiera puede leer y agregar su puntaje; nadie puede editar ni borrar.
create policy "lectura publica" on public.scores for select using (true);
create policy "alta publica"   on public.scores for insert with check (true);

create index scores_by_score    on public.scores (score desc);
create index scores_by_decision on public.scores (decision desc);
```

y agregá las variables de entorno:

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

La clave anónima es pública por diseño y con esas políticas solo permite leer y
dar de alta.

## Cómo está armado

Todo corre en el cliente. No hay llamadas a ninguna API, ni siquiera para las
explicaciones de los agentes.

| Archivo | Qué hace |
|---|---|
| `lib/engine.ts` | el juego. Port de `env.py`, verificado turno a turno |
| `lib/rng.ts` | azar compartido entre jugadores: mismos dados, mismas tormentas |
| `lib/models.ts` | los agentes entrenados, leídos de los binarios |
| `lib/oracle.ts` | la solución exacta y la descomposición habilidad / suerte |
| `lib/explain.ts` | explicaciones armadas con los números que el agente calculó |
| `lib/leaderboard.ts` | Supabase o `localStorage` |

Los binarios de `public/models/` los genera
`../gold_dice_rl/export_web.py`. Pesan 1.9 MB comprimidos entre todos, y el
oráculo (1.3 MB de esos) se carga recién al terminar la partida.

## Verificación

Tres chequeos, y los tres importan porque los errores que buscan son
silenciosos.

```bash
npm run verify
```

1. **Tipos.** `tsc --noEmit`.

2. **El motor contra `env.py`.** `scripts/gen_trace.py` inyecta un azar
   guionado en el ambiente original de la cátedra —sin tocarlo— y juega
   partidas con acciones aleatorias legales, incluidas cantidades parciales de
   `SCORE`. `scripts/check_engine.ts` reproduce las mismas tiradas y compara
   todo el estado en cada turno.

   > 60 partidas, 14.460 comparaciones, **0 discrepancias**.

3. **Las políticas contra los agentes de Python.** Un stride mal calculado en
   el export haría que el Campeón juegue distinto en el navegador sin dar
   ningún error. `scripts/gen_policy_probe.py` guarda la jugada de cada agente
   Python en 6.600 estados y `scripts/check_policy.ts` compara.

   > Campeón **6600/6600**, Novato **6600/6600**, Aprendiz 6595/6600.
   > Las 5 diferencias del Aprendiz son estados donde las dos mejores acciones
   > difieren en menos de 0.016 puntos: empates que el redondeo a int16 resuelve
   > para el otro lado.

## Equidad entre jugadores

En `env.py` un único generador sirve los dados y las tormentas, y
`rng.choice(size=num_dice)` consume una cantidad que depende de la política:
desde el primer turno en que dos agentes difieren en cantidad de dados, sus
flujos de azar se desincronizan. No existen números aleatorios comunes en el
ambiente original.

Acá sí, porque el juego controla su propio azar. `rollDice(turno, i)` es una
función pura de la semilla: el que tiene 5 dados usa los primeros 5 valores del
turno y el que tiene 3 usa los primeros 3, y las tormentas caen en los mismos
turnos para todos. **La diferencia de puntaje contra los modelos no tiene nada
de suerte adentro.**
