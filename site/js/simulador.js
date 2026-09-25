// Simulador do restante do Brasileirão 2026, no navegador (e no Node, para o teste que compara com o Python).
//
// Sorteia o placar de cada jogo restante a partir da grade de placares do modelo. O visitante pode fixar o
// resultado de alguns jogos (vitória, empate ou derrota); aí o placar é sorteado só entre os placares daquele
// resultado. A classificação segue o Art. 15 do regulamento: pontos, vitórias, saldo, gols pró, confronto
// direto (só entre 2 clubes) e sorteio no lugar dos cartões.

export const ZONA_DE_QUEDA = 17;

// gerador de números aleatórios com semente: o mesmo cenário dá sempre o mesmo número
function mulberry32(semente) {
  let a = semente >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// resultado de um placar do ponto de vista do mandante: 0 vitória, 1 empate, 2 derrota
const resultadoDoPlacar = (gm, gv) => (gm > gv ? 0 : gm === gv ? 1 : 2);

function prepararJogo(jogo, idx) {
  const n = jogo.grade.length;
  const celulas = [];
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) celulas.push({ gm: i, gv: j, p: jogo.grade[i][j] });
  const acumular = (lista) => {
    let soma = 0;
    const acc = new Float64Array(lista.length);
    lista.forEach((c, k) => { soma += c.p; acc[k] = soma; });
    return { lista, acc, soma };
  };
  return {
    m: idx[jogo.mandante], v: idx[jogo.visitante],
    todos: acumular(celulas),
    porResultado: [0, 1, 2].map((r) => acumular(celulas.filter((c) => resultadoDoPlacar(c.gm, c.gv) === r))),
  };
}

function sortear({ lista, acc, soma }, u) {
  const alvo = u * soma;
  let lo = 0, hi = acc.length - 1;
  while (lo < hi) {
    const meio = (lo + hi) >> 1;
    if (acc[meio] < alvo) lo = meio + 1; else hi = meio;
  }
  return lista[lo];
}

/**
 * @param dados    conteúdo de data/previsao.json
 * @param fixos    { indiceDoJogo: 0 | 1 | 2 }  resultado fixado, do ponto de vista do MANDANTE
 * @param n        número de temporadas simuladas
 * @returns        { times, chanceQueda[], posicoes[time][pos], n }
 */
export function simular(dados, fixos = {}, n = 10000, semente = 2026) {
  const rng = mulberry32(semente);
  const times = dados.times.map((t) => t.time);
  const k = times.length;
  const idx = Object.fromEntries(times.map((t, i) => [t, i]));
  const jogos = dados.jogos.map((j) => prepararJogo(j, idx));

  // jogos restantes de cada par de times, para o confronto direto
  const restantesDoPar = new Map();
  jogos.forEach((j, g) => {
    const chave = j.m < j.v ? j.m * k + j.v : j.v * k + j.m;
    if (!restantesDoPar.has(chave)) restantesDoPar.set(chave, []);
    restantesDoPar.get(chave).push(g);
  });
  const disputados = new Map();
  for (const [par, [pa, pb, saldoA]] of Object.entries(dados.confrontos)) {
    const [a, b] = par.split("|").map((t) => idx[t]);
    disputados.set(a < b ? a * k + b : b * k + a, a < b ? { pa, pb, saldo: saldoA } : { pa: pb, pb: pa, saldo: -saldoA });
  }

  const base = dados.times;
  const pts = new Int32Array(k), vit = new Int32Array(k), gp = new Int32Array(k), gc = new Int32Array(k);
  const gm = new Int8Array(jogos.length), gv = new Int8Array(jogos.length);
  const chave = new Float64Array(k);
  const ordem = Array.from({ length: k }, (_, i) => i);
  const posicoes = Array.from({ length: k }, () => new Int32Array(k));
  const caiu = new Int32Array(k);

  // x (índice menor) à frente de y no confronto direto? 1 sim, -1 não, 0 empate
  function confronto(x, y) {
    const [a, b] = x < y ? [x, y] : [y, x];
    const par = a * k + b;
    const d = disputados.get(par) ?? { pa: 0, pb: 0, saldo: 0 };
    let pa = d.pa, pb = d.pb, saldo = d.saldo;
    for (const g of restantesDoPar.get(par) ?? []) {
      const j = jogos[g];
      const [ga, gb] = j.m === a ? [gm[g], gv[g]] : [gv[g], gm[g]];
      pa += ga > gb ? 3 : ga === gb ? 1 : 0;
      pb += gb > ga ? 3 : ga === gb ? 1 : 0;
      saldo += ga - gb;
    }
    const cmp = pa !== pb ? Math.sign(pa - pb) : Math.sign(saldo);
    return x === a ? cmp : -cmp;
  }

  for (let s = 0; s < n; s++) {
    for (let i = 0; i < k; i++) { pts[i] = base[i].pts; vit[i] = base[i].v; gp[i] = base[i].gp; gc[i] = base[i].gc; }
    for (let g = 0; g < jogos.length; g++) {
      const j = jogos[g];
      const c = sortear(fixos[g] === undefined ? j.todos : j.porResultado[fixos[g]], rng());
      gm[g] = c.gm; gv[g] = c.gv;
      gp[j.m] += c.gm; gc[j.m] += c.gv; gp[j.v] += c.gv; gc[j.v] += c.gm;
      if (c.gm > c.gv) { pts[j.m] += 3; vit[j.m] += 1; }
      else if (c.gm < c.gv) { pts[j.v] += 3; vit[j.v] += 1; }
      else { pts[j.m] += 1; pts[j.v] += 1; }
    }
    // critérios 1º a 3º numa chave só; a parte decimal sorteia a ordem dos empatados
    for (let i = 0; i < k; i++) chave[i] = ((pts[i] * 100 + vit[i]) * 1000 + (gp[i] - gc[i] + 500)) * 1000 + gp[i] + rng() * 0.5;
    ordem.sort((x, y) => chave[y] - chave[x]);
    // 4º critério: confronto direto, só quando exatamente 2 clubes empatam nos critérios 1º a 3º
    for (let p = 0; p < k - 1; p++) {
      const a = ordem[p], b = ordem[p + 1];
      if (Math.floor(chave[a]) !== Math.floor(chave[b])) continue;
      const trio = (p > 0 && Math.floor(chave[ordem[p - 1]]) === Math.floor(chave[a])) ||
                   (p < k - 2 && Math.floor(chave[ordem[p + 2]]) === Math.floor(chave[a]));
      if (!trio && confronto(b, a) > 0) { ordem[p] = b; ordem[p + 1] = a; }
    }
    for (let p = 0; p < k; p++) {
      posicoes[ordem[p]][p] += 1;
      if (p + 1 >= ZONA_DE_QUEDA) caiu[ordem[p]] += 1;
    }
  }
  return {
    times, n,
    chanceQueda: Array.from(caiu, (c) => c / n),
    posicoes: posicoes.map((linha) => Array.from(linha, (c) => c / n)),
  };
}
