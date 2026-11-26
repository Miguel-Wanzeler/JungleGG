const $ = (s) => document.querySelector(s);

const params = new URLSearchParams(location.search);

const id = params.get("id");
let dadosMapa = null;
let camadaMapa = "movimentacao";

const CLASSES = {
  Fighter: "Lutador", Assassin: "Assassino", Mage: "Mago",
  Marksman: "Atirador", Support: "Suporte", Tank: "Tanque",
};

function pct(v){
  return v == null ? "--" : Number(v).toFixed(1).replace(".", ",") + "%";
}

function numero(v, casas = 1){
  return v == null ? "--" : Number(v).toFixed(casas).replace(".", ",");
}

function tier(win){

  if(win >= 54) return "S+";
  if(win >= 52) return "S";
  if(win >= 50) return "A";
  if(win >= 48) return "B";

  return "C";
}

async function carregar(){

  try{
    if(!id){
      document.querySelector("main").innerHTML = `
        <section class="erro">
          <h1>Selecione um campeão</h1>
          <p>Abra um campeão pelo catálogo ou pela busca para ver sua rota, itens e estatísticas.</p>
          <a class="botao-secundario" href="campeoes.html">Ver campeões</a>
        </section>`;
      return;
    }

    const r =
      await fetch(`/api/campeao/${id}`);

    if(r.status === 404){
      document.querySelector("main").innerHTML = `
        <section class="erro">
          <h1>Campeão não encontrado</h1>
          <p>Este link não corresponde a um campeão disponível no Data Dragon.</p>
          <a class="botao-secundario" href="campeoes.html">Ver campeões</a>
        </section>`;
      return;
    }
    if(!r.ok)
      throw Error(`HTTP ${r.status}`);

    const c =
      await r.json();

    $("#nome").textContent =
      c.nome;

    $("#titulo").textContent =
      c.titulo;

    $("#hero-icon").src =
      c.icone;

    $("#hero-splash").src =
      c.splash;

    $("#classes").innerHTML =
      c.classes
       .map(i =>
         `<span class="tag">${CLASSES[i] || i}</span>`
       )
       .join("");

    $("#win").textContent =
      pct(c.win);

    $("#pick").textContent =
      pct(c.pick);

    $("#ban").textContent =
      pct(c.ban);

    $("#kda").textContent =
      c.kda == null ? "--" : numero(c.kda, 2);

    $("#kda-detalhe").textContent =
      c.kills == null
        ? "Sem dados suficientes"
        : `${numero(c.kills)} K / ${numero(c.deaths)} D / ${numero(c.assists)} A`;

    $("#tier").textContent =
      tier(c.win);

    const patchs = c.itens_10_min || [];
    $("#clear-build").innerHTML = patchs.length
      ? `
        <div class="clear-build__etiqueta">Até 10 minutos</div>
        <div class="clear-build__itens">
          ${patchs.map(patch => `
            <div class="clear-build__item ${patch === patchs[0] ? "clear-build__item--mais-usado" : ""}" title="${patch.itens[0].nome}">
              <img src="${patch.itens[0].icone}" alt="${patch.itens[0].nome}" width="42" height="42">
              <span>${patch.itens[0].nome}</span>
              <small>${patch.percentual == null ? patch.jogos : `${patch.percentual.toFixed(1).replace(".", ",")}%`} · ${patch.jogos} ${patch.jogos === 1 ? "partida" : "partidas"}</small>
            </div>`).join("")}
        </div>`
      : '<span class="dado-vazio">O patch inicial ainda não possui amostra suficiente.</span>';

    const builds = c.builds || (c.build?.length
      ? [{itens: c.build, jogos: 0}]
      : []);
    $("#build").innerHTML = builds.length
      ? builds.map((build, indice) => `
          <article class="build-variacao">
            <div class="build-variacao__titulo">
              <strong>${indice === 0 ? "Mais frequente" : `Alternativa ${indice}`}</strong>
              <small>${build.jogos} ${build.jogos === 1 ? "partida" : "partidas"}</small>
            </div>
            <div class="build-grid">
              ${build.itens.map(item => `
                <div class="build-item" title="${item.nome}">
                  <img src="${item.icone}" alt="${item.nome}">
                  <span>${item.nome}</span>
                </div>
              `).join("")}
            </div>
          </article>
        `).join("")
      : `<span class="dado-vazio">Ainda não há builds coletadas para este campeão.</span>`;
    $("#fonte-build").textContent = c.amostra_build
      ? `${c.amostra_build} partidas com inventário final válido; os itens não indicam ordem de compra.`
      : "Sem amostra própria deste campeão.";

    const paginasRunas = c.paginas_runas || [];
    $("#runas").innerHTML = paginasRunas.length
      ? paginasRunas.map((pagina, indice) => `
          <article class="pagina-runa">
            <div class="build-variacao__titulo">
              <strong>${indice === 0 ? "Mais frequente" : `Alternativa ${indice}`}</strong>
              <small>${pagina.jogos} ${pagina.jogos === 1 ? "partida" : "partidas"}</small>
            </div>
            ${["Principal", "Secundária"].map(grupo => {
              const runasGrupo = pagina.runas.filter(r => r.grupo === grupo);
              return `
                <div class="runa-grupo">
                  <h3>${grupo}</h3>
                  <div class="runa-lista">
                    ${runasGrupo.map(r => `
                      <div class="runa runa--selecionada" aria-label="${r.nome}, selecionada">
                        <img src="${r.icone}" alt="">
                        <span>${r.nome}</span>
                        <span class="runa__check" aria-hidden="true">✓</span>
                      </div>
                    `).join("")}
                  </div>
                </div>
              `;
            }).join("")}
          </article>
        `).join("")
      : `<span class="dado-vazio">Ainda não há páginas de runas coletadas para este campeão.</span>`;
    $("#fonte-runas").textContent = c.amostra_runas
      ? `${c.amostra_runas} páginas observadas nas partidas deste campeão.`
      : "Sem amostra própria deste campeão.";

    const situacoesLado = c.situacoes_lado || {};
    const situacoesConfrontos = c.situacoes_confrontos || [];
    const seletorLado = $("#situacao-lado");
    const seletorAdversario = $("#situacao-adversario");
    seletorAdversario.innerHTML += situacoesConfrontos.map(adversario => `
      <option value="${adversario.id}">${adversario.nome}</option>
    `).join("");

    const nomesMetricas = {
      farm_por_minuto: ["Farm por minuto", " tropas/min"],
      ouro_por_minuto: ["Ouro por minuto", " ouro/min"],
      participacao_abates: ["Participação em abates", "%"],
      visao_por_minuto: ["Visão por minuto", " pts/min"],
      wards_controle: ["Sentinelas de controle", ""],
      wards_destruidas: ["Sentinelas destruídas", ""],
      acampamentos_inimigos: ["Acampamentos inimigos", ""],
      caranguejos: ["Caranguejos", ""],
      dano_campeoes_por_minuto: ["Dano a campeões/min", ""],
      wards_colocadas: ["Sentinelas colocadas", ""],
    };
    const nomesObjetivos = {
      dragoes: "Dragões",
      baroes: "Barões",
      arautos: "Arautos",
      void_grubs: "Void Grubs",
      torres: "Torres",
    };

    const renderSituacao = () => {
      const lado = seletorLado.value;
      const labelLado = lado === "100" ? "Azul" : "Vermelho";
      const baseLado = situacoesLado[lado];
      const idAdversario = seletorAdversario.value;
      const adversarioSelecionado = situacoesConfrontos.find(
        item => String(item.id) === idAdversario,
      );
      const situacaoConfronto = adversarioSelecionado?.por_lado?.[lado];
      const situacao = situacaoConfronto || baseLado;
      const usandoFallback = Boolean(idAdversario && !situacaoConfronto);
      const nomeAdversario = adversarioSelecionado?.nome;
      const fonteBuild = situacaoConfronto?.jogos >= 3
        && situacaoConfronto.builds?.some(build => build.jogos >= 3)
        ? situacaoConfronto
        : baseLado;
      const fonteRunas = situacaoConfronto?.jogos >= 3
        && situacaoConfronto.paginas_runas?.some(pagina => pagina.jogos >= 3)
        ? situacaoConfronto
        : baseLado;
      const fallbackBuild = Boolean(idAdversario && fonteBuild !== situacaoConfronto);
      const fallbackRunas = Boolean(idAdversario && fonteRunas !== situacaoConfronto);

      if (!situacao?.jogos) {
        $("#situacao-resumo").innerHTML =
          `<span class="dado-vazio">Ainda não há amostra de partidas para o lado ${labelLado}.</span>`;
        $("#situacao-detalhes").innerHTML = "";
        return;
      }

      let leitura = "Sem tendência consistente";
      let classeLeitura = "situacao-status--neutro";
      if (situacaoConfronto?.jogos >= 5 && situacaoConfronto.win >= 55) {
        leitura = "Tendência favorável";
        classeLeitura = "situacao-status--bom";
      } else if (situacaoConfronto?.jogos >= 5 && situacaoConfronto.win <= 45) {
        leitura = "Tendência desfavorável";
        classeLeitura = "situacao-status--ruim";
      } else if (situacaoConfronto && situacaoConfronto.jogos < 5) {
        leitura = "Amostra baixa";
      }

      const detalheFonte = usandoFallback
        ? `Sem partidas suficientes contra ${nomeAdversario} no lado ${labelLado}; exibindo os dados gerais deste lado.`
        : situacaoConfronto
          ? `Resultado observado em ${nomeAdversario} no lado ${labelLado}; ${situacaoConfronto.jogos < 5 ? "amostra baixa para classificar como counter." : "não é garantia de vantagem na partida."}`
          : `Dados agregados de partidas no lado ${labelLado}.`;
      $("#situacao-resumo").innerHTML = `
        <div class="situacao-status ${classeLeitura}">
          <strong>${idAdversario ? leitura : "Visão geral do lado"}</strong>
          <span>${situacao.win == null ? "--" : pct(situacao.win)} de vitórias · ${situacao.jogos} partidas</span>
        </div>
        <p>${detalheFonte}</p>
      `;

      const metricas = Object.entries(situacao.metricas || {})
        .filter(([chave]) => nomesMetricas[chave])
        .map(([chave, valor]) => `
          <div class="situacao-metrica">
            <span>${nomesMetricas[chave][0]}</span>
            <strong>${numero(valor)}${nomesMetricas[chave][1]}</strong>
          </div>
        `).join("");
      const objetivos = Object.entries(situacao.objetivos_por_partida || {})
        .filter(([chave]) => nomesObjetivos[chave])
        .map(([chave, valor]) => `
          <div class="situacao-metrica">
            <span>${nomesObjetivos[chave]} por partida</span>
            <strong>${numero(valor, 2)}</strong>
          </div>
        `).join("");
      const buildsSituacionais = fonteBuild?.builds || [];
      const paginasSituacionais = fonteRunas?.paginas_runas || [];
      $("#situacao-detalhes").innerHTML = `
        <div class="situacao-coluna">
          <h3>Métricas médias</h3>
          <div class="situacao-metricas">
            ${metricas || `<span class="dado-vazio">Sem métricas disponíveis.</span>`}
            ${objetivos}
          </div>
        </div>
        <div class="situacao-coluna">
          <h3>Builds observadas</h3>
          ${fallbackBuild
            ? `<small class="situacao-fallback">Usando a amostra geral do lado; sem build confiável neste confronto.</small>`
            : ""}
          <div class="build-variacoes">
            ${buildsSituacionais.length
              ? buildsSituacionais.map((build, indice) => `
                <article class="build-variacao">
                  <div class="build-variacao__titulo">
                    <strong>${indice === 0 ? "Mais frequente" : "Alternativa"}</strong>
                    <small>${build.jogos} partidas</small>
                  </div>
                  <div class="build-grid">
                    ${build.itens.map(item => `
                      <div class="build-item" title="${item.nome}">
                        <img src="${item.icone}" alt="${item.nome}">
                        <span>${item.nome}</span>
                      </div>
                    `).join("")}
                  </div>
                </article>
              `).join("")
              : `<span class="dado-vazio">Sem build suficiente para este contexto.</span>`}
          </div>
        </div>
        <div class="situacao-coluna">
          <h3>Runas observadas</h3>
          ${fallbackRunas
            ? `<small class="situacao-fallback">Usando a amostra geral do lado; sem runa confiável neste confronto.</small>`
            : ""}
          ${paginasSituacionais.length
            ? paginasSituacionais.map(pagina => `
              <article class="pagina-runa">
                <strong>${pagina.jogos} ${pagina.jogos === 1 ? "partida" : "partidas"}</strong>
                ${["Principal", "Secundária"].map(grupo => {
                  const runasGrupo = pagina.runas.filter(runa => runa.grupo === grupo);
                  return `
                    <div class="runa-grupo">
                      <h4>${grupo}</h4>
                      <div class="runa-lista">
                        ${runasGrupo.map(runa => `
                          <div class="runa">
                            <img src="${runa.icone}" alt="">
                            <span>${runa.nome}</span>
                          </div>
                        `).join("")}
                      </div>
                    </div>
                  `;
                }).join("")}
              </article>
            `).join("")
            : `<span class="dado-vazio">Sem página de runas suficiente para este contexto.</span>`}
        </div>
      `;
    };
    seletorLado.addEventListener("change", renderSituacao);
    seletorAdversario.addEventListener("change", renderSituacao);
    renderSituacao();

    if(c.skills){
      const ordem = c.ordem_habilidades || [];
      const partidasCompletas = c.partidas_habilidades || 0;
      $("#skills").innerHTML = `
        <div class="skills-layout">
          <div class="skill-lista" aria-label="Habilidades do campeão">
            ${c.skills.map(s => `
              <div class="skill-info">
                <img src="${s.icone}" alt="${s.nome}">
                <div class="skill-info__texto">
                  <strong>${s.tecla} · ${s.nome}</strong>
                </div>
              </div>
            `).join("")}
          </div>
          <section class="skill-order-panel" aria-label="Ordem mais comum de evolução">
            <div class="skill-order-panel__cabecalho">
              <div>
                <h3>Ordem mais comum</h3>
                <p>Sequência dos níveis 1 ao 18</p>
              </div>
              ${ordem.length === 18
                ? `<span class="skill-order-panel__amostra">
                    ${c.amostra_habilidades} ${c.amostra_habilidades === 1 ? "partida" : "partidas"}
                  </span>`
                : ""}
            </div>
            ${ordem.length === 18
              ? `<div class="skill-ordem-scroll">
                  <ol class="skill-ordem">
                    ${ordem.map((tecla, indice) => `
                      <li class="skill-nivel ${indice === 0 ? "ativo" : ""} ${tecla === "R" ? "skill-nivel--ultimate" : ""}">
                        <span>Nível ${indice + 1}</span>
                        <strong>${tecla}</strong>
                      </li>
                    `).join("")}
                  </ol>
                </div>`
              : `<p class="skill-sem-dados">
                  Ainda não há sequências completas coletadas. O coletor está
                  configurado para recuperar timelines antigas gradualmente e
                  adicionar as novas partidas de alto elo.
                </p>`}
          </section>
        </div>
      `;
    }
    $("#fonte-habilidades").textContent = c.partidas_habilidades
      ? `${c.partidas_habilidades} sequências completas observadas em partidas encontradas por jogadores Challenger, Grão-Mestre e Mestre.`
      : "Dados observados em partidas ranqueadas de alto elo; a amostra começa a aparecer após a coleta.";

    if(c.clear){
      $("#clear").innerHTML =
        c.clear.map((camp, indice) =>
          `
          <div class="clear-step">
            <span class="clear-step__numero">${indice + 1}</span>
            <img class="clear-step__imagem" src="${camp.imagem}" alt="">
            <div>
              <strong>${nomeAcampamento(camp.nome)}</strong>
              <small>${camp.tempo}</small>
            </div>
          </div>
          `
        ).join("");
    }

    const renderMatchups = (elemento, lista) => {
      $(elemento).innerHTML = lista && lista.length
        ? lista.map(matchup =>
            `<div class="matchup">
              <img src="${matchup.icone}" alt="${matchup.nome}">
              <div class="matchup__conteudo">
                <strong>${matchup.nome}</strong>
                <small>
                  ${pct(matchup.win)} em ${matchup.jogos} partidas
                  <span>· Rotação ${numero(matchup.presenca)}%</span>
                </small>
                <span class="matchup__amostra">${matchup.confianca}</span>
              </div>
            </div>`
          ).join("")
        : `<span class="dado-vazio">Sem confrontos suficientes nas partidas coletadas.</span>`;
    };

    renderMatchups("#forte", c.forte);
    renderMatchups("#fraco", c.fraco);
    const textoFonte = c.fonte_matchups === "dados"
      ? "Win rate do confronto · frequência usada como desempate"
      : "Nenhum confronto com pelo menos 3 partidas";
    $("#fonte-forte").textContent = textoFonte;
    $("#fonte-fraco").textContent = textoFonte;
    carregarMapa();

  }

  catch(error){

    document.querySelector("main").innerHTML = `
      <div class="erro">
        Falha ao carregar o campeão.
      </div>
    `;
  }
}

async function carregarMapa(){
  const estado = $("#mapa-status");
  try{
    const r = await fetch(`/api/campeao/${encodeURIComponent(id || "")}/mapa`);
    if(!r.ok) throw new Error(`status ${r.status}`);
    dadosMapa = await r.json();
    $("#mapa-imagem").src = dadosMapa.imagem;

    const botoes = [...document.querySelectorAll(".mapa-abas button")];
    botoes.forEach(botao => {
      botao.disabled = !dadosMapa[botao.dataset.camada]?.length;
    });

    if(!dadosMapa[camadaMapa]?.length){
      if(dadosMapa.movimentacao.length) camadaMapa = "movimentacao";
      else if(dadosMapa.abates.length) camadaMapa = "abates";
    }
    atualizarMapa();

    if(!dadosMapa.partidas){
      estado.textContent =
        "Ainda não há timelines coletadas para este campeão. O coletor começará a preencher o mapa nas próximas execuções.";
    }else{
      estado.textContent =
        `${dadosMapa.partidas} partidas com posições · ` +
        `${dadosMapa.amostras.toLocaleString("pt-BR")} posições amostradas · ` +
        `${dadosMapa.total_abates} abates com participação.`;
    }
  }catch(error){
    console.error("Mapa de presença:", error);
    estado.textContent = "Não foi possível carregar os dados do mapa.";
  }
}

function atualizarMapa(){
  if(!dadosMapa) return;
  document.querySelectorAll(".mapa-abas button").forEach(botao => {
    botao.setAttribute("aria-pressed", botao.dataset.camada === camadaMapa);
  });

  const pontos = dadosMapa[camadaMapa] || [];
  const maximo = Math.max(...pontos.map(ponto => ponto.peso), 1);
  $("#mapa-pontos").innerHTML = pontos.map(ponto => {
    const intensidade = Math.max(0.18, ponto.peso / maximo);
    return `<span class="mapa-ponto ${camadaMapa === "abates" ? "mapa-ponto--abate" : ""}"
      style="left:${ponto.x}%;top:${ponto.y}%;--intensidade:${intensidade}"
      title="${ponto.peso} ocorrências"></span>`;
  }).join("");
}

function nomeAcampamento(nome) {
  return ({
    Red: "Rubrivira",
    Blue: "Azuporã",
    Gromp: "Grompe",
    Krugs: "Krugues",
    Raptores: "Acuâminas",
  })[nome] || nome;
}

document.querySelectorAll(".mapa-abas button").forEach(botao => {
  botao.addEventListener("click", () => {
    if(botao.disabled) return;
    camadaMapa = botao.dataset.camada;
    atualizarMapa();
  });
});

carregar();