#!/usr/bin/env python3
"""
A股分析 HTML 报告生成器 v5
阅读逻辑：总览 → 行情 → 技术 → 风险 → 预测 → 价位+因子 → 建议 → 小结
"""

import json, sys
from datetime import datetime

def _chg_sign(v): return f"+{v}" if (v or 0) >= 0 else str(v) if v is not None else "-"
def _chg_cls(v): return "up" if (v or 0) >= 0 else "down"
def _fmt(v, p=2):
    if v is None: return "-"
    if isinstance(v, float): return f"{v:.{p}f}"
    return str(v)
def _sc(s):
    if s >= 80: return "#34c759"
    if s >= 65: return "#30b0c7"
    if s >= 45: return "#ff9f0a"
    if s >= 30: return "#ff6b35"
    return "#ff3b30"
def _bar(s, m):
    p = min(100, s/m*100)
    return f'<div class="bar-track"><div class="bar-fill" style="width:{p}%;background:{_sc(s)}"></div></div>'

def render(data: dict) -> str:
    """生成单只股票的完整 HTML 报告"""
    I = data.get("基本信息", {})
    T = data.get("技术指标", {})
    signals = data.get("技术信号", [])
    A = data.get("交易建议", {})
    F = data.get("走势预测", {})
    risks = data.get("风险检测", [])
    fin = data.get("财务数据", {})
    ts = data.get("分析时间", "")
    name, code = I.get("名称",""), I.get("代码","")
    price, chg = I.get("最新价",0), I.get("涨跌幅",0)
    vol, amt = I.get("成交量",0), I.get("成交额",0)
    hs = I.get("换手率",0) or 0
    pe, pb = I.get("市盈率-动态",0) or 0, I.get("市净率",0) or 0
    mcap = I.get("总市值",0) or 0
    high, low, opn, prev = I.get("最高") or 0, I.get("最低") or 0, I.get("今开") or 0, I.get("昨收") or 0
    total = A.get("综合评分",0)
    rating, rating_desc = A.get("综合评级",""), A.get("评级说明","")
    sd = A.get("评分明细",{})
    lvls = A.get("关键价位",{})
    supports = lvls.get("支撑位",[])
    resistances = lvls.get("压力位",[])
    suggestions = A.get("操作建议",[])
    pos = A.get("仓位参考",{})
    fc_conf = F.get("预测置信度","")
    fc_trend = F.get("当前趋势","")
    fc_vol = F.get("日波动率","")
    fc_obs = F.get("观察要点",[])
    fc_periods = F.get("各周期预测",{})

    # 风险
    rp = []
    for r in risks:
        lv = r.get("级别","")
        if lv=="高": bg,c,bd="#ffe5e5","#cc1a1a","#ffcccc"
        elif lv=="中": bg,c,bd="#fff3e0","#cc6600","#ffe0b0"
        else: bg,c,bd="#e5f9ed","#1b7a3d","#c8f0d4"
        rp.append(f'<span class="risk-badge" style="background:{bg};color:{c};border:1px solid {bd}">{lv}风险</span><span>{r.get("信号","")}</span>')
    risk_html = "".join(f'<div class="risk-item">{p}</div>' for p in rp) if rp else '<span class="muted">未检测到显著风险信号</span>'

    # 信号
    sig_html = "".join(f'<span class="sig-tag">{s}</span>' for s in signals)

    # 因子
    factor_rows = ""
    for fn in ["趋势因子","动量因子","量价因子","估值因子","位置因子"]:
        fd = sd.get(fn,{})
        s,m,d = fd.get("得分",0), fd.get("满分",10), fd.get("说明","")
        factor_rows += f'<div class="factor-row"><div class="factor-head"><span>{fn}</span><span class="factor-score">{s}<i>/{m}</i></span></div>{_bar(s,m)}<div class="factor-note">{d}</div></div>'

    # 预测表
    frows = ""
    for k in ["day1","day5","day10","day30"]:
        p = fc_periods.get(k,{})
        if not p: continue
        chg_s = p.get("预计涨跌","")
        cn = float(chg_s.replace("%","").replace("+","")) if chg_s else 0
        cc = "#ff3b30" if cn>=0 else "#34c759"
        scs = p.get("情景分析",{})
        bull = scs.get("乐观",{})
        base = scs.get("基准",{})
        bear = scs.get("悲观",{})
        frows += f'''<tr>
            <td class="td-period">{p.get("周期","")}</td>
            <td class="td-num" style="color:{cc}">{p.get("基准预测",0)}</td>
            <td class="td-num" style="color:{cc};font-size:12px">{chg_s}</td>
            <td class="td-num">{p.get("68%置信区间","")}</td>
            <td class="td-num">{p.get("95%置信区间","")}</td>
            <td class="td-sc">
                <span class="sc bull">{bull.get("价格","")}<i>{bull.get("概率","")}</i></span>
                <span class="sc base">{base.get("价格","")}<i>{base.get("概率","")}</i></span>
                <span class="sc bear">{bear.get("价格","")}<i>{bear.get("概率","")}</i></span>
            </td></tr>'''

    # 财务
    fin_rows = ""
    if fin and "error" not in fin:
        for k,v in fin.items():
            if k=="报告期": continue
            fin_rows += f'<tr><td class="td-label">{k}</td><td class="td-num">{v}</td></tr>'

    cc = _chg_cls(chg)
    sc = _sc(total)
    # 趋势方向色
    trend_c = "#ff3b30" if "升" in fc_trend or "偏多" in fc_trend else ("#34c759" if "降" in fc_trend or "偏空" in fc_trend else "#8e8e93")

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name}（{code}）技术分析</title>
<style>
:root{{
  --bg:#f2f2f7; --card:#fff; --card2:#fafafc; --border:#e4e4ea; --border2:#f0f0f3;
  --text:#1c1c1e; --text2:#515154; --text3:#8e8e93;
  --up:#ff3b30; --down:#34c759; --warn:#ff9f0a; --blue:#0071e3; --blue-bg:#f0f5ff;
  --r:16px; --rs:10px;
  --fn:"SF Mono","Cascadia Code","JetBrains Mono",monospace;
  --ui:-apple-system,"SF Pro Display","PingFang SC","Helvetica Neue",system-ui,sans-serif;
  /* 响应式字号变量 */
  --fs-h1:26px; --fs-price:58px; --fs-chg:21px; --fs-hero-score:42px;
  --fs-card-pad:28px 32px; --fs-hero-pad:28px 34px; --fs-body:15px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  background:var(--bg);color:var(--text);font-family:var(--ui);
  font-size:var(--fs-body);line-height:1.65;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
}}
.container{{max-width:880px;margin:0 auto;padding:40px 24px 80px}}

/* 声明条 */
.notice{{
  background:var(--blue-bg);border:1px solid #c8d8f0;border-radius:var(--r);
  padding:13px 22px;font-size:13px;color:#4a6a9a;text-align:center;margin-bottom:24px;line-height:1.7
}}
.notice b{{color:var(--blue)}}

/* 头部 */
.header{{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
.header h1{{font-size:var(--fs-h1);font-weight:700;letter-spacing:-.02em}}
.header h1 span{{font-size:15px;color:var(--text3);margin-left:10px;font-weight:500}}
.price-block{{margin-top:6px;display:flex;align-items:baseline;gap:12px}}
.price-num{{font-size:var(--fs-price);font-weight:800;letter-spacing:-.04em;line-height:1}}
.price-chg{{font-size:var(--fs-chg);font-weight:650;font-family:var(--fn)}}
.header-meta{{text-align:right;color:var(--text3);font-size:13px}}
.up{{color:var(--up)}}.down{{color:var(--down)}}

/* 卡片 */
.card{{background:var(--card);border-radius:var(--r);padding:var(--fs-card-pad);margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.03),0 4px 12px rgba(0,0,0,.03);border:1px solid var(--border)}}
.card-title{{font-size:13px;font-weight:700;color:var(--blue);letter-spacing:.04em;margin-bottom:22px;display:flex;align-items:center;gap:10px}}
.card-title::after{{content:"";flex:1;height:1px;background:var(--border)}}
.card-em{{box-shadow:0 2px 8px rgba(0,0,0,.05),0 10px 28px rgba(0,0,0,.05)}}
.card-blue{{background:var(--blue-bg);border-color:#c8d8f0}}

/* 网格 */
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}

/* KV行 */
.kv{{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;font-size:14px}}
.kv+.kv{{border-top:1px solid var(--border2)}}
.kv-key{{color:var(--text3);font-size:13px;flex-shrink:0;margin-right:16px}}
.kv-val{{font-family:var(--fn);font-weight:520;color:var(--text2);font-size:14px;text-align:right}}

/* 子标题 */
.sub-t{{font-size:12px;font-weight:700;color:var(--text3);letter-spacing:.06em;margin:24px 0 12px}}

/* Hero 总览卡片 */
.hero-card{{
  display:flex;align-items:center;gap:32px;flex-wrap:wrap;
  background:var(--card);border-radius:var(--r);padding:var(--fs-hero-pad);margin-bottom:18px;
  box-shadow:0 2px 8px rgba(0,0,0,.05),0 10px 28px rgba(0,0,0,.05);
  border:1px solid var(--border);
}}
.hero-score{{
  width:108px;height:108px;border-radius:50%;border:5px solid;
  display:flex;align-items:center;justify-content:center;
  font-size:var(--fs-hero-score);font-weight:800;letter-spacing:-.03em;
  flex-shrink:0;
  box-shadow:0 2px 8px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.05);
}}
.hero-info{{flex:1;min-width:200px}}
.hero-rating{{font-size:20px;font-weight:700;margin-bottom:4px}}
.hero-desc{{font-size:14px;color:var(--text3);line-height:1.6;margin-bottom:8px}}
.hero-meta{{display:flex;gap:20px;flex-wrap:wrap;font-size:13px;color:var(--text2)}}
.hero-meta strong{{font-weight:650;color:var(--text)}}

/* 涨跌瓷片 */
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.tile{{text-align:center;padding:20px 10px 16px;background:var(--card2);border-radius:var(--rs);border:1px solid var(--border)}}
.tile-val{{font-family:var(--fn);font-size:28px;font-weight:750;letter-spacing:-.02em;line-height:1.1}}
.tile-label{{font-size:12px;color:var(--text3);margin-top:6px;font-weight:500}}

/* 因子 */
.factor-row{{margin-bottom:12px}}
.factor-head{{display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px}}
.factor-head span:first-child{{font-weight:500}}
.factor-score{{font-family:var(--fn);color:var(--text2);font-weight:600}}
.factor-score i{{color:var(--text3);font-size:11px;font-weight:400;font-style:normal}}
.bar-track{{height:5px;background:#e8e8ed;border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px}}
.factor-note{{font-size:12px;color:var(--text3);margin-top:2px;line-height:1.5}}

/* 价位标签 */
.lvl{{display:inline-block;padding:6px 15px;border-radius:20px;font-family:var(--fn);font-size:14px;font-weight:650;margin:3px 6px 3px 0}}
.lvl.s{{background:#e5f9ed;color:#1b7a3d;border:1px solid #c8f0d4}}
.lvl.s em,.lvl.r em{{font-style:normal;font-weight:400;font-size:12px;opacity:.6;font-family:var(--ui);margin-left:4px}}
.lvl.r{{background:#ffe5e5;color:#c41e3a;border:1px solid #ffd0d0}}

/* 建议项 */
.advice{{padding:12px 18px;background:var(--blue-bg);border-left:3px solid var(--blue);border-radius:0 var(--rs) var(--rs) 0;font-size:14px;color:var(--text2);margin:6px 0;line-height:1.6}}

/* 表格 */
.tbl-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
.tbl{{width:100%;border-collapse:collapse;font-size:13px;min-width:600px}}
.tbl thead th{{text-align:left;padding:9px 14px;font-size:11px;font-weight:700;color:var(--text3);letter-spacing:.06em;border-bottom:2px solid var(--border);background:var(--card2);white-space:nowrap}}
.tbl tbody td{{padding:11px 14px;border-bottom:1px solid var(--border2);color:var(--text2);white-space:nowrap}}
.td-period{{font-weight:650;color:var(--text)}}
.td-num{{font-family:var(--fn);font-size:13px}}
.td-sc{{min-width:200px}}
.td-label{{color:var(--text3);font-size:13px;width:150px}}

/* 情景胶囊 */
.sc{{display:inline-block;padding:4px 11px;border-radius:14px;font-family:var(--fn);font-size:12px;font-weight:650;margin:1px 4px}}
.sc i{{font-size:10px;font-weight:400;opacity:.6;margin-left:3px;font-style:normal}}
.sc.bull{{background:#e5f9ed;color:#1b7a3d}}
.sc.base{{background:#f5f5f8;color:#8e8e93;border:1px solid #e4e4ea}}
.sc.bear{{background:#ffe5e5;color:#c41e3a}}

/* 信号标签 */
.sig-tag{{display:inline-block;background:var(--card2);color:var(--text2);padding:4px 12px;border-radius:16px;margin:3px 5px;font-size:13px;border:1px solid var(--border);font-weight:500}}

/* 风险 */
.risk-list{{display:flex;flex-wrap:wrap;gap:10px 24px}}
.risk-item{{font-size:14px;display:flex;align-items:center;gap:8px}}
.risk-badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700;white-space:nowrap}}

/* 观察项 */
.obs{{font-size:14px;color:var(--text2);padding:5px 0;display:flex;align-items:baseline;gap:10px}}
.obs-dot{{width:7px;height:7px;border-radius:50%;background:var(--blue);flex-shrink:0;margin-top:7px}}

/* 小结 */
.summary-box{{
  padding:18px 22px;background:#fff;border-radius:var(--rs);
  border-left:3px solid var(--blue);font-size:15px;color:var(--text);line-height:1.7;
  box-shadow:0 1px 3px rgba(0,0,0,.03);
}}
.summary-box .big-score{{font-size:22px;font-weight:800;font-family:var(--fn)}}

.flex-meta{{display:flex;gap:24px;flex-wrap:wrap;align-items:center;margin-bottom:16px}}
.flex-meta span{{color:var(--text3);font-size:13px}}
.flex-meta strong{{color:var(--text);font-weight:650}}
.muted{{color:var(--text3)}}
.footer{{text-align:center;color:var(--text3);font-size:12px;margin-top:48px;padding-top:22px;border-top:1px solid var(--border)}}

/* ================================================ */
/*  响应式：平板 ≤768px                               */
/* ================================================ */
@media (max-width: 768px) {{
  :root {{
    --fs-h1:22px; --fs-price:46px; --fs-chg:18px;
    --fs-hero-score:34px; --fs-card-pad:22px 20px; --fs-hero-pad:22px 24px;
    --fs-body:14px;
  }}
  .container {{ padding:24px 16px 56px }}
  .header {{ flex-direction:column;align-items:flex-start;gap:8px }}
  .header-meta {{ text-align:left }}
  .g2 {{ grid-template-columns:1fr;gap:16px }}
  .g3 {{ grid-template-columns:1fr 1fr;gap:12px }}
  .hero-card {{ flex-direction:column;text-align:center;gap:18px }}
  .hero-info {{ text-align:center }}
  .hero-score {{ width:90px;height:90px;border-width:4px }}
  .hero-meta {{ justify-content:center }}
  .tiles {{ grid-template-columns:repeat(2,1fr) }}
  .tile {{ padding:16px 8px 12px }}
  .tile-val {{ font-size:22px }}
  .card-title {{ margin-bottom:16px }}
  .sub-t {{ margin:18px 0 10px }}
  .kv {{ flex-direction:column;align-items:flex-start;gap:2px;padding:8px 0 }}
  .kv-key {{ margin-right:0;margin-bottom:2px }}
  .kv-val {{ text-align:left;font-size:16px }}
  .flex-meta {{ gap:12px 20px }}
  .risk-list {{ flex-direction:column;gap:6px }}
  .risk-item {{ font-size:13px }}
  .price-block {{ flex-direction:column;align-items:flex-start;gap:4px }}
  .price-chg {{ font-size:16px }}
  .advice {{ font-size:13px;padding:10px 14px }}
  .lvl {{ padding:5px 12px;font-size:13px }}
  .summary-box {{ font-size:14px;padding:14px 16px }}
  .summary-box .big-score {{ font-size:20px }}
  .notice {{ font-size:12px;padding:10px 14px }}
  .footer {{ font-size:11px;margin-top:32px }}
}}

/* ================================================ */
/*  响应式：手机 ≤480px                               */
/* ================================================ */
@media (max-width: 480px) {{
  :root {{
    --fs-h1:20px; --fs-price:38px; --fs-chg:16px;
    --fs-hero-score:30px; --fs-card-pad:18px 14px; --fs-hero-pad:20px 18px;
    --fs-body:14px;
  }}
  .container {{ padding:20px 10px 48px }}
  .g3 {{ grid-template-columns:1fr }}
  .hero-score {{ width:78px;height:78px;border-width:3px }}
  .hero-rating {{ font-size:17px }}
  .hero-desc {{ font-size:13px }}
  .hero-meta {{ font-size:12px;gap:8px 14px }}
  .tile-val {{ font-size:20px }}
  .tile-label {{ font-size:11px }}
  .tbl {{ font-size:11px;min-width:480px }}
  .tbl thead th {{ padding:6px 8px;font-size:9px }}
  .tbl tbody td {{ padding:8px;font-size:11px }}
  .sc {{ padding:3px 8px;font-size:11px }}
  .sc i {{ font-size:9px }}
  .sig-tag {{ padding:3px 9px;font-size:12px;margin:2px 3px }}
  .card-title {{ font-size:12px;margin-bottom:14px }}
  .kv-val {{ font-size:15px }}
  .factor-note {{ font-size:11px }}
  .obs {{ font-size:13px }}
  .summary-box {{ font-size:13px }}
  .summary-box .big-score {{ font-size:18px }}
}}

/* ================================================ */
/*  UX: 打印优化                                     */
/* ================================================ */
@media print {{
  body {{ background:#fff;color:#000;font-size:12px }}
  .card,.hero-card {{ box-shadow:none;border:1px solid #ccc;break-inside:avoid }}
  .notice {{ background:#f9f9f9;border:1px solid #ccc;color:#333 }}
  .card-blue {{ background:#f0f5ff }}
  .tbl-wrap {{ overflow-x:visible }}
  .tbl {{ min-width:auto }}
}}
</style>
</head>
<body>
<div class="container">

<!-- ====== 头部 ====== -->
<div class="header">
  <div>
    <h1>{name}<span>{code}</span></h1>
    <div class="price-block"><span class="price-num">{price}</span><span class="price-chg {cc}">{_chg_sign(chg)}%</span></div>
  </div>
  <div class="header-muted">{ts}</div>
</div>

<!-- ====== 1. 总览 — 一眼结论 ====== -->
<div class="hero-card">
  <div class="hero-score" style="border-color:{sc};color:{sc}">{total}</div>
  <div class="hero-info">
    <div class="hero-rating" style="color:{sc}">{rating}</div>
    <div class="hero-desc">{rating_desc}</div>
    <div class="hero-meta">
      <span>趋势 <strong style="color:{trend_c}">{fc_trend}</strong></span>
      <span>波动率 <strong>{fc_vol}</strong></span>
      <span>置信度 <strong>{fc_conf}</strong></span>
    </div>
  </div>
</div>
'''

    # 交易信号横幅
    trade_sig = A.get("交易信号", {})
    if trade_sig.get("信号"):
        sig_bg = "#e5f9ed" if "买" in trade_sig.get("信号","") else ("#fff3e0" if "减" in trade_sig.get("信号","") else "#f0f5ff")
        sig_c = "#1b7a3d" if "买" in trade_sig.get("信号","") else ("#cc6600" if "减" in trade_sig.get("信号","") else "#0071e3")
        html += f'''<div style="text-align:center;margin-bottom:16px;padding:12px 20px;background:{sig_bg};border-radius:12px;font-size:16px;font-weight:700;color:{sig_c}">
    📶 交易信号：{trade_sig.get("信号")} — {trade_sig.get("说明")}
    │ 止损 {trade_sig.get("止损价","-")} │ 止盈 {trade_sig.get("止盈价","-")}
    </div>'''

    html += f'''
<!-- ====== 2. 行情概览 ====== -->
<div class="card">
  <div class="card-title">行情概览</div>
  <div class="g2">
    <div>
      <div class="kv"><span class="kv-key">今开 / 昨收</span><span class="kv-val">{_fmt(opn)} / {_fmt(prev)}</span></div>
      <div class="kv"><span class="kv-key">最高 / 最低</span><span class="kv-val">{_fmt(high)} / {_fmt(low)}</span></div>
      <div class="kv"><span class="kv-key">成交量</span><span class="kv-val">{vol:,} 手</span></div>
      <div class="kv"><span class="kv-key">成交额</span><span class="kv-val">{amt/1e8:.2f} 亿</span></div>
    </div>
    <div>
      <div class="kv"><span class="kv-key">换手率</span><span class="kv-val">{hs}%</span></div>
      <div class="kv"><span class="kv-key">市盈率 / 市净率</span><span class="kv-val">{_fmt(pe)} / {_fmt(pb)}</span></div>
      <div class="kv"><span class="kv-key">总市值</span><span class="kv-val">{mcap/1e8:,.0f} 亿</span></div>
      <div class="kv"><span class="kv-key">数据来源</span><span class="kv-val" style="font-family:var(--ui)">{I.get('_数据源','')}</span></div>
    </div>
  </div>
</div>

<!-- ====== 3. 技术指标 ====== -->
<div class="card">
  <div class="card-title">技术指标</div>
  <div class="g2">
    <div>
      <div class="kv"><span class="kv-key">MA5 / MA10</span><span class="kv-val">{_fmt(T.get('MA5'))} / {_fmt(T.get('MA10'))}</span></div>
      <div class="kv"><span class="kv-key">MA20 / MA60</span><span class="kv-val">{_fmt(T.get('MA20'))} / {_fmt(T.get('MA60'))}</span></div>
      <div class="kv"><span class="kv-key">均线排列</span><span class="kv-val" style="font-family:var(--ui)">{T.get('均线排列','-')}</span></div>
      <div class="kv"><span class="kv-key">布林带（上/中/下）</span><span class="kv-val">{_fmt(T.get('BOLL_UPPER'))} / {_fmt(T.get('BOLL_MID'))} / {_fmt(T.get('BOLL_LOWER'))}</span></div>
    </div>
    <div>
      <div class="kv"><span class="kv-key">RSI(14)</span><span class="kv-val">{_fmt(T.get('RSI14'))} &middot; <span style="font-family:var(--ui)">{T.get('RSI状态','-')}</span></span></div>
      <div class="kv"><span class="kv-key">MACD（DIF / DEA / BAR）</span><span class="kv-val">{_fmt(T.get('MACD_DIF'))} / {_fmt(T.get('MACD_DEA'))} / {_fmt(T.get('MACD_BAR'))}</span></div>
      <div class="kv"><span class="kv-key">MACD 信号</span><span class="kv-val" style="font-family:var(--ui)">{T.get('MACD信号','-')}</span></div>
      <div class="kv"><span class="kv-key">KDJ（K / D / J）</span><span class="kv-val">{_fmt(T.get('K'))} / {_fmt(T.get('D'))} / {_fmt(T.get('J'))}</span></div>
      <div class="kv"><span class="kv-key">KDJ 状态</span><span class="kv-val" style="font-family:var(--ui)">{T.get('KDJ状态','-')}</span></div>
    </div>
  </div>

  <div class="sub-t">近期涨跌与量价关系</div>
  <div class="tiles">
    <div class="tile"><div class="tile-val" style="color:{'var(--up)' if (T.get('近5日涨跌幅') or 0)>=0 else 'var(--down)'}">{_chg_sign(T.get('近5日涨跌幅'))}%</div><div class="tile-label">近 5 日</div></div>
    <div class="tile"><div class="tile-val" style="color:{'var(--up)' if (T.get('近10日涨跌幅') or 0)>=0 else 'var(--down)'}">{_chg_sign(T.get('近10日涨跌幅'))}%</div><div class="tile-label">近 10 日</div></div>
    <div class="tile"><div class="tile-val" style="color:{'var(--up)' if (T.get('近20日涨跌幅') or 0)>=0 else 'var(--down)'}">{_chg_sign(T.get('近20日涨跌幅'))}%</div><div class="tile-label">近 20 日</div></div>
    <div class="tile"><div class="tile-val" style="color:var(--text2);font-size:15px;font-family:var(--ui);font-weight:650">{T.get('量价关系','-')}</div><div class="tile-label">量价关系</div></div>
  </div>
  {f'<div style="margin-top:14px">{sig_html}</div>' if sig_html else ''}
</div>

<!-- ====== 4. 风险检测 ====== -->
<div class="card">
  <div class="card-title">风险检测</div>
  <div class="risk-list">{risk_html}</div>
</div>

<!-- ====== 5. 走势预测 ====== -->
<div class="card">
  <div class="card-title">多周期走势预测</div>
  <div class="flex-meta">
    <span>当前趋势 <strong style="color:{trend_c}">{fc_trend}</strong></span>
    <span>日波动率 <strong>{fc_vol}</strong></span>
    <span>预测置信度 <strong>{fc_conf}</strong></span>
  </div>
  <div class="tbl-wrap">
  <table class="tbl">
    <thead><tr><th>周期</th><th>基准预测</th><th>预计涨跌</th><th>68% 置信区间</th><th>95% 置信区间</th><th>三情景推演</th></tr></thead>
    <tbody>{frows}</tbody>
  </table>
  </div>
  <div class="sub-t">观察要点</div>
  {''.join(f'<div class="obs"><span class="obs-dot"></span>{o}</div>' for o in fc_obs)}
  <div style="color:var(--text3);font-size:12px;margin-top:14px;line-height:1.7">{F.get('重要提示','')}</div>
</div>

<!-- ====== 6. 关键价位 + 因子明细（并排） ====== -->
<div class="g2">
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">关键价位</div>
    <div class="sub-t" style="margin-top:0">支撑位</div>
    <div style="margin-bottom:14px">{''.join(f'<span class="lvl s">{s.get("价位","")}<em>{s.get("类型","")}</em></span>' for s in supports)}</div>
    <div class="sub-t">压力位</div>
    <div>{''.join(f'<span class="lvl r">{r.get("价位","")}<em>{r.get("类型","")}</em></span>' for r in resistances)}</div>
  </div>
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">五因子评分明细</div>
    {factor_rows}
  </div>
</div>

<!-- ====== 7. 操作建议 + 仓位 ====== -->
<div class="card card-em">
  <div class="card-title">操作建议与仓位参考</div>
  {''.join(f'<div class="advice">{s}</div>' for s in suggestions)}
  <div style="margin-top:18px;padding:16px 20px;background:var(--card2);border-radius:var(--rs);display:flex;align-items:center;gap:16px;flex-wrap:wrap">
    <span style="font-size:17px;font-weight:750;color:var(--warn)">{pos.get('建议','')}</span>
    <span style="color:var(--text3);font-size:14px">{pos.get('说明','')}</span>
  </div>
</div>

<!-- ====== 8. 综合小结 ====== -->
<div class="card card-blue">
  <div class="card-title" style="color:var(--blue)">综合小结</div>
  <div class="summary-box">
    <span>综合评分</span>
    <span class="big-score" style="color:{sc}">{total}</span>
    <span style="color:var(--text3)">/ 100</span>
    <span style="margin:0 12px;color:var(--border)">|</span>
    <span style="font-weight:700;color:{sc}">{rating}</span>
    <span style="color:var(--text3)">&middot; {rating_desc}</span>
  </div>
</div>
'''

    if fin_rows:
        html += f'''
<div class="card"><div class="card-title">财务数据</div>
<div class="tbl-wrap"><table class="tbl"><tbody>{fin_rows}</tbody></table></div></div>'''

    html += f'''
<div class="footer">{name}（{code}）技术分析报告 &middot; {ts} &middot; 东方财富 / 腾讯财经</div>
</div></body></html>'''
    return html

# ==================== 多股票合并报告（Tab 切换） ====================

def render_multi(outputs: list) -> str:
    """生成多股票合并报告，Tab 切换展示"""

    # 复用单只股票 render() 生成 body，避免维护两份 HTML 模板
    def _stock_section(out: dict) -> str:
        full_html = render(out)
        start = full_html.find('<div class="container">')
        end = full_html.rfind('</div>')
        if start != -1 and end != -1:
            # 提取 container 内容（含开标签不含闭标签），补上 </div> 闭合
            return full_html[start:end] + '</div>'
        return ""

    # 构建 stocks 数据
    stocks = []
    for out in outputs:
        I = out.get("基本信息", {})
        name = I.get("名称", "")
        code = I.get("代码", "")
        price = I.get("最新价", 0)
        chg = I.get("涨跌幅", 0)
        total = out.get("交易建议", {}).get("综合评分", 0)
        stocks.append({
            "name": name, "code": code, "price": price,
            "chg": chg, "total": total, "body": _stock_section(out)
        })

    # 生成 tab 导航
    tab_btns = ""
    tab_contents = ""
    for i, s in enumerate(stocks):
        active = "active" if i == 0 else ""
        chg_sign = f"+{s['chg']}" if s['chg'] >= 0 else str(s['chg'])
        chg_cls = "up" if s['chg'] >= 0 else "down"
        sc = _sc(s['total'])
        tab_btns += f'''<button class="tab-btn {active}" onclick="switchTab({i})" style="border-color:{sc}">
          <span class="tab-name">{s['name']}</span>
          <span class="tab-code">{s['code']}</span>
          <span class="tab-price {chg_cls}">{s['price']} {chg_sign}%</span>
          <span class="tab-score" style="color:{sc}">{s['total']}分</span>
        </button>'''
        tab_contents += f'<div class="tab-content {active}" id="tab-{i}">{s["body"]}</div>'

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>自选股批量分析</title>
<style>
:root{{
  --bg:#f2f2f7; --card:#fff; --card2:#fafafc; --border:#e4e4ea; --border2:#f0f0f3;
  --text:#1c1c1e; --text2:#515154; --text3:#8e8e93;
  --up:#ff3b30; --down:#34c759; --warn:#ff9f0a; --blue:#0071e3; --blue-bg:#f0f5ff;
  --r:16px; --rs:10px;
  --fn:"SF Mono","Cascadia Code","JetBrains Mono",monospace;
  --ui:-apple-system,"SF Pro Display","PingFang SC","Helvetica Neue",system-ui,sans-serif;
  --fs-h1:22px; --fs-price:46px; --fs-chg:18px;
  --fs-hero-score:34px; --fs-card-pad:24px 28px; --fs-hero-pad:24px 28px; --fs-body:14px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  background:var(--bg);color:var(--text);font-family:var(--ui);
  font-size:var(--fs-body);line-height:1.65;
  -webkit-font-smoothing:antialiased;
}}
.container{{max-width:960px;margin:0 auto;padding:20px 16px 80px}}

/* 声明条 */
.notice{{
  background:var(--blue-bg);border:1px solid #c8d8f0;border-radius:var(--r);
  padding:13px 22px;font-size:13px;color:#4a6a9a;text-align:center;margin-bottom:24px;line-height:1.7
}}
.notice b{{color:var(--blue)}}

/* Tab 导航 */
.tab-bar{{
  display:flex;gap:6px;overflow-x:auto;padding:0 0 14px 0;
  -webkit-overflow-scrolling:touch;scrollbar-width:none;
  border-bottom:2px solid var(--border);margin-bottom:24px;
}}
.tab-bar::-webkit-scrollbar{{display:none}}
.tab-btn{{
  flex-shrink:0;padding:10px 16px;border-radius:12px;
  border:2px solid var(--border);background:var(--card);
  cursor:pointer;text-align:left;transition:all .15s;
  font-family:var(--ui);min-width:120px;
  display:flex;flex-direction:column;gap:2px;
}}
.tab-btn:hover{{background:#f5f5f8;border-color:#ccc}}
.tab-btn.active{{background:var(--blue-bg);border-width:2px;box-shadow:0 2px 8px rgba(0,113,227,.12)}}
.tab-name{{font-size:13px;font-weight:700;color:var(--text);white-space:nowrap}}
.tab-code{{font-size:11px;color:var(--text3);font-family:var(--fn)}}
.tab-price{{font-size:12px;font-family:var(--fn);font-weight:600}}
.tab-score{{font-size:11px;font-weight:700}}
.up{{color:var(--up)}}.down{{color:var(--down)}}

/* Tab 内容 */
.tab-content{{display:none}}
.tab-content.active{{display:block}}

/* 头部 */
.header{{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:20px}}
.header h1{{font-size:var(--fs-h1);font-weight:700;letter-spacing:-.02em}}
.header h1 span{{font-size:13px;color:var(--text3);margin-left:8px;font-weight:500}}
.price-block{{margin-top:4px;display:flex;align-items:baseline;gap:10px}}
.price-num{{font-size:var(--fs-price);font-weight:800;letter-spacing:-.04em;line-height:1}}
.price-chg{{font-size:var(--fs-chg);font-weight:650;font-family:var(--fn)}}
.header-muted{{color:var(--text3);font-size:12px}}

/* 卡片 */
.card{{background:var(--card);border-radius:var(--r);padding:var(--fs-card-pad);margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.03),0 4px 12px rgba(0,0,0,.03);border:1px solid var(--border)}}
.card-title{{font-size:12px;font-weight:700;color:var(--blue);letter-spacing:.04em;margin-bottom:18px;display:flex;align-items:center;gap:8px}}
.card-title::after{{content:"";flex:1;height:1px;background:var(--border)}}
.card-em{{box-shadow:0 2px 8px rgba(0,0,0,.05),0 10px 28px rgba(0,0,0,.05)}}
.card-blue{{background:var(--blue-bg);border-color:#c8d8f0}}

.g2{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
.kv{{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;font-size:13px}}
.kv+.kv{{border-top:1px solid var(--border2)}}
.kv-key{{color:var(--text3);font-size:12px;flex-shrink:0;margin-right:12px}}
.kv-val{{font-family:var(--fn);font-weight:520;color:var(--text2);font-size:13px;text-align:right}}
.sub-t{{font-size:11px;font-weight:700;color:var(--text3);letter-spacing:.06em;margin:20px 0 10px}}

/* Hero */
.hero-card{{
  display:flex;align-items:center;gap:24px;flex-wrap:wrap;
  background:var(--card);border-radius:var(--r);padding:var(--fs-hero-pad);margin-bottom:16px;
  box-shadow:0 2px 8px rgba(0,0,0,.05),0 10px 28px rgba(0,0,0,.05);
  border:1px solid var(--border);
}}
.hero-score{{
  width:90px;height:90px;border-radius:50%;border:4px solid;
  display:flex;align-items:center;justify-content:center;
  font-size:var(--fs-hero-score);font-weight:800;letter-spacing:-.03em;
  flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.05);
}}
.hero-info{{flex:1;min-width:180px}}
.hero-rating{{font-size:18px;font-weight:700;margin-bottom:3px}}
.hero-desc{{font-size:13px;color:var(--text3);line-height:1.6;margin-bottom:6px}}
.hero-meta{{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--text2)}}
.hero-meta strong{{font-weight:650;color:var(--text)}}

/* 涨跌瓷片 */
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.tile{{text-align:center;padding:14px 8px 12px;background:var(--card2);border-radius:var(--rs);border:1px solid var(--border)}}
.tile-val{{font-family:var(--fn);font-size:22px;font-weight:750;letter-spacing:-.02em;line-height:1.1}}
.tile-label{{font-size:11px;color:var(--text3);margin-top:4px;font-weight:500}}

/* 因子 */
.factor-row{{margin-bottom:10px}}
.factor-head{{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px}}
.factor-head span:first-child{{font-weight:500}}
.factor-score{{font-family:var(--fn);color:var(--text2);font-weight:600}}
.factor-score i{{color:var(--text3);font-size:10px;font-weight:400;font-style:normal}}
.bar-track{{height:4px;background:#e8e8ed;border-radius:2px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:2px}}
.factor-note{{font-size:11px;color:var(--text3);margin-top:2px;line-height:1.5}}

/* 价位 */
.lvl{{display:inline-block;padding:4px 12px;border-radius:16px;font-family:var(--fn);font-size:13px;font-weight:650;margin:2px 4px 2px 0}}
.lvl.s{{background:#e5f9ed;color:#1b7a3d;border:1px solid #c8f0d4}}
.lvl.s em,.lvl.r em{{font-style:normal;font-weight:400;font-size:11px;opacity:.6;font-family:var(--ui);margin-left:3px}}
.lvl.r{{background:#ffe5e5;color:#c41e3a;border:1px solid #ffd0d0}}

.advice{{padding:10px 16px;background:var(--blue-bg);border-left:3px solid var(--blue);border-radius:0 var(--rs) var(--rs) 0;font-size:13px;color:var(--text2);margin:5px 0;line-height:1.6}}

.tbl-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
.tbl{{width:100%;border-collapse:collapse;font-size:12px;min-width:520px}}
.tbl thead th{{text-align:left;padding:7px 10px;font-size:10px;font-weight:700;color:var(--text3);letter-spacing:.06em;border-bottom:2px solid var(--border);background:var(--card2);white-space:nowrap}}
.tbl tbody td{{padding:9px 10px;border-bottom:1px solid var(--border2);color:var(--text2);white-space:nowrap}}
.td-period{{font-weight:650;color:var(--text)}}
.td-num{{font-family:var(--fn);font-size:12px}}
.td-sc{{min-width:180px}}
.td-label{{color:var(--text3);font-size:12px;width:140px}}

.sc{{display:inline-block;padding:3px 8px;border-radius:12px;font-family:var(--fn);font-size:11px;font-weight:650;margin:1px 3px}}
.sc i{{font-size:9px;font-weight:400;opacity:.6;margin-left:2px;font-style:normal}}
.sc.bull{{background:#e5f9ed;color:#1b7a3d}}
.sc.base{{background:#f5f5f8;color:#8e8e93;border:1px solid #e4e4ea}}
.sc.bear{{background:#ffe5e5;color:#c41e3a}}

.sig-tag{{display:inline-block;background:var(--card2);color:var(--text2);padding:3px 10px;border-radius:14px;margin:2px 4px;font-size:12px;border:1px solid var(--border);font-weight:500}}

.risk-list{{display:flex;flex-wrap:wrap;gap:8px 20px}}
.risk-item{{font-size:13px;display:flex;align-items:center;gap:6px}}
.risk-badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;white-space:nowrap}}

.obs{{font-size:13px;color:var(--text2);padding:4px 0;display:flex;align-items:baseline;gap:8px}}
.obs-dot{{width:6px;height:6px;border-radius:50%;background:var(--blue);flex-shrink:0;margin-top:6px}}

.summary-box{{
  padding:14px 18px;background:#fff;border-radius:var(--rs);
  border-left:3px solid var(--blue);font-size:14px;color:var(--text);line-height:1.7;
  box-shadow:0 1px 3px rgba(0,0,0,.03);
}}
.summary-box .big-score{{font-size:20px;font-weight:800;font-family:var(--fn)}}

.flex-meta{{display:flex;gap:20px;flex-wrap:wrap;align-items:center;margin-bottom:14px}}
.flex-meta span{{color:var(--text3);font-size:12px}}
.flex-meta strong{{color:var(--text);font-weight:650}}
.muted{{color:var(--text3)}}
.footer{{text-align:center;color:var(--text3);font-size:11px;margin-top:40px;padding-top:18px;border-top:1px solid var(--border)}}

@media (max-width: 768px) {{
  .g2{{grid-template-columns:1fr;gap:14px}}
  .hero-card{{flex-direction:column;text-align:center;gap:14px}}
  .hero-score{{width:72px;height:72px;font-size:28px}}
  .hero-info{{text-align:center}}
  .hero-meta{{justify-content:center}}
  .tiles{{grid-template-columns:repeat(2,1fr)}}
  .tile-val{{font-size:18px}}
  .tab-btn{{min-width:100px;padding:8px 12px}}
  .tab-name{{font-size:12px}}
  :root{{--fs-price:38px;--fs-h1:20px}}
}}
@media (max-width: 480px) {{
  .tab-bar{{gap:4px}}
  .tab-btn{{min-width:90px;padding:6px 10px;border-radius:10px}}
  :root{{--fs-price:32px;--fs-card-pad:16px 12px;--fs-hero-pad:16px 14px}}
}}
</style>
</head>
<body>
<div class="container">

<div class="tab-bar" id="tabBar">{tab_btns}</div>

{tab_contents}

<div class="footer">自选股批量技术分析报告 &middot; {ts} &middot; 东方财富 / 腾讯财经</div>
</div>

<script>
function switchTab(idx) {{
  document.querySelectorAll('.tab-btn').forEach((b,i) => b.classList.toggle('active', i===idx));
  document.querySelectorAll('.tab-content').forEach((c,i) => c.classList.toggle('active', i===idx));
  localStorage.setItem('gupiao-active-tab', idx);
}}
// 恢复上次选中的 tab
(function() {{
  var last = localStorage.getItem('gupiao-active-tab');
  if (last) switchTab(parseInt(last));
}})();
</script>

</body></html>'''

    return html


# ==================== 文本报告（飞书/IM 适配） ====================

def _bar_txt(s, m, w=16):
    """文字进度条"""
    p = min(1, s / m)
    filled = int(p * w)
    bar = "█" * filled + "░" * (w - filled)
    return f"{bar} {s}/{m}"


def render_text(data: dict) -> str:
    """生成与 HTML 8 段式一致的纯文本报告"""
    I = data.get("基本信息", {})
    T = data.get("技术指标", {})
    A = data.get("交易建议", {})
    F = data.get("走势预测", {})
    risks = data.get("风险检测", [])
    ts = data.get("分析时间", "")

    name, code = I.get("名称", ""), I.get("代码", "")
    price, chg = I.get("最新价", 0), I.get("涨跌幅", 0)
    vol, amt = I.get("成交量", 0), I.get("成交额", 0)
    hs = I.get("换手率", 0) or 0
    pe, pb = I.get("市盈率-动态", 0) or 0, I.get("市净率", 0) or 0
    mcap = I.get("总市值", 0) or 0
    high, low, opn, prev = I.get("最高") or 0, I.get("最低") or 0, I.get("今开") or 0, I.get("昨收") or 0
    total = A.get("综合评分", 0)
    rating, rating_desc = A.get("综合评级", ""), A.get("评级说明", "")
    sd = A.get("评分明细", {})
    lvls = A.get("关键价位", {})
    supports = lvls.get("支撑位", [])
    resistances = lvls.get("压力位", [])
    suggestions = A.get("操作建议", [])
    pos = A.get("仓位参考", {})
    fc_conf = F.get("预测置信度", "")
    fc_trend = F.get("当前趋势", "")
    fc_vol = F.get("日波动率", "")
    fc_obs = F.get("观察要点", [])
    fc_periods = F.get("各周期预测", {})
    signals = data.get("技术信号", [])

    chg_sign = f"+{chg}" if (chg or 0) >= 0 else str(chg)

    def f(v, p=2):
        if v is None:
            return "-"
        if isinstance(v, float):
            return f"{v:.{p}f}"
        return str(v)

    # 评分颜色标记
    if total >= 80:
        sc_mark = "🌟"
    elif total >= 65:
        sc_mark = "✅"
    elif total >= 45:
        sc_mark = "⏸️"
    elif total >= 30:
        sc_mark = "⚠️"
    else:
        sc_mark = "🔴"

    lines = []

    # ═══════ 头部 ═══════
    lines.append("")
    lines.append(f"{name}（{code}）")
    lines.append(f"最新价: {price}   涨跌幅: {chg_sign}%")
    lines.append(f"分析时间: {ts}")

    # ═══════ ① 总览 ═══════
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  综合评分: {total}/100 {sc_mark}")
    lines.append(f"  评级: {rating}")
    lines.append(f"  说明: {rating_desc}")
    lines.append(f"  当前趋势: {fc_trend}   波动率: {fc_vol}   置信度: {fc_conf}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    # ═══════ ② 行情概览 ═══════
    lines.append("")
    lines.append("── 行情概览 ──")
    lines.append(f"  今开: {f(opn)}    昨收: {f(prev)}")
    lines.append(f"  最高: {f(high)}    最低: {f(low)}")
    lines.append(f"  成交量: {vol:,} 手    成交额: {amt/1e8:.2f} 亿")
    lines.append(f"  换手率: {hs}%    量比: {I.get('量比','-')}")
    lines.append(f"  PE: {f(pe)}    PB: {f(pb)}")
    lines.append(f"  总市值: {mcap/1e8:,.0f} 亿    数据源: {I.get('_数据源','')}")

    # ═══════ ③ 技术指标 ═══════
    lines.append("")
    lines.append("── 技术指标 ──")
    ma5, ma10, ma20, ma60 = f(T.get('MA5')), f(T.get('MA10')), f(T.get('MA20')), f(T.get('MA60'))
    lines.append(f"  均线: MA5={ma5}  MA10={ma10}  MA20={ma20}  MA60={ma60}")
    lines.append(f"  排列: {T.get('均线排列','-')}")
    lines.append(f"  布林带: 上轨={f(T.get('BOLL_UPPER'))}  中轨={f(T.get('BOLL_MID'))}  下轨={f(T.get('BOLL_LOWER'))}")
    lines.append(f"  RSI(14): {f(T.get('RSI14'))}  — {T.get('RSI状态','-')}")
    lines.append(f"  MACD: DIF={f(T.get('MACD_DIF'))}  DEA={f(T.get('MACD_DEA'))}  BAR={f(T.get('MACD_BAR'))}")
    lines.append(f"  信号: {T.get('MACD信号','-')}")
    lines.append(f"  KDJ: K={f(T.get('K'))}  D={f(T.get('D'))}  J={f(T.get('J'))}  — {T.get('KDJ状态','-')}")
    lines.append(f"  近5日: {_chg_sign(T.get('近5日涨跌幅'))}%    近10日: {_chg_sign(T.get('近10日涨跌幅'))}%    近20日: {_chg_sign(T.get('近20日涨跌幅'))}%")
    lines.append(f"  量价关系: {T.get('量价关系','-')}")

    if signals:
        lines.append("  技术信号:")
        for s in signals:
            lines.append(f"    {s}")

    # ═══════ ④ 风险检测 ═══════
    lines.append("")
    lines.append("── 风险检测 ──")
    for r in risks:
        lv = r.get("级别", "")
        sig = r.get("信号", "")
        icon = "🔴" if lv == "高" else ("🟠" if lv == "中" else "🟢")
        lines.append(f"  {icon} [{lv}风险] {sig}")

    # ═══════ ⑤ 走势预测 ═══════
    lines.append("")
    lines.append(f"── 多周期走势预测（当前趋势: {fc_trend}  波动率: {fc_vol}  置信度: {fc_conf}）──")
    lines.append(f"  {'周期':<12} {'基准价':>8} {'涨跌':>8} {'68%区间':>20} {'95%区间':>20}")
    lines.append("  " + "-" * 68)
    for k in ["day1", "day5", "day10", "day30"]:
        p = fc_periods.get(k, {})
        if not p:
            continue
        chg_str = p.get("预计涨跌", "")
        lines.append(f"  {p.get('周期',''):<12} {p.get('基准预测',0):>8} {chg_str:>8} {p.get('68%置信区间',''):>20} {p.get('95%置信区间',''):>20}")

    # 情景分析
    scs = fc_periods.get("day5", {}).get("情景分析", {})
    if scs:
        bull = scs.get("乐观", {})
        base = scs.get("基准", {})
        bear = scs.get("悲观", {})
        lines.append(f"\n  5日三情景: 乐观 {bull.get('价格','')}({bull.get('概率','')}) | 基准 {base.get('价格','')}({base.get('概率','')}) | 悲观 {bear.get('价格','')}({bear.get('概率','')})")

    if fc_obs:
        lines.append("")
        lines.append("  观察要点:")
        for o in fc_obs:
            lines.append(f"    · {o}")

    # ═══════ ⑥ 关键价位 + 因子 ═══════
    lines.append("")
    lines.append("── 关键价位 ──")
    if supports:
        for s in supports:
            lines.append(f"  支撑: {s.get('价位','')}  ({s.get('类型','')})")
    if resistances:
        for r in resistances:
            lines.append(f"  压力: {r.get('价位','')}  ({r.get('类型','')})")

    lines.append("")
    lines.append("── 五因子评分 ──")
    for fn in ["趋势因子", "动量因子", "量价因子", "估值因子", "位置因子"]:
        fd = sd.get(fn, {})
        s, m, d = fd.get("得分", 0), fd.get("满分", 10), fd.get("说明", "")
        lines.append(f"  {fn}: {_bar_txt(s, m)}    {d}")

    # ═══════ ⑦ 操作建议 ═══════
    lines.append("")
    lines.append("── 操作建议与仓位参考 ──")
    for s in suggestions:
        lines.append(f"  {s}")
    lines.append("")
    lines.append(f"  📊 仓位: {pos.get('建议','')} — {pos.get('说明','')}")

    # ═══════ ⑧ 综合小结 ═══════
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  综合评分: {total}/100  {rating}")
    lines.append(f"  {rating_desc}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"— {name}（{code}）技术分析报告 · {ts} —")

    return "\n".join(lines)


# ==================== 飞书卡片消息 ====================

def render_card(data: dict) -> str:
    """生成飞书卡片消息（精简版，适合IM展示）"""
    I = data.get("基本信息", {})
    T = data.get("技术指标", {})
    A = data.get("交易建议", {})
    F = data.get("走势预测", {})
    risks = data.get("风险检测", [])
    signals = data.get("技术信号", [])
    ts = data.get("分析时间", "")

    name = I.get("名称", "")
    code = I.get("代码", "")
    price = I.get("最新价", 0)
    chg = I.get("涨跌幅", 0)
    high = I.get("最高", "-")
    low = I.get("最低", "-")
    volume = I.get("成交量", 0)
    hs = I.get("换手率", 0) or 0
    total = A.get("综合评分", 0)
    rating = A.get("综合评级", "")
    fc_trend = F.get("当前趋势", "")
    fc_vol = F.get("日波动率", "")
    suggestions = A.get("操作建议", [])
    pos = A.get("仓位参考", {})

    chg_sign = f"+{chg}" if (chg or 0) >= 0 else str(chg)
    chg_icon = "🔴" if (chg or 0) >= 0 else "🟢"

    if total >= 80:
        sc_icon, sc_tag = "🌟", "强烈看好"
    elif total >= 65:
        sc_icon, sc_tag = "✅", "偏多"
    elif total >= 45:
        sc_icon, sc_tag = "⏸️", "中性观望"
    elif total >= 30:
        sc_icon, sc_tag = "⚠️", "偏空"
    else:
        sc_icon, sc_tag = "🔴", "谨慎回避"

    # 风险
    risk_lines = ""
    for r in risks:
        lv = r.get("级别", "")
        if lv == "高":
            risk_lines += f"🟢 {r.get('信号', '')}\n"
        elif lv == "中":
            risk_lines += f"🟠 {r.get('信号', '')}\n"
    if not risk_lines:
        risk_lines = "🔴 未检测到显著风险\n"

    # 关键信号前3条
    key_sigs = signals[:3] if signals else []
    sig_text = "\n".join(f"· {s}" for s in key_sigs) if key_sigs else ""

    # 首条建议
    first_advice = suggestions[0] if suggestions else "暂无"

    # 5日/30日预测
    day5 = F.get('各周期预测', {}).get('day5', {})
    day30 = F.get('各周期预测', {}).get('day30', {})

    # 共振信息
    resonance = A.get("评分明细", {}).get("共振加成")
    resonance_text = ""
    if resonance and resonance.get("得分", 0) != 0:
        r_sign = "+" if resonance["得分"] > 0 else ""
        resonance_text = f"　│　共振 {r_sign}{resonance['得分']}"

    # 交易信号
    trade_sig = A.get("交易信号", {})
    sig_text = trade_sig.get("信号", "")
    sig_desc = trade_sig.get("说明", "")
    sig_line = f"\n📶 **交易信号：{sig_text}** — {sig_desc}" if sig_text else ""

    card = f"""**{name}（{code}）**

{chg_icon} **{price}**　{chg_sign}%　│　{sc_icon} {total}分 {sc_tag}{resonance_text}　│　趋势：{fc_trend}{sig_line}

**行情**
今开 {I.get('今开','-')}　昨收 {I.get('昨收','-')}　最高 {high}　最低 {low}
成交量 {volume/10000:.0f}万手　换手率 {hs}%

**技术**
均线：{T.get('均线排列','-')}　│　ADX：{T.get('ADX','-')}（{T.get('ADX状态','-')}）
MACD：{T.get('MACD信号','-')}　│　RSI：{T.get('RSI14','-')}（{T.get('RSI状态','-')}）
KDJ：{T.get('KDJ状态','-')}　│　CCI：{T.get('CCI','-')}（{T.get('CCI状态','-')}）
WR：{T.get('WR','-')}（{T.get('WR状态','-')}）　│　量价：{T.get('量价关系','-')}
"""
    if sig_text:
        card += f"\n**关键信号**\n{sig_text}\n"

    # ATR 止损
    atr_val = T.get("ATR")
    atr_line = ""
    if atr_val and price:
        sl = round(price - atr_val * 3, 2)
        tp = round(price + atr_val * 5, 2)
        atr_line = f"\n🎯 ATR止损: {sl}　止盈: {tp}"

    card += f"""
**风险**
{risk_lines}
**走势预测**　趋势：{fc_trend}　波动率：{fc_vol}
5日 {day5.get('基准预测','-')}（{day5.get('预计涨跌','-')}）　30日 {day30.get('基准预测','-')}（{day30.get('预计涨跌','-')}）{atr_line}

**操作建议**
{first_advice}
📊 仓位：{pos.get('建议','')}
"""

    return card


# ==================== 回测报告 ====================

def render_backtest_card(bt: dict) -> str:
    """生成回测结果卡片（文本）"""
    total_ret = float(bt.get("总收益率", "0").replace("%", "").replace("+", ""))
    icon = "🔴" if total_ret > 0 else "🟢"
    sharpe = bt.get("夏普比率", 0)

    lines = []
    name = bt.get("股票名称", bt.get("股票代码", ""))
    code = bt.get("股票代码", "")
    lines.append(f"📊 **{name}（{code}） 历史回测报告**")
    lines.append("")
    lines.append(f"回测区间：{bt.get('回测区间','')}　│　{bt.get('总交易日',0)}个交易日")
    lines.append("")
    lines.append(f"### {icon} 总收益率：{bt.get('总收益率','')}　　年化：{bt.get('年化收益率','')}")
    lines.append(f"夏普比率：{sharpe}　│　最大回撤：{bt.get('最大回撤','')}　│　胜率：{bt.get('胜率','')}")
    lines.append(f"交易次数：{bt.get('交易次数',0)}　│　盈亏比：{bt.get('盈亏比',0)}　│　平均持仓：{bt.get('平均持仓天数',0)}天")
    lines.append(f"平均盈利：{bt.get('平均盈利','')}　│　平均亏损：{bt.get('平均亏损','')}")
    lines.append(f"平均评分：{bt.get('平均评分',0)}（范围 {bt.get('评分范围','0~0')}）")
    lines.append("")

    # 交易明细
    trades = bt.get("交易记录", [])
    if trades:
        lines.append("**交易明细：**")
        for i, t in enumerate(trades[-10:], 1):  # 最近10笔
            ret = t.get("return_pct", 0)
            r_icon = "✅" if ret > 0 else "❌"
            lines.append(f"  {r_icon} {t.get('entry_date','')} → {t.get('exit_date','')} "
                        f"{t.get('entry_price',0):.2f}→{t.get('exit_price',0):.2f} "
                        f"{ret:+.2f}%  {t.get('days_held',0)}天 | {t.get('reason','')}")
        if len(trades) > 10:
            lines.append(f"  ...（共{len(trades)}笔，仅显示最近10笔）")

    return "\n".join(lines)


def render_backtest_html(bt: dict) -> str:
    """生成回测 HTML 报告"""
    name = bt.get("股票名称", bt.get("股票代码", ""))
    code = bt.get("股票代码", "")
    total_ret = float(bt.get("总收益率", "0").replace("%", "").replace("+", ""))
    color = "#ff3b30" if total_ret > 0 else "#34c759"
    trades = bt.get("交易记录", [])

    # 收益曲线数据
    curve_data = []
    running = 0
    for t in trades:
        running += t.get("return_pct", 0)
        curve_data.append(running)

    trade_rows = ""
    for i, t in enumerate(trades):
        ret = t.get("return_pct", 0)
        rc = "#ff3b30" if ret > 0 else "#34c759"
        trade_rows += f'''<tr>
            <td>{i+1}</td><td>{t.get('entry_date','')}</td><td>{t.get('entry_price',0):.2f}</td>
            <td>{t.get('exit_date','')}</td><td>{t.get('exit_price',0):.2f}</td>
            <td style="color:{rc};font-weight:700">{ret:+.2f}%</td>
            <td>{t.get('days_held',0)}天</td><td style="font-size:12px">{t.get('reason','')}</td></tr>'''

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name}（{code}）历史回测</title>
<style>
:root{{--bg:#f2f2f7;--card:#fff;--text:#1c1c1e;--text2:#515154;--text3:#8e8e93;
  --blue:#0071e3;--up:#ff3b30;--down:#34c759;--r:16px;
  --ui:-apple-system,"SF Pro Display","PingFang SC",system-ui,sans-serif;
  --fn:"SF Mono",monospace;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:var(--ui);padding:32px 16px;-webkit-font-smoothing:antialiased}}
.container{{max-width:960px;margin:0 auto}}
h1{{font-size:28px;font-weight:700;margin-bottom:8px}}
h1 span{{font-size:14px;color:var(--text3);font-weight:500;margin-left:8px}}
h2{{font-size:16px;font-weight:700;margin:28px 0 14px;color:var(--blue)}}
/* Hero */
.hero{{display:flex;gap:24px;flex-wrap:wrap;margin:20px 0}}
.metric-card{{background:var(--card);border-radius:var(--r);padding:20px 24px;text-align:center;min-width:120px;flex:1;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.metric-val{{font-size:32px;font-weight:800;font-family:var(--fn);letter-spacing:-.02em}}
.metric-label{{font-size:12px;color:var(--text3);margin-top:6px;font-weight:500}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.card{{background:var(--card);border-radius:var(--r);padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,.04);margin-bottom:14px}}
.card-title{{font-size:12px;font-weight:700;color:var(--blue);letter-spacing:.04em;margin-bottom:14px}}
.kv{{display:flex;justify-content:space-between;padding:6px 0;font-size:13px}}
.kv-key{{color:var(--text3);font-size:12px}}.kv-val{{font-family:var(--fn);font-weight:600;color:var(--text2)}}
.kv+.kv{{border-top:1px solid #f0f0f3}}
/* Table */
.tbl-wrap{{overflow-x:auto}}
.tbl{{width:100%;border-collapse:collapse;font-size:12px;min-width:700px}}
.tbl th{{text-align:left;padding:8px 10px;font-size:10px;font-weight:700;color:var(--text3);letter-spacing:.05em;border-bottom:2px solid #e4e4ea;background:#fafafc}}
.tbl td{{padding:8px 10px;border-bottom:1px solid #f0f0f3;color:var(--text2);font-family:var(--fn);font-size:12px}}
.notice{{background:#f0f5ff;border:1px solid #c8d8f0;border-radius:12px;padding:12px 18px;font-size:12px;color:#4a6a9a;text-align:center;margin-top:24px}}
.notice b{{color:var(--blue)}}
/* Curve */
.bar-chart{{display:flex;align-items:flex-end;gap:3px;height:120px;padding:8px 0}}
.bar{{flex:1;border-radius:3px 3px 0 0;min-width:2px;transition:height .2s}}
@media(max-width:768px){{.hero{{flex-direction:column}}.g2{{grid-template-columns:1fr}}.metric-val{{font-size:24px}}}}
</style></head><body>
<div class="container">
<h1>{name}（{code}）回测报告<span>{bt.get("回测区间","")} · {bt.get("总交易日",0)}日</span></h1>

<div class="hero">
  <div class="metric-card"><div class="metric-val" style="color:{color}">{bt.get("总收益率","")}</div><div class="metric-label">总收益率</div></div>
  <div class="metric-card"><div class="metric-val" style="color:{color}">{bt.get("年化收益率","")}</div><div class="metric-label">年化收益</div></div>
  <div class="metric-card"><div class="metric-val">{bt.get("胜率","")}</div><div class="metric-label">胜率</div></div>
  <div class="metric-card"><div class="metric-val">{bt.get("夏普比率",0)}</div><div class="metric-label">夏普比率</div></div>
  <div class="metric-card"><div class="metric-val" style="color:#ff3b30">{bt.get("最大回撤","")}</div><div class="metric-label">最大回撤</div></div>
</div>

<div class="g2">
  <div class="card">
    <div class="card-title">交易统计</div>
    <div class="kv"><span class="kv-key">交易次数</span><span class="kv-val">{bt.get("交易次数",0)}</span></div>
    <div class="kv"><span class="kv-key">盈亏比</span><span class="kv-val">{bt.get("盈亏比",0)}</span></div>
    <div class="kv"><span class="kv-key">平均盈利</span><span class="kv-val" style="color:var(--up)">{bt.get("平均盈利","")}</span></div>
    <div class="kv"><span class="kv-key">平均亏损</span><span class="kv-val" style="color:var(--down)">{bt.get("平均亏损","")}</span></div>
    <div class="kv"><span class="kv-key">平均持仓</span><span class="kv-val">{bt.get("平均持仓天数",0)} 天</span></div>
  </div>
  <div class="card">
    <div class="card-title">评分统计</div>
    <div class="kv"><span class="kv-key">平均评分</span><span class="kv-val">{bt.get("平均评分",0)}</span></div>
    <div class="kv"><span class="kv-key">评分范围</span><span class="kv-val">{bt.get("评分范围","0~0")}</span></div>
    <div class="kv"><span class="kv-key">策略规则</span><span class="kv-val" style="font-family:var(--ui);font-size:11px">评分&gt;65买入 / &lt;40卖出 / ATR×3止损</span></div>
  </div>
</div>

<div class="card">
  <div class="card-title">收益曲线（逐笔累计）</div>
  <div class="bar-chart">{"".join(f'<div class="bar" style="height:{max(2,abs(c)*2)}px;background:{"#ff3b30" if c>=0 else "#34c759"}" title="{c:+.2f}%"></div>' for c in curve_data[-60:])}</div>
  <div style="text-align:center;font-size:10px;color:var(--text3);margin-top:6px">最近{min(60,len(curve_data))}笔交易 &middot; 红色=盈利 绿色=亏损</div>
</div>

<h2>交易明细（共{len(trades)}笔）</h2>
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>#</th><th>入场日</th><th>入场价</th><th>出场日</th><th>出场价</th><th>收益</th><th>持仓</th><th>原因</th></tr></thead>
<tbody>{trade_rows}</tbody></table></div>

</div></body></html>'''
    return html


if __name__ == "__main__":
    print(render(json.load(sys.stdin)))
