#include <bits/stdc++.h>
using namespace std;

// DP exacta sobre una grilla finita. El estado es (turno, dados, bonus,
// escudos, oro) antes de tirar. Los puntos no entran: no cambian el futuro.
// Usamos dos capas porque el turno t solo consulta el turno t+1.
const int T = 30, N = 9, B = 9, S = 5, G = 700;
const double STORM = 0.15, NEG = -1e100;

int id(int n, int b, int s, int g) {
    return (((n * (B + 1) + b) * (S + 1) + s) * (G + 1) + g);
}

int dice_cost(int n) { return 18 + 8 * (n - 1); }
int upgrade_cost(int b) { return 8 + 8 * b; }

// Distribucion conjunta de (suma, maximo) de n dados. Es una convolucion,
// no una simulacion, por eso la DP no depende de semillas.
vector<vector<pair<pair<int, int>, double>>> distributions() {
    vector<vector<pair<pair<int, int>, double>>> out(N + 1);
    map<pair<int, int>, double> d{{{0, 0}, 1.0}};
    for (int n = 1; n <= N; ++n) {
        map<pair<int, int>, double> nd;
        for (auto [state, p] : d)
            for (int face = 1; face <= 6; ++face)
                nd[{state.first + face, max(state.second, face)}] += p / 6.0;
        d = nd;
        for (auto x : d) out[n].push_back(x);
    }
    return out;
}

int main() {
    const int SZ = (N + 1) * (B + 1) * (S + 1) * (G + 1);
    vector<double> next(SZ), cur(SZ), stay(G + 1), best(G + 1), store(G + 1);
    auto rolls = distributions();

    // Caso base: en el turno 30 se tira y despues conviene puntuar todo.
    for (int n = 1; n <= N; ++n)
        for (int b = 0; b <= B; ++b)
            for (int s = 0; s <= S; ++s)
                for (int g = 0; g <= G; ++g)
                    next[id(n, b, s, g)] = g + n * (3.5 + b);

    for (int t = T - 1; t >= 1; --t) {
        fill(cur.begin(), cur.end(), 0.0);
        for (int n = 1; n <= N; ++n) for (int b = 0; b <= B; ++b)
        for (int s = 0; s <= S; ++s) {
            auto tail = [&](int nn, int bb, int ss, int gold, int carry = 0) {
                int keep = min(G, gold + carry);
                double v = (1.0 - STORM) * next[id(nn, bb, ss, keep)];
                if (ss) v += STORM * next[id(nn, bb, ss - 1, keep)];
                else v += STORM * next[id(nn, bb, 0, min(G, gold / 2 + carry))];
                return v;
            };
            for (int g = 0; g <= G; ++g) stay[g] = best[g] = tail(n, b, s, g);

            // SCORE(k): g-k queda como oro. maximo prefijo en O(G).
            double pref = NEG;
            for (int g = 0; g <= G; ++g) {
                pref = max(pref, stay[g] - g);
                best[g] = max(best[g], g + pref);
                if (n < N && g >= dice_cost(n))
                    best[g] = max(best[g], tail(n + 1, b, s, g - dice_cost(n)));
                if (b < B && g >= upgrade_cost(b))
                    best[g] = max(best[g], tail(n, b + 1, s, g - upgrade_cost(b)));
                if (s < S && g >= 5)
                    best[g] = max(best[g], tail(n, b, s + 1, g - 5));
            }

            // Antes de decidir observamos suma y maximo. STORE depende del maximo.
            for (int gold = 0; gold <= G; ++gold) {
                double expected = 0.0;
                for (auto [roll, p] : rolls[n]) {
                    int g = min(G, gold + roll.first + n * b);
                    double decision = best[g];
                    if (g >= 4) decision = max(decision, tail(n, b, s, g - 4, roll.second + b));
                    expected += p * decision;
                }
                cur[id(n, b, s, gold)] = expected;
            }
        }
        next.swap(cur);
    }
    cout << fixed << setprecision(3) << next[id(1, 0, 0, 0)] << '\n';
}
