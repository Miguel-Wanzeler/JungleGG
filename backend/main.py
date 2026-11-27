# uvicorn main:app --reload --app-dir backend
import httpx
import os
import asyncio
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles
import json
from starlette.middleware.trustedhost import TrustedHostMiddleware

from services.ddragon import (
    buscar_itens,
    obter_campeao,
    obter_campeoes,
    obter_itens_por_ids,
    obter_mapa_summoners_rift,
    obter_runas_por_ids,
    resolver_id,
)

COLETOR_STATUS = {
    "automatico": False,
    "em_execucao": False,
    "ultima_execucao": None,
    "ultima_erro": None,
}
COLETOR_LOCK = asyncio.Lock()
PASTA_BACKEND_AUTOMATICO = Path(__file__).resolve().parent


def executar_coleta_automatica():
    chave = os.environ.get("RIOT_API_KEY", "").strip()
    if not chave:
        COLETOR_STATUS["ultima_erro"] = "RIOT_API_KEY não configurada"
        return

    limite = int(os.environ.get("COLETOR_LIMITE", "300"))
    resultado = subprocess.run(
        [sys.executable, "coletor.py", str(limite)],
        cwd=PASTA_BACKEND_AUTOMATICO,
        env={**os.environ, "RIOT_API_KEY": chave},
        capture_output=True,
        text=True,
        timeout=1800,
    )
    COLETOR_STATUS["ultima_execucao"] = datetime.now().isoformat(timespec="seconds")
    COLETOR_STATUS["ultima_erro"] = (
        None if resultado.returncode == 0
        else f"Coletor terminou com código {resultado.returncode}"
    )


async def tarefa_coleta_automatica():
    chave = os.environ.get("RIOT_API_KEY", "").strip()
    habilitada = (
        chave
        and os.environ.get("COLETOR_AUTOMATICO", "1").strip().lower()
        not in ("0", "false", "no")
    )
    COLETOR_STATUS["automatico"] = bool(habilitada)
    if not habilitada:
        COLETOR_STATUS["ultima_erro"] = "RIOT_API_KEY não configurada"
        return

    intervalo = max(
        int(os.environ.get("COLETOR_INTERVALO_MINUTOS", "60")),
        5,
    )
    await asyncio.sleep(30)
    while True:
        async with COLETOR_LOCK:
            if not COLETOR_STATUS["em_execucao"]:
                COLETOR_STATUS["em_execucao"] = True
                try:
                    await asyncio.to_thread(executar_coleta_automatica)
                except Exception as exc:
                    COLETOR_STATUS["ultima_erro"] = str(exc)
                finally:
                    COLETOR_STATUS["em_execucao"] = False
        await asyncio.sleep(intervalo * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarefa = asyncio.create_task(tarefa_coleta_automatica())
    yield
    tarefa.cancel()
    try:
        await tarefa
    except asyncio.CancelledError:
        pass


# A API pública só expõe leituras; não publica a documentação automática.
app = FastAPI(
    lifespan=lifespan,
    title="JungleGG",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost",
    ).split(",")
    if host.strip()
]
if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS precisa conter ao menos um host permitido.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


@app.middleware("http")
async def adicionar_cabecalhos_seguranca(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https://ddragon.leagueoflegends.com "
        "https://wiki.leagueoflegends.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response


# Tratador de erro global: se QUALQUER rota falhar ao falar com o Data Dragon,
# cai aqui e devolve um erro 502 legível, em vez de quebrar o servidor.
# (502 = "o servidor de que dependo falhou")
@app.exception_handler(httpx.HTTPError)
async def erro_data_dragon(request: Request, exc: httpx.HTTPError):
    return JSONResponse(
        status_code=502,
        content={"detail": "Não foi possível falar com o Data Dragon"},
    )


# Rota de teste: serve pra saber se o servidor está de pé
@app.get("/api/ping")
def ping():
    return {"status": "ok"}


@app.get("/api/coleta/status")
def status_coleta():
    return {
        "automatico": COLETOR_STATUS["automatico"],
        "em_execucao": COLETOR_STATUS["em_execucao"],
        "ultima_execucao": COLETOR_STATUS["ultima_execucao"],
        "ultima_erro": (
            None if COLETOR_STATUS["ultima_erro"] in (
                None,
                "RIOT_API_KEY não configurada",
            )
            else "Falha na última atualização automática"
        ),
    }


# Lista com todos os campeões
@app.get("/api/campeoes")
async def listar_campeoes():
    campeoes = await obter_campeoes()
    dados = (
        json.loads(ARQUIVO_STATS.read_text(encoding="utf-8"))
        if ARQUIVO_STATS.exists()
        else {}
    )
    total = max(dados.get("partidas", 0), 1)
    estatisticas = dados.get("campeoes", {})
    resultado = []
    for campeao in campeoes:
        stats = estatisticas.get(campeao["id"], {})
        jogos = stats.get("jogos", 0)
        por_lado = {}
        for lado, linha in stats.get("por_lado", {}).items():
            if lado in ("100", "200"):
                jogos_lado = linha.get("jogos", 0)
                por_lado[lado] = {
                    "jogos": jogos_lado,
                    "win": (
                        round(linha.get("vitorias", 0) / jogos_lado * 100, 1)
                        if jogos_lado else None
                    ),
                }
        resultado.append({
            **campeao,
            "jogos": jogos,
            "win": (
                round(stats.get("vitorias", 0) / jogos * 100, 1)
                if jogos >= MIN_JOGOS else None
            ),
            "pick": round(jogos / (total * 2) * 100, 1) if jogos else 0,
            "ban": round(stats.get("bans", 0) / total * 100, 1),
            "amostra_build": stats.get("builds_partidas", 0),
            "amostra_runas": stats.get("runas_partidas", 0),
            "amostra_habilidades": sum(
                stats.get("ordens_habilidades", {}).values()
            ),
            "confrontos": sum(
                1
                for confronto in stats.get("confrontos", {}).values()
                if confronto.get("jogos", 0) >= 3
            ),
            "por_lado": por_lado,
        })
    return resultado


# {nome} é um parâmetro de caminho: /api/campeao/wukong ou /api/campeao/MonkeyKing
@app.get("/api/campeao/{nome}")
async def detalhar_campeao(nome: str):

    campeao = await obter_campeao(nome)

    if campeao is None:
        raise HTTPException(
            status_code=404,
            detail="Campeão não encontrado"
        )

    win = None
    pick = None
    ban = None
    kda = None
    kills = None
    deaths = None
    assists = None
    jogos = 0
    forte = []
    fraco = []
    fonte_matchups = "dados"
    stats_campeao = {}

    if ARQUIVO_STATS.exists():

        dados = json.loads(
            ARQUIVO_STATS.read_text(
                encoding="utf-8"
            )
        )

        total = max(
            dados["partidas"],
            1
        )

        stats = dados["campeoes"].get(campeao["id"])
        stats_campeao = stats or {}

        if stats and stats["jogos"] >= MIN_JOGOS:
            jogos = stats["jogos"]
            win = round(
                stats["vitorias"]
                / stats["jogos"]
                * 100,
                1
            )

            pick = round(
                stats["jogos"]
                / (total * 2)
                * 100,
                1
            )

            ban = round(
                stats["bans"]
                / total
                * 100,
                1
            )
            kills = round(stats["kills"] / stats["jogos"], 1)
            deaths = round(stats["mortes"] / stats["jogos"], 1)
            assists = round(stats["assistencias"] / stats["jogos"], 1)
            kda = round(
                (stats["kills"] + stats["assistencias"])
                / max(stats["mortes"], 1),
                2
            )
        elif stats:
            jogos = stats["jogos"]
            if stats["jogos"] > 0:
                kills = round(stats["kills"] / stats["jogos"], 1)
                deaths = round(stats["mortes"] / stats["jogos"], 1)
                assists = round(stats["assistencias"] / stats["jogos"], 1)
                kda = round(
                    (stats["kills"] + stats["assistencias"])
                    / max(stats["mortes"], 1),
                    2
                )

        confrontos = stats.get("confrontos", {}) if stats else {}
        por_id = {c["id"]: c for c in await obter_campeoes()}
        confrontos_validos = []
        total_confrontos = sum(
            confronto.get("jogos", 0)
            for confronto in confrontos.values()
        )
        for adversario, confronto in confrontos.items():
            jogos_confronto = confronto.get("jogos", 0)
            if jogos_confronto < 3 or adversario not in por_id:
                continue
            win_confronto = round(
                confronto.get("vitorias", 0) / jogos_confronto * 100,
                1,
            )
            presenca = round(
                jogos_confronto / max(total_confrontos, 1) * 100,
                1,
            )
            if jogos_confronto >= 10:
                confianca = "Amostra forte"
            elif jogos_confronto >= 5:
                confianca = "Amostra moderada"
            else:
                confianca = "Amostra baixa"
            confrontos_validos.append({
                **por_id[adversario],
                "win": win_confronto,
                "jogos": jogos_confronto,
                "presenca": presenca,
                "confianca": confianca,
            })

        confrontos_validos.sort(
            key=lambda item: (-item["win"], -item["jogos"], item["nome"]),
        )
        forte = confrontos_validos[:4]
        confrontos_fracos = sorted(
            confrontos_validos,
            key=lambda item: (item["win"], -item["jogos"], item["nome"]),
        )
        fraco = confrontos_fracos[:4]
        fonte_matchups = "dados" if confrontos_validos else "sem_dados"

    elif campeao["id"] in EXEMPLO:

        win, pick, ban = EXEMPLO[
            campeao["id"]
        ]


    builds = []
    for chave, quantidade in sorted(
        stats_campeao.get("builds", {}).items(),
        key=lambda item: (-item[1], item[0]),
    )[:3]:
        itens = await obter_itens_por_ids(chave.split(","))
        itens = [
            item for item in itens
            if item["no_mapa"] and item["comprando"]
        ]
        if len(itens) >= 3:
            builds.append({"itens": itens, "jogos": quantidade})
    build = builds[0]["itens"] if builds else []

    itens_10_min = []
    for chave, quantidade in sorted(
        stats_campeao.get("itens_10_min", {}).items(),
        key=lambda item: (-item[1], item[0]),
    )[:3]:
        itens = await obter_itens_por_ids([chave])
        itens = [
            item for item in itens
            if item["no_mapa"] and item["comprando"]
        ]
        itens_10_min.extend(
            {"itens": itens, "jogos": quantidade}
            for item in itens
        )

    paginas_runas = []
    for chave, quantidade in sorted(
        stats_campeao.get("paginas_runas", {}).items(),
        key=lambda item: (-item[1], item[0]),
    )[:3]:
        pagina = json.loads(chave)
        principal = pagina.get("principal", [])
        secundaria = pagina.get("secundaria", [])
        runas_pagina = await obter_runas_por_ids(principal + secundaria)
        runas_pagina = [
            {
                **runa,
                "grupo": (
                    "Principal" if runa["id"] in principal else "Secundária"
                ),
            }
            for runa in runas_pagina
        ]
        if runas_pagina:
            paginas_runas.append({
                "runas": runas_pagina,
                "jogos": quantidade,
            })
    runas = paginas_runas[0]["runas"] if paginas_runas else []

    classes = campeao.get("classes", [])
    perfis_clear = {
        "LeeSin": [
            ("Red", "0:38"), ("Krugs", "1:23"), ("Raptores", "2:08"),
            ("Lobos", "2:50"), ("Blue", "3:32"), ("Gromp", "4:10"),
        ],
        "MonkeyKing": [
            ("Blue", "0:38"), ("Gromp", "1:20"), ("Lobos", "2:02"),
            ("Raptores", "2:48"), ("Red", "3:32"), ("Krugs", "4:12"),
        ],
        "Nidalee": [
            ("Blue", "0:38"), ("Gromp", "1:18"), ("Lobos", "2:00"),
            ("Raptores", "2:42"), ("Red", "3:28"), ("Krugs", "4:05"),
        ],
        "Karthus": [
            ("Red", "0:38"), ("Krugs", "1:22"), ("Raptores", "2:10"),
            ("Lobos", "2:58"), ("Blue", "3:40"), ("Gromp", "4:18"),
        ],
    }
    rota = perfis_clear.get(
        campeao["id"],
        [
            ("Red" if "Fighter" in classes or "Assassin" in classes else "Blue", "0:38"),
            ("Krugs" if "Fighter" in classes or "Assassin" in classes else "Gromp", "1:22"),
            ("Raptores", "2:08"),
            ("Lobos", "2:50"),
            ("Blue" if "Fighter" in classes or "Assassin" in classes else "Red", "3:32"),
            ("Gromp" if "Fighter" in classes or "Assassin" in classes else "Krugs", "4:10"),
        ],
    )
    imagens_acampamentos = {
        "Red": "https://wiki.leagueoflegends.com/en-us/images/thumb/Red_Brambleback_Render.png/96px-Red_Brambleback_Render.png?87cd0",
        "Blue": "https://wiki.leagueoflegends.com/en-us/images/thumb/Blue_Sentinel_Render.png/96px-Blue_Sentinel_Render.png?05fd9",
        "Gromp": "https://wiki.leagueoflegends.com/en-us/images/thumb/Gromp_Render.png/96px-Gromp_Render.png?e479e",
        "Lobos": "https://wiki.leagueoflegends.com/en-us/images/thumb/Greater_Murk_Wolf_Render.png/96px-Greater_Murk_Wolf_Render.png?39018",
        "Raptores": "https://wiki.leagueoflegends.com/en-us/images/thumb/Crimson_Raptor_Render.png/96px-Crimson_Raptor_Render.png?6345a",
        "Krugs": "https://wiki.leagueoflegends.com/en-us/images/thumb/Ancient_Krug_Render.png/96px-Ancient_Krug_Render.png?ea8dd",
    }
    clear = [
        {"nome": nome, "tempo": tempo, "imagem": imagens_acampamentos[nome]}
        for nome, tempo in rota
    ]
    skills = [
        {
            "tecla": habilidade["tecla"],
            "nome": habilidade["nome"],
            "icone": habilidade["icone"],
        }
        for habilidade in campeao.get("habilidades", [])
    ]
    ordens_habilidades = stats_campeao.get("ordens_habilidades", {})
    ordem_coletada = sorted(
        ordens_habilidades.items(),
        key=lambda item: (-item[1], item[0]),
    )
    ordem = ordem_coletada[0][0].split(",") if ordem_coletada else []
    amostra_habilidades = ordem_coletada[0][1] if ordem_coletada else 0
    partidas_habilidades = sum(ordens_habilidades.values())
    fonte_recomendacoes = (
        "dados" if builds or paginas_runas or ordem else "sem_dados"
    )

    async def formatar_situacao(fonte):
        jogos_situacao = fonte.get("jogos", 0)
        amostras = fonte.get("amostras_metricas", {})
        metricas = fonte.get("metricas", {})
        metricas_medias = {
            chave: round(valor / amostras[chave], 1)
            for chave, valor in metricas.items()
            if amostras.get(chave, 0)
        }
        builds_situacionais = []
        for chave, quantidade in sorted(
            fonte.get("builds", {}).items(),
            key=lambda item: (-item[1], item[0]),
        )[:2]:
            itens = await obter_itens_por_ids(chave.split(","))
            itens = [
                item for item in itens
                if item["no_mapa"] and item["comprando"]
            ]
            if len(itens) >= 3:
                builds_situacionais.append({"itens": itens, "jogos": quantidade})

        paginas_situacionais = []
        for chave, quantidade in sorted(
            fonte.get("paginas_runas", {}).items(),
            key=lambda item: (-item[1], item[0]),
        )[:2]:
            pagina = json.loads(chave)
            principal = pagina.get("principal", [])
            secundaria = pagina.get("secundaria", [])
            runas_situacionais = await obter_runas_por_ids(principal + secundaria)
            runas_situacionais = [
                {
                    **runa,
                    "grupo": (
                        "Principal" if runa["id"] in principal else "Secundária"
                    ),
                }
                for runa in runas_situacionais
            ]
            if runas_situacionais:
                paginas_situacionais.append({
                    "runas": runas_situacionais,
                    "jogos": quantidade,
                })

        resposta = {
            "jogos": jogos_situacao,
            "vitorias": fonte.get("vitorias", 0),
            "win": (
                round(fonte.get("vitorias", 0) / jogos_situacao * 100, 1)
                if jogos_situacao else None
            ),
            "builds": builds_situacionais,
            "paginas_runas": paginas_situacionais,
            "metricas": metricas_medias,
            "objetivos_por_partida": {
                chave: round(valor / jogos_situacao, 2)
                for chave, valor in fonte.get("objetivos", {}).items()
                if jogos_situacao
            },
        }
        return resposta

    situacoes_lado = {}
    for lado, fonte in stats_campeao.get("por_lado", {}).items():
        if lado in ("100", "200"):
            situacoes_lado[lado] = await formatar_situacao(fonte)

    situacoes_confrontos = []
    for adversario, confronto in stats_campeao.get("confrontos", {}).items():
        if adversario not in por_id or not confronto.get("por_lado"):
            continue
        por_lado_confronto = {}
        for lado, fonte in confronto["por_lado"].items():
            if lado in ("100", "200") and fonte.get("jogos", 0):
                por_lado_confronto[lado] = await formatar_situacao(fonte)
        if por_lado_confronto:
            situacoes_confrontos.append({
                **por_id[adversario],
                "por_lado": por_lado_confronto,
            })
    situacoes_confrontos.sort(key=lambda item: item["nome"])

    total_itens_10_min = sum(
        entry["jogos"]
        for entry in itens_10_min
    )
    itens_10_min_resposta = [
        {
            "itens": [item],
            "jogos": quantidade,
            "percentual": (
                round(quantidade / total_itens_10_min * 100, 1)
                if total_itens_10_min else 0
            ),
        }
        for quantidade, item in sorted(
            (
                (entry["jogos"], entry["itens"][0])
                for entry in itens_10_min
            ),
            key=lambda entry: (-entry[0], entry[1]["nome"]),
        )
    ]

    return {
        **campeao,
        "win": win,
        "pick": pick,
        "ban": ban,
        "kda": kda,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "jogos": jogos,
        "build": build,
        "builds": builds,
        "itens_10_min": itens_10_min_resposta,
        "amostra_build": stats_campeao.get("builds_partidas", 0),
        "skills": skills,
        "runas": runas,
        "paginas_runas": paginas_runas,
        "amostra_runas": stats_campeao.get("runas_partidas", 0),
        "clear": clear,
        "forte": forte,
        "fraco": fraco,
        "fonte_matchups": fonte_matchups,
        "ordem_habilidades": ordem,
        "amostra_habilidades": amostra_habilidades,
        "partidas_habilidades": partidas_habilidades,
        "fonte_recomendacoes": fonte_recomendacoes,
        "situacoes_lado": situacoes_lado,
        "situacoes_confrontos": situacoes_confrontos,
    }


@app.get("/api/campeao/{nome}/mapa")
async def obter_mapa_calor(nome: str):
    id_campeao = await resolver_id(nome)
    if id_campeao is None:
        raise HTTPException(status_code=404, detail="Campeão não encontrado")

    estatisticas = {}
    if ARQUIVO_STATS.exists():
        dados = json.loads(ARQUIVO_STATS.read_text(encoding="utf-8"))
        estatisticas = dados.get("campeoes", {}).get(id_campeao, {})
    mapa = estatisticas.get("mapa_calor", {})

    def pontos(contagens):
        resultado = []
        for chave, quantidade in contagens.items():
            try:
                celula_x, celula_y = (int(valor) for valor in chave.split(",", 1))
            except ValueError:
                continue
            if not (0 <= celula_x < 30 and 0 <= celula_y < 30):
                continue
            resultado.append({
                "x": round((celula_x + 0.5) / 30 * 100, 2),
                "y": round(100 - (celula_y + 0.5) / 30 * 100, 2),
                "peso": quantidade,
            })
        return resultado

    abates = mapa.get("abates", {})
    return {
        "campeao": id_campeao,
        "imagem": await obter_mapa_summoners_rift(),
        "partidas": mapa.get("partidas", 0),
        "amostras": mapa.get("amostras", 0),
        "total_abates": sum(abates.values()),
        "movimentacao": pontos(mapa.get("movimentacao", {})),
        "abates": pontos(abates),
    }


# Itens pelos ids: /api/itens?ids=3057,3044,3051
# Query(...) significa que o parâmetro é obrigatório
@app.get("/api/itens")
async def listar_itens(ids: str = Query(..., description="ids separados por vírgula")):
    lista_de_ids = [i.strip() for i in ids.split(",") if i.strip()]
    return await obter_itens_por_ids(lista_de_ids)


@app.get("/api/itens/selva")
async def listar_itens_mais_observados_na_selva():
    dados = (
        json.loads(ARQUIVO_STATS.read_text(encoding="utf-8"))
        if ARQUIVO_STATS.exists()
        else {}
    )
    contagens = {}
    amostra_inventarios = 0
    for estatistica in dados.get("campeoes", {}).values():
        for chave, quantidade in estatistica.get("builds", {}).items():
            if not isinstance(quantidade, int) or quantidade < 1:
                continue
            ids = {item_id for item_id in chave.split(",") if item_id}
            if len(ids) < 3:
                continue
            amostra_inventarios += quantidade
            for item_id in ids:
                contagens[item_id] = contagens.get(item_id, 0) + quantidade

    ids_populares = [
        item_id
        for item_id, _ in sorted(
            contagens.items(),
            key=lambda item: (-item[1], item[0]),
        )[:12]
    ]
    itens = await obter_itens_por_ids(ids_populares) if ids_populares else []
    itens_por_id = {
        item["id"]: item
        for item in itens
        if item["no_mapa"] and item["comprando"]
    }
    resultado = []
    for item_id in ids_populares:
        item = itens_por_id.get(item_id)
        if item is None:
            continue
        partidas = contagens[item_id]
        resultado.append({
            **item,
            "partidas": partidas,
            "percentual": round(partidas / amostra_inventarios * 100, 1),
        })

    return {
        "amostra": amostra_inventarios,
        "atualizado": dados.get("atualizado"),
        "itens": resultado,
    }


@app.get("/api/destaques")
async def destaques():
    por_id = {c["id"]: c for c in await obter_campeoes()}

    if ARQUIVO_STATS.exists():
        # DADOS REAIS: calcula as taxas a partir das contagens do coletor
        dados = json.loads(ARQUIVO_STATS.read_text(encoding="utf-8"))
        total = max(dados["partidas"], 1)
        linhas = []
        for id_, s in dados["campeoes"].items():
            if id_ in por_id and s["jogos"] >= MIN_JOGOS:
                win = s["vitorias"] / s["jogos"] * 100
                pick = s["jogos"] / (total * 2) * 100  # 2 junglers por partida
                ban = s["bans"] / total * 100
                linhas.append((id_, win, pick, ban))
        linhas.sort(key=lambda l: l[2], reverse=True)  # mais jogados primeiro
        linhas = linhas[:9]
        info = {"exemplo": False, "partidas": total, "atualizado": dados.get("atualizado")}
    else:
        linhas = [(i, *v) for i, v in EXEMPLO.items() if i in por_id]
        info = {"exemplo": True}

    campeoes = [
        {**por_id[i], "win": round(w, 1), "pick": round(p, 1), "ban": round(b, 1)}
        for i, w, p, b in linhas
    ]
    return {**info, "campeoes": campeoes}

# Busca por nome: /api/itens/buscar?nome=sheen
# E com limite de ouro: /api/itens/buscar?nome=&max_ouro=1000
@app.get("/api/itens/buscar")
async def procurar_itens(nome: str = "", max_ouro: int | None = None):
    return await buscar_itens(nome, max_ouro)


@app.get("/riot.txt", response_class=PlainTextResponse)
@app.get("/index.html/riot.txt", response_class=PlainTextResponse)
async def verificar_produto_riot():
    return PlainTextResponse(
        "3e2c31ca-81d1-490b-ad47-8bc352dd6a30",
        media_type="text/plain; charset=utf-8",
    )


# Serve a pasta "frontend" como site. Precisa ficar POR ÚLTIMO:
# o FastAPI testa as rotas na ordem, então /api/... é atendido antes e
# todo o resto cai aqui. html=True abre o index.html em "/".
PASTA_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=PASTA_FRONTEND, html=True), name="frontend")

# Arquivo que o coletor de partidas vai gerar (ainda não existe)
ARQUIVO_STATS = Path(__file__).resolve().parent / "data" / "estatisticas.json"

# Campeões com poucas partidas dão taxas enganosas, então são ignorados
MIN_JOGOS = 30

# Números de EXEMPLO, usados enquanto não houver dados reais
# formato: id do campeão: (win %, pick %, ban %)
EXEMPLO = {
    "MonkeyKing": (51.8, 9.4, 12.1), "Hecarim": (50.3, 7.8, 4.2),
    "Shaco": (48.9, 5.1, 8.7), "Graves": (49.6, 8.6, 2.5),
    "Sylas": (50.9, 3.2, 9.8), "Viego": (49.2, 10.5, 3.1),
    "Lillia": (52.4, 4.7, 6.0), "Chogath": (51.1, 2.9, 1.4),
    "Kayn": (50.6, 9.9, 7.3),
}


