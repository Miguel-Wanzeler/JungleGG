# <img src="frontend/assets/logo.svg?v=2" width="42" align="center"> JungleGG

**Estatísticas de League of Legends feitas para quem joga na selva.**

O JungleGG transforma dados de partidas ranqueadas em recomendações visuais de campeões, rotas de clear, builds, runas, confrontos e movimento pelo mapa.

> JungleGG não é aprovado pela Riot Games e não reflete as opiniões da Riot Games ou de pessoas oficialmente envolvidas com League of Legends.

## Visão geral

- Estatísticas de campeão por partidas coletadas
- Taxa de vitória, escolha e banimento
- Builds e runas mais observadas
- Patch inicial observado nos primeiros 10 minutos
- Sugestão de clear por perfil de campeão
- Confrontos fortes e difíceis
- Mapa de presença e participação em abates
- Dados por lado azul ou vermelho
- Interface responsiva para desktop e celular

## Tecnologias

- Python 3.14
- FastAPI
- Uvicorn
- HTTPX
- HTML, CSS e JavaScript
- Data Dragon da Riot Games
- API REST da Riot Games

## Executar localmente

### Pré-requisitos

- Python 3.11 ou superior
- Chave temporária ou de produção da Riot Games

### Instalação

```powershell
git clone https://github.com/Miguel-Wanzeler/JungleGG.git
cd JungleGG

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configuração

Copie `.env.example` como referência e configure o ambiente do processo.

```powershell
$env:RIOT_API_KEY="RGAPI-sua-chave"
$env:ALLOWED_HOSTS="127.0.0.1,localhost"
$env:COLETOR_AUTOMATICO="1"
$env:COLETOR_INTERVALO_MINUTOS="60"
$env:COLETOR_LIMITE="300"
```

> Nunca envie `RIOT_API_KEY` para o GitHub, HTML ou JavaScript. Use apenas variáveis de ambiente no backend.

### Inicialização

```powershell
uvicorn main:app --reload --app-dir backend
```

Acesse `http://127.0.0.1:8000`.

## Coleta automática

O coletor busca jogadores de alto elo do Brasil, partidas ranqueadas recentes e timelines relacionadas.

### Variáveis

| Variável | Finalidade | Padrão |
|---|---|---|
| `RIOT_API_KEY` | Chave secreta da API da Riot | Obrigatória |
| `ALLOWED_HOSTS` | Domínios autorizados pelo servidor | `127.0.0.1,localhost` |
| `COLETOR_AUTOMATICO` | Liga ou desliga o coletor em segundo plano | `1` |
| `COLETOR_INTERVALO_MINUTOS` | Intervalo entre execuções | `60` |
| `COLETOR_LIMITE` | Novas partidas por execução | `300` |

Os dados são gravados em `backend/data/estatisticas.json`. Arquivos de partidas já processadas evitam duplicação.

### Chave da Riot

Chaves temporárias do portal de desenvolvedores expiram em cerca de 24 horas. Para manter o projeto atualizado sem renovação diária, solicite uma chave de produção à Riot Games.

## Estrutura

```text
backend/
  main.py
  coletor.py
  services/ddragon.py
  data/
frontend/
  assets/
  css/
  js/
  index.html
  campeoes.html
  campeao.html
  rotas.html
  sobre.html
```

## Implantação

O projeto inclui `requirements.txt`, `Procfile` e suporte a variáveis de ambiente.

Exemplo para Railway:

```text
uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT
```

Configure no painel da plataforma:

- `RIOT_API_KEY`
- `ALLOWED_HOSTS`
- `COLETOR_AUTOMATICO=1`
- `COLETOR_INTERVALO_MINUTOS=60`
- `COLETOR_LIMITE=300`

## Dados e limitações

O JungleGG apresenta tendências observadas, não previsões garantidas. Taxas são exibidas apenas quando existe uma amostra mínima suficiente. Builds representam inventários finais observados e não uma ordem obrigatória de compra.

## Contato

- GitHub: [Miguel-Wanzeler](https://github.com/Miguel-Wanzeler)
- LinkedIn: [Miguel Wanzeler](https://www.linkedin.com/in/miguel-wanzeler/)
- E-mail: [contatomiguelwanzeler@gmail.com](mailto:contatomiguelwanzeler@gmail.com)

## Aviso legal

JungleGG não é afiliado à Riot Games. League of Legends e Riot Games são marcas ou marcas registradas da Riot Games, Inc.
