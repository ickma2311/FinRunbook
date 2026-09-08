"use strict";
(() => {
  const tabs = [...document.querySelectorAll(".question-tab")];
  const panels = [...document.querySelectorAll(".result-panel")];
  const company = document.getElementById("prompt-company"), cutoff = document.getElementById("prompt-cutoff"), output = document.getElementById("prompt-output"), status = document.getElementById("copy-status");
  const defaults = {"earnings-update":{company:"Lululemon (LULU)",cutoff:"2026-09-04"},"data-cleaning":{company:"Lululemon, Amazon, Microsoft and Alphabet",cutoff:"2026-09-04"},"company-comparison":{company:"Amazon (AWS), Microsoft (Azure) and Alphabet (Google Cloud)",cutoff:"2026-09-03"}};
  let active = "earnings-update", customizedCompany = false, customizedCutoff = false;
  function buildPrompt() {
    const companies = company.value.trim() || "[company or companies]", date = cutoff.value || "[evidence cutoff YYYY-MM-DD]";
    const tasks = {
      "earnings-update": `Use FinRunbook to review earnings for ${companies}, using evidence available through ${date}. Identify the latest reported quarter by that cutoff and compare it with the prior-year quarter and longer business trend. Separate company-reported results, management guidance and analyst calculations. Show material one-offs separately with formulas; do not relabel them as company-adjusted earnings. Identify what changed and questions left unresolved.`,
      "data-cleaning": `Use FinRunbook to prepare financial data for ${companies}, using the source package I provide and evidence available through ${date}. If the source package is missing, ask me for it. Preserve original values, units, signs, exact dates, durations, business scopes and source locators. Normalize units explicitly. Derive quarters from year-to-date figures only for compatible cumulative measures, then reconcile to reported quarters. Preserve threshold operators, leave missing values blank and keep incompatible comparisons separate. Return input and cleaned CSV tables, formulas, a metric dictionary and an exception log.`,
      "company-comparison": `Use FinRunbook to compare ${companies}, using evidence available through ${date} and the latest five complete fiscal years then available. Compare business models, growth, segment economics and investment requirements to identify questions for deeper research. Preserve fiscal dates and product scope; distinguish parent from segment spending. Keep revenue thresholds as bounds and missing margins unknown. Do not rank incompatible disclosures as like-for-like observations.`
    };
    output.value = tasks[active] + "\n\nUse primary sources where available. Retain source references and calculations, disclose material uncertainty and unresolved conflicts, produce an English interactive HTML financial report with downloadable data, and run FinRunbook validation with its limitations visible. This is research, not a trade recommendation.";
    status.textContent = "Paste into Codex, Claude Code or OpenCode.";
  }
  function activate(id, focus = false) {
    if (!defaults[id]) return;
    active = id;
    tabs.forEach(tab => {const selected = tab.dataset.panel === id; tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1; if (selected && focus) tab.focus();});
    panels.forEach(panel => {panel.hidden = panel.id !== id;});
    if (!customizedCompany) company.value = defaults[id].company;
    if (!customizedCutoff) cutoff.value = defaults[id].cutoff;
    buildPrompt();
  }
  document.documentElement.classList.add("enhanced");
  document.querySelector(".question-tabs").setAttribute("role", "tablist");
  tabs.forEach((tab, index) => {
    tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", tab.dataset.panel);
    const panel = document.getElementById(tab.dataset.panel); panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", tab.id); panel.tabIndex = 0;
    tab.addEventListener("click", event => {event.preventDefault(); activate(tab.dataset.panel); history.replaceState(null, "", tab.getAttribute("href"));});
    tab.addEventListener("keydown", event => {
      if (event.key === " ") {event.preventDefault(); tab.click(); return;}
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {event.preventDefault(); activate(tabs[next].dataset.panel, true); history.replaceState(null, "", tabs[next].getAttribute("href"));}
    });
  });
  company.addEventListener("input", () => {customizedCompany = true; buildPrompt();});
  cutoff.addEventListener("input", () => {customizedCutoff = true; buildPrompt();});
  document.getElementById("prompt-form").addEventListener("submit", event => event.preventDefault());
  document.getElementById("copy-prompt").addEventListener("click", async () => {
    try {if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable"); await navigator.clipboard.writeText(output.value); status.textContent = "Copied. Paste into your agent with FinRunbook installed.";}
    catch {output.focus(); output.select(); status.textContent = "Prompt selected. Press ⌘C or Ctrl+C to copy, then paste into your agent.";}
  });
  window.addEventListener("hashchange", () => {const id = location.hash.slice(1); if (defaults[id]) activate(id);});
  activate(defaults[location.hash.slice(1)] ? location.hash.slice(1) : active);
})();
