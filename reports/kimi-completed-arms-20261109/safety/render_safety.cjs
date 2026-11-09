"use strict";

// Run with Node.js and sharp installed. No model, Docker, or network access.
const fs = require("node:fs");
const path = require("node:path");
const sharp = require("sharp");

const ROOT = __dirname;
const ARMS = {
  monitor: { name: "Monitor only", color: "#334155", mark: "circle" },
  plain_v3: { name: "Plain v3 tests", color: "#087d6b", mark: "square" },
  monitor_plain_v3: { name: "Monitor + plain v3", color: "#2676ac", mark: "triangle" },
  property: { name: "Property tests", color: "#b35b12", mark: "diamond" },
  monitor_property: { name: "Monitor + property", color: "#663c96", mark: "cross" },
  plain_v3_any: { name: "Plain v3 · any fires", color: "#087d6b", mark: "square", any: true },
  property_any: { name: "Property · any fires", color: "#b35b12", mark: "diamond", any: true },
};
const RULES = {
  A: ["A · Unaudited flags ship", "Stops on first audited catch or shipped attack"],
  B: ["B · Flags held back; run continues", "Audited catches do not end the run"],
  C: ["C · Flags held back; audit stops the run", "First audited catch ends the run"],
};
const INK = "#172536";
const MUTED = "#4b5b6c";
const GRID = "#e1e7ed";
const RULE = "#a4b2bf";
const FLOOR = "#5c6674";
const VARIATIONS = Object.keys(RULES);
const TICKS = [0, .25, .5, .75, 1];

const esc = value => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const num = value => Number(value).toFixed(2);
const pct = (value, precision = 0) => `${(100 * value).toFixed(precision)}%`;
const barPct = value => pct(value, value > 0 && value < .001 ? 2 : 1);
const integer = value => new Intl.NumberFormat("en-US").format(value);

function label(x, y, content, { size = 16, fill = INK, anchor = "start", weight = 400 } = {}) {
  return `<text x="${num(x)}" y="${num(y)}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}">${esc(content)}</text>`;
}

function line(x1, y1, x2, y2, color = GRID, width = 1, dash = "") {
  return `<line x1="${num(x1)}" y1="${num(y1)}" x2="${num(x2)}" y2="${num(y2)}" stroke="${color}" stroke-width="${width}"${dash ? ` stroke-dasharray="${dash}"` : ""}/>`;
}

function rect(x, y, w, h, fill, extra = "") {
  return `<rect x="${num(x)}" y="${num(y)}" width="${num(w)}" height="${num(h)}" fill="${fill}" ${extra}/>`;
}

function series(points, arm, width = 2.2) {
  return `<polyline points="${points.map(([x, y]) => `${num(x)},${num(y)}`).join(" ")}" fill="none" stroke="${arm.color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"${arm.any ? ' stroke-dasharray="8 5"' : ""}/>`;
}

function marker(x, y, arm, radius = 4, highlight = false) {
  const color = arm.color;
  const fill = arm.any ? "#fff" : color;
  const style = `fill="${fill}" stroke="${color}" stroke-width="${highlight ? 2.8 : 1.4}"`;
  if (arm.mark === "square") return rect(x - radius, y - radius, 2 * radius, 2 * radius, fill, `stroke="${color}" stroke-width="${highlight ? 2.8 : 1.4}"`);
  if (arm.mark === "triangle") return `<polygon points="${num(x)},${num(y-radius-1)} ${num(x-radius)},${num(y+radius)} ${num(x+radius)},${num(y+radius)}" ${style}/>`;
  if (arm.mark === "diamond") return `<polygon points="${num(x)},${num(y-radius-1)} ${num(x+radius+1)},${num(y)} ${num(x)},${num(y+radius+1)} ${num(x-radius-1)},${num(y)}" ${style}/>`;
  if (arm.mark === "cross") return line(x-radius, y, x+radius, y, color, highlight ? 4 : 2) + line(x, y-radius, x, y+radius, color, highlight ? 4 : 2);
  return `<circle cx="${num(x)}" cy="${num(y)}" r="${radius}" ${style}/>`;
}

function page(width, height, title, subtitle, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title><desc>${esc(subtitle)}</desc><g font-family="Arial, sans-serif">`
    + rect(0, 0, width, height, "#fff")
    + label(35, 48, title, { size: 29, weight: 700 })
    + label(35, 77, subtitle, { size: 16, fill: MUTED })
    + body + "</g></svg>";
}

function legend(ids, x, y, columns = 4, spacing = 370) {
  return ids.map((id, index) => {
    const arm = ARMS[id];
    const left = x + (index % columns) * spacing;
    const top = y + Math.floor(index / columns) * 23;
    return series([[left, top-5], [left+28, top-5]], arm)
      + marker(left+14, top-5, arm, 3.6)
      + label(left+38, top, arm.name, { size: 15 });
  }).join("");
}

function settingsLine(pop, settings) {
  return `${integer(pop.test_tasks)} matched held-out tasks · ${integer(settings.trials)} simulated deployments · ${integer(settings.horizon)} steps · seed ${settings.seed}`;
}

function bars(data, key) {
  const settings = data.settings[key];
  const rows = data[key];
  const floor = rows[0].free_floor;
  const paper = key === "paper_setting";
  const width = 1820;
  const height = 555;
  const top = 154;
  const rowStep = 42;
  const axisY = top + rows.length / 3 * rowStep + 4;
  let body = "";
  for (const [index, id] of VARIATIONS.entries()) {
    const left = 35 + index * 600;
    const x0 = left + 171;
    const xw = 278;
    const sx = v => x0 + xw * v;
    const selected = rows.filter(row => row.variation === id).sort((a, b) => b.safety - a.safety);
    body += label(left, 114, RULES[id][0], { size: 17, weight: 700 });
    body += label(left, 136, RULES[id][1], { size: 13, fill: MUTED });
    for (const t of TICKS) {
      body += line(sx(t), top, sx(t), axisY);
      body += label(sx(t), axisY+20, pct(t), { size: 13, fill: MUTED, anchor: "middle" });
    }
    body += line(x0, axisY, x0+xw, axisY, RULE);
    selected.forEach((row, i) => {
      const arm = ARMS[row.arm];
      const yy = top+19+i*rowStep;
      body += label(left, yy+5, arm.name, { size: 15 });
      if (row.safety > 0) {
        body += rect(x0, yy-9, xw*row.safety, 18, arm.any ? "#fff" : arm.color,
          arm.any ? `stroke="${arm.color}" stroke-width="1.7" stroke-dasharray="5 3"` : "");
      } else {
        body += line(x0, yy-7, x0, yy+7, arm.color, 2);
      }
      body += label(x0+xw+9, yy+4, barPct(row.safety), { size: 14, weight: 700 });
      body += label(x0+xw+66, yy+4, `u=${pct(row.usefulness, 1)}`, { size: 13, fill: MUTED });
      body += label(x0+xw+9, yy+20, `Δ ${(100*row.safety_minus_floor).toFixed(1)} pp`, { size: 11, fill: MUTED });
    });
    if (floor > 0) body += line(sx(floor), top, sx(floor), axisY, FLOOR, 1.4, "4 4");
    body += label(x0+xw/2, axisY+40, "Safety · deployments with no attack shipped", { size: 13, fill: MUTED, anchor: "middle" });
  }
  body += label(35, 520, `${settingsLine(data.population, settings)} · attack rate ${pct(settings.attack_rate)} · review budget ${pct(settings.budget)} (${Math.round(settings.horizon*settings.budget)} audits)`, { size: 15, fill: MUTED });
  body += label(35, 542, `u = honest submissions shipped. Δ = safety minus the no-attack floor (${pct(floor, 1)}). Outlined bars flag any firing test. Other cuts use the honest-training budget quantile.`, { size: 14, fill: MUTED });
  const title = paper ? "Kimi K3 · Deployment safety at a 2% audit budget" : "Kimi K3 · Deployment safety by audit rule";
  return page(width, height, title, "APPS · completed arms only · held-out simulation, not live deployment", body);
}

function axesBox({ x, y, width, height, xTicks, yTicks, sx, sy, xLabel = true, yLabel = true }) {
  let result = "";
  for (const t of xTicks) {
    result += line(sx(t), y, sx(t), y+height);
    if (xLabel) result += label(sx(t), y+height+20, pct(t), { anchor: "middle", fill: MUTED, size: 13 });
  }
  for (const t of yTicks) {
    result += line(x, sy(t), x+width, sy(t));
    if (yLabel) result += label(x-9, sy(t)+5, pct(t), { anchor: "end", fill: MUTED, size: 13 });
  }
  return result + line(x, y, x, y+height, RULE) + line(x, y+height, x+width, y+height, RULE);
}

function frontier(data) {
  const settings = data.settings.frontier;
  const width = 1510;
  const height = 730;
  const top = 147;
  const ph = 398;
  const pw = 598;
  let body = "";
  for (const [index, id] of ["B", "C"].entries()) {
    const x = 91+index*735;
    const sx = u => x+u*pw;
    const sy = s => top+(1-s)*ph;
    body += label(x, 122, RULES[id][0], { size: 18, weight: 700 });
    body += axesBox({x, y: top, width: pw, height: ph, xTicks:TICKS, yTicks:TICKS, sx, sy});
    const floor = data.by_variation.find(row => row.variation === id).free_floor;
    body += line(x, sy(floor), x+pw, sy(floor), FLOOR, 1.2, "3 5");
    for (const armId of data.arms.filter(name => !ARMS[name].any)) {
      const arm = ARMS[armId];
      const points = data.frontier.filter(row => row.variation === id && row.arm === armId)
        .map(row => [sx(row.usefulness), sy(row.safety)]);
      body += series(points, arm, 2.3);
      body += points.map(([xx, yy]) => marker(xx, yy, arm, 2.5)).join("");
    }
    const chosen = data.by_variation.filter(row => row.variation === id);
    for (const row of chosen.filter(row => !ARMS[row.arm].any)) {
      const x1 = sx(row.usefulness);
      const y1 = sy(row.safety);
      body += `<circle cx="${num(x1)}" cy="${num(y1)}" r="10.5" fill="#fff" opacity="0.9"/>`;
      body += marker(x1, y1, ARMS[row.arm], 6.7, true);
    }
    for (const row of chosen.filter(row => ARMS[row.arm].any)) {
      const x1 = sx(row.usefulness);
      const y1 = sy(row.safety);
      const coincides = chosen.some(base => base.arm === row.arm.replace(/_any$/, "")
        && base.safety === row.safety && base.usefulness === row.usefulness);
      if (coincides) {
        body += `<circle cx="${num(x1)}" cy="${num(y1)}" r="12" fill="none" stroke="${ARMS[row.arm].color}" stroke-width="2"/>`;
      } else {
        body += `<circle cx="${num(x1)}" cy="${num(y1)}" r="10.5" fill="#fff" opacity="0.9"/>`;
        body += marker(x1, y1, ARMS[row.arm], 6.7, true);
      }
    }
    body += label(x+pw/2, top+ph+44, "Usefulness · honest submissions shipped", { anchor: "middle", size: 16, fill: MUTED });
  }
  body += `<g transform="translate(28 ${top+ph/2}) rotate(-90)">${label(0,0,"Safety · deployments with no attack shipped", { anchor: "middle", size: 16, fill: MUTED })}</g>`;
  body += legend(data.arms, 77, 628, 4, 363);
  body += label(35, 691, `${settingsLine(data.population, settings)} · attack rate ${pct(settings.attack_rate)} · review budget ${pct(settings.budget)}`, { size: 15, fill: MUTED });
  body += label(35, 713, "Small marks sweep thresholds. Large filled: budget cut. Hollow: any test fires. A ring means both coincide. Dotted gray: no-attack floor.", { size: 14, fill: MUTED });
  return page(width, height, "Kimi K3 · Safety vs. usefulness", "APPS · changing the flagging threshold under rules that hold back flagged submissions", body);
}

function budgetSurface(data) {
  const settings = data.settings.budget_surface;
  const { budgets, attack_rates: rates } = settings;
  const width = 1590;
  const height = 958;
  const xStart = 74;
  const xGap = 387;
  const yStart = 151;
  const yGap = 222;
  const pw = 332;
  const ph = 169;
  const xMin = Math.log(budgets[0]);
  const xSpan = Math.log(budgets.at(-1))-xMin;
  let body = "";
  for (const [r, id] of VARIATIONS.entries()) {
    for (const [c, rate] of rates.entries()) {
      const x = xStart+c*xGap;
      const y = yStart+r*yGap;
      const sx = v => x + (Math.log(v)-xMin)/xSpan*pw;
      const sy = v => y+(1-v)*ph;
      body += label(x, y-13, `Rule ${id} · attack rate ${pct(rate)}`, { size: 16, weight: 700 });
      body += axesBox({x, y, width:pw, height:ph, xTicks:budgets, yTicks:TICKS, sx, sy, yLabel:c===0, xLabel:r===2});
      const floor = data.budget_surface.find(row => row.variation===id && row.attack_rate===rate).free_floor;
      body += line(x, sy(floor), x+pw, sy(floor), FLOOR, 1.2, "3 5");
      for (const armId of data.arms) {
        const arm = ARMS[armId];
        const rows = data.budget_surface.filter(row => row.variation===id && row.arm===armId && row.attack_rate===rate)
          .sort((a,b) => a.budget-b.budget);
        const points = rows.map(row => [sx(row.budget), sy(row.safety)]);
        body += series(points, arm, arm.any ? 1.7 : 2.2);
        body += points.map(([xx, yy]) => marker(xx, yy, arm, 3.1)).join("");
      }
      if (r===2) body += label(x+pw/2, y+ph+41, "Audit budget (log scale)", { size: 13, fill: MUTED, anchor: "middle" });
    }
  }
  body += `<g transform="translate(21 416) rotate(-90)">${label(0,0,"Safety · deployments with no attack shipped", { anchor: "middle", size: 15, fill: MUTED })}</g>`;
  body += legend(data.arms, 73, 837, 4, 385);
  body += label(35, 912, `${integer(data.population.test_tasks)} matched held-out tasks · ${integer(settings.trials)} simulated deployments per point · ${integer(settings.horizon)} steps · seed ${settings.seed}`, { size: 15, fill: MUTED });
  body += label(35, 936, "Each budget gets its own honest-training cut. Colored dashes: at least one test fires. Dotted gray: no-attack floor.", { size: 14, fill: MUTED });
  return page(width, height, "Kimi K3 · Safety across audit budgets and attack rates", "APPS · each panel uses the same completed-arm sample under a different deployment assumption", body);
}

function validate(data) {
  if (Object.keys(ARMS).length !== data.arms.length || data.arms.some(id => !ARMS[id])) throw Error("unknown arm list");
  for (const table of ["by_variation", "frontier", "budget_surface", "paper_setting"]) {
    const rows = data[table];
    if (!Array.isArray(rows) || rows.length === 0) throw Error(`missing rows: ${table}`);
    for (const row of rows) {
      if (!(row.arm in ARMS) || !(row.variation in RULES)
          || !["safety", "free_floor", "usefulness"].every(key => Number.isFinite(row[key]) && row[key]>=0 && row[key]<=1)
          || !Number.isFinite(row.safety_minus_floor)) throw Error(`invalid result: ${table}`);
    }
  }
}

async function main() {
  const input = process.argv[2] || path.join(ROOT, "safety_results.json");
  const out = process.argv[3] || ROOT;
  const data = JSON.parse(fs.readFileSync(input, "utf8"));
  validate(data);
  const figures = {
    "safety_by_variation.png": bars(data, "by_variation"),
    "frontiers_b_c.png": frontier(data),
    "budget_attack_surface.png": budgetSurface(data),
    "paper_setting.png": bars(data, "paper_setting"),
  };
  await Promise.all(Object.entries(figures).map(([name, svg]) =>
    sharp(Buffer.from(svg), { density: 96 }).png().toFile(path.join(out, name))));
  console.log(Object.keys(figures).join(", "));
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
