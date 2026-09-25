// Vai cair? — lê data/previsao.json e monta a página. Animações com Motion (motion.dev, em site/vendor).
import { simular } from "./simulador.js";

const TIME = "Corinthians";
const M = window.Motion;  // carregado antes deste módulo (script com defer)
const MOVIMENTO = Boolean(M) && !matchMedia("(prefers-reduced-motion: reduce)").matches;
const SVG = "http://www.w3.org/2000/svg";
const SUAVE = [0.2, 0.7, 0.2, 1];

// ---------- utilidades ----------

const esc = (v) => String(v ?? "—").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (x, casas = 0) => x.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const pct = (x, casas = 1) => {
  if (x >= 0.9995) return ">99,9%";
  if (x > 0 && x < 0.0005) return "<0,1%";
  return `${num(100 * x, casas)}%`;
};
const dataCurta = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) : "sem data");
const $ = (id) => document.getElementById(id);
const cor = (variavel) => getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();

function el(tag, attrs = {}, texto) {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (texto !== undefined) e.textContent = texto;
  return e;
}
function barraV(x, y, w, h, r = 4) {
  r = Math.min(r, h, w / 2);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}
function barraH(x, y, w, h, r = 4) {
  r = Math.min(r, w, h / 2);
  return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
}

function dica(container) {
  const d = document.createElement("div");
  d.className = "dica";
  container.appendChild(d);
  return {
    mostrar(html, evento) {
      d.innerHTML = html;
      const caixa = container.getBoundingClientRect();
      let x = evento.clientX - caixa.left + 12;
      if (x + d.offsetWidth > caixa.width) x = evento.clientX - caixa.left - d.offsetWidth - 12;
      d.style.left = `${Math.max(0, x)}px`;
      d.style.top = `${evento.clientY - caixa.top - d.offsetHeight - 8}px`;
      d.style.opacity = 1;
    },
    esconder() { d.style.opacity = 0; },
  };
}

function tintaSobre(variavel) {
  const hex = cor(variavel);
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return 1.05 / (lum + 0.05) >= (lum + 0.05) / 0.05 ? "#fff" : "#0a0a0a";
}

function barra3(partes, classe = "") {
  return `<div class="barra3 ${classe}" role="img" aria-label="${esc(partes.map((p) => `${p.rotulo} ${pct(p.valor, 0)}`).join(", "))}">${
    partes.map((p) => `<span style="width:${100 * p.valor}%;background:var(${p.cor});color:${tintaSobre(p.cor)}">${p.valor >= 0.12 ? pct(p.valor, 0) : ""}</span>`).join("")}</div>`;
}
const legenda = (partes) => `<div class="legenda">${partes.map((p) => `<div><span class="chave" style="background:var(${p.cor})"></span>${esc(p.rotulo)}</div>`).join("")}</div>`;

// número que conta até o valor (com Motion) — ou aparece direto, para quem pediu menos movimento
function contar(elemento, de, ate, formatar, opcoes = {}) {
  if (!MOVIMENTO) { elemento.textContent = formatar(ate); return null; }
  return M.animate(de, ate, { duration: 1.1, ease: SUAVE, ...opcoes, onUpdate: (v) => { elemento.textContent = formatar(v); } });
}

// roda a ação quando o elemento aparece na tela, uma vez só
function aoAparecer(elemento, acao, amount = 0.25) {
  if (!MOVIMENTO) { acao(); return; }
  const parar = M.inView(elemento, () => { acao(); parar(); }, { amount });
}

function animarBarras(container, eixo) {
  if (!MOVIMENTO) return;
  const barras = container.querySelectorAll(".barra");
  const escala = eixo === "v" ? "scaleY" : "scaleX";
  M.animate(barras, { [escala]: 0 }, { duration: 0 });  // começa zerada, pelo próprio Motion
  aoAparecer(container, () => M.animate(barras, { [escala]: [0, 1] }, { delay: M.stagger(eixo === "v" ? 0.03 : 0.05), type: "spring", bounce: 0.25, duration: 0.9 }));
}

function doPontoDeVista(j, time) {
  const casa = j.mandante === time;
  return { casa, adversario: casa ? j.visitante : j.mandante,
           vence: casa ? j.p_mandante : j.p_visitante, empate: j.p_empate, perde: casa ? j.p_visitante : j.p_mandante };
}
function placarFrase(j, v) {
  const [m, vis] = j.placar_mais_provavel;
  const [nosso, deles] = v.casa ? [m, vis] : [vis, m];
  if (nosso > deles) return `vitória por ${nosso} x ${deles}`;
  if (nosso === deles) return `empate em ${nosso} x ${deles}`;
  return `derrota por ${deles} x ${nosso}`;
}
// resultado do ponto de vista do Corinthians ("v", "e", "d") → do ponto de vista do mandante (0, 1, 2)
const paraMandante = (jogo, r) => (r === "e" ? 1 : (r === "v") === (jogo.mandante === TIME) ? 0 : 2);

// ---------- faixa de validade: muda sozinha em 07/10, pelo horário de Brasília ----------

function hojeEmBrasilia() {
  const teste = new URLSearchParams(location.search).get("hoje");  // ex.: ?hoje=2026-10-07, para conferir a troca
  if (teste && /^\d{4}-\d{2}-\d{2}$/.test(teste)) return teste;
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function faixaDeValidade(dados) {
  const voltou = hojeEmBrasilia() >= dados.validade.volta_do_campeonato;
  const faixa = $("faixa");
  faixa.textContent = voltou ? "O campeonato voltou; esta foi a previsão da pausa" : `Previsão feita na pausa, com dados até a ${dados.dados.rodada}ª rodada`;
  faixa.classList.toggle("voltou", voltou);
}

// ---------- herói: 1.000 pontos, cada um valendo 100 temporadas ----------

class Pontos {
  constructor(canvas, total = 1000) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.total = total;
    this.vermelhos = 0;               // quantos pontos estão vermelhos agora (número quebrado durante a animação)
    this.queda = MOVIMENTO ? 0 : 99;  // relógio da chuva de pontos, em segundos
    this.brilho = 0;                  // respiração leve dos pontos vermelhos
    this.energia = 0;                 // 1 enquanto os pontos mudam de cor; some quando a animação para
    // ordem fixa em que os pontos ficam vermelhos: espalhada, e a mesma em qualquer cenário
    let s = 2026;
    const aleatorio = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
    const ordem = Array.from({ length: total }, (_, i) => i);
    for (let i = total - 1; i > 0; i--) { const j = Math.floor(aleatorio() * (i + 1)); [ordem[i], ordem[j]] = [ordem[j], ordem[i]]; }
    this.posto = new Int16Array(total);
    ordem.forEach((p, k) => { this.posto[p] = k; });
    this.atraso = Float32Array.from({ length: total }, () => aleatorio());
    this.medir();
  }

  medir() {
    const largura = this.canvas.parentElement.clientWidth;
    this.colunas = largura >= 600 ? 50 : 40;
    this.linhas = Math.ceil(this.total / this.colunas);
    this.celula = largura / this.colunas;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = Math.round(largura * dpr);
    this.canvas.height = Math.round(this.linhas * this.celula * dpr);
    this.canvas.style.height = `${this.linhas * this.celula}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.desenhar();
  }

  desenhar() {
    const { ctx, celula } = this;
    const vermelho = cor("--perde");
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    const raio = celula * 0.3;
    for (let i = 0; i < this.total; i++) {
      const lin = Math.floor(i / this.colunas), col = i % this.colunas;
      // chuva: cada ponto cai com um atraso próprio e quica ao chegar
      const inicio = lin * 0.035 + this.atraso[i] * 0.35;
      const p = Math.min(1, Math.max(0, (this.queda - inicio) / 0.55));
      if (p <= 0) continue;
      const c1 = 1.7, c3 = c1 + 1;
      const pulo = 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2;  // "ease out back"
      const y = (lin + 0.5) * celula - (1 - pulo) * celula * 8;
      const x = (col + 0.5) * celula;
      const falta = this.vermelhos - this.posto[i];  // > 0: já está vermelho
      if (falta > 0) {
        const estalo = this.energia * Math.max(0, 1 - falta / 14);  // o ponto que acabou de virar cresce um pouco
        ctx.fillStyle = vermelho;
        ctx.globalAlpha = p;
        ctx.beginPath(); ctx.arc(x, y, raio * (1 + 0.6 * estalo + 0.08 * this.brilho), 0, Math.PI * 2); ctx.fill();
      } else {
        ctx.fillStyle = "#5c5c5c";  // cinza sólido: a foto do fundo não muda o tom de um ponto para outro
        ctx.globalAlpha = p;
        ctx.beginPath(); ctx.arc(x, y, raio, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
  }

  chover() {
    if (!MOVIMENTO) { this.queda = 99; this.desenhar(); return Promise.resolve(); }
    return M.animate(0, 2.2, { duration: 2.2, ease: "linear", onUpdate: (t) => { this.queda = t; this.desenhar(); } }).finished;
  }

  pintar(alvo, aoMudar) {
    if (this.animacao) this.animacao.stop();
    if (!MOVIMENTO) { this.vermelhos = alvo; this.desenhar(); aoMudar?.(alvo); return; }
    this.energia = 1;
    const animacao = M.animate(this.vermelhos, alvo, {
      type: "spring", stiffness: 38, damping: 14, restDelta: 0.1,
      onUpdate: (v) => { this.vermelhos = v; this.desenhar(); aoMudar?.(v); },
    });
    this.animacao = animacao;
    animacao.finished.then(() => {
      if (this.animacao !== animacao) return;
      M.animate(1, 0, { duration: 0.5, onUpdate: (e) => { this.energia = e; this.desenhar(); } });
    });
  }

  respirar() {
    if (!MOVIMENTO) return;
    M.inView(this.canvas, () => {
      const a = M.animate(0, 1, { duration: 1.8, repeat: Infinity, repeatType: "reverse", ease: "easeInOut",
                                  onUpdate: (v) => { this.brilho = v; this.desenhar(); } });
      return () => a.stop();  // para de animar quando sai da tela (economiza bateria)
    });
  }
}

function regua(container, dados, chance) {
  const s = dados.sensibilidade, ufmg = dados.ufmg.chance_queda_corinthians;
  const W = Math.max(300, container.clientWidth), m = { l: 6, r: 6 };
  const x = (v) => m.l + (W - m.l - m.r) * (v / 0.35);
  const svg = el("svg", { viewBox: `0 -8 ${W} 84`, role: "img",
    "aria-label": `Previsão ${pct(chance)}. Com outras escolhas de modelo, de ${pct(s.minimo, 0)} a ${pct(s.maximo, 0)}. UFMG: ${pct(ufmg)}.` });
  svg.appendChild(el("text", { x: m.l, y: 6 }, `Com outras escolhas de modelo: ${pct(s.minimo, 0)} a ${pct(s.maximo, 0)}`));
  svg.appendChild(el("rect", { x: x(0), y: 38, width: x(0.35) - x(0), height: 4, rx: 2, fill: "var(--grade)" }));
  const faixa = el("rect", { x: x(s.minimo), y: 34, width: x(s.maximo) - x(s.minimo), height: 12, rx: 6, fill: "#3a3a3a" });
  faixa.style.transformBox = "fill-box";
  faixa.style.transformOrigin = "center";
  svg.appendChild(faixa);
  const gUfmg = el("g", {});
  gUfmg.append(el("circle", { cx: x(ufmg), cy: 40, r: 6, fill: "var(--bg)", stroke: "var(--texto)", "stroke-width": 2 }),
               el("text", { x: x(ufmg), y: 66, "text-anchor": "middle" }, `UFMG ${pct(ufmg)}`));
  svg.appendChild(gUfmg);
  const gNosso = el("g", {});
  const rotulo = el("text", { x: 0, y: 26, "text-anchor": "middle", class: "forte" }, pct(chance));
  gNosso.append(el("circle", { cx: 0, cy: 40, r: 7, fill: "var(--perde)" }), rotulo);
  gNosso.style.transform = `translateX(${x(chance)}px)`;
  svg.appendChild(gNosso);
  svg.appendChild(el("text", { x: x(0), y: 66, opacity: 0.55 }, "0%"));
  svg.appendChild(el("text", { x: x(0.35), y: 66, "text-anchor": "end", opacity: 0.55 }, "35%"));
  container.replaceChildren(svg);
  return {
    mover(novo) {
      const destino = `translateX(${x(novo)}px)`;
      rotulo.textContent = pct(novo);
      if (MOVIMENTO) M.animate(gNosso, { transform: destino }, { type: "spring", stiffness: 120, damping: 16 });
      else gNosso.style.transform = destino;
    },
    entrar() {
      if (!MOVIMENTO) return;
      M.animate(faixa, { opacity: [0, 1], transform: ["scaleX(0)", "scaleX(1)"] }, { duration: 0.8, ease: SUAVE, delay: 0.1 });
      M.animate([gUfmg, gNosso], { opacity: [0, 1] }, { duration: 0.5, delay: M.stagger(0.2, { startDelay: 0.5 }) });
    },
  };
}

function heroi(dados) {
  const c = dados.corinthians;
  const proximo = dados.jogos.findIndex((j) => [j.mandante, j.visitante].includes(TIME));
  const jogo = dados.jogos[proximo];
  const adv = jogo.mandante === TIME ? jogo.visitante : jogo.mandante;
  const numero = $("numero-queda"), frase = $("frase-heroi");
  const pontos = new Pontos($("tela-pontos"));
  const reguaHeroi = regua($("regua"), dados, c.chance_queda);

  const escreverFrase = (chance, cenario) => {
    const n = Math.round(chance * 1000);
    // "1 em cada 4": a forma mais fácil de ler uma chance (os pontos mostram a conta exata)
    const umEm = chance >= 0.001 ? `<b>1 em cada ${num(Math.max(1, Math.round(1 / chance)))}</b>` : "<b>menos de 1 em cada 1.000</b>";
    frase.innerHTML = cenario
      ? `${cenario}, o Corinthians cai em ${umEm} temporadas simuladas.`
      : `O Corinthians cai em ${umEm} temporadas simuladas.`;
    $("tela-pontos").setAttribute("aria-label", `Mil pontos, cada um valendo 100 das 100 mil temporadas simuladas. ${num(n)} vermelhos: Corinthians rebaixado.`);
  };

  // cenários do próximo jogo: calculados no navegador, com o mesmo simulador dos 10 jogos
  const cache = { modelo: c.chance_queda };
  const cenarios = [
    { id: "modelo", rotulo: "Previsão do modelo" },
    { id: "v", rotulo: `Vence o ${adv}` },
    { id: "e", rotulo: `Empata com o ${adv}` },
    { id: "d", rotulo: `Perde para o ${adv}` },
  ];
  const nomeCenario = { v: `Se vencer o ${esc(adv)}`, e: `Se empatar com o ${esc(adv)}`, d: `Se perder para o ${esc(adv)}` };
  $("chips").innerHTML = cenarios.map((s) => `<button type="button" class="chip" data-c="${s.id}" aria-pressed="${s.id === "modelo"}">${esc(s.rotulo)}</button>`).join("");

  let fimDoTexto;
  const mostrar = (chance, id) => {
    pontos.pintar(chance * 1000, (v) => { numero.textContent = pct(v / 1000); });
    clearTimeout(fimDoTexto);
    if (MOVIMENTO) fimDoTexto = setTimeout(() => { numero.textContent = pct(chance); }, 1800);
    else numero.textContent = pct(chance);
    escreverFrase(chance, id === "modelo" ? null : nomeCenario[id]);
    reguaHeroi.mover(chance);
  };

  $("chips").addEventListener("click", (e) => {
    const botao = e.target.closest(".chip");
    if (!botao) return;
    const id = botao.dataset.c;
    $("chips").querySelectorAll(".chip").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
    requestAnimationFrame(() => {  // deixa o toque responder antes de calcular
      if (!(id in cache)) {
        const r = simular(dados, { [proximo]: paraMandante(jogo, id) }, 20000);
        cache[id] = r.chanceQueda[r.times.indexOf(TIME)];
      }
      mostrar(cache[id], id);
    });
  });

  escreverFrase(c.chance_queda, null);
  numero.textContent = MOVIMENTO ? "0,0%" : pct(c.chance_queda);
  pontos.chover().then(() => {
    mostrar(c.chance_queda, "modelo");
    reguaHeroi.entrar();
    pontos.respirar();
  });
  if (MOVIMENTO) {
    M.animate(".sobretitulo, .numero-heroi, .frase-heroi", { opacity: [0, 1], y: [24, 0] }, { duration: 0.8, delay: M.stagger(0.12), ease: SUAVE });
    M.animate(".legenda-pontos, .chips-rotulo, .chips, .regua, .descer", { opacity: [0, 1], y: [16, 0] }, { duration: 0.6, delay: M.stagger(0.1, { startDelay: 1.6 }), ease: SUAVE });
    // a foto da torcida desce mais devagar que a página (profundidade)
    M.scroll(M.animate("#heroi-foto", { transform: ["translateY(0px) scale(1.06)", "translateY(90px) scale(1.14)"] }, { ease: "linear" }),
             { target: $("manchete"), offset: ["start start", "end start"] });
  }
  let largura = $("pontos").clientWidth;
  new ResizeObserver(() => {
    const nova = $("pontos").clientWidth;
    if (nova !== largura) { largura = nova; pontos.medir(); }
  }).observe($("pontos"));
}

// ---------- pontos que faltam e próximo jogo ----------

function faltam(dados) {
  const n = dados.corinthians.pontos_para_menos_de_5pct;
  const jogos = dados.jogos.filter((j) => [j.mandante, j.visitante].includes(TIME));
  const hist = dados.historia_17o;
  const min17 = Math.min(...hist.map((h) => h.pontos_17o)), max17 = Math.max(...hist.map((h) => h.pontos_17o));
  $("faltam").innerHTML = `
    <p class="rotulo">Quantos pontos faltam</p>
    <p class="valor-medio"><span id="n-faltam">${n.faltam}</span> pontos</p>
    <p class="pequeno">Chegando a <b>${n.pontos_finais}</b>, a chance de cair fica abaixo de 5%. São ${jogos.length} jogos, com ${3 * jogos.length} pontos em disputa.</p>
    <p class="pequeno suave">Desde 2006, o 17º colocado (o primeiro da zona de queda) fez entre ${min17} e ${max17} pontos.</p>`;
  aoAparecer($("faltam"), () => contar($("n-faltam"), 0, n.faltam, (x) => num(Math.round(x))));
}

function proximo(dados) {
  const j = dados.jogos.filter((x) => [x.mandante, x.visitante].includes(TIME))[0];
  const v = doPontoDeVista(j, TIME);
  const partes = [
    { valor: v.vence, cor: "--vence", rotulo: `${TIME} vence` },
    { valor: v.empate, cor: "--empate", rotulo: "Empate" },
    { valor: v.perde, cor: "--perde", rotulo: `${v.adversario} vence` },
  ];
  $("proximo").innerHTML = `
    <p class="rotulo">Próximo jogo · ${dataCurta(j.data)} · ${j.rodada}ª rodada</p>
    <p class="valor-jogo">${esc(j.mandante)} x ${esc(j.visitante)}</p>
    ${barra3(partes, "fina")}
    ${legenda(partes.map((p) => ({ ...p, rotulo: `${p.rotulo} ${pct(p.valor, 0)}` })))}
    <p class="pequeno suave" style="margin-top:10px">Placar mais provável: ${placarFrase(j, v)} ·
      gols esperados ${j.gols_esperados.map((g) => num(g, 1)).join(" x ")}${j.equilibrado ? " · jogo equilibrado" : ""}</p>`;
  const barra = $("proximo").querySelector(".barra3");
  if (MOVIMENTO) { barra.style.transform = "scaleX(0)"; aoAparecer($("proximo"), () => M.animate(barra, { scaleX: [0, 1] }, { duration: 0.9, ease: SUAVE })); }
}

// ---------- gráficos ----------

function graficoPosicoes(container, dist, posAtual) {
  const W = Math.max(300, container.clientWidth), H = 240, m = { t: 28, r: 8, b: 28, l: 36 };
  const faixa = (W - m.l - m.r) / dist.length;
  const largura = Math.min(24, faixa - 2);
  const topo = Math.max(0.05, Math.ceil(Math.max(...dist) * 20) / 20);
  const y = (v) => m.t + (H - m.t - m.b) * (1 - v / topo);
  const queda = dist.slice(16).reduce((a, b) => a + b, 0);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Chance do Corinthians terminar em cada posição. Zona de queda, 17º a 20º: ${pct(queda)}.` });
  svg.appendChild(el("rect", { x: m.l + 16 * faixa, y: m.t - 22, width: 4 * faixa, height: H - m.b - m.t + 22, fill: "var(--faixa-z4)", rx: 6 }));
  svg.appendChild(el("text", { x: W - m.r - 4, y: m.t - 8, "text-anchor": "end", class: "forte" }, `Zona de queda: ${pct(queda)}`));
  for (let v = 0; v <= topo + 1e-9; v += 0.05) {
    svg.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: v === 0 ? "var(--eixo)" : "var(--grade)", "stroke-width": 1 }));
    svg.appendChild(el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, `${Math.round(v * 100)}%`));
  }
  const rotulos = faixa >= 28 ? dist.map((_, k) => k + 1) : faixa >= 18 ? [1, 3, 5, 7, 9, 11, 13, 15, 17, 18, 19, 20] : [1, 5, 10, 15, 17, 20];
  const d = dica(container);
  dist.forEach((p, i) => {
    const pos = i + 1;
    const cx = m.l + i * faixa + faixa / 2;
    if (p > 0) svg.appendChild(el("path", { d: barraV(cx - largura / 2, y(p), largura, y(0) - y(p)), fill: pos >= 17 ? "var(--perde)" : "var(--barra)", class: "barra v" }));
    const perto = pos !== posAtual && Math.abs(pos - posAtual) * faixa < 26;
    if ((rotulos.includes(pos) && !perto) || pos === posAtual) {
      svg.appendChild(el("text", { x: cx, y: H - m.b + 16, "text-anchor": "middle", class: pos === posAtual ? "forte" : "" }, pos === posAtual ? `${pos}º*` : `${pos}º`));
    }
    const alvo = el("rect", { x: cx - faixa / 2, y: m.t, width: faixa, height: H - m.t - m.b, class: "alvo" });
    alvo.addEventListener("pointermove", (e) => d.mostrar(`<b>${pos}º lugar</b>: ${pct(p)}${pos >= 17 ? " · cai" : ""}`, e));
    alvo.addEventListener("pointerleave", () => d.esconder());
    svg.appendChild(alvo);
  });
  container.prepend(svg);
}

function graficoQueda(container, times) {
  const lista = times.filter((t) => t.chance_queda >= 0.005).sort((a, b) => b.chance_queda - a.chance_queda);
  const W = Math.max(300, container.clientWidth), linha = 32, m = { t: 8, r: 56, b: 8, l: 124 };
  const H = m.t + m.b + lista.length * linha;
  const x = (v) => m.l + (W - m.l - m.r) * v;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Chance de queda dos times ameaçados" });
  for (const v of [0, 0.25, 0.5, 0.75, 1]) {
    svg.appendChild(el("line", { x1: x(v), x2: x(v), y1: m.t, y2: H - m.b, stroke: v === 0 ? "var(--eixo)" : "var(--grade)", "stroke-width": 1 }));
  }
  const d = dica(container);
  lista.forEach((t, i) => {
    const yy = m.t + i * linha;
    const eh = t.time === TIME;
    svg.appendChild(el("text", { x: m.l - 8, y: yy + linha / 2 + 4, "text-anchor": "end", class: eh ? "forte" : "" }, `${t.time} (${t.pos}º)`));
    svg.appendChild(el("path", { d: barraH(x(0), yy + (linha - 16) / 2, Math.max(2, x(t.chance_queda) - x(0)), 16), fill: eh ? "var(--texto)" : "var(--barra-2)", class: "barra h" }));
    svg.appendChild(el("text", { x: x(t.chance_queda) + 6, y: yy + linha / 2 + 4, class: eh ? "forte" : "" }, pct(t.chance_queda)));
    const alvo = el("rect", { x: 0, y: yy, width: W, height: linha, class: "alvo" });
    alvo.addEventListener("pointermove", (e) => d.mostrar(`<b>${esc(t.time)}</b>: ${pct(t.chance_queda)} de cair<br>${t.pos}º com ${t.pts} pts hoje · termina com ${num(t.pontos_finais_media, 1)} pts em média`, e));
    alvo.addEventListener("pointerleave", () => d.esconder());
    svg.appendChild(alvo);
  });
  container.prepend(svg);
}

function grafico17o(container, hist, alvo) {
  const W = Math.max(300, container.clientWidth), H = 200, m = { t: 12, r: 8, b: 24, l: 32 };
  const faixa = (W - m.l - m.r) / hist.length;
  const largura = Math.min(20, faixa - 2);
  const min = 30, max = 50;
  const y = (v) => m.t + (H - m.t - m.b) * (1 - (v - min) / (max - min));
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Pontos do 17º colocado em cada ano desde 2006. A meta do Corinthians é ${alvo} pontos.` });
  for (let v = min; v <= max; v += 5) {
    svg.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: v === min ? "var(--eixo)" : "var(--grade)", "stroke-width": 1 }));
    svg.appendChild(el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, String(v)));
  }
  const d = dica(container);
  hist.forEach((h, i) => {
    const cx = m.l + i * faixa + faixa / 2;
    svg.appendChild(el("path", { d: barraV(cx - largura / 2, y(h.pontos_17o), largura, y(min) - y(h.pontos_17o)), fill: "var(--barra-2)", class: "barra v" }));
    if (i % 4 === 0 || i === hist.length - 1) svg.appendChild(el("text", { x: cx, y: H - m.b + 16, "text-anchor": "middle" }, `’${String(h.temporada).slice(2)}`));
    const a = el("rect", { x: cx - faixa / 2, y: m.t, width: faixa, height: H - m.t - m.b, class: "alvo" });
    a.addEventListener("pointermove", (e) => d.mostrar(`<b>${h.temporada}</b>: 17º com ${h.pontos_17o} pontos (16º, o primeiro fora da queda: ${h.pontos_16o})`, e));
    a.addEventListener("pointerleave", () => d.esconder());
    svg.appendChild(a);
  });
  svg.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: y(alvo), y2: y(alvo), stroke: "var(--perde)", "stroke-width": 2 }));
  container.prepend(svg);
}

function graficoSensibilidade(container, s) {
  const W = Math.max(300, container.clientWidth), linha = 44, m = { t: 4, r: 52, b: 4, l: 8 };
  const H = m.t + m.b + s.variantes.length * linha;
  const x = (v) => m.l + (W - m.l - m.r) * (v / 0.3);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Chance de queda com outras escolhas de modelo: de ${pct(s.minimo)} a ${pct(s.maximo)}` });
  s.variantes.forEach((v, i) => {
    const yy = m.t + i * linha;
    const principal = i === 0;
    svg.appendChild(el("text", { x: m.l, y: yy + 14, class: principal ? "forte" : "" }, v.nome));
    svg.appendChild(el("path", { d: barraH(x(0), yy + 20, Math.max(2, x(v.chance) - x(0)), 14), fill: principal ? "var(--perde)" : "var(--barra-2)", class: "barra h" }));
    svg.appendChild(el("text", { x: x(v.chance) + 6, y: yy + 31, class: principal ? "forte" : "" }, pct(v.chance)));
  });
  container.prepend(svg);
}

// ---------- os 10 jogos e o simulador ----------

function jogosESimulador(dados) {
  const jogosCor = dados.jogos.map((j, g) => ({ j, g, v: doPontoDeVista(j, TIME) })).filter(({ j }) => [j.mandante, j.visitante].includes(TIME));
  const esperados = jogosCor.reduce((s, { v }) => s + 3 * v.vence + v.empate, 0);
  const n = dados.corinthians.pontos_para_menos_de_5pct;
  const escolhas = {};  // índice do jogo -> "v" | "e" | "d" (do ponto de vista do Corinthians)

  $("jogos-conteudo").innerHTML = `
    <p>Somando os ${jogosCor.length} jogos, o modelo espera <b>${num(esperados, 1)} pontos</b> para o Corinthians.
      Para a chance de cair ficar abaixo de 5%, ele precisa de <b>${n.faltam}</b>.</p>
    <p class="suave pequeno"><b style="color:var(--texto)">Simule:</b> toque em Vence, Empata ou Perde nos jogos que quiser.
      Os outros jogos continuam sorteados pelo modelo.</p>
    ${legenda([{ cor: "--vence", rotulo: `${TIME} vence` }, { cor: "--empate", rotulo: "Empate" }, { cor: "--perde", rotulo: "Adversário vence" }])}
    <ol class="jogos">${jogosCor.map(({ j, g, v }) => `
      <li class="jogo" data-g="${g}">
        <div class="quando"><b>${dataCurta(j.data)}</b>${j.rodada}ª rod.</div>
        <div class="titulo">${esc(v.adversario)}<small>${v.casa ? "em casa" : "fora"}</small>${j.equilibrado ? '<span class="selo">equilibrado</span>' : ""}</div>
        <div class="placar">placar provável<b>${placarFrase(j, v)}</b></div>
        ${barra3([{ valor: v.vence, cor: "--vence", rotulo: `${TIME} vence` }, { valor: v.empate, cor: "--empate", rotulo: "Empate" }, { valor: v.perde, cor: "--perde", rotulo: `${v.adversario} vence` }])}
        <div class="escolha" role="group" aria-label="Simular o resultado contra ${esc(v.adversario)}">
          <button type="button" data-r="v" aria-pressed="false">Vence</button>
          <button type="button" data-r="e" aria-pressed="false">Empata</button>
          <button type="button" data-r="d" aria-pressed="false">Perde</button>
        </div>
      </li>`).join("")}
    </ol>
    <div class="cenario escondido" id="cenario" aria-live="polite">
      <div><p>Seu cenário</p><span class="grande" id="cenario-chance">—</span></div>
      <p id="cenario-texto" style="flex:1"></p>
      <button type="button" class="botao" id="cenario-limpar">Limpar</button>
    </div>`;

  // as linhas entram uma a uma quando a lista aparece
  const linhas = $("jogos-conteudo").querySelectorAll(".jogo");
  if (MOVIMENTO) {
    linhas.forEach((l) => { l.style.opacity = 0; });
    aoAparecer($("jogos-conteudo").querySelector(".jogos"), () => {
      M.animate(linhas, { opacity: [0, 1], x: [-16, 0] }, { delay: M.stagger(0.06), duration: 0.5, ease: SUAVE });
      M.animate($("jogos-conteudo").querySelectorAll(".jogo .barra3"), { scaleX: [0, 1] }, { delay: M.stagger(0.06, { startDelay: 0.15 }), duration: 0.8, ease: SUAVE });
    }, 0.05);
  }

  let chanceAnterior = dados.corinthians.chance_queda;
  const recalcular = () => {
    const fixos = {};
    let pontos = 0;
    for (const [g, r] of Object.entries(escolhas)) {
      fixos[g] = paraMandante(dados.jogos[g], r);
      pontos += r === "v" ? 3 : r === "e" ? 1 : 0;
    }
    const qtd = Object.keys(escolhas).length;
    const painel = $("cenario");
    const estavaEscondido = painel.classList.contains("escondido");
    painel.classList.toggle("escondido", qtd === 0);
    document.querySelectorAll(".jogo[data-g]").forEach((li) => li.classList.toggle("fixado", li.dataset.g in escolhas));
    if (!qtd) { chanceAnterior = dados.corinthians.chance_queda; return; }
    if (estavaEscondido && MOVIMENTO) M.animate(painel, { y: [80, 0], opacity: [0, 1] }, { type: "spring", bounce: 0.3, duration: 0.6 });
    const r = simular(dados, fixos, 10000);
    const chance = r.chanceQueda[r.times.indexOf(TIME)];
    contar($("cenario-chance"), chanceAnterior, chance, (x) => pct(x), { duration: 0.6 });
    chanceAnterior = chance;
    const delta = 100 * (chance - dados.corinthians.chance_queda);
    $("cenario-texto").textContent = `${qtd} ${qtd === 1 ? "jogo fixado" : "jogos fixados"}, ${pontos} de ${3 * qtd} pontos. ` +
      `${Math.abs(delta) < 0.05 ? "Igual à previsão" : `${delta < 0 ? "−" : "+"}${num(Math.abs(delta), 1)} ponto${Math.abs(delta) >= 1.95 ? "s" : ""} percentua${Math.abs(delta) >= 1.95 ? "is" : "l"} em relação à previsão`}.`;
  };

  $("jogos-conteudo").addEventListener("click", (e) => {
    const botao = e.target.closest(".escolha button");
    if (!botao) return;
    const li = botao.closest(".jogo");
    const g = li.dataset.g, r = botao.dataset.r;
    if (escolhas[g] === r) delete escolhas[g]; else escolhas[g] = r;
    li.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(escolhas[g] === b.dataset.r)));
    requestAnimationFrame(recalcular);
  });
  $("cenario-limpar").addEventListener("click", () => {
    for (const g of Object.keys(escolhas)) delete escolhas[g];
    document.querySelectorAll(".escolha button").forEach((b) => b.setAttribute("aria-pressed", "false"));
    recalcular();
  });
}

// ---------- rodada da volta (recolhida) ----------

function rodadaVolta(dados) {
  const jogos = dados.jogos.filter((j) => j.rodada <= dados.dados.rodada + 1).sort((a, b) => (a.data ?? "9999").localeCompare(b.data ?? "9999"));
  const cores = [{ cor: "--mandante", rotulo: "Mandante vence" }, { cor: "--empate", rotulo: "Empate" }, { cor: "--visitante", rotulo: "Visitante vence" }];
  $("rodada-volta").innerHTML = `
    <details>
      <summary>Rodada da volta: ${jogos.length} jogos</summary>
      <p class="suave pequeno">Os jogos atrasados e a ${dados.dados.rodada + 1}ª rodada, previstos antes de acontecer.</p>
      ${legenda(cores)}
      <ol class="jogos">${jogos.map((j) => `
        <li class="jogo">
          <div class="quando"><b>${dataCurta(j.data)}</b>${j.rodada}ª rod.</div>
          <div class="titulo" style="font-size:1.1rem">${esc(j.mandante)} x ${esc(j.visitante)}${j.equilibrado ? '<span class="selo">equilibrado</span>' : ""}</div>
          <div class="placar">placar provável<b>${j.placar_mais_provavel.join(" x ")}</b></div>
          ${barra3([{ valor: j.p_mandante, cor: "--mandante", rotulo: `${j.mandante} vence` }, { valor: j.p_empate, cor: "--empate", rotulo: "Empate" }, { valor: j.p_visitante, cor: "--visitante", rotulo: `${j.visitante} vence` }])}
        </li>`).join("")}
      </ol>
      <p class="pequeno suave">"Sem data": jogo adiado, ainda sem nova data. "Equilibrado": as chances de vitória dos dois times diferem menos de 10 pontos percentuais.</p>
    </details>`;
  const det = $("rodada-volta").querySelector("details");
  det.addEventListener("toggle", () => {
    if (!det.open || !MOVIMENTO) return;
    M.animate(det.querySelectorAll(".jogo"), { opacity: [0, 1], y: [10, 0] }, { delay: M.stagger(0.04), duration: 0.4, ease: SUAVE });
  });
}

// ---------- os dados, em camadas ----------

function mapaCobertura(container, c) {
  container.style.setProperty("--anos", c.anos.length);
  const marcos = new Set([c.anos[0].temporada, 2010, 2015, 2020, c.anos.at(-1).temporada]);
  let html = "";
  Object.entries(c.linhas).forEach(([chave, rotulo]) => {
    html += `<div class="nome">${esc(rotulo)}</div>`;
    c.anos.forEach((a) => {
      const cel = a[chave];
      const classe = cel.pct >= 90 ? "completo" : cel.pct > 0 ? "parcial" : "";
      const texto = `<b>${esc(a.temporada)} · ${esc(rotulo)}</b><br>${cel.pct > 0 ? `${num(cel.pct, 0)}% dos jogos · ${esc(cel.fonte)}` : "sem dado"}`;
      html += `<div class="celula ${classe}" data-dica="${esc(texto)}"></div>`;  // escapado duas vezes: no atributo e no conteúdo
    });
  });
  html += `<div></div>${c.anos.map((a) => `<div class="ano">${marcos.has(a.temporada) ? `’${String(a.temporada).slice(2)}` : ""}</div>`).join("")}`;
  container.innerHTML = html;
  const d = dica(container);
  container.addEventListener("pointermove", (e) => { const alvo = e.target.closest(".celula"); if (alvo) d.mostrar(alvo.dataset.dica, e); else d.esconder(); });
  container.addEventListener("pointerleave", () => d.esconder());
}

function osDados(dados) {
  const m = dados.modelo;
  const bt = m.backtest;
  const prova = bt.prova_2026;
  const linhasProva = [["Só o mando de campo", prova.so_mando], ["Times em situação parecida (Elo)", prova.situacao_parecida],
    ["Modelo 1 (Dixon-Coles)", prova.modelo1], ["Modelo 2 com xG", prova.xg], ["Combinação usada no site", prova.combinacao]];
  const ufmg = dados.ufmg.chance_queda_corinthians, nosso = dados.corinthians.chance_queda;
  $("dados").innerHTML = `
    <h2>Os dados</h2>
    <div class="resumo-dados">
      <div><p class="rotulo">Jogos analisados</p><p class="valor" data-contar="${dados.dados.jogos_na_base}">${num(dados.dados.jogos_na_base)}</p><p class="pequeno suave">de 2003 a 2026</p></div>
      <div><p class="rotulo">Temporadas simuladas</p><p class="valor" data-contar="${dados.dados.simulacoes}">${num(dados.dados.simulacoes)}</p><p class="pequeno suave">para cada chance</p></div>
      <div><p class="rotulo">Dados até</p><p class="valor">${dataCurta(dados.dados.ate)}</p><p class="pequeno suave">${dados.dados.rodada}ª rodada</p></div>
    </div>

    <h3>Quantos pontos o 17º colocado fez</h3>
    <p class="pequeno suave">Uma barra por ano, desde 2006. A linha vermelha marca ${dados.corinthians.pontos_para_menos_de_5pct.pontos_finais} pontos, a meta do Corinthians nesta previsão.</p>
    <div class="grafico" id="g-17o"></div>

    <details>
      <summary>De onde vêm os dados</summary>
      <ul class="lista">
        <li><a href="https://www.football-data.org/" rel="noopener">football-data.org</a>: jogos, resultados e tabela de 2026.</li>
        <li><a href="https://github.com/adaoduque/Brasileirao_Dataset" rel="noopener">Brasileirão Dataset</a>, de Adão Duque: resultados de 2003 a 2024, usados só para treinar o modelo.</li>
        <li>football-data.co.uk: resultados de 2025 e conferência das outras fontes.</li>
        <li><a href="https://www.api-football.com/" rel="noopener">API-Football</a>: finalizações e xG por jogo, de 2022 a 2026.</li>
        <li>UFMG (divulgada na imprensa): só para comparar a chance de queda.</li>
      </ul>
      <p class="pequeno suave" style="margin-top:8px">${num(dados.dados.jogos_conferidos)} jogos foram conferidos entre duas fontes, sem nenhuma diferença.
        Nenhuma base é republicada aqui: o site mostra só agregados e previsões.</p>
      <div class="mapa" id="mapa"></div>
      <div class="legenda" style="margin-top:8px">
        <div><span class="chave" style="background:var(--completo)"></span>dado completo</div>
        <div><span class="chave" style="background:var(--parcial)"></span>parcial</div>
        <div><span class="chave" style="background:var(--vazio);outline:1px solid var(--borda)"></span>sem dado</div>
      </div>
    </details>

    <details>
      <summary>O que o modelo considera</summary>
      <ul class="lista">
        <li><b>Placares</b>, com mais peso para os jogos recentes: um jogo perde metade do peso a cada ${num(m.decaimento_meia_vida_anos, 1)} anos.</li>
        <li><b>Força de ataque e de defesa</b> de cada time, que já leva em conta a força dos adversários.</li>
        <li><b>Mando de campo</b>: em casa, um time marca em média ${num(100 * (m.mando_gols - 1), 0)}% mais gols do que marcaria em campo neutro.</li>
        <li><b>Elo, forma em casa e fora, pontos recentes e descanso</b>, no segundo modelo.</li>
        <li>Os dois modelos são combinados: ${Math.round(100 * m.peso_modelo1)}% Dixon-Coles e ${Math.round(100 * (1 - m.peso_modelo1))}% XGBoost.</li>
      </ul>
      <p class="pequeno suave" style="margin-top:8px">Testamos as chances criadas (xG e finalizações): com os poucos anos de dado disponíveis, elas não melhoraram a previsão e ficaram de fora.</p>
    </details>

    <details>
      <summary>O que o modelo não sabe</summary>
      <p>Lesões, suspensões, troca de técnico, crise no clube, motivação e o calendário de outras competições.
        Tudo isso só aparece quando vira resultado em campo. E a previsão não é atualizada depois da pausa.</p>
    </details>

    <details>
      <summary>Aprendido dos dados x escolha manual</summary>
      <div class="duas-colunas">
        <div><p><b>Aprendido dos dados</b></p><ul class="lista">
          <li>força de ataque e defesa de cada time</li><li>vantagem do mando</li><li>quanto os jogos antigos perdem de peso</li>
          <li>o peso de cada modelo na combinação</li></ul></div>
        <div><p><b>Escolha manual, documentada</b></p><ul class="lista">
          <li>selo "equilibrado": diferença menor que 10 pontos percentuais</li><li>meta de risco: chance de queda abaixo de 5%</li>
          <li>cartões do desempate (sem dado): viram sorteio</li><li>${num(dados.dados.simulacoes)} temporadas por simulação</li></ul></div>
      </div>
    </details>

    <details>
      <summary>Como sabemos se funciona</summary>
      <p>O modelo previu, sem ver o resultado, os ${num(bt.modelo1_2022_2025.jogos)} jogos de 2022 a 2025 e os de 2026 até a pausa.
        Nota de erro nos jogos de 2026 (log-loss; quanto menor, melhor):</p>
      <div class="tabela"><table>
        <tbody>${linhasProva.map(([nome, v]) => `<tr><td></td><td>${nome}</td><td>${num(v, 3)}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="pequeno suave" style="margin-top:8px">A combinação supera o Dixon-Coles sozinho em ${pct(bt.chance_combinacao_melhor, 0)} dos sorteios de teste.
        Quando o modelo diz 40–50%, o resultado acontece em ${pct(bt.calibracao.find((c) => c.faixa.startsWith("40"))?.real ?? 0, 0)} das vezes.</p>
      <p>A UFMG, com um método parecido (gols como sorteio de Poisson e força dos times), calculou ${pct(ufmg)}; aqui deu ${pct(nosso)}.
        Modelos diferentes chegam a números próximos, mas não iguais: aqui, a diferença é de ${num(Math.abs(100 * (nosso - ufmg)), 1)} pontos percentuais.</p>
      <p>A previsão foi registrada no GitHub antes dos jogos. Depois de 02/12, sai a comparação com o que aconteceu.</p>
    </details>

    <details>
      <summary>E se o modelo fosse outro?</summary>
      <p>Cada linha troca uma escolha do modelo e simula de novo. A previsão publicada é a que foi melhor no teste com jogos passados;
        as outras mostram quanto o número depende dessas escolhas.</p>
      <div class="grafico" id="g-sens"></div>
      <p class="pequeno suave">Quanto mais peso nos jogos recentes, menor o risco do Corinthians: em 2026, Internacional e Grêmio
        estão abaixo do que costumam ser, e o histórico deles pesa menos.</p>
    </details>

    <details>
      <summary>Código e crédito</summary>
      <p>O código está aberto no <a href="https://github.com/EduardoLopes01/rebaixamento_corinthians_2026" rel="noopener">GitHub</a>.
        A estrutura segue o <a href="https://github.com/mar-antaya/world_cup_predictions" rel="noopener">projeto de previsão da Copa de Mar Antaya</a>,
        adaptado de seleções para clubes. Animações feitas com <a href="https://motion.dev" rel="noopener">Motion</a>.</p>
    </details>`;
  if (dados.cobertura?.status === "ok") mapaCobertura($("mapa"), dados.cobertura);
  aoAparecer($("dados").querySelector(".resumo-dados"), () =>
    document.querySelectorAll("#dados [data-contar]").forEach((e) => contar(e, 0, Number(e.dataset.contar), (x) => num(Math.round(x)), { duration: 1.4 })));
}

// ---------- carga, entradas ao rolar e redesenho ----------

function desenharGraficos(dados, animar) {
  document.querySelectorAll(".grafico svg, .grafico .dica").forEach((n) => n.remove());
  graficoPosicoes($("g-posicoes"), dados.corinthians.distribuicao_posicao, dados.corinthians.pos_atual);
  graficoQueda($("g-queda"), dados.times);
  grafico17o($("g-17o"), dados.historia_17o, dados.corinthians.pontos_para_menos_de_5pct.pontos_finais);
  graficoSensibilidade($("g-sens"), dados.sensibilidade);
  if (animar) {
    animarBarras($("g-posicoes"), "v");
    animarBarras($("g-queda"), "h");
    animarBarras($("g-17o"), "v");
  }
}

function entradasAoRolar() {
  if (!MOVIMENTO) return;
  document.querySelectorAll(".revela").forEach((secao) => {
    secao.style.opacity = 0;
    aoAparecer(secao, () => M.animate(secao, { opacity: [0, 1], y: [32, 0] }, { duration: 0.7, ease: SUAVE }), 0.12);
  });
  // toque com resposta física nos botões
  M.press(".escolha button, .chip, .botao", (botao) => {
    M.animate(botao, { scale: 0.94 }, { duration: 0.08 });
    return () => M.animate(botao, { scale: 1 }, { type: "spring", stiffness: 600, damping: 18 });
  });
}

async function iniciar() {
  let dados;
  try {
    const r = await fetch("data/previsao.json");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    dados = await r.json();
  } catch (e) {
    $("frase-heroi").textContent = `Não foi possível carregar a previsão (${e.message}). Tente recarregar a página.`;
    return;
  }
  faixaDeValidade(dados);
  heroi(dados);
  faltam(dados);
  proximo(dados);
  jogosESimulador(dados);
  rodadaVolta(dados);
  osDados(dados);
  $("posicao-sub").textContent = `Chance de cada posição final, em ${num(dados.dados.simulacoes)} temporadas simuladas. * = posição hoje.`;
  desenharGraficos(dados, true);
  entradasAoRolar();

  // gráficos dentro de blocos recolhidos só têm largura depois de abertos
  document.querySelectorAll("#dados details").forEach((d) => d.addEventListener("toggle", () => { if (d.open) desenharGraficos(dados, false); }));
  let largura = $("g-queda").clientWidth;
  new ResizeObserver(() => {
    const nova = $("g-queda").clientWidth;
    if (nova !== largura) { largura = nova; desenharGraficos(dados, false); }
  }).observe($("g-queda"));
}

iniciar();
