const $ = (seletor) => document.querySelector(seletor);

const CLASSES = {
  Fighter: "Lutador",
  Assassin: "Assassino",
  Mage: "Mago",
  Marksman: "Atirador",
  Support: "Suporte",
  Tank: "Tanque",
};

const POSICOES_ACAMPAMENTOS = {
  Red: [34, 69],
  Krugs: [44, 77],
  Raptores: [53, 67],
  Lobos: [50, 51],
  Blue: [39, 41],
  Gromp: [38, 29],
};

const escapar = (valor) => String(valor ?? "").replace(/[&<>"']/g, (caractere) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[caractere]));

const semAcentos = (texto) => texto
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLocaleLowerCase("pt-BR");

let campeoes = [];
let resultados = [];
let requisicaoAtual = 0;
let requisicaoRotasPopulares = 0;
let ladoSelecionado = "blue";
let imagemMapa = "";
let passosAtuais = [];
let rotasPopulares = [];
let carregandoRotasPopulares = false;
const campoBusca = $("#busca-rota");
const listaResultados = $("#resultados-rota");
const cacheRotas = new Map();

function fecharResultados() {
  listaResultados.hidden = true;
  campoBusca.setAttribute("aria-expanded", "false");
}

function desenharResultados() {
  const termo = semAcentos(campoBusca.value.trim());
  if (!termo) {
    fecharResultados();
    resultados = [];
    return;
  }

  resultados = campeoes
    .filter((campeao) => semAcentos(`${campeao.nome} ${campeao.id}`).includes(termo))
    .slice(0, 7);

  listaResultados.innerHTML = resultados.length
    ? resultados.map((campeao, indice) => `
      <button class="resultado-rota" type="button" role="option"
              aria-selected="false" data-indice="${indice}" data-id="${escapar(campeao.id)}">
        <img src="${escapar(campeao.icone)}" alt="" width="38" height="38">
        <span class="resultado-rota__texto">
          <strong>${escapar(campeao.nome)}</strong>
          <small>${escapar(campeao.classes.map((classe) => CLASSES[classe] || classe).join(" · "))}</small>
        </span>
      </button>`).join("")
    : '<p class="erro-lista">Nenhum campeão encontrado.</p>';
  listaResultados.hidden = false;
  campoBusca.setAttribute("aria-expanded", "true");
}

function nomeAcampamento(nome) {
  return ({ Red: "Red", Blue: "Blue" })[nome] || nome;
}

async function obterDadosCampeao(id) {
  const emCache = cacheRotas.get(id);
  if (emCache) return emCache;

  const resposta = await fetch(`/api/campeao/${encodeURIComponent(id)}`);
  if (!resposta.ok) throw new Error(`Detalhes de ${id}: HTTP ${resposta.status}`);
  const campeao = await resposta.json();
  cacheRotas.set(id, campeao);
  return campeao;
}

async function obterImagemMapa(id) {
  if (imagemMapa) return imagemMapa;
  const resposta = await fetch(`/api/campeao/${encodeURIComponent(id)}/mapa`);
  if (!resposta.ok) throw new Error(`Mapa de Summoner's Rift: HTTP ${resposta.status}`);
  const dados = await resposta.json();
  if (!dados.imagem) throw new Error("A API não retornou a imagem do mapa.");
  imagemMapa = dados.imagem;
  return imagemMapa;
}

function obterCoordenadas(passos) {
  return passos.map((passo, indice) => {
    const [xOriginal, yOriginal] = POSICOES_ACAMPAMENTOS[passo.nome] || [50, 50];
    const x = ladoSelecionado === "red" ? 100 - xOriginal : xOriginal;
    const y = ladoSelecionado === "red" ? 100 - yOriginal : yOriginal;
    return { x, y, indice, passo };
  });
}

function desenharMapa(passos) {
  const pontos = obterCoordenadas(passos);
  $("#rota-caminho").setAttribute(
    "points",
    pontos.map(({ x, y }) => `${x},${y}`).join(" "),
  );
  $("#rota-marcadores").innerHTML = pontos.map(({ x, y, indice, passo }) => `
    <span class="rota-mapa__marcador"
          style="left:${x}%;top:${y}%"
          title="${indice + 1}. ${escapar(nomeAcampamento(passo.nome))} — ${escapar(passo.tempo)}"
          aria-label="${indice + 1}. ${escapar(nomeAcampamento(passo.nome))}, ${escapar(passo.tempo)}">
      ${indice + 1}
    </span>`).join("");
  $("#rota-lado-mapa").textContent =
    ladoSelecionado === "blue" ? "Lado azul" : "Lado vermelho";
  $("#rota-card").dataset.lado = ladoSelecionado;
}

function desenharPassos(passos) {
  $("#rota-passos").innerHTML = passos.map((passo, indice) => `
    <article class="rota-passo">
      <span class="rota-passo__numero">${indice + 1}</span>
      <img src="${escapar(passo.imagem)}" alt="" loading="lazy">
      <strong>${escapar(nomeAcampamento(passo.nome))}</strong>
      <small>${escapar(passo.tempo)}</small>
    </article>`).join("");
}

function desenharItensCampeao(campeao) {
  const patchs = campeao.itens_10_min || [];

  if (!patchs.length) {
    $("#rota-build").innerHTML =
      '<p class="estado-rota">O patch inicial ainda não possui amostra suficiente.</p>';
    return;
  }

  $("#rota-build").innerHTML = `
    <div class="rota-build__etiqueta">Até 10 minutos</div>
    <div class="rota-build__itens">
      ${patchs.map((patch) => {
        const item = patch.itens[0];
        return `
        <div class="rota-build__item ${patch === patchs[0] ? "rota-build__item--mais-usado" : ""}" title="${escapar(item.nome)}">
          <img src="${escapar(item.icone)}" alt="${escapar(item.nome)}" width="44" height="44" loading="lazy">
          <span>${escapar(item.nome)}</span>
          <small>${patch.percentual == null ? patch.jogos : `${patch.percentual.toFixed(1).replace(".", ",")}%`} · ${patch.jogos} ${patch.jogos === 1 ? "partida" : "partidas"}</small>
        </div>`;
      }).join("")}
    </div>`;
}

function desenharRotasPopulares() {
  const lado = ladoSelecionado === "blue" ? "Azul" : "Vermelho";
  const classeLado = ladoSelecionado === "blue" ? "azul" : "vermelho";
  $("#rotas-populares").innerHTML = rotasPopulares.length
    ? rotasPopulares.map((campeao) => `
      <button class="rota-popular ${campeao.id === $("#rota-nome").dataset.id ? "selecionada" : ""}"
              type="button" data-id="${escapar(campeao.id)}"
              aria-pressed="${campeao.id === $("#rota-nome").dataset.id}">
        <span class="rota-popular__identidade">
          <img src="${escapar(campeao.icone)}" alt="" width="42" height="42" loading="lazy">
          <strong>${escapar(campeao.nome)}</strong>
        </span>
        <span class="rota-popular__passos" aria-label="Ordem dos acampamentos">
          ${campeao.clear.map((passo, indice) => `
            ${indice ? '<span class="rota-popular__seta" aria-hidden="true">›</span>' : ""}
            <img src="${escapar(passo.imagem)}" alt="${escapar(nomeAcampamento(passo.nome))}"
                 title="${escapar(nomeAcampamento(passo.nome))}" loading="lazy">`).join("")}
        </span>
        <span class="rota-popular__lado rota-popular__lado--${classeLado}">Lado ${lado}</span>
      </button>`).join("")
    : `<p class="estado-rota">${carregandoRotasPopulares
      ? "Carregando rotas populares..."
      : "Ainda não foi possível carregar outras rotas."}</p>`;
}

async function carregarItensGerais() {
  try {
    const resposta = await fetch("/api/itens/selva");
    if (!resposta.ok) throw new Error(`Itens gerais: HTTP ${resposta.status}`);
    const dados = await resposta.json();
    const itens = dados.itens || [];
    if (!itens.length) {
      $("#itens-gerais").innerHTML =
        '<p class="estado-rota">Ainda não há inventários suficientes para resumir itens da selva.</p>';
      $("#fonte-itens-gerais").textContent =
        "Os itens aparecerão aqui quando houver inventários finais válidos nas partidas coletadas.";
      return;
    }

    $("#itens-gerais").innerHTML = itens.map((item) => `
      <article class="item-geral">
        <img src="${escapar(item.icone)}" alt="" width="50" height="50" loading="lazy">
        <strong title="${escapar(item.nome)}">${escapar(item.nome)}</strong>
        <small>${item.percentual.toFixed(1).replace(".", ",")}% · ${item.partidas} partidas</small>
      </article>`).join("");
    const atualizacao = dados.atualizado
      ? ` Atualizado em ${dados.atualizado.replace("T", " ")}.`
      : "";
    $("#fonte-itens-gerais").textContent =
      `Frequência em ${dados.amostra} inventários finais coletados; não indica ordem de compra nem build ideal.${atualizacao}`;
  } catch (erro) {
    console.error("Não foi possível carregar os itens gerais da selva:", erro);
    $("#itens-gerais").innerHTML =
      '<p class="estado-rota">Não foi possível carregar os itens. Tente atualizar a página.</p>';
    $("#fonte-itens-gerais").textContent = "Falha ao consultar os itens agregados das partidas.";
  }
}

async function carregarRotasPopulares() {
  const requisicao = ++requisicaoRotasPopulares;
  carregandoRotasPopulares = true;
  desenharRotasPopulares();
  const maisEscolhidos = [...campeoes]
    .sort((a, b) => b.pick - a.pick || a.nome.localeCompare(b.nome, "pt-BR"));
  const candidatos = maisEscolhidos.slice(0, 5);

  const rotas = await Promise.all(candidatos.map(async (resumo) => {
    try {
      return await obterDadosCampeao(resumo.id);
    } catch (erro) {
      console.error(`Não foi possível carregar a rota de ${resumo.nome}:`, erro);
      return null;
    }
  }));
  if (requisicao !== requisicaoRotasPopulares) return;

  rotasPopulares = rotas.filter((campeao) => campeao?.clear?.length);
  carregandoRotasPopulares = false;
  desenharRotasPopulares();
}

async function carregarRota(id) {
  const requisicao = ++requisicaoAtual;
  $("#status-rotas").textContent = "Carregando dados do campeão...";

  try {
    const campeao = await obterDadosCampeao(id);
    if (requisicao !== requisicaoAtual) return;

    const passos = campeao.clear || [];
    if (!passos.length) {
      throw new Error("Este campeão ainda não tem uma sugestão de rota.");
    }

    try {
      $("#rota-mapa-imagem").src = await obterImagemMapa(campeao.id);
      $("#rota-mapa-imagem").hidden = false;
      $("#rota-mapa-fallback").hidden = true;
    } catch (erroMapa) {
      console.error("Não foi possível carregar o mapa:", erroMapa);
      $("#rota-mapa-imagem").removeAttribute("src");
      $("#rota-mapa-imagem").hidden = true;
      $("#rota-mapa-fallback").hidden = false;
    }
    if (requisicao !== requisicaoAtual) return;

    $("#rota-icone").src = campeao.icone;
    $("#rota-icone").alt = `Ícone de ${campeao.nome}`;
    $("#rota-nome").textContent = campeao.nome;
    $("#rota-nome").dataset.id = campeao.id;
    const classes = campeao.classes.map((classe) => CLASSES[classe] || classe).join(" · ");
    const resumoAmostra = campeao.jogos >= 30
      ? `${campeao.jogos} partidas coletadas · taxa de vitória ${campeao.win == null ? "--" : `${campeao.win.toFixed(1).replace(".", ",")}%`}`
      : `Amostra baixa (${campeao.jogos} partidas) · taxa de vitória inconclusiva`;
    $("#rota-resumo").textContent = `${classes} · ${resumoAmostra}`;
    $("#rota-guia").href = `campeao.html?id=${encodeURIComponent(campeao.id)}`;

    passosAtuais = passos;
    desenharMapa(passosAtuais);
    desenharPassos(passosAtuais);
    desenharItensCampeao(campeao);
    $("#rota-geral").hidden = true;
    $("#rota-card").hidden = false;
    $("#seletor-lado").hidden = false;
    $("#status-rotas").textContent = `Rota exibida para ${campeao.nome}.`;
    campoBusca.value = campeao.nome;
    desenharRotasPopulares();
  } catch (erro) {
    if (requisicao !== requisicaoAtual) return;
    console.error("Não foi possível carregar a rota:", erro);
    $("#status-rotas").textContent =
      "Não foi possível carregar essa rota. A visão geral continua disponível; tente outro campeão.";
  }
}

function mostrarVisaoGeral() {
  requisicaoAtual += 1;
  passosAtuais = [];
  const url = new URL(location.href);
  url.searchParams.delete("id");
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  $("#rota-card").hidden = true;
  $("#rota-geral").hidden = false;
  $("#seletor-lado").hidden = true;
  $("#rota-nome").dataset.id = "";
  campoBusca.value = "";
  fecharResultados();
  $("#status-rotas").textContent =
    "Visão geral da selva. Escolha um campeão para consultar uma rota específica.";
  desenharRotasPopulares();
}

campoBusca.addEventListener("input", desenharResultados);
campoBusca.addEventListener("focus", desenharResultados);
campoBusca.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape") fecharResultados();
  if (evento.key === "Enter" && resultados.length) {
    evento.preventDefault();
    const campeao = resultados[0];
    campoBusca.value = campeao.nome;
    fecharResultados();
    void carregarRota(campeao.id);
  }
});
listaResultados.addEventListener("click", (evento) => {
  const botao = evento.target.closest("button[data-id]");
  if (!botao) return;
  const campeao = campeoes.find((item) => item.id === botao.dataset.id);
  if (!campeao) return;
  campoBusca.value = campeao.nome;
  fecharResultados();
  void carregarRota(campeao.id);
});
document.querySelectorAll(".seletor-lado__botao").forEach((botao) => {
  botao.addEventListener("click", () => {
    ladoSelecionado = botao.dataset.lado;
    document.querySelectorAll(".seletor-lado__botao").forEach((opcao) => {
      opcao.setAttribute("aria-pressed", String(opcao === botao));
    });
    desenharMapa(passosAtuais);
    desenharRotasPopulares();
  });
});
$("#rotas-populares").addEventListener("click", (evento) => {
  const botao = evento.target.closest("button[data-id]");
  if (botao) void carregarRota(botao.dataset.id);
});
$("#rota-voltar-geral").addEventListener("click", mostrarVisaoGeral);
document.addEventListener("click", (evento) => {
  if (!evento.target.closest(".seletor-rota")) fecharResultados();
});

async function inicializar() {
  try {
    const resposta = await fetch("/api/campeoes");
    if (!resposta.ok) throw new Error(`Lista de campeões: HTTP ${resposta.status}`);
    campeoes = await resposta.json();
    void carregarRotasPopulares();
    void carregarItensGerais();
    const idInicial = new URLSearchParams(location.search).get("id");
    if (!idInicial) {
      $("#status-rotas").textContent =
        "Visão geral da selva. Escolha um campeão para consultar uma rota específica.";
      return;
    }
    const selecionado = campeoes.find((campeao) => campeao.id === idInicial);
    if (!selecionado) {
      $("#status-rotas").textContent =
        "O campeão do link não foi encontrado. A visão geral da selva continua disponível.";
      return;
    }
    await carregarRota(selecionado.id);
  } catch (erro) {
    console.error("Não foi possível iniciar as rotas:", erro);
    $("#status-rotas").textContent = "Falha ao carregar os dados.";
  }
}

inicializar();
