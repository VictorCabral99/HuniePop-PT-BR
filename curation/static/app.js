const FLAG_HELP = {
  vazio: ["bad", "Sem tradução. No jogo esta fala continua em inglês."],
  igual: ["bad", "A tradução está igual ao inglês."],
  eu: ["bad", "Soa como português de Portugal (tu, contigo, estás a…). Reescreva com você."],
  chave: ["bad", "Rótulo interno (success, morning…). Se o jogo compara essa palavra, deixe em inglês."],
  pausa: ["warn", "O inglês marca uma pausa ····· que sumiu na tradução."],
  longo: ["warn", "Ficou bem mais longa. Pode cortar no botão ou na caixa de diálogo."],
  curto: ["warn", "Ficou bem mais curta. Confira se não caiu um pedaço."],
  reescrito: ["warn", "Ao gravar o arquivo do jogo, o script troca algumas palavras. Confira a prévia sem acento."],
  nome: ["ok", "Nome de personagem. Vazio mantém o inglês, que é o certo."],
  mantido: ["ok", "Mantido em inglês de propósito."],
  "chave-ok": ["ok", "Rótulo interno ainda em inglês. É o mais seguro se a tela não mostra essa palavra."],
};

const ROLE_LABEL = {
  fala: "Fala",
  jogador: "Jogador",
  jogadora: "Jogadora",
  escolha: "Escolha",
  rotulo: "Rótulo",
};

const GIRLS = ["Kyu", "Aiko", "Audrey", "Beli", "Celeste", "Jessie", "Kyanna", "Lola", "Momo", "Nikki", "Tiffany", "Venus"];
const STORY = [
  "GameOpeningPart1", "GameOpeningPart2", "GameOpeningPart3", "GameOpeningPart4",
  "GirlIntroInjection1", "GirlIntroInjection2", "Greeting", "Valediction",
  "AskDate", "DateGreeting", "DateValediction", "GivenGift", "GivenDateGift",
  "GivenFood", "GivenDrink", "MatchToken", "QuestionIntro", "QuestionCorrect",
  "QuestionIncorrect", "QuestionBadChoice", "QuizIntro", "QuizCorrect", "QuizIncorrect",
  "InventoryFull", "IsTooHungry", "QueryIntro", "QueryDuplicate", "GameEnding", "SexualSounds",
];

const FILTERS = [
  ["alerta", "Alertas"],
  ["aviso", "Avisos"],
  ["eu", "Tom de Portugal"],
  ["vazio", "Sem tradução"],
  ["igual", "Igual ao inglês"],
  ["pausa", "Pausa"],
  ["chave", "Rótulo interno"],
  ["reescrito", "Reescrito pelo script"],
  ["ok", "Aprovadas"],
  ["fix", "Para corrigir"],
  ["tudo", "Todas"],
];

const CATS = [
  ["", "Tudo"],
  ["dialogue", "Diálogo"],
  ["ui", "Interface"],
  ["item", "Itens"],
  ["message", "Mensagens"],
  ["other", "Outros"],
];

const state = {
  strings: [],
  byId: new Map(),
  scenes: [],
  scene: null,
  sceneId: "GameOpeningPart1",
  mode: "jogo",
  gender: "jogador",
  showEn: false,
  showGame: false,
  selected: null,
  query: "",
  sceneQuery: "",
  flag: "alerta",
  cat: "",
  limit: 80,
  dirty: false,
  previewTimer: 0,
};

const $ = (id) => document.getElementById(id);

function problemFlags(flags) {
  return (flags || []).filter((flag) => ["vazio", "igual", "eu", "chave"].includes(flag));
}

function warningFlags(flags) {
  return (flags || []).filter((flag) => ["pausa", "longo", "curto", "reescrito"].includes(flag));
}

function needsReview(item) {
  return item && item.status !== "ok" && problemFlags(item.flags).length > 0;
}

function fillText(el, text) {
  el.replaceChildren();
  const src = text || "";
  const re = /(\u00b7{2,}|\.{3,}|…+)/g;
  let last = 0;
  let match;
  while ((match = re.exec(src))) {
    if (match.index > last) el.append(src.slice(last, match.index));
    const span = document.createElement("span");
    span.className = "pause";
    span.textContent = " ··· ";
    el.append(span);
    last = match.index + match[0].length;
  }
  if (last < src.length) el.append(src.slice(last));
}

function fmtWhen(iso) {
  if (!iso) return "";
  const when = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
  return `${when} (Brasília)`;
}

function showError(message) {
  const el = $("error");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "não deu para falar com a curadoria");
  return data;
}

function recomputeDerived() {
  for (const scene of state.scenes) {
    scene.alerts = (scene.ids || []).filter((id) => needsReview(state.byId.get(id))).length;
  }
  const stats = {
    total: state.strings.length,
    applied: state.strings.filter((item) => (item.pt || "").trim() && item.pt !== item.en).length,
    problems: state.strings.filter(needsReview).length,
    approved: state.strings.filter((item) => item.status === "ok").length,
  };
  renderStats(stats);
  renderScenes();
}

function renderStats(stats) {
  const box = $("stats");
  box.replaceChildren();
  const bits = [
    ["", stats.total.toLocaleString("pt-BR"), "frases"],
    ["", stats.applied.toLocaleString("pt-BR"), "entram no jogo"],
    ["bad", stats.problems.toLocaleString("pt-BR"), "alertas"],
    ["ok", stats.approved.toLocaleString("pt-BR"), "aprovadas"],
  ];
  for (const [kind, strong, label] of bits) {
    const pill = document.createElement("span");
    pill.className = `pill ${kind}`.trim();
    const b = document.createElement("strong");
    b.textContent = strong;
    pill.append(b, ` ${label}`);
    box.append(pill);
  }
}

function sceneLabel(scene) {
  let name = scene.id;
  if (scene.girl && name.toLowerCase().includes(scene.girl.toLowerCase())) {
    name = name.replace(new RegExp(scene.girl, "ig"), "").replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, "");
  }
  return name || scene.id;
}

function sortStory(list) {
  return [...list].sort((a, b) => {
    const ia = STORY.indexOf(a.id);
    const ib = STORY.indexOf(b.id);
    if (ia === -1 && ib === -1) return a.id.localeCompare(b.id);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
}

function sortNumbered(list) {
  return [...list].sort((a, b) => {
    const na = Number((a.id.match(/(\d+)$/) || [])[1] || 0);
    const nb = Number((b.id.match(/(\d+)$/) || [])[1] || 0);
    return na - nb || a.id.localeCompare(b.id);
  });
}

function matchesScene(scene) {
  const q = state.sceneQuery.trim().toLowerCase();
  if (!q) return true;
  return [scene.id, scene.girl, scene.kind, sceneLabel(scene)].join(" ").toLowerCase().includes(q);
}

function appendSceneButtons(parent, scenes) {
  for (const scene of scenes) {
    if (!matchesScene(scene)) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `scene-btn${scene.id === state.sceneId ? " is-on" : ""}`;
    button.dataset.scene = scene.id;
    const label = document.createElement("span");
    label.textContent = sceneLabel(scene);
    button.append(label);
    if (scene.alerts) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = String(scene.alerts);
      button.append(badge);
    }
    button.addEventListener("click", () => openScene(scene.id));
    parent.append(button);
  }
}

function detailsBlock(title, count, alerts, open) {
  const details = document.createElement("details");
  details.className = "group";
  if (open) details.open = true;
  const summary = document.createElement("summary");
  const name = document.createElement("span");
  name.textContent = title;
  const meta = document.createElement("span");
  meta.textContent = alerts ? `${count} · ${alerts} alertas` : String(count);
  summary.append(name, meta);
  details.append(summary);
  return details;
}

function renderScenes() {
  const root = $("scene-list");
  root.replaceChildren();
  const visible = state.scenes.filter(matchesScene);
  const historia = sortStory(state.scenes.filter((scene) => !scene.girl));
  const hist = detailsBlock("História", historia.length, historia.reduce((sum, scene) => sum + scene.alerts, 0), !state.sceneQuery || historia.some(matchesScene));
  appendSceneButtons(hist, historia);
  if (hist.querySelector(".scene-btn")) root.append(hist);

  for (const girl of GIRLS) {
    const mine = state.scenes.filter((scene) => scene.girl === girl);
    if (!mine.length) continue;
    const main = mine.filter((scene) => !/question|quiz/i.test(scene.id));
    const questions = sortNumbered(mine.filter((scene) => /question/i.test(scene.id)));
    const quizzes = sortNumbered(mine.filter((scene) => /quiz/i.test(scene.id)));
    const open = Boolean(state.sceneQuery) ? mine.some(matchesScene) : state.scene && state.scene.girl === girl;
    const block = detailsBlock(girl, mine.length, mine.reduce((sum, scene) => sum + scene.alerts, 0), open);
    appendSceneButtons(block, main);
    for (const [label, list] of [["Perguntas", questions], ["Quiz", quizzes]]) {
      if (!list.some(matchesScene)) continue;
      const nested = detailsBlock(label, list.length, list.reduce((sum, scene) => sum + scene.alerts, 0), Boolean(state.sceneQuery));
      nested.classList.add("nested");
      appendSceneButtons(nested, list);
      block.append(nested);
    }
    if (block.querySelector(".scene-btn")) root.append(block);
  }
  if (!root.childElementCount) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = visible.length ? "" : "Nenhuma cena com esse nome.";
    root.append(empty);
  }
}

function lineText(line) {
  if (state.showGame) return line.game || line.pt || "";
  return line.pt || "";
}

function renderLines() {
  const root = $("lines");
  root.replaceChildren();
  const scene = state.scene;
  if (!scene) return;
  $("scene-kicker").textContent = scene.girl ? scene.girl : "História";
  $("scene-title").textContent = sceneLabel(scene);
  const hidden = scene.lines.filter((line) => {
    if (state.gender === "jogador" && line.role === "jogadora") return true;
    if (state.gender === "jogadora" && line.role === "jogador") return true;
    return false;
  }).length;
  $("scene-hint").textContent = hidden
    ? `${hidden} ${hidden === 1 ? "fala da outra variante está oculta" : "falas da outra variante estão ocultas"}. A fonte do jogo não tem acento.`
    : "A fonte do jogo não tem acento: o arquivo instalado troca não por nao.";

  for (const line of scene.lines) {
    if (state.gender === "jogador" && line.role === "jogadora") continue;
    if (state.gender === "jogadora" && line.role === "jogador") continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `bubble ${line.role}${line.id === state.selected ? " is-on" : ""}`;
    button.dataset.id = line.id;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = ROLE_LABEL[line.role] || "Fala";
    if (needsReview(line)) {
      const dot = document.createElement("span");
      dot.className = "dot bad";
      meta.append(dot);
    } else if (line.status === "ok") {
      const dot = document.createElement("span");
      dot.className = "dot ok";
      meta.append(dot);
    }
    const spoken = document.createElement("p");
    const text = lineText(line);
    fillText(spoken, text || "— sem tradução, fica em inglês —");
    button.append(meta, spoken);
    if (state.showEn) {
      const en = document.createElement("p");
      en.className = "en";
      fillText(en, line.en);
      button.append(en);
    }
    button.addEventListener("click", () => selectLine(line.id));
    root.append(button);
  }
}

function passesFilter(item) {
  if (state.cat && item.cat !== state.cat) return false;
  if (state.flag === "alerta" && !needsReview(item)) return false;
  if (state.flag === "aviso" && !warningFlags(item.flags).length) return false;
  if (state.flag === "ok" && item.status !== "ok") return false;
  if (state.flag === "fix" && item.status !== "fix") return false;
  if (["eu", "vazio", "igual", "pausa", "chave", "reescrito"].includes(state.flag) && !(item.flags || []).includes(state.flag)) return false;
  const q = state.query.trim().toLowerCase();
  if (!q) return true;
  return [item.en, item.pt, item.game, item.id, ...(item.where || [])].join("\n").toLowerCase().includes(q);
}

function renderFilters() {
  const root = $("filters");
  root.replaceChildren();
  for (const [id, label] of FILTERS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip${state.flag === id ? " is-on" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => {
      state.flag = id;
      state.limit = 80;
      renderFilters();
      renderPhrases();
    });
    root.append(button);
  }
  for (const [id, label] of CATS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip${state.cat === id ? " is-on" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => {
      state.cat = id;
      state.limit = 80;
      renderFilters();
      renderPhrases();
    });
    root.append(button);
  }
}

function clip(text, size = 180) {
  const value = text || "";
  return value.length > size ? `${value.slice(0, size)}…` : value;
}

function renderPhrases() {
  const matched = state.strings.filter(passesFilter);
  $("phrase-count").textContent = `${matched.length.toLocaleString("pt-BR")} frases neste filtro`;
  const root = $("phrase-list");
  root.replaceChildren();
  for (const item of matched.slice(0, state.limit)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `phrase${item.id === state.selected ? " is-on" : ""}`;
    button.dataset.id = item.id;
    const left = document.createElement("div");
    left.className = "col";
    const enLabel = document.createElement("b");
    enLabel.textContent = "Inglês";
    const en = document.createElement("p");
    en.textContent = clip(item.en);
    left.append(enLabel, en);
    const right = document.createElement("div");
    right.className = "col";
    const ptLabel = document.createElement("b");
    ptLabel.textContent = "Tradução";
    const pt = document.createElement("p");
    pt.textContent = clip(item.pt) || "— sem tradução —";
    const sub = document.createElement("p");
    sub.className = "sub";
    const bits = [item.cat, ...(item.where || []).slice(0, 2)];
    if (item.status === "ok") bits.push("aprovada");
    if (item.status === "fix") bits.push("revisar");
    if (problemFlags(item.flags).length) bits.push("alerta");
    sub.textContent = bits.join(" · ");
    right.append(ptLabel, pt, sub);
    button.append(left, right);
    button.addEventListener("click", () => selectLine(item.id, { scroll: false }));
    root.append(button);
  }
  $("phrase-more").hidden = matched.length <= state.limit;
}

function renderFlags(flags) {
  const root = $("ed-flags");
  root.replaceChildren();
  for (const flag of flags || []) {
    const help = FLAG_HELP[flag];
    if (!help) continue;
    const p = document.createElement("p");
    p.className = `flag ${help[0]}`;
    p.textContent = help[1];
    root.append(p);
  }
}

function renderEditor() {
  const item = state.byId.get(state.selected);
  const form = $("editor-form");
  const empty = $("editor-empty");
  if (!item) {
    form.hidden = true;
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  form.hidden = false;
  $("ed-kicker").textContent = `${item.cat} · aparece ${item.n}×`;
  const where = $("ed-where");
  where.replaceChildren();
  for (const sceneId of (item.where || []).slice(0, 8)) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = sceneId;
    button.addEventListener("click", () => openScene(sceneId, item.id));
    where.append(button);
  }
  fillText($("ed-en"), item.en);
  $("pt-input").value = item.pt || "";
  $("note-input").value = item.note || "";
  fillText($("ed-game"), item.game || "");
  renderFlags(item.flags);
  $("ok-btn").textContent = item.status === "ok" ? "Tirar aprovação" : "Aprovar";
  $("fix-btn").textContent = item.status === "fix" ? "Tirar marcação" : "Marcar revisão";
  const when = fmtWhen(item.updated);
  $("save-state").textContent = when ? `salvo ${when}` : "";
  state.dirty = false;
}

function remember(item) {
  const previous = state.byId.get(item.id) || {};
  const next = { ...previous, ...item, where: item.where || previous.where || [] };
  state.byId.set(item.id, next);
  const index = state.strings.findIndex((row) => row.id === item.id);
  if (index >= 0) state.strings[index] = next;
  if (state.scene) {
    state.scene.lines = state.scene.lines.map((line) => (line.id === item.id ? { ...line, ...next } : line));
  }
  return next;
}

async function selectLine(id, options = {}) {
  if (!id) return;
  if (state.dirty && state.selected && state.selected !== id) {
    const saved = await save();
    if (!saved) return;
  }
  state.selected = id;
  renderEditor();
  document.querySelectorAll(".bubble, .phrase").forEach((node) => {
    node.classList.toggle("is-on", node.dataset.id === id);
  });
  if (options.scroll !== false) {
    const bubble = document.querySelector(`.bubble[data-id="${CSS.escape(id)}"]`);
    if (bubble) bubble.scrollIntoView({ block: "nearest" });
  }
}

async function openScene(id, lineId) {
  showError("");
  const scene = await api(`/api/scene?id=${encodeURIComponent(id)}`);
  state.scene = scene;
  state.sceneId = id;
  state.mode = "jogo";
  applyMode();
  for (const line of scene.lines) {
    if (!line.id) continue;
    const known = state.byId.get(line.id);
    if (known) Object.assign(line, { ...known, role: line.role, idx: line.idx });
  }
  renderScenes();
  renderLines();
  const pick = lineId || scene.lines.find((line) => line.role !== "rotulo" && line.id)?.id || scene.lines.find((line) => line.id)?.id;
  if (pick) await selectLine(pick);
  history.replaceState(null, "", `#jogo/${id}`);
}

function applyMode() {
  const jogo = state.mode === "jogo";
  $("mode-jogo").classList.toggle("is-on", jogo);
  $("mode-frases").classList.toggle("is-on", !jogo);
  $("desk").classList.toggle("is-phrases", !jogo);
  $("scene-pane").hidden = !jogo;
  $("lines").hidden = !jogo;
  $("stage-bar").hidden = !jogo;
  $("scene-hint").hidden = !jogo;
  $("phrase-pane").hidden = jogo;
  if (!jogo) {
    renderFilters();
    renderPhrases();
    history.replaceState(null, "", "#frases");
  }
}

async function save(extra = {}) {
  const item = state.byId.get(state.selected);
  if (!item) return false;
  const pt = extra.pt !== undefined ? extra.pt : $("pt-input").value;
  const note = extra.note !== undefined ? extra.note : $("note-input").value;
  let status = extra.status !== undefined ? extra.status : item.status || "";
  clearTimeout(state.previewTimer);
  $("save-btn").disabled = true;
  try {
    const saved = await api("/api/line", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: item.id, pt, status, note }),
      keepalive: Boolean(extra.keepalive),
    });
    remember(saved);
    state.dirty = false;
    recomputeDerived();
    if (state.scene) renderLines();
    if (state.mode === "frases") renderPhrases();
    renderEditor();
    $("save-state").textContent = `salvo ${fmtWhen(saved.updated)}`;
    showError("");
    return true;
  } catch (error) {
    showError(error.message);
    return false;
  } finally {
    $("save-btn").disabled = false;
  }
}

function adoptCatalog(catalog, options = {}) {
  state.strings = catalog.strings;
  state.byId = new Map(catalog.strings.map((item) => [item.id, item]));
  state.scenes = catalog.scenes;
  renderStats(catalog.stats);
  if (!options.keepScene) return;
  if (state.scene) {
    state.scene.lines = state.scene.lines.map((line) => {
      const fresh = state.byId.get(line.id);
      return fresh ? { ...line, ...fresh, role: line.role, idx: line.idx } : line;
    });
    const sceneMeta = state.scenes.find((scene) => scene.id === state.sceneId);
    if (sceneMeta) state.scene.alerts = sceneMeta.alerts;
  }
  renderScenes();
}

async function previewSoon() {
  clearTimeout(state.previewTimer);
  state.previewTimer = setTimeout(async () => {
    const item = state.byId.get(state.selected);
    if (!item) return;
    try {
      const preview = await api("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, pt: $("pt-input").value }),
      });
      fillText($("ed-game"), preview.game || "");
      renderFlags(preview.flags);
      const bubble = document.querySelector(`.bubble[data-id="${CSS.escape(item.id)}"] p`);
      if (bubble && state.mode === "jogo") {
        const shown = state.showGame ? preview.game : $("pt-input").value;
        fillText(bubble, shown || "— sem tradução, fica em inglês —");
      }
    } catch (error) {
      showError(error.message);
    }
  }, 180);
}

function nextAlert() {
  if (state.mode === "frases") {
    const matched = state.strings.filter(passesFilter);
    const index = matched.findIndex((item) => item.id === state.selected);
    const next = matched[index + 1] || matched[0];
    if (next) selectLine(next.id, { scroll: false });
    return;
  }
  if (!state.scene) return;
  const lines = state.scene.lines.filter((line) => line.id && !(state.gender === "jogador" && line.role === "jogadora") && !(state.gender === "jogadora" && line.role === "jogador"));
  const index = lines.findIndex((line) => line.id === state.selected);
  const later = lines.slice(index + 1).find(needsReview) || lines.find(needsReview);
  if (later) selectLine(later.id);
}

function bind() {
  $("mode-jogo").addEventListener("click", () => {
    state.mode = "jogo";
    applyMode();
    if (state.sceneId) openScene(state.sceneId, state.selected);
  });
  $("mode-frases").addEventListener("click", () => {
    state.mode = "frases";
    applyMode();
  });
  for (const id of ["gender-jogador", "gender-jogadora"]) {
    $(id).addEventListener("click", () => {
      state.gender = $(id).dataset.gender;
      $("gender-jogador").classList.toggle("is-on", state.gender === "jogador");
      $("gender-jogadora").classList.toggle("is-on", state.gender === "jogadora");
      renderLines();
    });
  }
  $("show-en").addEventListener("change", () => {
    state.showEn = $("show-en").checked;
    renderLines();
  });
  $("show-game").addEventListener("change", () => {
    state.showGame = $("show-game").checked;
    renderLines();
  });
  $("scene-search").addEventListener("input", () => {
    state.sceneQuery = $("scene-search").value;
    renderScenes();
  });
  $("phrase-search").addEventListener("input", () => {
    state.query = $("phrase-search").value;
    state.limit = 80;
    renderPhrases();
  });
  $("phrase-more").addEventListener("click", () => {
    state.limit += 80;
    renderPhrases();
  });
  $("editor-form").addEventListener("submit", (event) => {
    event.preventDefault();
    save();
  });
  $("pt-input").addEventListener("input", () => {
    state.dirty = true;
    $("save-state").textContent = "alteração ainda não salva";
    previewSoon();
  });
  $("note-input").addEventListener("input", () => {
    state.dirty = true;
    $("save-state").textContent = "alteração ainda não salva";
  });
  $("ok-btn").addEventListener("click", () => {
    const item = state.byId.get(state.selected);
    save({ status: item && item.status === "ok" ? "" : "ok" });
  });
  $("fix-btn").addEventListener("click", () => {
    const item = state.byId.get(state.selected);
    save({ status: item && item.status === "fix" ? "" : "fix" });
  });
  $("keep-btn").addEventListener("click", () => {
    const item = state.byId.get(state.selected);
    if (!item) return;
    $("pt-input").value = item.en;
    save({ pt: item.en });
  });
  $("next-alert").addEventListener("click", () => nextAlert());
  $("apply-btn").addEventListener("click", async () => {
    if (state.dirty) {
      const saved = await save();
      if (!saved) return;
    }
    try {
      const result = await api("/api/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      adoptCatalog({ strings: state.strings, scenes: state.scenes, stats: result.stats }, { keepScene: true });
      $("save-state").textContent = `arquivo do jogo gravado (${result.rows.toLocaleString("pt-BR")} frases)`;
      showError("");
    } catch (error) {
      showError(error.message);
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      save();
    }
  });
  window.addEventListener("beforeunload", () => {
    if (!state.dirty || !state.selected) return;
    const item = state.byId.get(state.selected);
    if (!item) return;
    navigator.sendBeacon("/api/line", new Blob([JSON.stringify({
      id: item.id,
      pt: $("pt-input").value,
      status: item.status || "",
      note: $("note-input").value,
    })], { type: "application/json" }));
  });
}

async function boot() {
  bind();
  try {
    const catalog = await api("/api/catalog");
    adoptCatalog(catalog);
    renderScenes();
    const hash = location.hash || "";
    const sceneMatch = hash.match(/^#jogo\/([A-Za-z0-9_]+)/);
    if (hash.startsWith("#frases")) {
      state.mode = "frases";
      applyMode();
      return;
    }
    await openScene(sceneMatch ? sceneMatch[1] : "GameOpeningPart1");
  } catch (error) {
    showError(error.message);
    $("scene-title").textContent = "Não abriu";
  }
}

boot();
