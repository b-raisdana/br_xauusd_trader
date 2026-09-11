import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/b.dana/Desktop/XAAUSD-PAction-projectFolder";
const outDir = `${root}/outputs/20260910_trade_comparison`;
const data = JSON.parse(await fs.readFile(`${outDir}/comparison_data.json`, "utf8"));
const wb = Workbook.create();
const summary = wb.worksheets.add("خلاصه");
const daily = wb.worksheets.add("روزانه");
const detail = wb.worksheets.add("تفاوت معاملات");
const font = "Arial";

const stats = (rows) => {
  const pnl = rows.reduce((s, r) => s + r.pnl, 0);
  const gp = rows.filter(r => r.pnl > 0).reduce((s, r) => s + r.pnl, 0);
  const gl = -rows.filter(r => r.pnl < 0).reduce((s, r) => s + r.pnl, 0);
  return { trades: rows.length, pnl, gp, gl, pf: gl ? gp / gl : null };
};
const familyStats = (rows, family) => stats(rows.filter(r => r.family === family));
const old = stats(data.old), final = stats(data.final);
const matched = data.details.filter(r => r.status === "matched").length;

summary.getRange("A2:F2").merge();
summary.getRange("A2").values = [["مقایسه معاملات FINAL_MVP و RISK200_GROSS_15"]];
summary.getRange("A4:F4").values = [["نسخه", "معامله", "سود ناخالص", "زیان ناخالص", "سود خالص", "Profit Factor"]];
summary.getRange("A5:F6").values = [
  ["FINAL_MVP", final.trades, final.gp, final.gl, final.pnl, final.pf],
  ["RISK200_GROSS_15", old.trades, old.gp, old.gl, old.pnl, old.pf],
];
summary.getRange("A8:D8").values = [["خانواده", "PnL نهایی", "PnL قدیمی", "اختلاف Final-Old"]];
summary.getRange("A9:D11").values = ["breakout", "pullback", "reversal"].map(f => {
  const a = familyStats(data.final, f).pnl, b = familyStats(data.old, f).pnl;
  return [f, a, b, a - b];
});
summary.getRange("A13:B17").values = [
  ["شاخص", "مقدار"], ["همتای دقیق همان کندل", matched],
  ["فقط Final", data.details.filter(r => r.status === "final_only").length],
  ["فقط قدیمی", data.details.filter(r => r.status === "old_only").length],
  ["مزیت خالص قدیمی ($)", old.pnl - final.pnl],
];
summary.getRange("A19:F22").values = [
  ["نتیجه تحلیلی", "", "", "", "", ""],
  ["عامل اصلی", "Reversal قدیمی +73.93$ بود، درحالی‌که Reversal نهایی -66.78$ شد؛ اثر خالص 140.71$ به نفع قدیمی.", "", "", "", ""],
  ["جبران Final", "ورود مستقیم Breakout در Final برابر +35.51$ سود ساخت، اما اختلاف Reversal را جبران نکرد.", "", "", "", ""],
  ["محدودیت", "Final علت Block هر Candidate را ثبت نکرده؛ ردیف‌های بدون همتا فقط وقتی علت قطعی دارند که تفاوت Rule مستقیماً قابل شناسایی باشد.", "", "", "", ""],
];
for (const row of [19,20,21,22]) summary.getRange(`B${row}:F${row}`).merge();

const days = [...new Set([...data.old, ...data.final].map(r => r.day))].sort();
daily.getRange("A1:G1").values = [["تاریخ", "معاملات Final", "PnL Final", "معاملات قدیمی", "PnL قدیمی", "اختلاف Final-Old", "نسخه بهتر"]];
daily.getRange(`A2:G${days.length + 1}`).values = days.map(day => {
  const f = data.final.filter(r => r.day === day), o = data.old.filter(r => r.day === day);
  const fp = stats(f).pnl, op = stats(o).pnl;
  return [new Date(`${day}T00:00:00`), f.length, fp, o.length, op, fp-op, fp > op ? "Final" : fp < op ? "قدیمی" : "برابر"];
});

const headers = ["تاریخ", "کندل M15", "وضعیت", "خانواده", "جهت", "Zone Final", "Priority Final", "زمان ورود Final", "Entry Final", "SL Final", "TP Final", "PnL Final", "Zone قدیمی", "زمان ورود قدیمی", "Entry قدیمی", "SL قدیمی", "TP قدیمی", "PnL قدیمی", "اختلاف Final-Old", "علت تفاوت", "سطح اثبات"];
detail.getRange("A1:U1").values = [headers];
const matrix = data.details.map(row => {
  const f=row.final, o=row.old, base=f||o;
  return [new Date(`${base.day}T00:00:00`), new Date(base.candle), row.status, base.family, base.direction,
    f?.zone||"", f?.priority||"", f ? new Date(f.open_time) : null, f?.entry??null, f?.sl??null, f?.tp??null, f?.pnl??null,
    o?.zone||"", o ? new Date(o.open_time) : null, o?.entry??null, o?.sl??null, o?.tp??null, o?.pnl??null,
    row.pnl_delta_final_minus_old, row.reason, row.evidence];
});
detail.getRangeByIndexes(1,0,matrix.length,headers.length).values = matrix;

for (const sheet of [summary,daily,detail]) { sheet.showGridLines=false; sheet.getUsedRange().format.font={name:font,size:10}; }
for (const [sheet, range] of [[summary,"A4:F4"],[summary,"A8:D8"],[summary,"A13:B13"],[daily,"A1:G1"],[detail,"A1:U1"]]) {
  sheet.getRange(range).format={fill:"#1F4E78",font:{name:font,bold:true,color:"#FFFFFF"},verticalAlignment:"center",horizontalAlignment:"center",wrapText:true};
}
summary.getRange("A2:F2").format.font={name:font,size:15,bold:true,color:"#1F2937"};
summary.getRange("A19:F19").format={fill:"#D9EAF7",font:{name:font,bold:true,color:"#1F2937"}};
summary.getRange("B20:F22").format.wrapText=true;
summary.getRange("C5:F6").format.numberFormat="0.00";
summary.getRange("F5:F6").format.numberFormat="0.000";
summary.getRange("B9:D11").format.numberFormat="0.00";
daily.getRange(`A2:A${days.length+1}`).format.numberFormat="yyyy-mm-dd";
daily.getRange(`C2:F${days.length+1}`).format.numberFormat="0.00";
detail.getRange(`A2:A${matrix.length+1}`).format.numberFormat="yyyy-mm-dd";
detail.getRange(`B2:B${matrix.length+1}`).format.numberFormat="hh:mm";
detail.getRange(`H2:H${matrix.length+1}`).format.numberFormat="yyyy-mm-dd hh:mm:ss";
detail.getRange(`N2:N${matrix.length+1}`).format.numberFormat="yyyy-mm-dd hh:mm:ss";
detail.getRange(`I2:L${matrix.length+1}`).format.numberFormat="0.00";
detail.getRange(`O2:S${matrix.length+1}`).format.numberFormat="0.00";
daily.freezePanes.freezeRows(1); detail.freezePanes.freezeRows(1); detail.freezePanes.freezeColumns(5);
summary.getRange("A1:F22").format.autofitColumns(); daily.getUsedRange().format.autofitColumns(); detail.getUsedRange().format.autofitColumns();
summary.getRange("A:A").format.columnWidth=22; summary.getRange("B:F").format.columnWidth=18;
detail.getRange("T:U").format.columnWidth=48; detail.getRange("T2:U329").format.wrapText=true;
detail.getRange("A:U").format.rowHeight=18; detail.getRange("A1:U1").format.rowHeight=34;
summary.tables.add("A4:F6",true,"SummaryMetrics"); daily.tables.add(`A1:G${days.length+1}`,true,"DailyComparison"); detail.tables.add(`A1:U${matrix.length+1}`,true,"TradeDifferences");
wb.recalculate();
const inspect = await wb.inspect({kind:"table",range:"خلاصه!A2:F22",include:"values,formulas",tableMaxRows:25,tableMaxCols:8});
console.log(inspect.ndjson);
const preview = await wb.render({sheetName:"خلاصه",range:"A1:F22",scale:1.5,format:"png"});
await fs.writeFile(`${outDir}/comparison_preview.png`,new Uint8Array(await preview.arrayBuffer()));
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(`${outDir}/FINAL_MVP_vs_RISK200_GROSS_15_trade_comparison.xlsx`);
