// Simulador do restante do Brasileirão 2026, no navegador (e no Node, para o teste que compara com o Python).
//
// Sorteia o placar de cada jogo restante a partir da grade de placares do modelo. O visitante pode fixar o
// resultado de alguns jogos (vitória, empate ou derrota); aí o placar é sorteado só entre os placares daquele
// resultado. A classificação segue o Art. 15 do regulamento: pontos, vitórias, saldo, gols pró, confronto
// direto (só entre 2 clubes) e sorteio no lugar dos cartões.

export const ZONA_DE_QUEDA = 17;
// temporadas por cenário no navegador: o mesmo número da previsão principal
export const N_NAVEGADOR = 100_000;
// o cálculo é dividido em partes com sementes fixas, que rodam em paralelo nos núcleos do aparelho;
// o resultado é o mesmo com 1 ou 8 núcleos
export const PARTES = 8;
export const sementeDaParte = (p) => 2026 + p;

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

// placares possíveis de um jogo (todos, ou só os de um resultado fixado) em vetores, prontos para sortear
function distribuicao(grade, resultado) {
  const gm = [], gv = [], p = [];
  for (let i = 0; i < grade.length; i++) {
    for (let j = 0; j < grade.length; j++) {
      if (resultado !== undefined && resultadoDoPlacar(i, j) !== resultado) continue;
      gm.push(i); gv.push(j); p.push(grade[i][j]);
    }
  }
  // método do alias (Walker): sorteio em tempo constante, com um único número aleatório
  const n = p.length, soma = p.reduce((s, x) => s + x, 0);
  const prob = new Float64Array(n), alias = new Int32Array(n);
  const escala = p.map((x) => (x / soma) * n);
  const pequenos = [], grandes = [];
  escala.forEach((x, i) => (x < 1 ? pequenos : grandes).push(i));
  while (pequenos.length && grandes.length) {
    const a = pequenos.pop(), g = grandes.pop();
    prob[a] = escala[a]; alias[a] = g;
    escala[g] = escala[g] + escala[a] - 1;
    (escala[g] < 1 ? pequenos : grandes).push(g);
  }
  for (const i of [...pequenos, ...grandes]) { prob[i] = 1; alias[i] = i; }
  return { gm: Int8Array.from(gm), gv: Int8Array.from(gv), prob, alias, n };
}

/**
 * @param dados    conteúdo de data/previsao.json
 * @param fixos    { indiceDoJogo: 0 | 1 | 2 }  resultado fixado, do ponto de vista do MANDANTE
 * @param n        número de temporadas simuladas
 * @returns        { times, chanceQueda[], posicoes[time][pos], n }
 */
export function simular(dados, fixos = {}, n = N_NAVEGADOR, semente = 2026) {
  const rng = mulberry32(semente);
  const times = dados.times.map((t) => t.time);
  const k = times.length;
  const idx = Object.fromEntries(times.map((t, i) => [t, i]));
  const nj = dados.jogos.length;
  const mand = new Int32Array(nj), vis = new Int32Array(nj);
  const dist = dados.jogos.map((j, g) => {
    mand[g] = idx[j.mandante]; vis[g] = idx[j.visitante];
    return distribuicao(j.grade, fixos[g]);
  });

  // jogos restantes de cada par de times, para o confronto direto
  const restantesDoPar = new Map();
  for (let g = 0; g < nj; g++) {
    const chave = mand[g] < vis[g] ? mand[g] * k + vis[g] : vis[g] * k + mand[g];
    if (!restantesDoPar.has(chave)) restantesDoPar.set(chave, []);
    restantesDoPar.get(chave).push(g);
  }
  const disputados = new Map();
  for (const [par, [pa, pb, saldoA]] of Object.entries(dados.confrontos)) {
    const [a, b] = par.split("|").map((t) => idx[t]);
    disputados.set(a < b ? a * k + b : b * k + a, a < b ? { pa, pb, saldo: saldoA } : { pa: pb, pb: pa, saldo: -saldoA });
  }

  const basePts = Int32Array.from(dados.times, (t) => t.pts), baseVit = Int32Array.from(dados.times, (t) => t.v);
  const baseGp = Int32Array.from(dados.times, (t) => t.gp), baseGc = Int32Array.from(dados.times, (t) => t.gc);
  const pts = new Int32Array(k), vit = new Int32Array(k), gp = new Int32Array(k), gc = new Int32Array(k);
  const gm = new Int8Array(nj), gv = new Int8Array(nj);
  const chave = new Float64Array(k);
  const ordem = Int32Array.from({ length: k }, (_, i) => i);
  const posicoes = Array.from({ length: k }, () => new Int32Array(k));
  const caiu = new Int32Array(k);

  // x (índice menor) à frente de y no confronto direto? 1 sim, -1 não, 0 empate
  function confronto(x, y) {
    const [a, b] = x < y ? [x, y] : [y, x];
    const par = a * k + b;
    const d = disputados.get(par) ?? { pa: 0, pb: 0, saldo: 0 };
    let pa = d.pa, pb = d.pb, saldo = d.saldo;
    for (const g of restantesDoPar.get(par) ?? []) {
      const [ga, gb] = mand[g] === a ? [gm[g], gv[g]] : [gv[g], gm[g]];
      pa += ga > gb ? 3 : ga === gb ? 1 : 0;
      pb += gb > ga ? 3 : ga === gb ? 1 : 0;
      saldo += ga - gb;
    }
    const cmp = pa !== pb ? Math.sign(pa - pb) : Math.sign(saldo);
    return x === a ? cmp : -cmp;
  }

  for (let s = 0; s < n; s++) {
    pts.set(basePts); vit.set(baseVit); gp.set(baseGp); gc.set(baseGc);
    for (let g = 0; g < nj; g++) {
      // sorteia um placar: o número aleatório escolhe uma célula e decide entre ela e o seu alias
      const d = dist[g];
      const u = rng() * d.n, i = u | 0;
      const c = u - i < d.prob[i] ? i : d.alias[i];
      const a = d.gm[c], b = d.gv[c], m = mand[g], v = vis[g];
      gm[g] = a; gv[g] = b;
      gp[m] += a; gc[m] += b; gp[v] += b; gc[v] += a;
      if (a > b) { pts[m] += 3; vit[m] += 1; }
      else if (a < b) { pts[v] += 3; vit[v] += 1; }
      else { pts[m] += 1; pts[v] += 1; }
    }
    // critérios 1º a 3º numa chave só; a parte decimal sorteia a ordem dos empatados
    for (let i = 0; i < k; i++) chave[i] = ((pts[i] * 100 + vit[i]) * 1000 + (gp[i] - gc[i] + 500)) * 1000 + gp[i] + rng() * 0.5;
    // ordenação por inserção, da maior chave para a menor: a tabela muda pouco de uma temporada para outra
    for (let p = 1; p < k; p++) {
      const t = ordem[p], c = chave[t];
      let q = p - 1;
      while (q >= 0 && chave[ordem[q]] < c) { ordem[q + 1] = ordem[q]; q--; }
      ordem[q + 1] = t;
    }
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

// as PARTES do cálculo, uma depois da outra (no teste e em navegador sem Worker): mesmo resultado do site
export function simularEmPartes(dados, fixos = {}) {
  const partes = Array.from({ length: PARTES }, (_, p) => simular(dados, fixos, N_NAVEGADOR / PARTES, sementeDaParte(p)));
  return {
    times: partes[0].times, n: N_NAVEGADOR,
    chanceQueda: partes[0].chanceQueda.map((_, i) => partes.reduce((s, r) => s + r.chanceQueda[i], 0) / PARTES),
  };
}
