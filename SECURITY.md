# Segurança

## Como reportar um problema

Encontrou uma falha de segurança no site ou no código? Não abra uma issue pública.
Use o botão **"Report a vulnerability"** na aba **Security** deste repositório (reporte privado do GitHub).
A resposta vem em até 7 dias.

## O que o projeto faz para se proteger

- **Site estático**, sem servidor, banco de dados, login, formulários ou cookies. Não recebe dados de quem visita.
- **Nenhuma chave no site ou no repositório**: as chaves das APIs de dados ficam só no `.env` local, fora do Git.
  O histórico completo do Git foi verificado antes de o repositório ficar público.
- **Content-Security-Policy restrita** (`site/_headers`): scripts só do próprio domínio e do Cloudflare Web Analytics;
  sem `eval`, iframes, plugins ou formulários. Também HSTS, `nosniff`, `X-Frame-Options` e `Referrer-Policy`.
- **Bibliotecas copiadas para `site/vendor`** (sem CDN de terceiros), com versão fixa e licença junto.
- **Varredura automática** a cada push e toda semana (`.github/workflows/seguranca.yml`):
  Bandit, pip-audit, npm audit, Semgrep e detect-secrets. Ações do GitHub fixadas por SHA, com permissão só de leitura.
- **Dependabot** avisa quando alguma dependência tiver falha conhecida.

## Rodar as mesmas verificações localmente

```powershell
pip install -r requirements-dev.txt
bandit -r src tools -q
pip-audit -r requirements.txt
npm audit
semgrep scan --metrics=off --config p/javascript --config p/xss --config p/secrets --config p/python --config p/security-audit --exclude site/vendor --exclude node_modules .
```
