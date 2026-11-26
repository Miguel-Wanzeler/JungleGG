// ==================================================================
// HOME DO JUNGLEGG
// Fluxo: carrega a lista de campeões (pra busca) e os destaques (pros cards),
// desenha tudo e liga os eventos de teclado, clique e ordenação.
// ==================================================================

// ---------- ATALHOS E FUNÇÕES PEQUENAS ----------
const $ = (seletor) => document.querySelector(seletor);

// true se a pessoa pediu "menos movimento" no sistema (acessibilidade)
const reduzMovimento = matchMedia("(prefers-reduced-motion: reduce)").matches;

// Os nomes das classes vêm em inglês do Data Dragon; aqui traduzimos
const CLASSES = {
  Fighter: "Lutador", Assassin: "Assassino", Mage: "Mago",
  Marksman: "Atirador", Support: "Suporte", Tank: "Tanque",
};
const nomeClasses = (lista) => lista.map((c) => CLASSES[c] || c).join(", ");

// Tira acentos e maiúsculas pra a busca achar "Cho'Gath" digitando "chogath"
const semAcento = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

// 60.4 -> "60,4%"
const pct = (v) => v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";

// Protege o HTML: o que o usuário digita nunca pode virar código
const esc = (t) => t.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const abrir = (id) => { location.href = "campeao.html?id=" + encodeURIComponent(id); };

// ---------- ESTADO ----------
let campeoes = [];     // todos os campeões (usado pela busca)
let destaques = [];    // campeões com win, pick e ban (usado pelos cards)
let ordem = "pick";    // critério de ordenação atual
let resultados = [];   // sugestões da busca neste momento
let ativo = -1;        // posição da sugestão marcada pelas setas

const campo = document.querySelector("#campo-busca");
const lista = document.querySelector("#resultados");
const grid = document.querySelector("#grid");

if (!campo || !lista || !grid) {
  throw new Error(
    `Elemento não encontrado:
    campo=${!!campo}
    lista=${!!lista}
    grid=${!!grid}`
  );
}

// ==================================================================
// BUSCA: digita, vê sugestões, navega com setas, Enter abre
// ==================================================================
function fechar() {
  lista.hidden = true;
  campo.setAttribute("aria-expanded", "false");
  campo.removeAttribute("aria-activedescendant");
}

function marcarAtivo() {
  [...lista.children].forEach((li, i) => li.setAttribute("aria-selected", i === ativo));
  const li = lista.children[ativo];
  if (li) {
    campo.setAttribute("aria-activedescendant", li.id);
    li.scrollIntoView({ block: "nearest" });
  }
}

function desenharResultados() {
  const texto = campo.value.trim();
  if (!texto) { fechar(); return; }

  if (!campeoes.length) {
    lista.innerHTML = '<li class="vazio">Carregando campeões...</li>';
    resultados = [];
  } else {
    const t = semAcento(texto);
    resultados = campeoes
      .filter((c) => semAcento(c.nome).includes(t) || semAcento(c.id).includes(t))
      // Quem COMEÇA com o texto vem primeiro
      .sort((a, b) => Number(semAcento(b.nome).startsWith(t)) - Number(semAcento(a.nome).startsWith(t)))
      .slice(0, 6);

    lista.innerHTML = resultados.length
      ? resultados.map((c, i) => `
          <li role="option" id="op-${i}" data-id="${esc(c.id)}">
            <img src="${c.icone}" alt="" width="36" height="36">
            <div><div class="nome">${esc(c.nome)}</div><div class="sub">${esc(c.titulo)}, ${nomeClasses(c.classes)}</div></div>
          </li>`).join("")
      : `<li class="vazio">Nenhum campeão com “${esc(texto)}”. Confere a grafia.</li>`;
  }
  ativo = resultados.length ? 0 : -1;
  lista.hidden = false;
  campo.setAttribute("aria-expanded", "true");
  marcarAtivo();
}

campo.addEventListener("input", desenharResultados);
campo.addEventListener("focus", desenharResultados);
campo.addEventListener("blur", fechar);

campo.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    if (!resultados.length) return;
    e.preventDefault();
    const passo = e.key === "ArrowDown" ? 1 : -1;
    ativo = (ativo + passo + resultados.length) % resultados.length;
    marcarAtivo();
  } else if (e.key === "Enter") {
    if (resultados[ativo]) abrir(resultados[ativo].id);
  } else if (e.key === "Escape") {
    campo.value = "";
    fechar();
  }
});

// mousedown (e não click) porque o blur do campo fecharia a lista antes do clique chegar
lista.addEventListener("mousedown", (e) => {
  const li = e.target.closest("li[data-id]");
  if (li) { e.preventDefault(); abrir(li.dataset.id); }
});

// Atalhos globais: "/" ou Ctrl+K focam a busca de qualquer lugar da página
document.addEventListener("keydown", (e) => {
  const digitando = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  const atalho = (e.key === "/" && !digitando) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k");
  if (atalho) { e.preventDefault(); campo.focus(); campo.select(); }
});

// ==================================================================
// CARDS DE DESTAQUE
// ==================================================================
function htmlCard(d) {
  const lado = d.win >= 50 ? "bom" : "ruim";  // verde se ganha mais do que perde
  return `
    <a class="card" href="campeao.html?id=${encodeURIComponent(d.id)}" data-id="${esc(d.id)}">
      <span class="card__fundo" style="background-image:url('${d.splash}')"></span>
      <div class="card__topo">
        <img class="card__icone" src="${d.icone}" alt="" width="56" height="56" loading="lazy">
        <div><h3>${esc(d.nome)}</h3><span class="card__classe">${nomeClasses(d.classes)}</span></div>
      </div>
      <div class="win"><span>Win</span><strong class="${lado}">${pct(d.win)}</strong></div>
      <div class="barra"><i class="${lado}" style="--v:${Math.min(d.win, 100)}%"></i></div>
      <div class="mini">
        <span>Pick <b>${pct(d.pick)}</b></span>
        <span>Ban <b class="ban">${pct(d.ban)}</b></span>
      </div>
    </a>`;
}

function desenharCards() {
  const ordenados = [...destaques].sort((a, b) => b[ordem] - a[ordem]);
  grid.classList.remove("pronto");
  grid.innerHTML = ordenados.map(htmlCard).join("");
  // Dois frames de espera: o navegador precisa pintar as barras vazias primeiro,
  // senão a animação de encher não acontece
  requestAnimationFrame(() => requestAnimationFrame(() => grid.classList.add("pronto")));
}

// Hero: mostra a arte do campeão mais jogado
function desenharHero(exemplo) {
  const top = [...destaques].sort((a, b) => b.pick - a.pick)[0];
  if (!top) return;
  const arte = $("#hero-arte");
  arte.href = "campeao.html?id=" + encodeURIComponent(top.id);
  arte.querySelector("img").src = top.splash;
  $("#hero-legenda").textContent = `${top.nome}, ${pct(top.win)} de vitórias${exemplo ? " (exemplo)" : ""}`;
  arte.hidden = false;
}

// ==================================================================
// ORDENAR COM ANIMAÇÃO (técnica "FLIP")
// 1) anota onde cada card está  2) reordena o HTML
// 3) vê onde cada card foi parar  4) anima do lugar antigo pro novo
// ==================================================================
const posicoes = () => new Map([...grid.children].map((el) => [el.dataset.id, el.getBoundingClientRect()]));

function ordenar(nova) {
  if (nova === ordem) return;
  ordem = nova;
  document.querySelectorAll(".abas button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.ordem === nova));

  const antes = posicoes();
  [...destaques].sort((a, b) => b[nova] - a[nova]).forEach((d) => {
    grid.append(grid.querySelector(`[data-id="${CSS.escape(d.id)}"]`));
  });
  if (reduzMovimento) return;

  const depois = posicoes();
  grid.querySelectorAll(".card").forEach((el) => {
    const a = antes.get(el.dataset.id), n = depois.get(el.dataset.id);
    const dx = a.left - n.left, dy = a.top - n.top;
    if (dx || dy) {
      el.animate(
        [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
        { duration: 450, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" }
      );
    }
  });
}
document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => ordenar(b.dataset.ordem)));

// ==================================================================
// CARREGAMENTO DOS DADOS
// ==================================================================
async function carregarLista() {
  try {
    const r = await fetch("/api/campeoes");
    if (!r.ok) throw new Error("status " + r.status);
    campeoes = await r.json();
    if (document.activeElement === campo) desenharResultados();  // atualiza se já estava digitando
  } catch (erro) {
    console.error("Lista de campeões:", erro);
  }
}

async function carregarDestaques() {
  // Enquanto espera, mostra 9 cards vazios (esqueleto)
  grid.classList.remove("pronto");
  grid.innerHTML = '<div class="card card--esqueleto" aria-hidden="true"></div>'.repeat(9);
  try {
    const r = await fetch("/api/destaques");
    if (!r.ok) throw new Error("status " + r.status);
    const dados = await r.json();
    destaques = dados.campeoes;

    // Diz de onde vêm os números, pra ninguém confundir exemplo com dado real
    $("#fonte").textContent = dados.exemplo
      ? "Números de exemplo. Os reais aparecem quando o coletor de partidas estiver rodando."
      : `Baseado em ${dados.partidas.toLocaleString("pt-BR")} partidas ranqueadas` +
        (dados.atualizado ? `, atualizado em ${new Date(dados.atualizado).toLocaleDateString("pt-BR")}.` : ".");

    desenharCards();
    desenharHero(dados.exemplo);
  } catch (erro) {
    console.error("Destaques:", erro);
    grid.innerHTML = `<div class="erro"><p>Não foi possível carregar os campeões. Confere se o servidor está rodando.</p>
      <button type="button" id="tentar">Tentar de novo</button></div>`;
    $("#tentar").addEventListener("click", carregarDestaques);
  }
}

carregarLista();
carregarDestaques();