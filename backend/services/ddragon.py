import re
import time

import httpx  # biblioteca pra fazer chamadas HTTP (pedir dados de outro site)

# Endereço base do Data Dragon, a "pasta pública" da Riot com dados e imagens
BASE = "https://ddragon.leagueoflegends.com"

# Idioma dos textos (nomes, descrições). pt_BR = português do Brasil
IDIOMA = "pt_BR"

# Quanto tempo guardamos cada resultado em memória antes de buscar de novo
CACHE_SEGUNDOS = 3600  # 1 hora

# ----------------------------------------------------------------------
# CACHE
# Um dicionário que guarda resultados já buscados.
# Formato: { "chave": (valor, momento_em_que_vence) }
# Assim não chamamos o Data Dragon a cada visita ao site.
# ----------------------------------------------------------------------
_cache = {}


def _cache_get(chave: str):
    """Devolve o valor guardado, se existir e ainda não tiver vencido."""
    guardado = _cache.get(chave)
    if guardado and time.time() < guardado[1]:
        return guardado[0]
    return None


def _cache_set(chave: str, valor):
    """Guarda um valor com prazo de validade."""
    _cache[chave] = (valor, time.time() + CACHE_SEGUNDOS)


# ----------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ----------------------------------------------------------------------
async def _buscar_json(url: str):
    """Faz um GET na url e devolve a resposta já convertida em dicionário/lista."""
    # AsyncClient permite esperar a resposta sem travar o servidor
    async with httpx.AsyncClient(timeout=10) as client:
        resposta = await client.get(url)
        # Se o site respondeu com erro (404, 500...), levanta uma exceção
        resposta.raise_for_status()
        return resposta.json()


def _limpar_html(texto: str) -> str:
    """Os textos da Riot vêm com tags HTML (<br>, <font>...). Aqui tiramos elas."""
    texto = re.sub(r"<br\s*/?>", " ", texto)  # quebra de linha vira espaço
    texto = re.sub(r"<[^>]+>", "", texto)  # remove qualquer outra tag
    return re.sub(r"\s+", " ", texto).strip()  # tira espaços repetidos


async def obter_versao() -> str:
    """Descobre a versão mais recente do jogo (usada nos links de imagem e dados)."""
    versao = _cache_get("versao")
    if versao:
        return versao

    versoes = await _buscar_json(f"{BASE}/api/versions.json")
    versao = versoes[0]  # o primeiro item da lista é sempre o mais novo
    _cache_set("versao", versao)
    return versao


async def obter_mapa_summoners_rift() -> str:
    """URL da imagem do mapa principal na versão mais recente do Data Dragon."""
    versao = await obter_versao()
    return f"{BASE}/cdn/{versao}/img/map/map11.png"


# ----------------------------------------------------------------------
# CAMPEÕES (lista completa)
# ----------------------------------------------------------------------
async def obter_campeoes():
    """Devolve a lista de todos os campeões, usando o cache quando possível."""
    lista = _cache_get("campeoes")
    if lista:
        return lista

    versao = await obter_versao()
    dados = await _buscar_json(f"{BASE}/cdn/{versao}/data/{IDIOMA}/champion.json")

    campeoes = []
    for c in dados["data"].values():
        campeoes.append(
            {
                "id": c["id"],  # nome interno (ex: Wukong é "MonkeyKing")
                "nome": c["name"],  # nome exibido
                "titulo": c["title"],  # ex: "o Rei Macaco"
                "classes": c["tags"],  # ex: ["Fighter", "Assassin"]
                "icone": f"{BASE}/cdn/{versao}/img/champion/{c['image']['full']}",
                "splash": f"{BASE}/cdn/img/champion/splash/{c['id']}_0.jpg",
            }
        )

    campeoes.sort(key=lambda c: c["nome"])
    _cache_set("campeoes", campeoes)
    return campeoes


async def resolver_id(texto: str):
    """
    Converte o que o usuário digitou no id interno do campeão.
    Aceita o id ("MonkeyKing") ou o nome ("Wukong"), sem diferenciar maiúsculas.
    Devolve None se não achar.
    """
    texto = texto.strip().lower()
    for c in await obter_campeoes():
        if texto in (c["id"].lower(), c["nome"].lower()):
            return c["id"]
    return None


# ----------------------------------------------------------------------
# CAMPEÃO (detalhes: passiva e habilidades)
# ----------------------------------------------------------------------
async def obter_campeao(texto: str):
    """Devolve os detalhes de um campeão, ou None se ele não existir."""
    id_campeao = await resolver_id(texto)
    if id_campeao is None:
        return None

    chave = f"campeao:{id_campeao}"
    guardado = _cache_get(chave)
    if guardado:
        return guardado

    versao = await obter_versao()
    # Cada campeão tem o seu próprio arquivo, com habilidades e textos completos
    dados = await _buscar_json(
        f"{BASE}/cdn/{versao}/data/{IDIOMA}/champion/{id_campeao}.json"
    )
    c = dados["data"][id_campeao]

    # "spells" vem sempre na ordem Q, W, E, R. Usamos zip pra juntar a tecla com a habilidade.
    habilidades = []
    for tecla, s in zip(["Q", "W", "E", "R"], c["spells"]):
        habilidades.append(
            {
                "tecla": tecla,
                "nome": s["name"],
                "descricao": _limpar_html(s["description"]),
                "recarga": s["cooldownBurn"],  # ex: "8/7/6/5/4" (um valor por nível)
                "custo": s["costBurn"],  # ex: "50/50/50/50/50"
                "alcance": s["rangeBurn"],
                "icone": f"{BASE}/cdn/{versao}/img/spell/{s['image']['full']}",
            }
        )

    resultado = {
        "id": c["id"],
        "nome": c["name"],
        "titulo": c["title"],
        "classes": c["tags"],
        "icone": f"{BASE}/cdn/{versao}/img/champion/{c['image']['full']}",
        "splash": f"{BASE}/cdn/img/champion/splash/{c['id']}_0.jpg",
        # A passiva fica separada das 4 habilidades e tem pasta de imagem própria
        "passiva": {
            "nome": c["passive"]["name"],
            "descricao": _limpar_html(c["passive"]["description"]),
            "icone": f"{BASE}/cdn/{versao}/img/passive/{c['passive']['image']['full']}",
        },
        "habilidades": habilidades,
    }

    _cache_set(chave, resultado)
    return resultado


# ----------------------------------------------------------------------
# ITENS
# ----------------------------------------------------------------------
async def _carregar_itens():
    """Baixa o item.json e devolve um dicionário { id_do_item: dados_limpos }."""
    itens = _cache_get("itens")
    if itens:
        return itens

    versao = await obter_versao()
    dados = await _buscar_json(f"{BASE}/cdn/{versao}/data/{IDIOMA}/item.json")
    # Também baixamos os nomes em inglês, pra poder buscar "trinity" ou "sheen"
    dados_en = await _buscar_json(f"{BASE}/cdn/{versao}/data/en_US/item.json")

    itens = {}
    for id_item, i in dados["data"].items():
        itens[id_item] = {
            "id": id_item,
            "nome": i["name"],
             # Nome em inglês, usado só na busca
            "nome_en": dados_en["data"].get(id_item, {}).get("name", ""),
            "resumo": i.get("plaintext", ""),  # frase curta explicando o item
            "descricao": _limpar_html(i["description"]),
            "custo_total": i["gold"]["total"],  # preço do item completo
            "custo_base": i["gold"]["base"],  # preço só da parte que falta comprar
            "compra_de": i.get("from", []),  # ids dos itens que formam este
            "vira": i.get("into", []),  # ids dos itens que este ajuda a formar
            "icone": f"{BASE}/cdn/{versao}/img/item/{i['image']['full']}",
            # "11" é o código do mapa Summoner's Rift. Evita itens de outros modos.
            "no_mapa": i.get("maps", {}).get("11", False),
            "comprando": i["gold"].get("purchasable", False),
        }

    _cache_set("itens", itens)
    return itens


async def obter_itens_por_ids(ids: list[str]):
    """Devolve os itens pedidos. Ids que não existem são ignorados."""
    todos = await _carregar_itens()
    return [todos[i] for i in ids if i in todos]


async def obter_runas_por_ids(ids: list[int]):
    """Devolve nome e ícone oficiais das runas selecionadas."""
    chave = "runas"
    runas = _cache_get(chave)
    if runas is None:
        versao = await obter_versao()
        dados = await _buscar_json(
            f"{BASE}/cdn/{versao}/data/{IDIOMA}/runesReforged.json"
        )
        runas = {
            runa["id"]: {
                "id": runa["id"],
                "nome": runa["name"],
                "icone": f"{BASE}/cdn/img/{runa['icon']}",
            }
            for arvore in dados
            for slot in arvore["slots"]
            for runa in slot["runes"]
        }
        _cache_set(chave, runas)
    return [runas[id_runa] for id_runa in ids if id_runa in runas]


async def buscar_itens(nome: str, max_ouro: int | None = None):
    """
    Busca itens pelo nome (parte do nome serve).
    Se max_ouro for informado, só traz itens que custam até esse valor.
    Mostra só itens comprados no Summoner's Rift, no máximo 20.
    """
    todos = await _carregar_itens()
    nome = nome.strip().lower()

    achados = []
    for item in todos.values():
        if not item["no_mapa"] or not item["comprando"]:
            continue  # pula itens que não existem na loja do mapa principal
        # Procura o texto no nome em português OU no nome em inglês
        if nome and nome not in item["nome"].lower() and nome not in item["nome_en"].lower():
            continue
        if max_ouro is not None and item["custo_total"] > max_ouro:
            continue  # pula quem passou do limite de ouro
        achados.append(item)

    achados.sort(key=lambda i: i["custo_total"])  # do mais barato ao mais caro
    return achados[:20]