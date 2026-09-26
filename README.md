# Vai cair? A chance do Corinthians ser rebaixado no Brasileirão 2026

**Veja o site: [rebaixamentocorinthians.com.br](https://rebaixamentocorinthians.com.br)**

Na pausa da Data Fifa, o Corinthians estava em **14º lugar, com 32 pontos**, três acima da zona de rebaixamento.
Este projeto responde a pergunta que todo corintiano fez: **vai cair?**

> ### 24,1%: o Corinthians cai em 1 de cada 4 temporadas simuladas
> Previsão feita uma única vez, com os jogos até a 28ª rodada (20/09/2026),
> e registrada em [`predictions/2026-09-26_pausa.json`](predictions/2026-09-26_pausa.json) antes da bola voltar a rolar. **Não é recomendação de aposta.**

Site independente, feito para estudo e sem fins comerciais, sem vínculo com o Sport Club Corinthians Paulista.
Projeto de produto de dados feito com IA: o autor decide e revisa; o Claude Code escreve e executa.

## Os 10 jogos que decidem

Chance de cada resultado, do ponto de vista do Corinthians:

| Data | Rodada | Adversário | Onde | Vence | Empata | Perde |
|---|---|---|---|---|---|---|
| 07/10 | 29ª | Internacional | fora | **25%** | 30% | 45% |
| 11/10 | 30ª | Palmeiras | fora | **13%** | 23% | 64% |
| 16/10 | 31ª | Vitória | em casa | **52%** | 28% | 20% |
| 23/10 | 32ª | Vasco | fora | **30%** | 29% | 41% |
| 27/10 | 33ª | Mirassol | em casa | **43%** | 28% | 29% |
| 03/11 | 34ª | São Paulo | fora | **24%** | 30% | 46% |
| 17/11 | 35ª | Botafogo | em casa | **40%** | 30% | 31% |
| 20/11 | 36ª | Atlético-MG | fora | **22%** | 28% | 50% |
| 27/11 | 37ª | Grêmio | em casa | **46%** | 28% | 25% |
| 01/12 | 38ª | Remo | fora | **37%** | 27% | 37% |

- **Quantos pontos faltam:** somando os 10 jogos, o modelo espera cerca de **12,8 pontos**.
  Para a chance de cair ficar abaixo de 5%, o Corinthians precisa chegar a **45 pontos**: faltam **13**, de 30 em disputa.
- **Referência:** desde 2006, o 17º colocado (o primeiro da zona de queda) fez entre 36 e 46 pontos.
- **No site dá para simular:** toque em Vence, Empata ou Perde em qualquer jogo e veja a chance mudar na hora.
  Por exemplo, vencer o Internacional derruba a chance para cerca de 1 em cada 10.

## A briga contra a queda

| Hoje | Time | Pontos | Chance de cair |
|---|---|---|---|
| 20º | Chapecoense | 18 | >99,9% |
| 19º | Remo | 23 | 97,9% |
| 18º | Internacional | 28 | 54,5% |
| 17º | Grêmio | 29 | 51,2% |
| 16º | Vasco | 31 | 27,1% |
| 14º | Corinthians | 32 | **24,1%** |
| 13º | Vitória | 33 | 18,8% |
| 15º | Mirassol | 32 | 16,0% |

Quatro times caem. Chapecoense e Remo estão quase condenados, então a disputa real é por duas vagas,
principalmente entre Internacional, Grêmio, Vasco e Corinthians, com Vitória e Mirassol logo atrás.

## Como funciona

**1. Os dados.** O modelo aprendeu com **9.442 jogos do Brasileirão desde 2003**.
Antes de usar, os resultados foram conferidos em duas fontes diferentes: 5.216 jogos, nenhuma diferença.

**2. A força de cada time.** O primeiro modelo (chamado Dixon-Coles) olha os placares e aprende quanto cada time
costuma marcar e sofrer, levando em conta a força de quem estava do outro lado. Três ideias simples:
- **Jogo recente vale mais:** um jogo de cerca de dois anos atrás pesa metade de um jogo de hoje.
- **Jogar em casa ajuda:** o mandante marca, em média, 39% mais gols do que marcaria em campo neutro.
- **Exemplo:** para Internacional x Corinthians, no dia 07/10, o modelo espera algo como
  **1,33 x 0,93 gols**.
  Daí saem as chances: Internacional vence 45%, empate 30%, Corinthians vence 25%.

**3. O momento do time.** O segundo modelo (XGBoost) olha a fase atual: sequência de pontos, desempenho em casa e fora,
ranking de força (Elo) e dias de descanso. Os dois são misturados: **85% o primeiro, 15% o segundo**,
a mistura que errou menos quando testada em jogos passados.

**4. Jogar o campeonato 100 mil vezes.** Com a chance de cada jogo, o computador sorteia o resultado dos 103 jogos
que faltam, como se jogasse um dado viciado em cada partida, e monta a tabela final. Isso é feito **100.000 vezes**.
Em cerca de 24.130 delas, o Corinthians termina entre o 17º e o 20º lugar: daí os 24,1%.
Empates na tabela são decididos como manda o regulamento: vitórias, saldo, gols marcados e confronto direto.

**5. Como sabemos que funciona.** O modelo "previu" 1.518 jogos de 2022 a 2025 sem ver o resultado.
Quando ele dizia que algo tinha entre 40% e 50% de chance, aquilo aconteceu em 48% das vezes: as chances batem com a realidade.
A UFMG, com um método parecido, calculou 21,4%. Trocando escolhas do nosso modelo, o número fica entre
16% e 25%.

**6. Nada vai ao ar sem conferência.** Antes de publicar, quatro checagens precisam passar:
- a tabela montada a partir dos resultados é igual à oficial, nos 20 times;
- vitória + empate + derrota somam 100% em cada jogo;
- as chances de queda dos 20 times somam exatamente 4 (são 4 vagas na zona de rebaixamento);
- se o número ficar longe do da UFMG (mais de 15 pontos percentuais), a diferença é explicada antes.

**O que o modelo não sabe:** lesões, suspensões, troca de técnico, crise e motivação. Tudo isso só aparece quando vira resultado em campo.
E a previsão não é atualizada: depois do fim do campeonato (02/12), sai a comparação com o que aconteceu.

## Fontes e créditos

- **Data provided by football-data.org** — jogos, resultados e tabela de 2026.
- [Brasileirão Dataset](https://github.com/adaoduque/Brasileirao_Dataset), de Adão Duque: resultados de 2003 a 2024, só para treinar o modelo.
- football-data.co.uk: resultados de 2025 e conferência das outras fontes.
- [API-Football](https://www.api-football.com/): finalizações e xG por jogo, de 2022 a 2026 (testados; não entraram na previsão final).
- UFMG (divulgada na imprensa): só para comparar a chance de queda.
- Inspirado no [projeto de previsão da Copa de Mar Antaya](https://github.com/mar-antaya/world_cup_predictions).

---

## Para quem quer rodar o código

Requisitos: Python 3.12, Git e Node.js LTS. No Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # e cole as suas chaves das APIs no .env (nunca no código)
python -m src.diagnostico   # testa as fontes e baixa os dados para o cache local
python -m src.pipeline      # dos dados até site/data/previsao.json, em uns 3 minutos
pytest                      # testes: desempate, somas de probabilidade e ausência de vazamento
npm run site                # abre o site em http://localhost:8000
```

O pipeline roda, na ordem: consolidação das fontes, backtest do Modelo 1 (Dixon-Coles), variáveis e backtest
do Modelo 2 (XGBoost) com o Portão 2, previsão com 100 mil temporadas e as checagens, sensibilidade, diagnóstico,
o JSON do site e a imagem de prévia para redes sociais. O snapshot da previsão (`python -m src.publish.registro`)
foi gravado uma única vez e nunca é refeito. Página interna de conferência dos dados: `npm run validacao` e http://localhost:8001/dev/validacao/.

| Pasta | Conteúdo |
|---|---|
| `src/ingest/` | Coleta das fontes, com cache e limite de chamadas |
| `src/features/`, `src/models/`, `src/simulate/` | Variáveis, modelos e simulação |
| `src/checks/` | Checagens de publicação |
| `predictions/` | Snapshot único e datado da previsão |
| `site/` | Site publicado (Cloudflare Pages) |

## Segurança

- [SECURITY.md](SECURITY.md): como reportar um problema e o que o projeto faz para se proteger
  (varredura automática com Bandit, pip-audit, npm audit, Semgrep e detect-secrets a cada push).

## Licença

O **código** deste repositório (Python, JavaScript, HTML e CSS escritos para o projeto) está sob a [licença MIT](LICENSE):
qualquer pessoa pode usar, copiar e adaptar, desde que mantenha o aviso de autoria.

**Não estão cobertos pela licença MIT** e seguem os direitos de cada dono:

| Item | Dono e licença |
|---|---|
| Escudo e marca do Corinthians (`site/img/escudo-corinthians.svg`) | Sport Club Corinthians Paulista. Marca registrada, usada só para identificação num projeto de estudo sem fins comerciais |
| Foto do topo (`site/img/torcida-*`) | Anderson Bueno Pereira, via Wikimedia Commons, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.pt-br) (redimensionada) |
| Motion (`site/vendor/motion/`) | Motion B.V., licença MIT (arquivo junto) |
| Fonte Barlow Condensed (`site/vendor/@fontsource/`) | The Barlow Project Authors, SIL Open Font License 1.1 (arquivo junto) |
| Dados de futebol | Cada fonte mantém seus termos (ver "Fontes e créditos"). O repositório guarda só previsões e agregados |
