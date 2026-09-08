"use strict";

const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const readable = value => value === null || value === undefined || value === "" ? "Not specified" : typeof value === "object" ? JSON.stringify(value) : String(value);
const list = value => Array.isArray(value) ? value : value == null ? [] : [value];
function pair(dl, label, value) { dl.append(el("dt", label), el("dd", readable(value))); }
function sourceEvidence(input) {
  const section = el("div", undefined, "source-item");
  section.append(el("p", `${input.id} · ${input.company} · ${input.metric}`));
  const dl = el("dl", undefined, "evidence-grid");
  pair(dl, "Package", input.source_package);
  pair(dl, "Saved fact", input.fact_id);
  if (input.record_type) pair(dl, "Record type", input.record_type);
  if (input.note) pair(dl, "Note", input.note);
  pair(dl, "Locator", list(input.locators).map(readable).join("; "));
  section.append(dl);
  const links = el("ul");
  for (const url of list(input.source_urls)) {
    const item = el("li");
    if (typeof url === "string" && /^https?:\/\//i.test(url)) {
      const link = el("a", url); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; item.append(link);
    } else item.textContent = readable(url);
    links.append(item);
  }
  if (!links.children.length) links.append(el("li", "No source URL recorded."));
  section.append(links);
  return section;
}
function observationTable(rows, cleaned, inputs) {
  const wrap = el("div", undefined, "table-wrap"), table = el("table");
  table.append(el("caption", cleaned ? "Output observations · inspect each formula and its inputs below" : "Input observations · saved extracted values, not raw document pages"));
  const head = el("thead"), headings = el("tr");
  for (const title of ["Company / metric", "Value", "Units", "Period", "Business scope"]) headings.append(el("th", title));
  headings.querySelectorAll("th").forEach(th => th.scope = "col");
  head.append(headings); table.append(head);
  for (const row of rows) {
    const body = el("tbody"), tr = el("tr");
    const metric = el("td", row.company, "metric"); metric.append(el("span", row.metric, "subvalue"), el("span", row.id, "row-label"));
    const operator = row.operator && row.operator !== "=" ? `${row.operator} ` : "";
    const value = el("td", row.value == null ? "Not disclosed" : `${operator}${typeof row.value === "number" ? row.value.toLocaleString("en-US", {maximumFractionDigits: 8}) : row.value}`, "value");
    if (cleaned) value.append(el("span", readable(row.status), "subvalue"));
    const period = el("td", readable(row.period), "period");
    period.append(el("span", `${readable(row.start_date)} → ${readable(row.end_date)}`, "subvalue"), el("span", readable(row.duration), "subvalue"));
    tr.append(metric, value, el("td", readable(row.units)), period, el("td", readable(row.scope), "scope"));
    const evidenceRow = el("tr", undefined, "evidence-row"), evidenceCell = el("td"), details = el("details"); evidenceCell.colSpan = 5;
    details.append(el("summary", cleaned ? "Evidence & transformation" : "Source evidence"));
    const dl = el("dl", undefined, "evidence-grid");
    pair(dl, "Operator", row.operator || "=");
    if (cleaned) { pair(dl, "Transformation", row.transformation); pair(dl, "Comparison group", row.comparison_group); pair(dl, "Input IDs", list(row.input_ids).join(", ")); }
    details.append(dl);
    const evidence = cleaned ? list(row.input_ids).map(id => inputs.get(id)).filter(Boolean) : [row];
    for (const input of evidence) details.append(sourceEvidence(input));
    if (!evidence.length) details.append(el("p", "No linked input observation; inspect the exception and method notes."));
    evidenceCell.append(details); evidenceRow.append(evidenceCell); body.append(tr, evidenceRow); table.append(body);
  }
  wrap.append(table); return wrap;
}
function render(data) {
  const inputs = new Map(data.inputs.map(row => [row.id, row]));
  const outputs = new Map(data.outputs.map(row => [row.id, row]));
  const exceptions = new Map(data.exceptions.map(row => [row.id, row]));
  const cases = document.getElementById("cases"), filters = document.getElementById("case-filters");
  if (data.meta.cutoff) document.getElementById("cutoff").textContent = `Saved research cutoff: ${readable(data.meta.cutoff)}`;
  document.getElementById("dataset-limitation").textContent = data.meta.limitation || "";
  const choices = [{id: "all", title: "All cases"}, ...data.cases];
  const selected = choices.some(item => item.id === location.hash.slice(1)) ? location.hash.slice(1) : "all";
  function select(id) {
    filters.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.case === id)));
    cases.querySelectorAll(".case").forEach(section => section.hidden = id !== "all" && section.id !== id);
  }
  for (const item of choices) {
    const button = el("button", item.title); button.type = "button"; button.dataset.case = item.id; button.setAttribute("aria-controls", "cases");
    button.addEventListener("click", () => { select(item.id); history.replaceState(null, "", `#${item.id}`); }); filters.append(button);
  }
  data.cases.forEach((item, index) => {
    const section = el("article", undefined, "case"); section.id = item.id;
    section.append(el("p", `CASE ${String(index + 1).padStart(2, "0")}`, "case-number"), el("h3", item.title));
    const context = el("dl", undefined, "case-context"); pair(context, "Problem", item.problem); pair(context, "Rule", item.rule); pair(context, "Limit", item.limitation); section.append(context);
    section.append(el("h4", "Before · saved observations"), observationTable(item.input_ids.map(id => inputs.get(id)).filter(Boolean), false, inputs));
    section.append(el("h4", "After · prepared data"), observationTable(item.output_ids.map(id => outputs.get(id)).filter(Boolean), true, inputs));
    const notes = el("aside", undefined, "exceptions"); notes.append(el("h4", "Exceptions & decisions"));
    const ul = el("ul");
    for (const exception of item.exception_ids.map(id => exceptions.get(id)).filter(Boolean)) {
      const li = el("li"); li.append(el("p", exception.issue), el("p", exception.action), el("p", `${exception.resolved ? "Resolved" : "Unresolved"} · ${exception.id} · affected: ${list(exception.affected_ids).join(", ")}`, "status")); ul.append(li);
    }
    notes.append(ul); section.append(notes); cases.append(section);
  });
  for (const item of data.dictionary) pair(document.getElementById("dictionary"), item.field, item.definition);
  select(selected); document.getElementById("load-status").textContent = "";
}
fetch("data.json").then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }).then(render).catch(() => {
  document.getElementById("load-status").textContent = "The saved dataset could not be loaded. Serve this folder over HTTP, or use the downloadable files below.";
});
