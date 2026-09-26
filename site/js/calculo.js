// Worker do simulador: roda uma parte das 100 mil temporadas fora da tela principal.
// Vários Workers dividem o cálculo entre os núcleos do aparelho; a página continua respondendo ao toque.
import { simular } from "./simulador.js";

let dados;
self.onmessage = ({ data }) => {
  if (data.dados) { dados = data.dados; return; }
  const r = simular(dados, data.fixos, data.n, data.semente);
  self.postMessage(r.chanceQueda[r.times.indexOf(data.time)]);
};
