// Copia os arquivos de front-end de node_modules para site/vendor, junto com a licença de cada pacote.
// O site continua HTML/CSS/JS puros e sem CDN externo: tudo sai do próprio domínio,
// o que mantém a Content-Security-Policy simples.
//
// Para adicionar um pacote:
//   1. npm install <pacote>
//   2. inclua uma linha em PACOTES com os arquivos que o site vai usar
//   3. npm run vendor
//   4. no HTML: <script src="vendor/<pacote>/<arquivo>" defer></script>

import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");

const PACOTES = [
  { pacote: "motion", arquivos: ["dist/motion.js"] },  // animações (motion.dev), MIT
  {
    pacote: "@fontsource/barlow-condensed",  // fonte dos títulos e números, OFL
    arquivos: ["files/barlow-condensed-latin-600-normal.woff2", "files/barlow-condensed-latin-800-normal.woff2"],
  },
];

if (PACOTES.length === 0) {
  console.log("Nenhum pacote listado em tools/vendor.mjs ainda.");
}

for (const { pacote, arquivos } of PACOTES) {
  const origem = join(RAIZ, "node_modules", pacote);
  if (!existsSync(origem)) {
    console.error(`✗ ${pacote}: não instalado. Rode: npm install ${pacote}`);
    process.exitCode = 1;
    continue;
  }
  const destino = join(RAIZ, "site", "vendor", pacote);
  mkdirSync(destino, { recursive: true });
  for (const arquivo of [...arquivos, "LICENSE", "LICENSE.md", "LICENSE.txt"]) {
    const caminho = join(origem, arquivo);
    if (existsSync(caminho)) copyFileSync(caminho, join(destino, basename(arquivo)));
    else if (arquivos.includes(arquivo)) {
      console.error(`✗ ${pacote}: arquivo ${arquivo} não encontrado`);
      process.exitCode = 1;
    }
  }
  console.log(`✓ ${pacote} → site/vendor/${pacote}`);
}
