import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = `${root}/outputs/v1_final_review`;

function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === "," && !quoted) { row.push(cell); cell = ""; }
    else if ((ch === "\n" || ch === "\r") && !quoted) {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const headers = rows[0].map((header) => header.replace(/^\uFEFF/, ""));
  return rows.slice(1).map((values) => Object.fromEntries(headers.map((h, i) => [h, values[i] ?? ""])));
}

function normalizeDate(value) {
  if (!value.includes("/")) return value;
  const [month, day, year] = value.split("/");
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function fileVersion(path) {
  if (path.startsWith("legacy_reference/")) return "Legacy reference";
  if (path.startsWith("artifacts/final_reporting/")) return "Final MVP predecessor evidence";
  if (path.startsWith("artifacts/v1_stabilized/")) return "V1 stabilized";
  if (path.startsWith("src/") || path.startsWith("tests/") || path.startsWith("config/mt5/") || path.startsWith("scripts/")) return "V1 current/shared tooling";
  return "Shared repository/governance";
}

const exactDescriptions = {
  "src/mt5/XAUUSD_MVP.mq5": "Current V1 MQL5 EA entry point; tester-only orchestration, safety and lifecycle.",
  "src/mt5/include/XauContracts.mqh": "Pure MQL contracts for zones, signals, risk and safety.",
  "src/mt5/include/XauState.mqh": "MQL state machines for trend, zones, pullbacks and TP lifecycle.",
  "src/mt5/include/XauCoordinator.mqh": "Causal MQL tick/bar coordinator and candidate generation.",
  "src/mt5/include/XauRequests.mqh": "Candidate eligibility, protected request preparation and rejection reasons.",
  "src/mt5/include/XauExecution.mqh": "Execution projection, ticket/position binding and durable recovery.",
  "src/mt5/include/XauNative.mqh": "Read-only/native MT5 data and execution outcome adapters.",
  "src/mt5/include/XauTesterBroker.mqh": "Only OrderSend adapter; hard-locked to local Strategy Tester.",
  "src/mt5/include/XauTesterRisk.mqh": "Symbol/Magic-filtered native risk and deal snapshots.",
  "src/mt5/include/XauAudit.mqh": "Durable order and candidate-block JSONL serialization.",
  "src/mt5/include/XauVisual.mqh": "Chart marker payload adapter; not an acceptance gate.",
  "src/mt5/generated/CoreVectors.mqh": "Generated MQL copy of 19 shared parity vectors.",
  "src/mt5/generated/DailyZones.mqh": "Generated canonical 23-day daily-zone input for MQL.",
  "src/xauusd/audit.py": "Python durable audit records, projection and reporting DTOs.",
  "src/xauusd/execution.py": "Python execution lifecycle and protection invariants.",
  "src/xauusd/market_state.py": "Python causal market state aggregator.",
  "src/xauusd/momentum.py": "Strict pullback momentum and TP decision logic.",
  "src/xauusd/orchestration.py": "Python bar/tick orchestration and daily lineage.",
  "src/xauusd/pullback.py": "Pullback windows, penetration, usage and pending lifecycle.",
  "src/xauusd/replay.py": "Deterministic replay with explicit broker outcomes.",
  "src/xauusd/risk.py": "Initial SL/TP, free space, RF and portfolio-risk contracts.",
  "src/xauusd/safety.py": "Daily loss, session flatten and restart fail-closed logic.",
  "src/xauusd/signals.py": "Breakout and reversal signal contracts.",
  "src/xauusd/tick_data.py": "MT5 tick normalization into causal M15 bars.",
  "src/xauusd/trend.py": "Daily progressive trend bootstrap and updates.",
  "src/xauusd/zones.py": "Canonical zone loading, normalization and merge.",
};

function describe(path) {
  if (exactDescriptions[path]) return exactDescriptions[path];
  const name = path.split("/").pop();
  if (path.startsWith("legacy_reference/")) {
    if (path.includes("/ea/")) return `Legacy MQL EA retained only for regression/history: ${name}`;
    if (path.includes("/generated/")) return `Legacy MT5 scenario configuration: ${name}`;
    if (path.includes("/results/") || path.includes("/reference/")) return `Immutable legacy result/evidence input: ${name}`;
    return `Legacy forensic/reproduction asset; never overrides current rules: ${name}`;
  }
  if (path.startsWith("tests/")) return `Automated regression/contract test: ${name}`;
  if (path.startsWith("config/mt5/")) return `Reproducible local-only MT5 tester configuration: ${name}`;
  if (path.startsWith("scripts/")) return `Project automation, extraction or verification utility: ${name}`;
  if (path.startsWith("docs/")) return `Source-of-truth project document: ${name}`;
  if (path.startsWith("artifacts/")) return `Committed compact test/report evidence: ${name}`;
  if (path.startsWith("integrations/")) return `Integration boundary documentation: ${name}`;
  if (path.startsWith(".agents/skills/")) return `Repository-local Codex execution skill: ${name}`;
  return `Repository configuration or shared project asset: ${name}`;
}

const v1Rows = parseCsv(await fs.readFile(`${root}/artifacts/v1_stabilized/v1_daily_performance_comparison.csv`, "utf8"));
const finalRows = parseCsv(await fs.readFile(`${root}/artifacts/final_reporting/final_daily_performance_comparison.csv`, "utf8"));
const ledger = parseCsv(await fs.readFile(`${root}/artifacts/v1_stabilized/v1_event_ledger.csv`, "utf8"));
const v1 = new Map(v1Rows.filter(r => r.scenario_id === "V1_STABILIZED_23D_REAL_TICK_200").map(r => [r.broker_day, Number(r.daily_net_pnl_usd)]));
const risk = new Map(v1Rows.filter(r => r.scenario_id === "RISK200_GROSS_15").map(r => [r.broker_day, Number(r.daily_net_pnl_usd)]));
const finalMvp = new Map(finalRows.filter(r => r.scenario_id === "FINAL_MVP_V2_0_0_CAPITAL_200").map(r => [normalizeDate(r.broker_day), Number(r.daily_net_pnl_usd)]));
const days = [...v1.keys()].sort();
const daily = days.map(day => [new Date(`${day}T00:00:00Z`), v1.get(day), finalMvp.get(day) ?? null, risk.get(day) ?? null]);
const pnls = ledger.filter(r => r.event_type === "POSITION_CLOSE").map(r => Number(r.realized_pnl_usd));
const gp = pnls.filter(x => x > 0).reduce((a, b) => a + b, 0);
const gl = -pnls.filter(x => x < 0).reduce((a, b) => a + b, 0);
let equity = 200, peak = 200, drawdown = 0;
for (const pnl of pnls) { equity += pnl; peak = Math.max(peak, equity); drawdown = Math.max(drawdown, peak - equity); }
const tracked = execFileSync(
  "git",
  ["-c", `safe.directory=${root.replaceAll("\\", "/")}`, "ls-files", "--cached", "--others", "--exclude-standard"],
  {cwd: root, encoding: "utf8"},
).trim().split(/\r?\n/);
const inventory = tracked.map(path => [path, fileVersion(path), describe(path)]);

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const dailySheet = workbook.worksheets.add("Daily comparison");
const filesSheet = workbook.worksheets.add("File inventory");
const howTo = workbook.worksheets.add("Small tests");
const live = workbook.worksheets.add("Live readiness");
for (const sheet of [summary, dailySheet, filesSheet, howTo, live]) sheet.showGridLines = false;

summary.getRange("A2:F2").merge();
summary.getRange("A2").values = [["V1 stabilized final review"]];
summary.getRange("A4:B14").values = [
  ["Metric", "V1 result"], ["23-day net PnL (USD)", pnls.reduce((a,b)=>a+b,0)], ["Final balance from 200 USD", equity],
  ["Closed trades", pnls.length], ["Wins / losses / breakeven", `${pnls.filter(x=>x>0).length} / ${pnls.filter(x=>x<0).length} / ${pnls.filter(x=>x===0).length}`],
  ["Gross profit (USD)", gp], ["Gross loss (USD)", gl], ["Profit factor", gp/gl], ["Closed-trade drawdown (USD)", drawdown],
  ["Technical gate", "PASS"], ["Real-money gate", "NO-GO"]
];
summary.getRange("D4:F8").values = [
  ["Scenario", "Net PnL (USD)", "Days"], ["V1 stabilized", [...v1.values()].reduce((a,b)=>a+b,0), v1.size],
  ["Final MVP predecessor", [...finalMvp.values()].reduce((a,b)=>a+b,0), finalMvp.size],
  ["RISK200_GROSS_15", [...risk.values()].reduce((a,b)=>a+b,0), risk.size],
  ["Note", "RISK200 has no 2026-08-10 row", "Not controlled A/B"]
];

dailySheet.getRange("A2:F2").merge(); dailySheet.getRange("A2").values = [["Day-by-day comparison (USD)"]];
dailySheet.getRange("A4:F4").values = [["Broker day", "V1", "Final MVP", "RISK200_GROSS_15", "V1 - Final", "V1 - Risk"]];
dailySheet.getRange("A5:D27").values = daily;
dailySheet.getRange("E5").formulas = [["=B5-C5"]]; dailySheet.getRange("E5:E27").fillDown();
dailySheet.getRange("F5").formulas = [["=IF(D5=\"\",\"\",B5-D5)"]]; dailySheet.getRange("F5:F27").fillDown();
dailySheet.getRange("A28:F28").values = [["Total / available rows", null, null, null, null, null]];
dailySheet.getRange("B28").formulas = [["=SUM(B5:B27)"]]; dailySheet.getRange("C28").formulas = [["=SUM(C5:C27)"]]; dailySheet.getRange("D28").formulas = [["=SUM(D5:D27)"]];

filesSheet.getRange("A2:C2").merge(); filesSheet.getRange("A2").values = [["Complete tracked-file inventory"]];
filesSheet.getRange("A4:C4").values = [["Path", "Version/scope", "Purpose"]];
filesSheet.getRange("A5").write(inventory);

howTo.getRange("A2:D2").merge(); howTo.getRange("A2").values = [["Safe small-test workflow"]];
howTo.getRange("A4:D12").values = [
  ["What to change", "File", "How", "Required check"],
  ["Capital 200/300", "Copy a config/mt5/*.ini", "Change Deposit and InpStrategyCapital together; keep 200→max3 or 300→max5.", "Run full acceptance for capital/risk changes"],
  ["Date range", "Copied tester INI", "Change FromDate/ToDate; ensure every Broker Day has canonical zones.", "Do not compare unequal ranges as A/B"],
  ["One-day smoke", "tester_qa_20260729.ini", "Copy and change dates only.", "Compile, then tester acceptance"],
  ["Execution toggle", "TesterInputs", "Keep InpEnableTrading=false and tester execution true only in Strategy Tester.", "Never enable live"],
  ["Strategy parameters", "docs/RULES.md + code", "Do not edit as a casual config tweak; create an experimental branch and locked variant.", "Contract tests + 23-day Real Tick"],
  ["Compile", "scripts/compile_mt5.ps1", "Run from repository root with PowerShell ExecutionPolicy Bypass.", "0 errors / 0 warnings"],
  ["Fast contracts", "scripts/quality_gate.ps1", "Runs lint, typing, tests and diff checks.", "All PASS"],
  ["MT5 acceptance", "scripts/run_mt5_tester_acceptance.ps1", "Pass -ConfigPath to the copied INI; close/allow automatic MT5 closure.", "failed=0, zero final exposure"]
];

live.getRange("A2:D2").merge(); live.getRange("A2").values = [["Real-market readiness gate"]];
live.getRange("A4:D12").values = [
  ["Gate", "Current", "Required before progression", "Decision"],
  ["G0 Research", "PASS", "Rules and reproducible configs", "Remain research-only"],
  ["G1 Backtest validated", "FAIL performance", "Robustness/OOS evidence; PF > 1 is not currently met", "NO-GO"],
  ["G2 Platform parity", "Partial", "Final live-path parity and remaining source coverage", "NO-GO"],
  ["G3 Demo/Paper", "NOT RUN", "Live feed, order lifecycle, disconnect/restart, reconciliation and kill switch", "Required"],
  ["G4 Limited live", "BLOCKED", "Explicit Leader approval after G3 and predefined risk/rollback", "Required"],
  ["Code execution lock", "Tester-only", "Build a separate reviewed live adapter; current EA rejects live use", "Missing"],
  ["Known defect/risk", "1 market invalid-stop reject", "Resolve or explicitly handle before Demo", "Missing"],
  ["Conclusion", "Technical V1 stable", "Not profitable on this 23-day run and not live-enabled", "NO-GO"]
];

const headerFill = "#1F4E78", lightFill = "#D9EAF7", warningFill = "#FCE4D6";
for (const [sheet, titleRange, headerRange] of [[summary,"A2:F2","A4:B4"],[dailySheet,"A2:F2","A4:F4"],[filesSheet,"A2:C2","A4:C4"],[howTo,"A2:D2","A4:D4"],[live,"A2:D2","A4:D4"]]) {
  sheet.getRange(titleRange).format = {font:{name:"Arial",size:14,bold:true,color:"#1F1F1F"}};
  sheet.getRange(headerRange).format = {fill:headerFill,font:{name:"Arial",size:10,bold:true,color:"#FFFFFF"},horizontalAlignment:"center",verticalAlignment:"center"};
  sheet.getUsedRange().format.font = {name:"Arial",size:10,color:"#1F1F1F"};
}
summary.getRange("D4:F4").format = {fill:headerFill,font:{name:"Arial",size:10,bold:true,color:"#FFFFFF"},horizontalAlignment:"center"};
summary.getRange("A5:A14").format.fill = lightFill;
summary.getRange("B14").format = {fill:warningFill,font:{name:"Arial",bold:true,color:"#C00000"}};
summary.getRange("B5:B12").format.numberFormat = "0.00";
dailySheet.getRange("A5:A27").format.numberFormat = "yyyy-mm-dd";
dailySheet.getRange("B5:F28").format.numberFormat = "0.00";
dailySheet.getRange("A28:F28").format.font = {name:"Arial",size:10,bold:true};
filesSheet.getRange(`A5:C${inventory.length+4}`).format.verticalAlignment = "top";
filesSheet.getRange(`B5:B${inventory.length+4}`).format.wrapText = true;
filesSheet.getRange(`C5:C${inventory.length+4}`).format.wrapText = true;
howTo.getRange("A5:D12").format.wrapText = true; live.getRange("A5:D12").format.wrapText = true;
live.getRange("D5:D12").format.fill = warningFill;
for (const sheet of [dailySheet, filesSheet, howTo, live]) sheet.freezePanes.freezeRows(4);
summary.getRange("A:F").format.autofitColumns(); dailySheet.getRange("A:F").format.autofitColumns();
filesSheet.getRange("A:A").format.columnWidth = 58; filesSheet.getRange("B:B").format.columnWidth = 25; filesSheet.getRange("C:C").format.columnWidth = 70;
howTo.getRange("A:A").format.columnWidth = 22; howTo.getRange("B:B").format.columnWidth = 30; howTo.getRange("C:D").format.columnWidth = 58;
live.getRange("A:A").format.columnWidth = 24; live.getRange("B:B").format.columnWidth = 20; live.getRange("C:C").format.columnWidth = 65; live.getRange("D:D").format.columnWidth = 18;
const chart = dailySheet.charts.add("line", dailySheet.getRange("A4:D27")); chart.title = "Daily PnL comparison"; chart.setPosition("H4", "P20");
workbook.recalculate();
await fs.mkdir(outputDir, {recursive:true});
const preview = await workbook.render({sheetName:"Summary",autoCrop:"all",scale:1,format:"png"});
await fs.writeFile(`${outputDir}/V1_FINAL_REVIEW_preview.png`, new Uint8Array(await preview.arrayBuffer()));
const inspection = await workbook.inspect({kind:"table",sheetId:"Summary",range:"A2:F14",include:"values,formulas",tableMaxRows:20,tableMaxCols:8});
console.log(inspection.ndjson);
const errors = await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:100},summary:"final formula error scan"});
console.log(errors.ndjson);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/V1_FINAL_REVIEW.xlsx`);
