"""
COLETOR DE PARTIDAS DO JUNGLEGG

O que faz, em ordem:
  1. Pega jogadores de alto elo do Brasil (Challenger, Grandmaster, Master).
  2. Pega as partidas ranqueadas recentes de cada um.
  3. Baixa cada partida nova e conta, por campeão: jogos de jungle, vitórias,
     bans, kills, mortes, assistências, mapa e ordem de habilidades.
  4. Busca timelines novas e antigas para montar mapas e recuperar sequências.
  5. Agrega desempenho, builds e runas por lado e por jungler adversário.
  6. Salva tudo em data/estatisticas.json, que a rota /api/destaques lê.

Como rodar (dentro da pasta backend, com o ambiente virtual ativo):
    PowerShell:  $env:RIOT_API_KEY="RGAPI-sua-chave"
                 python coletor.py          (coleta até 300 partidas novas)
                 python coletor.py 1000     (coleta até 1000)

Pode rodar várias vezes: partidas já contadas são guardadas em
data/partidas_vistas.txt e nunca entram duas vezes. Timelines já processadas são
registradas em data/timelines_vistas.txt; recomendações e dados situacionais têm
marcadores separados em data/recomendacoes_vistas.txt e
data/situacoes_vistas.txt. Até 20 partidas antigas por rodada são analisadas.
Ordens antigas são recuperadas em lotes separados de até 20 timelines por execução,
sem duplicar as estatísticas do mapa. Dados situacionais antigos também são
recuperados em lotes de até 20 partidas, sem recontar os resultados gerais.
"""
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# ----------------------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------------------
PLATAFORMA = "https://br1.api.riotgames.com"      # ligas e jogadores do Brasil
REGIAO = "https://americas.api.riotgames.com"     # partidas (Américas)
DDRAGON = "https://ddragon.leagueoflegends.com"
FILA = "RANKED_SOLO_5x5"
ID_FILA = 420                # 420 = ranqueada solo/duo
PAUSA = 1.25                 # segundos entre chamadas (~48 por minuto, abaixo do limite)
MAX_JOGADORES = 40           # quantos jogadores de alto elo usar por rodada
PARTIDAS_POR_JOGADOR = 10    # partidas recentes pedidas por jogador
SALVAR_A_CADA = 25           # salva o arquivo a cada X partidas (não perde nada se travar)
TAMANHO_GRADE_MAPA = 30      # resolução do mapa de calor (30 x 30 células)
LIMITE_COORDENADA_MAPA = 15000
MAX_TIMELINES_RETROATIVAS = 20  # limita chamadas extras por execução do coletor
MAX_HABILIDADES_RETROATIVAS = 20  # recupera ordens sem reprocessar mapas
MAX_SITUACOES_RETROATIVAS = 20  # cria dados por lado e matchup em lotes

PASTA_DADOS = Path(__file__).resolve().parent / "data"
ARQ_STATS = PASTA_DADOS / "estatisticas.json"
ARQ_VISTAS = PASTA_DADOS / "partidas_vistas.txt"
ARQ_TIMELINES = PASTA_DADOS / "timelines_vistas.txt"
ARQ_RECOMENDACOES = PASTA_DADOS / "recomendacoes_vistas.txt"
ARQ_HABILIDADES = PASTA_DADOS / "habilidades_vistas.txt"
ARQ_SITUACOES = PASTA_DADOS / "situacoes_vistas.txt"


class ChaveInvalida(Exception):
    """A Riot recusou a chave (inválida ou vencida)."""


# ----------------------------------------------------------------------
# CHAMADAS À API
# ----------------------------------------------------------------------
def pegar(cliente, url, params=None):
    """
    GET na API da Riot, respeitando o limite de uso.
    Devolve o JSON, ou None se a partida não existir ou falhar várias vezes.
    """
    for _ in range(5):
        time.sleep(PAUSA)  # espera antes de TODA chamada, pra não estourar o limite
        resposta = cliente.get(url, params=params)

        if resposta.status_code == 200:
            return resposta.json()
        if resposta.status_code == 429:  # limite atingido: a Riot diz quanto esperar
            espera = int(resposta.headers.get("Retry-After", "10"))
            print(f"  limite atingido, esperando {espera}s...")
            time.sleep(espera + 1)
        elif resposta.status_code in (401, 403):
            raise ChaveInvalida("Chave inválida ou vencida (a de desenvolvimento dura 24h).")
        elif resposta.status_code == 404:
            return None
        elif resposta.status_code >= 500:  # problema do lado da Riot: tenta de novo
            time.sleep(5)
        else:
            resposta.raise_for_status()
    return None


def mapa_campeoes():
    """
    A partida traz o campeão como NÚMERO (ex: 62). O nosso site usa o id em texto
    (ex: "MonkeyKing"). O Data Dragon tem a tabela que liga um ao outro.
    """
    with httpx.Client(timeout=15) as c:
        versoes = c.get(f"{DDRAGON}/api/versions.json")
        versoes.raise_for_status()
        versao = versoes.json()[0]
        dados = c.get(f"{DDRAGON}/cdn/{versao}/data/en_US/champion.json")
        dados.raise_for_status()
    return {int(v["key"]): v["id"] for v in dados.json()["data"].values()}


# ----------------------------------------------------------------------
# ARQUIVOS (ler e salvar o que já foi coletado)
# ----------------------------------------------------------------------
def carregar():
    if ARQ_STATS.exists():
        stats = json.loads(ARQ_STATS.read_text(encoding="utf-8"))
    else:
        stats = {"partidas": 0, "atualizado": None, "campeoes": {}}
    vistas = set(ARQ_VISTAS.read_text(encoding="utf-8").split()) if ARQ_VISTAS.exists() else set()
    timelines = set(ARQ_TIMELINES.read_text(encoding="utf-8").split()) if ARQ_TIMELINES.exists() else set()
    recomendacoes = (
        set(ARQ_RECOMENDACOES.read_text(encoding="utf-8").split())
        if ARQ_RECOMENDACOES.exists() else set()
    )
    habilidades = (
        set(ARQ_HABILIDADES.read_text(encoding="utf-8").split())
        if ARQ_HABILIDADES.exists() else set()
    )
    situacoes = set(stats.get("situacoes_vistas", []))
    if ARQ_SITUACOES.exists():
        situacoes.update(ARQ_SITUACOES.read_text(encoding="utf-8").split())
    return stats, vistas, timelines, recomendacoes, habilidades, situacoes


def salvar(stats, vistas, timelines, recomendacoes, habilidades, situacoes):
    PASTA_DADOS.mkdir(exist_ok=True)
    stats["atualizado"] = datetime.now().isoformat(timespec="seconds")
    stats["situacoes_vistas"] = sorted(situacoes)
    stats["itens_10_min_vistas"] = sorted(set(stats.get("itens_10_min_vistas", [])))
    # Escreve num arquivo temporário e troca no fim: se travar no meio, o arquivo bom não corrompe
    temporario = ARQ_STATS.with_suffix(".tmp")
    temporario.write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")
    temporario.replace(ARQ_STATS)
    ARQ_VISTAS.write_text("\n".join(sorted(vistas)), encoding="utf-8")
    ARQ_TIMELINES.write_text("\n".join(sorted(timelines)), encoding="utf-8")
    ARQ_RECOMENDACOES.write_text(
        "\n".join(sorted(recomendacoes)),
        encoding="utf-8",
    )
    ARQ_HABILIDADES.write_text(
        "\n".join(sorted(habilidades)),
        encoding="utf-8",
    )
    ARQ_SITUACOES.write_text(
        "\n".join(sorted(situacoes)),
        encoding="utf-8",
    )


# ----------------------------------------------------------------------
# COLETA
# ----------------------------------------------------------------------
def listar_jogadores(cliente):
    """Pega os 'puuid' (identificador do jogador) de alto elo e sorteia alguns."""
    puuids = []
    for liga in ("challenger", "grandmaster", "master"):
        dados = pegar(cliente, f"{PLATAFORMA}/lol/league/v4/{liga}leagues/by-queue/{FILA}")
        for entrada in (dados or {}).get("entries", []):
            if entrada.get("puuid"):
                puuids.append(entrada["puuid"])
        if len(puuids) >= MAX_JOGADORES * 3:
            break  # já temos jogadores de sobra, não precisa chamar a próxima liga
    if not puuids:
        print("Nenhum jogador encontrado. Confere a chave e a resposta de league-v4 no portal da Riot.")
    random.shuffle(puuids)  # sorteia pra não usar sempre os mesmos jogadores
    return puuids[:MAX_JOGADORES]


def coletar_ids(cliente, puuids, vistas, limite):
    """Lista os ids de partidas novas (que ainda não foram contadas)."""
    novos = []
    for i, puuid in enumerate(puuids, 1):
        ids = pegar(
            cliente,
            f"{REGIAO}/lol/match/v5/matches/by-puuid/{puuid}/ids",
            {"queue": ID_FILA, "type": "ranked", "start": 0, "count": PARTIDAS_POR_JOGADOR},
        ) or []
        for id_partida in ids:
            if id_partida not in vistas and id_partida not in novos:
                novos.append(id_partida)
        print(f"  jogador {i}/{len(puuids)}: {len(novos)} partidas novas até agora")
        if len(novos) >= limite:
            break
    return novos[:limite]


def _adicionar_celula(contagens, posicao):
    """Incrementa a célula do mapa que contém uma posição válida."""
    if not isinstance(posicao, dict):
        return False
    x = posicao.get("x")
    y = posicao.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return False
    if not (0 <= x <= LIMITE_COORDENADA_MAPA and 0 <= y <= LIMITE_COORDENADA_MAPA):
        return False

    celula_x = min(int(x / LIMITE_COORDENADA_MAPA * TAMANHO_GRADE_MAPA), TAMANHO_GRADE_MAPA - 1)
    celula_y = min(int(y / LIMITE_COORDENADA_MAPA * TAMANHO_GRADE_MAPA), TAMANHO_GRADE_MAPA - 1)
    chave = f"{celula_x},{celula_y}"
    contagens[chave] = contagens.get(chave, 0) + 1
    return True


def processar_ordens_habilidades(partida, timeline, stats, ids_campeao):
    """Conta sequências completas de habilidades observadas para junglers."""
    info = partida.get("info", {})
    if (
        info.get("queueId") != ID_FILA
        or info.get("gameEndedInEarlySurrender")
        or info.get("gameDuration", 0) < 300
    ):
        return 0

    participantes = info.get("participants", [])
    campeoes_por_jogador = {}
    for participante in participantes:
        campeao = ids_campeao.get(participante.get("championId"))
        if participante.get("teamPosition") != "JUNGLE" or not campeao:
            continue
        campeoes_por_jogador[participante["participantId"]] = campeao
    if not campeoes_por_jogador:
        return 0

    por_jogador = {participant_id: [] for participant_id in campeoes_por_jogador}
    eventos = [
        evento
        for frame in timeline.get("info", {}).get("frames", [])
        for evento in frame.get("events", [])
    ]
    eventos.sort(key=lambda evento: evento.get("timestamp", 0))
    teclas = {1: "Q", 2: "W", 3: "E", 4: "R"}
    for evento in eventos:
        if evento.get("type") != "SKILL_LEVEL_UP":
            continue
        participant_id = evento.get("participantId")
        habilidade = teclas.get(evento.get("skillSlot"))
        if participant_id in por_jogador and habilidade:
            por_jogador[participant_id].append(habilidade)

    processados = 0
    for participant_id, ordem_habilidades in por_jogador.items():
        if len(ordem_habilidades) != 18:
            continue
        campeao = campeoes_por_jogador[participant_id]
        estatistica = stats["campeoes"].setdefault(
            campeao,
            {"jogos": 0, "vitorias": 0, "bans": 0, "kills": 0, "mortes": 0,
             "assistencias": 0, "confrontos": {}},
        )
        ordens = estatistica.setdefault("ordens_habilidades", {})
        chave = ",".join(ordem_habilidades)
        ordens[chave] = ordens.get(chave, 0) + 1
        processados += 1
    return processados


def processar_itens_10_min(partida, timeline, stats, ids_campeao):
    """Conta apenas os itens de patch da jungle comprados até os primeiros 10 minutos."""
    participantes = partida.get("info", {}).get("participants", [])
    junglers = {
        participante["participantId"]: ids_campeao[participante["championId"]]
        for participante in participantes
        if participante.get("teamPosition") == "JUNGLE"
        and ids_campeao.get(participante.get("championId"))
    }
    ids_patch_jungle = {
        "1035", "1039", "1101", "1102", "1103", "1107",
    }
    processados = 0
    for frame in timeline.get("info", {}).get("frames", []):
        for evento in frame.get("events", []):
            if (
                evento.get("type") != "ITEM_PURCHASED"
                or evento.get("timestamp", 10 ** 12) > 600000
            ):
                continue
            participante_id = evento.get("participantId")
            campeao = junglers.get(participante_id)
            item_id = str(evento.get("itemId", 0))
            if not campeao or item_id not in ids_patch_jungle:
                continue
            estatistica = stats["campeoes"].setdefault(
                campeao,
                {"jogos": 0, "vitorias": 0, "bans": 0, "kills": 0, "mortes": 0,
                 "assistencias": 0, "confrontos": {}},
            )
            patchs = estatistica.setdefault("itens_10_min", {})
            patchs[item_id] = patchs.get(item_id, 0) + 1
            processados += 1
    return processados


def processar_timeline(partida, timeline, stats, ids_campeao):
    """Acumula posições e abates participados no mapa de cada jungler."""
    participantes = partida.get("info", {}).get("participants", [])
    junglers = {}
    for participante in participantes:
        campeao = ids_campeao.get(participante.get("championId"))
        if participante.get("teamPosition") != "JUNGLE" or not campeao:
            continue
        junglers[participante["participantId"]] = participante
        estatistica = stats["campeoes"].setdefault(
            campeao,
            {"jogos": 0, "vitorias": 0, "bans": 0, "kills": 0, "mortes": 0,
             "assistencias": 0, "confrontos": {}},
        )
        estatistica.setdefault(
            "mapa_calor",
            {"movimentacao": {}, "abates": {}, "partidas": 0, "amostras": 0},
        )
    if not junglers:
        return 0

    amostras_por_campeao = {}
    for frame in timeline.get("info", {}).get("frames", []):
        for participant_id, participant_frame in frame.get("participantFrames", {}).items():
            participante = junglers.get(int(participant_id))
            if not participante:
                continue
            campeao = ids_campeao[participante["championId"]]
            mapa = stats["campeoes"][campeao]["mapa_calor"]
            if _adicionar_celula(mapa["movimentacao"], participant_frame.get("position")):
                amostras_por_campeao[campeao] = amostras_por_campeao.get(campeao, 0) + 1
                mapa["amostras"] += 1

    times_por_id = {p["participantId"]: p.get("teamId") for p in participantes}
    junglers_por_id = {
        participant_id: ids_campeao[participante["championId"]]
        for participant_id, participante in junglers.items()
    }
    for frame in timeline.get("info", {}).get("frames", []):
        for evento in frame.get("events", []):
            if evento.get("type") != "CHAMPION_KILL":
                continue
            envolvidos = {
                evento.get("killerId"),
                *(evento.get("assistingParticipantIds") or []),
            }
            participantes_jungler = [
                participante_id
                for participante_id in envolvidos
                if participante_id in junglers_por_id
                and times_por_id.get(participante_id) != times_por_id.get(evento.get("victimId"))
            ]
            if not participantes_jungler:
                continue
            for participante_id in participantes_jungler:
                campeao = junglers_por_id[participante_id]
                mapa = stats["campeoes"][campeao]["mapa_calor"]
                _adicionar_celula(mapa["abates"], evento.get("position"))

    processar_ordens_habilidades(partida, timeline, stats, ids_campeao)
    processar_itens_10_min(partida, timeline, stats, ids_campeao)

    for campeao in amostras_por_campeao:
        stats["campeoes"][campeao]["mapa_calor"]["partidas"] += 1
    return sum(amostras_por_campeao.values())


def _registrar_builds_e_runas(estatistica, participante):
    itens = sorted({
        str(participante.get(f"item{indice}", 0))
        for indice in range(6)
        if int(participante.get(f"item{indice}", 0) or 0) > 0
    })
    if len(itens) >= 3:
        builds = estatistica.setdefault("builds", {})
        chave_build = ",".join(itens)
        builds[chave_build] = builds.get(chave_build, 0) + 1
        estatistica["builds_partidas"] = estatistica.get("builds_partidas", 0) + 1

    estilos = participante.get("perks", {}).get("styles", [])
    if len(estilos) < 2:
        return
    pagina = {
        "principal": [
            selecao.get("perk")
            for selecao in estilos[0].get("selections", [])
            if selecao.get("perk")
        ],
        "secundaria": [
            selecao.get("perk")
            for selecao in estilos[1].get("selections", [])
            if selecao.get("perk")
        ],
    }
    if not pagina["principal"] or not pagina["secundaria"]:
        return
    paginas = estatistica.setdefault("paginas_runas", {})
    chave_pagina = json.dumps(pagina, sort_keys=True, separators=(",", ":"))
    paginas[chave_pagina] = paginas.get(chave_pagina, 0) + 1
    estatistica["runas_partidas"] = estatistica.get("runas_partidas", 0) + 1


def processar_recomendacoes(partida, stats, ids_campeao):
    """Conta itens finais e páginas de runas das partidas ranqueadas de jungle."""
    info = partida.get("info", {})
    if (
        info.get("queueId") != ID_FILA
        or info.get("gameEndedInEarlySurrender")
        or info.get("gameDuration", 0) < 300
    ):
        return 0

    processados = 0
    for participante in info.get("participants", []):
        if participante.get("teamPosition") != "JUNGLE":
            continue
        campeao = ids_campeao.get(participante.get("championId"))
        if not campeao:
            continue

        estatistica = stats["campeoes"].setdefault(
            campeao,
            {"jogos": 0, "vitorias": 0, "bans": 0, "kills": 0, "mortes": 0,
             "assistencias": 0, "confrontos": {}},
        )
        processados += 1
        _registrar_builds_e_runas(estatistica, participante)
    return processados


def _adicionar_metrica(linha, chave, valor):
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return
    metricas = linha.setdefault("metricas", {})
    amostras = linha.setdefault("amostras_metricas", {})
    metricas[chave] = metricas.get(chave, 0) + valor
    amostras[chave] = amostras.get(chave, 0) + 1


def processar_situacoes(partida, stats, ids_campeao):
    """Agrega desempenho por lado, jungler adversário, build, runas e macro."""
    info = partida.get("info", {})
    if (
        info.get("queueId") != ID_FILA
        or info.get("gameEndedInEarlySurrender")
        or info.get("gameDuration", 0) < 300
    ):
        return 0

    participantes = info.get("participants", [])
    junglers = [
        participante
        for participante in participantes
        if participante.get("teamPosition") == "JUNGLE"
        and ids_campeao.get(participante.get("championId"))
    ]
    kills_por_time = {}
    for participante in participantes:
        team_id = participante.get("teamId")
        kills_por_time[team_id] = (
            kills_por_time.get(team_id, 0) + participante.get("kills", 0)
        )

    duracao_minutos = max(info.get("gameDuration", 0) / 60, 1)
    objetivos_por_time = {
        time_.get("teamId"): time_.get("objectives", {})
        for time_ in info.get("teams", [])
    }
    processados = 0
    for jungler in junglers:
        team_id = jungler.get("teamId")
        if team_id not in (100, 200):
            continue
        id_campeao = ids_campeao[jungler["championId"]]
        estatistica = stats["campeoes"].setdefault(
            id_campeao,
            {"jogos": 0, "vitorias": 0, "bans": 0, "kills": 0, "mortes": 0,
             "assistencias": 0, "confrontos": {}},
        )
        lado = str(team_id)
        por_lado = estatistica.setdefault("por_lado", {})
        linha_lado = por_lado.setdefault(lado, {
            "jogos": 0,
            "vitorias": 0,
            "builds": {},
            "paginas_runas": {},
            "metricas": {},
            "amostras_metricas": {},
            "objetivos": {},
        })
        linha_lado["jogos"] += 1
        linha_lado["vitorias"] += 1 if jungler.get("win") else 0
        _registrar_builds_e_runas(linha_lado, jungler)

        desafios = jungler.get("challenges", {})
        total_abates_time = kills_por_time.get(team_id, 0)
        if total_abates_time:
            participacao = (
                (jungler.get("kills", 0) + jungler.get("assists", 0))
                / total_abates_time
                * 100
            )
            _adicionar_metrica(linha_lado, "participacao_abates", participacao)
        _adicionar_metrica(
            linha_lado,
            "farm_por_minuto",
            (
                jungler.get("totalMinionsKilled", 0)
                + jungler.get("neutralMinionsKilled", 0)
            ) / duracao_minutos,
        )
        _adicionar_metrica(
            linha_lado,
            "ouro_por_minuto",
            jungler.get("goldEarned", 0) / duracao_minutos,
        )
        _adicionar_metrica(
            linha_lado,
            "dano_campeoes_por_minuto",
            jungler.get("totalDamageDealtToChampions", 0) / duracao_minutos,
        )
        if "visionScore" in jungler:
            _adicionar_metrica(
                linha_lado,
                "visao_por_minuto",
                jungler["visionScore"] / duracao_minutos,
            )
        for campo, chave in (
            ("wardsPlaced", "wards_colocadas"),
            ("wardsKilled", "wards_destruidas"),
        ):
            if campo in jungler:
                _adicionar_metrica(linha_lado, chave, jungler[campo])
        for campo, chave in (
            ("controlWardsPlaced", "wards_controle"),
            ("enemyJungleMonsterKills", "acampamentos_inimigos"),
            ("scuttleCrabKills", "caranguejos"),
        ):
            if campo in desafios:
                _adicionar_metrica(linha_lado, chave, desafios[campo])

        objetivos = objetivos_por_time.get(team_id, {})
        acumulados = linha_lado.setdefault("objetivos", {})
        for chave, nome_riot in (
            ("dragoes", "dragon"),
            ("baroes", "baron"),
            ("arautos", "riftHerald"),
            ("void_grubs", "horde"),
            ("torres", "tower"),
        ):
            quantidade = objetivos.get(nome_riot, {}).get("kills")
            if quantidade is not None:
                acumulados[chave] = acumulados.get(chave, 0) + quantidade

        adversario = next(
            (
                outro
                for outro in junglers
                if outro.get("teamId") != team_id
            ),
            None,
        )
        if adversario:
            id_adversario = ids_campeao[adversario["championId"]]
            confronto = estatistica.setdefault("confrontos", {}).setdefault(
                id_adversario,
                {"jogos": 0, "vitorias": 0},
            )
            confronto_lado = confronto.setdefault("por_lado", {}).setdefault(
                lado,
                {"jogos": 0, "vitorias": 0, "builds": {}, "paginas_runas": {}},
            )
            confronto_lado["jogos"] += 1
            confronto_lado["vitorias"] += 1 if jungler.get("win") else 0
            _registrar_builds_e_runas(confronto_lado, jungler)
        processados += 1
    return processados


def processar(partida, stats, ids_campeao):
    """Soma os números de UMA partida nas estatísticas. Devolve True se contou."""
    info = partida.get("info", {})
    # Ignora outras filas, partidas muito curtas e remakes (ninguém jogou de verdade)
    if (info.get("queueId") != ID_FILA
            or info.get("gameEndedInEarlySurrender")
            or info.get("gameDuration", 0) < 300):
        return False

    def linha(campeao):
        # Cria a linha do campeão zerada na primeira vez que ele aparece
        return stats["campeoes"].setdefault(
            campeao,
            {"jogos": 0, "vitorias": 0, "bans": 0, "kills": 0, "mortes": 0,
             "assistencias": 0, "confrontos": {}},
        )

    # 1) Jogos de jungle: só quem terminou a partida na posição JUNGLE
    for p in info.get("participants", []):
        if p.get("teamPosition") != "JUNGLE":
            continue
        campeao = ids_campeao.get(p.get("championId"))
        if not campeao:
            continue
        l = linha(campeao)
        l["jogos"] += 1
        l["vitorias"] += 1 if p.get("win") else 0
        l["kills"] += p.get("kills", 0)
        l["mortes"] += p.get("deaths", 0)
        l["assistencias"] += p.get("assists", 0)

        l.setdefault("confrontos", {})
        adversarios = [
            adversario
            for adversario in info.get("participants", [])
            if adversario.get("teamPosition") == "JUNGLE"
            and adversario.get("teamId") != p.get("teamId")
        ]
        for adversario in adversarios:
            campeao_adversario = ids_campeao.get(adversario.get("championId"))
            if not campeao_adversario:
                continue
            confronto = l["confrontos"].setdefault(
                campeao_adversario,
                {"jogos": 0, "vitorias": 0},
            )
            confronto["jogos"] += 1
            confronto["vitorias"] += 1 if p.get("win") else 0

    # 2) Bans: cada time bane até 5 campeões (ban "vazio" vem como -1 e é ignorado)
    for time_ in info.get("teams", []):
        for ban in time_.get("bans", []):
            campeao = ids_campeao.get(ban.get("championId"))
            if campeao:
                linha(campeao)["bans"] += 1

    stats["partidas"] += 1
    return True


def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    chave = os.environ.get("RIOT_API_KEY") or input("Cole a chave da Riot (RGAPI-...): ").strip()

    ids_campeao = mapa_campeoes()
    (
        stats,
        vistas,
        timelines,
        recomendacoes,
        habilidades_vistas,
        situacoes_vistas,
    ) = carregar()
    print(f"Já coletadas: {stats['partidas']} partidas. Meta desta rodada: até {limite} novas.")

    cliente = httpx.Client(headers={"X-Riot-Token": chave}, timeout=15)
    try:
        print("Buscando jogadores de alto elo...")
        puuids = listar_jogadores(cliente)
        print("Buscando partidas novas...")
        novos = coletar_ids(cliente, puuids, vistas, limite)

        print(
            f"Baixando {len(novos)} partidas e timelines "
            f"(cerca de {int(len(novos) * PAUSA * 2 / 60) + 1} min, mais o backfill)..."
        )
        for n, id_partida in enumerate(novos, 1):
            partida = pegar(cliente, f"{REGIAO}/lol/match/v5/matches/{id_partida}")
            vistas.add(id_partida)  # marca como vista mesmo se falhou, pra não insistir nela
            if partida:
                if processar(partida, stats, ids_campeao):
                    processar_recomendacoes(partida, stats, ids_campeao)
                    processar_situacoes(partida, stats, ids_campeao)
                    situacoes_vistas.add(id_partida)
                    recomendacoes.add(id_partida)
                    timeline = pegar(
                        cliente,
                        f"{REGIAO}/lol/match/v5/matches/{id_partida}/timeline",
                    )
                    if timeline:
                        amostras = processar_timeline(
                            partida,
                            timeline,
                            stats,
                            ids_campeao,
                        )
                        timelines.add(id_partida)
                        habilidades_vistas.add(id_partida)
                        stats.setdefault("itens_10_min_vistas", []).append(id_partida)
                        print(
                            f"  timeline {id_partida}: {amostras} posições de jungle"
                        )
                    else:
                        print(f"  timeline indisponível para {id_partida}; tentará novamente")
                else:
                    timelines.add(id_partida)
                    recomendacoes.add(id_partida)
                    situacoes_vistas.add(id_partida)
            else:
                timelines.add(id_partida)
                recomendacoes.add(id_partida)
            if n % SALVAR_A_CADA == 0:
                salvar(
                    stats,
                    vistas,
                    timelines,
                    recomendacoes,
                    habilidades_vistas,
                    situacoes_vistas,
                )
                print(f"  {n}/{len(novos)} baixadas, total contado: {stats['partidas']}")

        # Enriquece partidas antigas gradualmente, sem contar seus resultados duas vezes.
        pendentes = sorted(
            ((vistas - timelines) | (vistas - recomendacoes)) - set(novos)
        )[:MAX_TIMELINES_RETROATIVAS]
        if pendentes:
            print(f"Enriquecendo partidas antigas: {len(pendentes)} nesta execução...")
        for id_partida in pendentes:
            partida = pegar(cliente, f"{REGIAO}/lol/match/v5/matches/{id_partida}")
            precisa_timeline = id_partida not in timelines
            precisa_recomendacao = id_partida not in recomendacoes
            if partida and precisa_recomendacao:
                total = processar_recomendacoes(partida, stats, ids_campeao)
                recomendacoes.add(id_partida)
                print(f"  recomendações antigas {id_partida}: {total} junglers")
            elif not partida:
                recomendacoes.add(id_partida)

            if partida and id_partida not in situacoes_vistas:
                total = processar_situacoes(partida, stats, ids_campeao)
                situacoes_vistas.add(id_partida)
                print(f"  dados por lado antigos {id_partida}: {total} junglers")

            if partida and precisa_timeline:
                timeline = pegar(
                    cliente,
                    f"{REGIAO}/lol/match/v5/matches/{id_partida}/timeline",
                )
                if timeline:
                    amostras = processar_timeline(partida, timeline, stats, ids_campeao)
                    print(f"  timeline antiga {id_partida}: {amostras} posições de jungle")
                    habilidades_vistas.add(id_partida)
                    stats.setdefault("itens_10_min_vistas", []).append(id_partida)
                else:
                    print(f"  timeline antiga indisponível para {id_partida}")
                    continue
                timelines.add(id_partida)

        # Refaz a leitura das timelines antigas para recuperar skill orders.
        pendentes_habilidades = sorted(
            (timelines - habilidades_vistas) - set(novos)
        )[:MAX_HABILIDADES_RETROATIVAS]
        if pendentes_habilidades:
            print(
                "Recuperando ordens de habilidades de partidas antigas: "
                f"{len(pendentes_habilidades)} nesta execução..."
            )
        for id_partida in pendentes_habilidades:
            partida = pegar(cliente, f"{REGIAO}/lol/match/v5/matches/{id_partida}")
            if not partida:
                print(f"  partida indisponível para recuperar habilidades: {id_partida}")
                continue
            timeline = pegar(
                cliente,
                f"{REGIAO}/lol/match/v5/matches/{id_partida}/timeline",
            )
            if not timeline:
                print(f"  timeline indisponível para recuperar habilidades: {id_partida}")
                continue
            ordens = processar_ordens_habilidades(
                partida,
                timeline,
                stats,
                ids_campeao,
            )
            habilidades_vistas.add(id_partida)
            print(f"  ordens antigas {id_partida}: {ordens}")

        # Recupera patches iniciais das timelines já coletadas, sem recontar mapas.
        pendentes_patch = sorted(
            (set(timelines) - set(stats.get("itens_10_min_vistas", [])))
            - set(novos)
        )[:20]
        for id_partida in pendentes_patch:
            partida = pegar(cliente, f"{REGIAO}/lol/match/v5/matches/{id_partida}")
            timeline = (
                pegar(cliente, f"{REGIAO}/lol/match/v5/matches/{id_partida}/timeline")
                if partida else None
            )
            if partida and timeline:
                processados = processar_itens_10_min(
                    partida,
                    timeline,
                    stats,
                    ids_campeao,
                )
                stats.setdefault("itens_10_min_vistas", []).append(id_partida)
                print(f"  patch inicial antigo {id_partida}: {processados} compras")

        pendentes_situacoes = sorted(
            (vistas - situacoes_vistas) - set(novos)
        )[:MAX_SITUACOES_RETROATIVAS]
        if pendentes_situacoes:
            print(
                "Recuperando dados por lado e matchup de partidas antigas: "
                f"{len(pendentes_situacoes)} nesta execução..."
            )
        for id_partida in pendentes_situacoes:
            partida = pegar(cliente, f"{REGIAO}/lol/match/v5/matches/{id_partida}")
            if not partida:
                print(f"  partida indisponível para situacionais: {id_partida}")
                continue
            total = processar_situacoes(partida, stats, ids_campeao)
            situacoes_vistas.add(id_partida)
            print(f"  dados por lado antigos {id_partida}: {total} junglers")
        salvar(
            stats,
            vistas,
            timelines,
            recomendacoes,
            habilidades_vistas,
            situacoes_vistas,
        )
    except KeyboardInterrupt:
        print("\nInterrompido. Salvando o que já foi coletado...")
    except ChaveInvalida as erro:
        print(f"\n{erro}")
    finally:
        salvar(
            stats,
            vistas,
            timelines,
            recomendacoes,
            habilidades_vistas,
            situacoes_vistas,
        )  # salva sempre, mesmo se deu erro
        cliente.close()

    print(f"Pronto. Total: {stats['partidas']} partidas em {ARQ_STATS}")


if __name__ == "__main__":
    main()
