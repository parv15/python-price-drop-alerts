"""The stylesheet and the inline icons / mockup used by every page. No external files, fonts or scripts."""

from __future__ import annotations

CSS = """
:root{--bg:#faf9f6;--ink:#10231a;--body:#4f5e55;--muted:#6b786f;--line:#e5e8e2;--card:#fff;--accent:#3a6b4d;--accent-dark:#2d5640;--accent-soft:#e8f0ea;--blue:#2563a8;--blue-soft:#e6eefa;--amber:#9a6a12;--amber-soft:#fbf1dc;--red:#b42318;--red-soft:#fdeceb;--green:#2f7d4f;--green-soft:#e4f3e9;color-scheme:light}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:84px}
body{margin:0;background:var(--bg);color:var(--body);font:16px/1.6 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:0 28px}
a{color:var(--accent);text-underline-offset:3px}
a:hover{color:var(--accent-dark)}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:6px}
h1,h2,h3{color:var(--ink);margin:0;letter-spacing:-.02em}
h2{font-size:38px;line-height:1.15;font-weight:800;letter-spacing:-.03em}
h3{font-size:19px;line-height:1.3;font-weight:700}
p{margin:0 0 14px}
.muted{color:var(--muted)}
.center{text-align:center}

/* header */
.top{position:sticky;top:0;z-index:20;background:rgb(250 249 246 / .92);backdrop-filter:blur(10px);border-bottom:1px solid transparent}
.top .wrap{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;min-height:76px;gap:16px}
.logo{display:inline-flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-weight:800;font-size:22px;letter-spacing:-.02em}
.logo svg{width:34px;height:34px}
.nav{display:flex;gap:34px;font-size:15px}
.nav a{color:var(--ink);text-decoration:none;font-weight:500}
.nav a:hover{color:var(--accent)}
.top-actions{display:flex;justify-content:flex-end;align-items:center;gap:22px;font-size:15px}
.top-actions .plain{color:var(--ink);text-decoration:none;font-weight:500}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:46px;padding:11px 26px;border:0;border-radius:10px;background:var(--accent);color:#fff;font:inherit;font-weight:600;font-size:16px;text-decoration:none;cursor:pointer;box-shadow:0 8px 18px -10px rgb(45 86 64 / .7)}
.btn:hover{background:var(--accent-dark);color:#fff}
.btn[disabled]{opacity:.65;cursor:progress}
.btn.lg{min-height:60px;padding:16px 32px;font-size:19px;border-radius:12px}
.btn.block{width:100%}
.btn.ghost{background:#fff;color:var(--ink);border:1px solid #cfd6cd;box-shadow:none}
.btn.ghost:hover{background:var(--accent-soft);color:var(--accent-dark)}
.btn.danger{background:#fff;color:var(--red);border:1px solid #efc2bd;box-shadow:none}
.btn.danger:hover{background:var(--red-soft);color:var(--red)}
.btn.sm{min-height:38px;padding:7px 16px;font-size:14.5px;border-radius:9px}

/* flash */
.flash{margin:0;padding:12px 0;font-size:15px;font-weight:500;border-bottom:1px solid var(--line)}
.flash .wrap{display:block}
.flash.ok{background:var(--green-soft);color:#1d5a37}
.flash.warn{background:var(--amber-soft);color:#6b4a0c}
.flash.err{background:var(--red-soft);color:#8a1b12}

/* hero */
.hero{position:relative;overflow:hidden;background:radial-gradient(1200px 520px at 80% 20%,#eef2ea 0,rgb(250 249 246 / 0) 70%),var(--bg)}
.hero .wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.08fr);gap:48px;align-items:center;padding-top:44px;padding-bottom:76px}
.pill{display:inline-block;padding:9px 18px;border-radius:999px;background:var(--accent-soft);color:var(--accent-dark);font-size:15px;font-weight:500;margin-bottom:26px}
.hero h1{font-size:74px;line-height:1.02;font-weight:800;letter-spacing:-.04em;margin-bottom:26px}
.hero p.lead{font-size:20px;line-height:1.6;color:var(--body);max-width:30em;margin-bottom:32px}
.hero .assure{display:flex;flex-wrap:wrap;gap:18px 34px;margin-top:34px;font-size:15px;color:var(--ink)}
.hero .assure span{display:inline-flex;align-items:center;gap:10px}
.hero .assure svg{width:30px;height:30px;color:var(--accent)}

/* app mockup */
.mock{position:relative;padding:0 0 64px}
.mock-win{background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 34px 64px -30px rgb(16 35 26 / .38),0 2px 6px rgb(16 35 26 / .04);overflow:hidden;min-width:0}
.mock-bar{display:grid;grid-template-columns:70px 1fr 70px;align-items:center;padding:13px 18px;border-bottom:1px solid var(--line);background:#fcfcfa}
.mock-dots{display:flex;gap:7px}
.mock-dots i{width:11px;height:11px;border-radius:50%}
.mock-dots i:nth-child(1){background:#ef6b5e}.mock-dots i:nth-child(2){background:#f5bf4f}.mock-dots i:nth-child(3){background:#5fc454}
.mock-url{justify-self:center;display:flex;align-items:center;gap:7px;padding:4px 16px;border-radius:999px;background:#f1f2ee;color:var(--muted);font-size:12px;font-weight:500}
.mock-url svg{width:12px;height:12px}
.mock-body{display:grid;grid-template-columns:148px minmax(0,1fr)}
.mock-side{padding:18px 12px;border-right:1px solid var(--line);background:#fcfcfa;font-size:13px;display:flex;flex-direction:column;min-height:330px}
.mock-logo{display:flex;align-items:center;gap:9px;font-weight:800;color:var(--ink);padding:2px 8px 18px;font-size:14px;white-space:nowrap}
.mock-logo svg{width:22px;height:22px;flex:none}
.mock-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;color:var(--body);margin-bottom:3px;white-space:nowrap;font-weight:500}
.mock-item svg{width:17px;height:17px;flex:none}
.mock-item.on{background:var(--accent-soft);color:var(--accent-dark);font-weight:700}
.mock-item em{margin-left:auto;font-style:normal;font-size:11px;font-weight:700;background:var(--accent);color:#fff;border-radius:999px;padding:1px 7px}
.mock-foot{margin-top:auto;padding:12px 10px 0;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted);line-height:1.4;white-space:nowrap}
.mock-foot b{display:block;color:var(--ink);font-size:13px}
.mock-main{padding:20px 18px 58px;background:#fcfcfa;min-width:0}
.mock-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}
.mock-head b{display:block;color:var(--ink);font-size:16px;line-height:1.25;letter-spacing:-.01em}
.mock-head small{color:var(--muted);font-size:12px}
.mock-btn{background:var(--accent);color:#fff;border-radius:9px;padding:8px 13px;font-size:12.5px;font-weight:700;white-space:nowrap}
.mock-row{display:grid;grid-template-columns:42px minmax(0,1fr) 56px auto;align-items:center;gap:12px;background:#fff;border:1px solid var(--line);border-radius:13px;padding:11px 13px;margin-bottom:10px}
.mock-row .thumb{width:42px;height:42px;border-radius:11px;display:flex;align-items:center;justify-content:center}
.mock-row .thumb svg{width:24px;height:24px}
.t1{background:#e6efe8;color:#2f5d44}.t2{background:#e6edf7;color:#2b5aa8}.t3{background:#f6efdc;color:#8a6212}
.mock-row b{display:block;color:var(--ink);font-size:13px;line-height:1.3;white-space:nowrap}
.mock-row small{display:block;color:var(--muted);font-size:11.5px;white-space:nowrap}
.mock-row .sp{display:block;width:56px;height:22px}
.mock-row .mp{text-align:right;white-space:nowrap}
.mock-row .mp b{font-size:13.5px}
.mock-row .mp .drop{display:inline-block;margin-top:2px;background:var(--green-soft);color:var(--green);font-size:11.5px;font-weight:700;border-radius:6px;padding:1px 7px}
.mock-toast{position:absolute;right:22px;bottom:0;width:min(360px,70%);background:#fff;border:1px solid var(--line);border-radius:15px;padding:15px 17px;display:grid;grid-template-columns:42px 1fr auto;gap:3px 14px;box-shadow:0 26px 48px -22px rgb(16 35 26 / .45),0 2px 6px rgb(16 35 26 / .05)}
.mock-toast .ico{grid-row:1 / span 3;width:42px;height:42px;border-radius:11px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center}
.mock-toast .ico svg{width:22px;height:22px}
.mock-toast b{color:var(--ink);font-size:14.5px;line-height:1.3}
.mock-toast em{font-style:normal;color:var(--muted);font-size:12px}
.mock-toast p{grid-column:2 / span 2;margin:0;font-size:13.5px;line-height:1.45;color:var(--body)}
.mock-toast .tag{grid-column:2 / span 2;justify-self:start;margin-top:3px;background:var(--green-soft);color:#1d5a37;font-size:11.5px;font-weight:700;border-radius:999px;padding:2px 10px}

/* sections */
.section{padding:84px 0}
.section.alt{background:#f2f2ee}
.section-head{margin-bottom:34px}
.section-head p{font-size:18px;color:var(--body);margin:10px 0 0}
.section-head.center{text-align:center}

/* stats */
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:28px 0 26px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.stat small{display:block;color:var(--muted);font-size:14px}
.stat b{display:block;color:var(--ink);font-size:30px;line-height:1.25;font-weight:800;letter-spacing:-.02em}
.stat b.sm{font-size:20px;padding-top:6px}

/* tabs */
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px}
.tabs[hidden]{display:none}
.tab{font:inherit;font-size:14.5px;font-weight:600;padding:8px 16px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--body);cursor:pointer}
.tab span{margin-left:6px;color:var(--muted);font-weight:500}
.tab:hover{border-color:#c5cdc3}
.tab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tab.on span{color:#dbe9df}

/* product cards */
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.pcard{display:flex;flex-direction:column;gap:16px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:24px;text-decoration:none;color:inherit;box-shadow:0 14px 30px -26px rgb(16 35 26 / .5);transition:transform .15s,box-shadow .15s,border-color .15s}
.pcard:hover{transform:translateY(-2px);border-color:#c9d3c8;box-shadow:0 22px 40px -26px rgb(16 35 26 / .55);color:inherit}
.pcard[hidden]{display:none}
.pcard .top-row{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.pcard h3{font-size:18px;overflow-wrap:anywhere}
.pcard .dom{display:block;color:var(--muted);font-size:14px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:999px;font-size:12.5px;font-weight:600;white-space:nowrap;background:#eceeea;color:#46524a}
.chip::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.chip.target{background:var(--green-soft);color:#1d5a37}
.chip.watching{background:var(--blue-soft);color:#1d4f8c}
.chip.out{background:var(--amber-soft);color:#7a540c}
.chip.failing{background:var(--red-soft);color:var(--red)}
.chip.new{background:#eceeea;color:#46524a}
.pcard .price-row{display:flex;align-items:flex-end;justify-content:space-between;gap:12px}
.price{font-size:34px;line-height:1.1;font-weight:800;letter-spacing:-.03em;color:var(--ink)}
.delta{display:inline-flex;align-items:center;gap:4px;font-size:13px;font-weight:700;padding:4px 9px;border-radius:8px}
.delta.down{background:var(--green-soft);color:var(--green)}
.delta.up{background:var(--red-soft);color:var(--red)}
.delta.flat{background:#eceeea;color:var(--muted)}
.spark{display:block;width:100%;height:46px}
.pcard .meta{display:flex;justify-content:space-between;gap:10px;font-size:13.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
.pcard .meta b{color:var(--ink);font-weight:600}

/* forms */
.split{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.15fr);gap:64px;align-items:start}
.steps{list-style:none;margin:26px 0 0;padding:0;display:grid;gap:18px;max-width:30em}
.steps li{display:grid;grid-template-columns:44px 1fr;gap:16px;align-items:start}
.steps b{display:inline-flex;width:44px;height:44px;border-radius:50%;background:var(--accent-soft);color:var(--accent);align-items:center;justify-content:center;font-size:18px}
.steps strong{display:block;color:var(--ink);font-size:17px}
.steps span{font-size:15px;color:var(--body)}
.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:34px;box-shadow:0 24px 50px -34px rgb(16 35 26 / .5)}
.fields{display:grid;grid-template-columns:1fr 1fr;gap:20px 18px}
.field.full{grid-column:1/-1}
.field label{display:block;font-size:14.5px;font-weight:600;color:var(--ink);margin-bottom:7px}
.field small{display:block;margin-top:6px;color:var(--muted);font-size:13px}
.field input[type=text],.field input[type=url],.field input[type=number],.field input[type=email]{font:inherit;width:100%;height:52px;padding:0 16px;border:1px solid #cdd5cb;border-radius:11px;background:#fff;color:var(--ink)}
.field input::placeholder{color:#97a39a}
.field input:hover{border-color:#aeb9ac}
.field input:focus{outline:2px solid var(--accent);outline-offset:0;border-color:var(--accent)}
.field input[readonly]{background:#f4f5f2;color:var(--muted)}
.money{display:flex;align-items:center;height:52px;border:1px solid #cdd5cb;border-radius:11px;background:#fff;overflow:hidden}
.money:focus-within{outline:2px solid var(--accent);border-color:var(--accent)}
.money span{padding:0 0 0 16px;color:var(--muted);font-weight:600}
.field .money input{border:0;outline:0;height:50px;padding:0 16px 0 8px;border-radius:0}
.check{display:flex;gap:14px;align-items:flex-start;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:#fbfbf9;cursor:pointer;font-size:15px;color:var(--ink);font-weight:600;line-height:1.4}
.check input{width:19px;height:19px;margin:2px 0 0;accent-color:var(--accent);flex:none}
.check small{display:block;margin-top:3px;font-weight:400;color:var(--muted);font-size:13px}
.errors{margin:0 0 22px;padding:14px 18px;border-radius:12px;background:var(--red-soft);color:#8a1b12;font-size:15px}
.errors ul{margin:6px 0 0;padding-left:20px}
.hint{margin:14px 0 0;color:var(--muted);font-size:13.5px}

/* feature cards */
.features{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px}
.feature{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px}
.feature .ico{display:flex;width:60px;height:60px;border-radius:50%;align-items:center;justify-content:center;margin-bottom:20px}
.feature .ico svg{width:28px;height:28px}
.feature h3{font-size:21px;margin-bottom:8px}
.feature p{margin:0;font-size:16px;color:var(--body)}
.i-green{background:#e2f0e6;color:#2f6a46}.i-blue{background:#e6eefa;color:#2b5aa8}.i-amber{background:#fbf1dc;color:#9a6a12}.i-purple{background:#ece9f8;color:#4a3fa0}

/* product page */
.crumbs{padding:28px 0 0;font-size:15px}
.crumbs a{text-decoration:none;font-weight:500}
.p-head{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding:18px 0 28px;flex-wrap:wrap}
.p-head h1{font-size:44px;line-height:1.1;font-weight:800;letter-spacing:-.03em;margin-bottom:10px;overflow-wrap:anywhere}
.p-head .sub{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;color:var(--muted);font-size:15px}
.p-head .sub a{color:var(--muted)}
.actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.actions form{margin:0}
.tiles{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-bottom:22px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.tile small{display:block;color:var(--muted);font-size:13.5px}
.tile b{display:block;color:var(--ink);font-size:26px;line-height:1.3;font-weight:800;letter-spacing:-.02em}
.tile span{font-size:13px;color:var(--muted)}
.tile .pos{color:var(--green)}.tile .neg{color:var(--red)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:26px 28px;margin-bottom:22px}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.panel-head h2{font-size:22px;font-weight:700;letter-spacing:-.02em}
.ranges{display:flex;gap:6px}
.ranges a{padding:6px 14px;border-radius:999px;border:1px solid var(--line);font-size:14px;font-weight:600;text-decoration:none;color:var(--body);background:#fff}
.ranges a[aria-current=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.chart{display:block;width:100%;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:8px 22px;margin-top:14px;font-size:13.5px;color:var(--muted)}
.legend i{display:inline-block;width:18px;height:3px;border-radius:2px;margin-right:8px;vertical-align:middle;background:var(--accent)}
.legend i.t{background:none;border-top:2px dashed var(--blue);height:0}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px}
dl.facts{margin:0;display:grid;grid-template-columns:150px 1fr;gap:12px 18px;font-size:15px}
dl.facts dt{color:var(--muted)}dl.facts dd{margin:0;color:var(--ink);font-weight:500;overflow-wrap:anywhere}
.callout.info{background:var(--blue-soft);color:#1d4f8c}
.callout{padding:14px 18px;border-radius:12px;background:var(--red-soft);color:#8a1b12;font-size:15px;margin-bottom:22px}
table.hist{width:100%;border-collapse:collapse;font-size:15px}
table.hist th{text-align:left;font-size:12.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:10px 12px;border-bottom:1px solid var(--line)}
table.hist td{padding:13px 12px;border-bottom:1px solid var(--line)}
table.hist tr:last-child td{border-bottom:0}
table.hist td.num,table.hist th.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:var(--red)}.down{color:var(--green)}
.empty{padding:36px 8px;text-align:center;color:var(--muted)}
.narrow{max-width:760px;margin:0 auto}

@media (max-width:1020px){
  h2{font-size:32px}
  .hero .wrap{grid-template-columns:1fr;gap:20px}
  .hero h1{font-size:56px}
  .grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .features{grid-template-columns:repeat(2,minmax(0,1fr))}
  .split{grid-template-columns:1fr;gap:34px}
  .tiles{grid-template-columns:repeat(3,minmax(0,1fr))}
  .nav{display:none}
  .top .wrap{grid-template-columns:1fr auto}
  .mock-toast{right:12px;width:min(360px,92%)}
}
@media (max-width:700px){
  .wrap{padding:0 18px}
  .hero h1{font-size:44px}
  .hero p.lead{font-size:18px}
  .section{padding:56px 0}
  .stats{grid-template-columns:1fr 1fr}
  .grid,.features,.two{grid-template-columns:1fr}
  .tiles{grid-template-columns:1fr 1fr}
  .fields{grid-template-columns:1fr}
  .card{padding:22px}
  .mock-body{grid-template-columns:1fr}
  .mock-side{display:none}
  .mock-row{grid-template-columns:42px minmax(0,1fr) auto;gap:10px}
  .mock-row .sp{display:none}
  .mock-main{padding-bottom:112px}
  .p-head h1{font-size:34px}
  .top-actions .plain{display:none}
  dl.facts{grid-template-columns:1fr}
  table.hist .hide-sm{display:none}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""

TAG = ('<svg viewBox="0 0 36 36" aria-hidden="true"><path d="M4 8.5A4.5 4.5 0 0 1 8.5 4H18a4.5 4.5 0 0 1 3.2 1.3l11 11a4.5 4.5 0 0 1 0 6.4l-9.5 9.5a4.5 4.5 0 0 1-6.4 0l-11-11A4.5 4.5 0 0 1 4 18z" fill="#3a6b4d"/>'
       '<circle cx="12" cy="12" r="2.7" fill="#fff"/></svg>')

_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "bell": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z"/><path d="M10 19.5a2 2 0 0 0 4 0"/></svg>',
    "shield": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M12 3l7.5 2.8v5.6c0 4.6-3.2 8.3-7.5 9.6-4.3-1.3-7.5-5-7.5-9.6V5.8z"/><path d="M8.6 12.2l2.5 2.5 4.4-5"/></svg>',
    "bars": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><rect x="4" y="13" width="4" height="7" rx="1"/><rect x="10" y="8" width="4" height="12" rx="1"/><rect x="16" y="4" width="4" height="16" rx="1"/></svg>',
    "search": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>',
    "gear": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"/></svg>',
    "home": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M4 11l8-6.5 8 6.5V20H4z"/><path d="M10 20v-5h4v5"/></svg>',
    "heart": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.4A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
    "headphones": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M4.5 14v-2a7.5 7.5 0 0 1 15 0v2"/><rect x="3.5" y="13.5" width="4" height="6" rx="1.6"/><rect x="16.5" y="13.5" width="4" height="6" rx="1.6"/></svg>',
    "shoe": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M3 16.5V12l4 1.5 3-3 2.5 2.5 6 1.8a2.7 2.7 0 0 1 1.5 2.4v.8H3z"/><path d="M3 19.5h18"/></svg>',
    "phone": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><rect x="7" y="3" width="10" height="18" rx="2.4"/><path d="M11 18h2"/></svg>',
    "list": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="4.5" cy="6.5" r=".8"/><circle cx="4.5" cy="12" r=".8"/><circle cx="4.5" cy="17.5" r=".8"/></svg>',
    "lock": f'<svg viewBox="0 0 24 24" aria-hidden="true" {_STROKE}><rect x="5" y="10.5" width="14" height="9.5" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></svg>',
    "arrow": f'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {_STROKE}><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "plus": f'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" {_STROKE}><path d="M12 5v14M5 12h14"/></svg>',
    "refresh": f'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" {_STROKE}><path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v4.5h-4.5"/></svg>',
}


def _spark(points: str) -> str:
    return (f'<svg class="sp" viewBox="0 0 56 22" aria-hidden="true"><path d="{points}" fill="none" stroke="#2f7d4f" '
            'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>')


def mockup() -> str:
    """The illustrative app window in the hero. Sample products only, nothing here is real data."""
    def row(cls: str, icon: str, name: str, shop: str, trend: str, now: str, drop: str) -> str:
        return (f'<div class="mock-row"><span class="thumb {cls}">{ICONS[icon]}</span>'
                f'<div><b>{name}</b><small>{shop}</small></div>{_spark(trend)}'
                f'<div class="mp"><b>{now}</b><span class="drop">↓ {drop}</span></div></div>')
    return (
        '<div class="mock" aria-hidden="true"><div class="mock-win">'
        '<div class="mock-bar"><span class="mock-dots"><i></i><i></i><i></i></span>'
        f'<span class="mock-url">{ICONS["lock"]}localhost:8765</span><span></span></div>'
        '<div class="mock-body"><aside class="mock-side">'
        f'<div class="mock-logo">{TAG}<span>Price Alerts</span></div>'
        f'<div class="mock-item on">{ICONS["home"]}Dashboard</div>'
        f'<div class="mock-item">{ICONS["list"]}Products<em>3</em></div>'
        f'<div class="mock-item">{ICONS["bell"]}Alerts</div>'
        f'<div class="mock-item">{ICONS["gear"]}Settings</div>'
        '<div class="mock-foot"><b>Checked 2m ago</b>On a schedule</div></aside>'
        '<div class="mock-main"><div class="mock-head"><div><b>My tracked products</b><small>3 products · 1 at target</small></div>'
        '<span class="mock-btn">+ Add product</span></div>'
        + row("t1", "headphones", "Wireless headphones", "shop.example.com", "M2 4 H16 V8 H30 V13 H42 V17 H54", "$348.00", "13%")
        + row("t2", "shoe", "Running shoes", "store.example.com", "M2 5 H14 V10 H28 V6 H38 V15 H54", "$120.00", "20%")
        + row("t3", "phone", "Smartphone 128 GB", "market.example.com", "M2 6 H20 V10 H34 V14 H44 V17 H54", "$699.00", "13%")
        + '</div></div></div>'
        f'<div class="mock-toast"><span class="ico">{ICONS["bell"]}</span><b>Price drop alert!</b><em>2m ago</em>'
        '<p>Wireless headphones dropped to $348.00, 13% below the first price you saw.</p>'
        '<span class="tag">Target reached</span></div></div>'
    )
