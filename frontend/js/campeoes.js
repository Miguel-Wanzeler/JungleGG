const $ = (seletor) => document.querySelector(seletor);

const CLASSES = {
  Fighter: "Lutador",
  Assassin: "Assassino",
  Mage: "Mago",
  Marksman: "Atirador",
  Support: "Suporte",
  Tank: "Tanque",
};

const escapar = (valor) => String(valor ?? "").replace(/[&<>"']/g, (caractere) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[caractere]));

const percentual = (valor) => valor == null
  ? "--"
  : `${Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

const splashArt = (id) =>
  `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${encodeURIComponent(id)}_0.jpg`;

const semAcentos = (texto) => texto
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLocaleLowerCase("pt-BR");

let campeoes = [];
const grade = $("#grade-campeoes");
const busca = $("#busca-campeao");
const filtroClasse = $("#filtro-classe");
const ordenar = $("#ordenar-campeoes");

function desenharDestaques() {
  const destaques = [...campeoes]
    .filter((campeao) => campeao.jogos >= 30 && campeao.win != null)
    .sort((a, b) => b.pick - a.pick || a.nome.localeCompare(b.nome, "pt-BR"))
    .slice(0, 3);

  $("#grade-destaques").innerHTML = destaques.map((campeao, indice) => {
    const nome = escapar(campeao.nome);
    const arte = escapar(splashArt(campeao.id));
    const classes = escapar(
      campeao.classes.map((classe_) => CLASSES[classe_] || classe_).join(" · "),
    );
    const winClass = campeao.win >= 50 ? "bom" : "ruim";
    return `
      <a class="destaque-campeao" href="campeao.html?id=${encodeURIComponent(campeao.id)}">
        <img class="destaque-campeao__splash" src="${arte}" alt="" aria-hidden="true" loading="lazy" decoding="async">
        <div class="destaque-campeao__topo">
          <span class="destaque-campeao__posicao">0${indice + 1}</span>
          <span class="destaque-campeao__tag">Mais escolhido</span>
        </div>
        <div class="destaque-campeao__identidade">
          <img src="${escapar(campeao.icone)}" alt="" width="68" height="68" loading="lazy">
          <div>
            <h3>${nome}</h3>
            <span>${classes}</span>
          </div>
        </div>
        <div class="destaque-campeao__win">
          <span>Taxa de vitória</span>
          <strong class="${winClass}">${percentual(campeao.win)}</strong>
        </div>
        <div class="barra"><i class="${winClass}" style="--v:${Math.min(campeao.win, 100)}%"></i></div>
        <div class="destaque-campeao__rodape">
          <span>Escolha <strong>${percentual(campeao.pick)}</strong></span>
          <span>Banimento <strong>${percentual(campeao.ban)}</strong></span>
          <span>${campeao.jogos} partidas</span>
        </div>
      </a>`;
  }).join("");
}

function desenharCampeoes() {
  const termo = semAcentos(busca.value.trim());
  const classe = filtroClasse.value;
  const ordem = ordenar.value;

  const filtrados = campeoes
    .filter((campeao) => {
      const combinaNome = !termo
        || semAcentos(`${campeao.nome} ${campeao.id}`).includes(termo);
      const combinaClasse = !classe || campeao.classes.includes(classe);
      return combinaNome && combinaClasse;
    })
    .sort((a, b) => {
      if (ordem === "nome") return a.nome.localeCompare(b.nome, "pt-BR");
      const valorA = a[ordem] == null ? Number.NEGATIVE_INFINITY : a[ordem];
      const valorB = b[ordem] == null ? Number.NEGATIVE_INFINITY : b[ordem];
      return valorB - valorA || a.nome.localeCompare(b.nome, "pt-BR");
    });

  $("#contagem-campeoes").textContent =
    `${filtrados.length} ${filtrados.length === 1 ? "campeão" : "campeões"}`;

  if (!filtrados.length) {
    grade.innerHTML = '<p class="erro-lista">Nenhum campeão corresponde a esses filtros.</p>';
    return;
  }

  grade.innerHTML = filtrados.map((campeao) => {
    const nome = escapar(campeao.nome);
    const arte = escapar(splashArt(campeao.id));
    const classes = campeao.classes.map((classe_) => CLASSES[classe_] || classe_);
    const classesTexto = escapar(classes.join(" · "));
    const href = `campeao.html?id=${encodeURIComponent(campeao.id)}`;
    const temAmostra = campeao.jogos >= 30 && campeao.win != null;
    const winClass = temAmostra
      ? campeao.win >= 50 ? "bom" : "ruim"
      : "";
    const notaAmostra = temAmostra
      ? `${campeao.jogos} partidas · ${campeao.confrontos} confrontos`
      : `Amostra pequena · ${campeao.jogos} ${campeao.jogos === 1 ? "partida" : "partidas"}`;

    return `
      <a class="card card-campeao" href="${href}" data-id="${escapar(campeao.id)}">
        <img class="card__fundo card-campeao__splash" src="${arte}" alt="" aria-hidden="true" loading="lazy" decoding="async">
        <div class="card__topo">
          <img class="card__icone" src="${escapar(campeao.icone)}" alt="" width="56" height="56" loading="lazy">
          <div>
            <h3>${nome}</h3>
            <span class="card__classe">${classesTexto}</span>
          </div>
        </div>
        <div class="card-campeao__wr">
          <span>Taxa de vitória</span>
          <strong class="${winClass}">${percentual(temAmostra ? campeao.win : null)}</strong>
        </div>
        <div class="barra"><i class="${winClass}" style="--v:${temAmostra ? Math.min(campeao.win, 100) : 0}%"></i></div>
        <div class="card-campeao__metricas">
          <span class="card-campeao__metrica">Escolha <strong>${percentual(campeao.pick)}</strong></span>
          <span class="card-campeao__metrica">Banimento <strong>${percentual(campeao.ban)}</strong></span>
          <span class="card-campeao__metrica">Builds <strong>${campeao.amostra_build}</strong></span>
          <span class="card-campeao__metrica">Runas <strong>${campeao.amostra_runas}</strong></span>
        </div>
        <span class="card-campeao__meta ${temAmostra ? "" : "card-campeao__meta--pendente"}">${notaAmostra}</span>
      </a>`;
  }).join("");

  requestAnimationFrame(() => {
    grade.classList.add("pronto");
    $("#grade-destaques").classList.add("pronto");
  });
}

async function carregarCampeoes() {
  grade.innerHTML = '<div class="card card--esqueleto" aria-hidden="true"></div>'.repeat(6);
  try {
    const [respostaCampeoes, respostaDestaques] = await Promise.all([
      fetch("/api/campeoes"),
      fetch("/api/destaques"),
    ]);
    if (!respostaCampeoes.ok) throw new Error(`Lista de campeões: HTTP ${respostaCampeoes.status}`);
    if (!respostaDestaques.ok) throw new Error(`Estatísticas: HTTP ${respostaDestaques.status}`);

    campeoes = await respostaCampeoes.json();
    const destaques = await respostaDestaques.json();
    const comWinRate = campeoes.filter((campeao) => campeao.win != null).length;
    const atualizado = destaques.atualizado
      ? new Date(destaques.atualizado).toLocaleString("pt-BR")
      : "sem horário de atualização";
    $("#fonte-campeoes").textContent = destaques.exemplo
      ? `${campeoes.length} campeões. Estatísticas de exemplo até a coleta real.`
      : `${destaques.partidas.toLocaleString("pt-BR")} partidas analisadas · ${comWinRate} campeões com 30+ jogos · atualizado em ${atualizado}.`;
    desenharDestaques();
    desenharCampeoes();
  } catch (erro) {
    console.error("Não foi possível carregar o catálogo:", erro);
    grade.innerHTML = `
      <div class="erro-lista">
        <p>Não foi possível carregar os campeões. Verifique se a API está disponível.</p>
        <button type="button" id="tentar-novamente">Tentar novamente</button>
      </div>`;
    $("#tentar-novamente").addEventListener("click", carregarCampeoes);
  }
}

busca.addEventListener("input", desenharCampeoes);
filtroClasse.addEventListener("change", desenharCampeoes);
ordenar.addEventListener("change", desenharCampeoes);
carregarCampeoes();
