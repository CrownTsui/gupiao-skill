#!/usr/bin/env python3
"""
A股股票分析脚本
用法：python3 stock_analyzer.py <股票代码> [--deep]
输出：JSON 格式的结构化分析数据

数据源：东方财富API（通过 curl_cffi 模拟浏览器）
"""

import sys
import json
import argparse
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from curl_cffi import requests as cffi_requests

# ==================== 配置 ====================

EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SOHU_KLINE_URL = "https://q.stock.sohu.com/hisHq"
SINA_QUOTE_URL = "https://hq.sinajs.cn/list="

# 浏览器指纹
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

# 实时行情的字段映射
QUOTE_FIELDS = (
    "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,"
    "f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171"
)

# ==================== 网络请求 ====================

def _fetch_json(url: str, params: dict, timeout: int = 15) -> dict:
    """使用 curl_cffi 发请求，模拟 Chrome 浏览器指纹"""
    for attempt in range(3):
        try:
            resp = cffi_requests.get(
                url, params=params, headers=HEADERS,
                impersonate="chrome120", timeout=timeout
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep((attempt + 1) * 2)


def _fetch_text(url: str, referer: str, timeout: int = 10) -> str:
    """获取纯文本响应（用于新浪接口）"""
    headers = {**HEADERS, "Referer": referer}
    for attempt in range(3):
        try:
            resp = cffi_requests.get(
                url, headers=headers, impersonate="chrome120", timeout=timeout
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            if attempt == 2:
                raise
            time.sleep((attempt + 1) * 2)


# ==================== 行情数据 ====================

def _code_to_secid(code: str) -> str:
    """将6位代码转为东方财富 secid"""
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    elif code.startswith(("0", "3")):
        return f"0.{code}"
    elif code.startswith(("8", "4")):
        return f"0.{code}"
    else:
        raise ValueError(f"无法识别代码 {code} 的市场")


def _code_to_market(code: str) -> str:
    """判断市场"""
    if code.startswith(("5", "6", "9")):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    elif code.startswith(("8", "4")):
        return "bj"
    raise ValueError(f"无法识别代码 {code} 的市场")


def get_realtime_quote(code: str) -> dict:
    """获取实时行情——东方财富 / 新浪双源容错"""
    # 方案一：东方财富
    try:
        return _fetch_eastmoney_quote(code)
    except Exception:
        pass

    # 方案二：新浪财经
    try:
        return _fetch_sina_quote(code)
    except Exception:
        pass

    return {"error": f"所有数据源均无法访问，请稍后重试"}


def _fetch_eastmoney_quote(code: str) -> dict:
    """东方财富实时行情"""
    secid = _code_to_secid(code)
    data = _fetch_json(EASTMONEY_QUOTE_URL, {
        "secid": secid,
        "fields": QUOTE_FIELDS,
        "invt": "2",
        "fltt": "2",
    })
    d = data.get("data", {})
    if not d:
        raise ValueError(f"东方财富未返回代码 {code} 的数据")

    def v(key, default=None):
        """取值（invt=2 时 API 已自动缩放）"""
        val = d.get(key)
        if val is None:
            return default
        return round(float(val), 4) if isinstance(val, (int, float)) else val

    return {
        "名称": str(d.get("f58", "未知")),
        "代码": code,
        "最新价": v("f43"),
        "涨跌幅": v("f170"),
        "涨跌额": v("f169"),
        "成交量": int(d.get("f47", 0) or 0),
        "成交额": float(d.get("f48", 0) or 0),
        "振幅": v("f50"),  # TODO: 振幅字段待确认
        "最高": v("f44"),
        "最低": v("f45"),
        "今开": v("f46"),
        "昨收": v("f60"),
        "换手率": v("f168"),
        "量比": v("f50"),
        "市盈率-动态": v("f162"),
        "市净率": v("f167"),
        "总市值": float(d.get("f116", 0) or 0),
        "流通市值": float(d.get("f117", 0) or 0),
        "60日涨跌幅": None,
        "年初至今涨跌幅": None,
        "涨停价": v("f51"),
        "跌停价": v("f52"),
        "_数据源": "东方财富实时行情",
    }


def _fetch_sina_quote(code: str) -> dict:
    """新浪财经实时行情（备用）"""
    market = _code_to_market(code)
    sina_code = f"{market}{code}"
    text = _fetch_text(SINA_QUOTE_URL + sina_code, referer="https://finance.sina.com.cn")

    # var hq_str_sz000001="平安银行,11.32,11.32,11.30,..."
    if '="' not in text:
        raise ValueError(f"新浪返回格式异常: {text[:100]}")
    parts = text.split('"')[1].split(",")
    if len(parts) < 10:
        raise ValueError(f"新浪数据不完整: {text[:100]}")

    name = parts[0]
    open_price = float(parts[1])
    prev_close = float(parts[2])
    current = float(parts[3])
    high = float(parts[4])
    low = float(parts[5])
    volume = int(float(parts[8])) if parts[8] else 0
    amount = float(parts[9]) if parts[9] else 0

    return {
        "名称": name,
        "代码": code,
        "最新价": current,
        "涨跌幅": round((current / prev_close - 1) * 100, 2) if prev_close else 0,
        "涨跌额": round(current - prev_close, 2),
        "成交量": volume,
        "成交额": amount,
        "振幅": None,
        "最高": high,
        "最低": low,
        "今开": open_price,
        "昨收": prev_close,
        "换手率": None,
        "量比": None,
        "市盈率-动态": None,
        "市净率": None,
        "总市值": None,
        "流通市值": None,
        "60日涨跌幅": None,
        "年初至今涨跌幅": None,
        "涨停价": None,
        "跌停价": None,
        "_数据源": "新浪财经",
    }


# ==================== K线数据 ====================

def _kline_market_prefix(code: str) -> str:
    """K线接口的市场前缀"""
    if code.startswith(("5", "6", "9")):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    elif code.startswith(("8", "4")):
        return "bj"
    raise ValueError(f"无法识别代码 {code}")


def _fetch_kline_tencent(code: str, days: int) -> pd.DataFrame:
    """从腾讯财经获取前复权日K线"""
    prefix = _kline_market_prefix(code)
    param = f"{prefix}{code},day,,,{days + 30},qfq"
    text = _fetch_text(f"{TENCENT_KLINE_URL}?param={param}",
                       referer="http://web.ifzq.gtimg.cn/")
    data = json.loads(text)
    # 路径: data -> {prefix}{code} -> qfqday (或 day)
    stock = data.get("data", {}).get(f"{prefix}{code}", {})
    klines = stock.get("qfqday") or stock.get("day")
    if not klines:
        raise ValueError("腾讯K线数据为空")

    # 腾讯格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
    rows = []
    for item in klines[-days:]:
        rows.append({
            "日期": item[0],
            "开盘": float(item[1]),
            "收盘": float(item[2]),
            "最高": float(item[3]),
            "最低": float(item[4]),
            "成交量": float(item[5]) if len(item) > 5 else 0,
        })
    return pd.DataFrame(rows)


def _fetch_kline_sohu(code: str, days: int) -> pd.DataFrame:
    """从搜狐获取日K线（备用）"""
    prefix = _kline_market_prefix(code)
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    text = _fetch_text(
        f"{SOHU_KLINE_URL}?code=cn_{code}&start={start}&end={end}",
        referer="https://q.stock.sohu.com/")
    data = json.loads(text)
    hq = data[0].get("hq", [])
    if not hq:
        raise ValueError("搜狐K线数据为空")

    # 搜狐格式: [日期, 开盘, 收盘, 涨跌额, 涨跌幅, 最低, 最高, 成交量(手), 成交额(万), 换手率]
    rows = []
    for item in hq[-days:]:
        rows.append({
            "日期": item[0],
            "开盘": float(item[1]),
            "收盘": float(item[2]),
            "最高": float(item[6]) if len(item) > 6 else float(item[1]),
            "最低": float(item[5]) if len(item) > 5 else float(item[1]),
            "成交量": float(item[7]) * 100 if len(item) > 7 else 0,  # 手→股
        })
    return pd.DataFrame(rows)


def get_kline_data(code: str, days: int = 120) -> dict:
    """获取K线数据并计算全部技术指标（腾讯主源 + 搜狐备源）"""
    df = None
    for name, fetcher in [("腾讯", _fetch_kline_tencent), ("搜狐", _fetch_kline_sohu)]:
        try:
            df = fetcher(code, days)
            if not df.empty:
                break
        except Exception:
            continue

    if df is None or df.empty:
        return {"error": "所有K线数据源均无法访问"}

    try:
        close = df["收盘"].values.astype(float)
        high = df["最高"].values.astype(float)
        low = df["最低"].values.astype(float)
        volume = df["成交量"].values.astype(float)

        # ---- 计算各项技术指标 ----
        ma5 = _calc_ma(close, 5)
        ma10 = _calc_ma(close, 10)
        ma20 = _calc_ma(close, 20)
        ma60 = _calc_ma(close, 60)
        rsi14 = _calc_rsi(close, 14)
        dif, dea, macd_bar = _calc_macd(close)
        upper, mid, lower = _calc_boll(close, 20)
        k, d, j = _calc_kdj(high, low, close, 9)
        adx, plus_di, minus_di = _calc_adx(high, low, close, 14)
        cci = _calc_cci(high, low, close, 14)
        wr = _calc_wr(high, low, close, 14)
        atr = _calc_atr(high, low, close, 14)

        def v(arr, idx=-1):
            val = arr[idx]
            return round(float(val), 4) if val is not None and not np.isnan(val) else None

        result = {
            "最新收盘": v(close),
            "MA5": v(ma5), "MA10": v(ma10), "MA20": v(ma20), "MA60": v(ma60),
            "RSI14": v(rsi14),
            "MACD_DIF": v(dif), "MACD_DEA": v(dea), "MACD_BAR": v(macd_bar),
            "BOLL_UPPER": round(float(upper[-1]), 2) if not np.isnan(upper[-1]) else None,
            "BOLL_MID": round(float(mid[-1]), 2) if not np.isnan(mid[-1]) else None,
            "BOLL_LOWER": round(float(lower[-1]), 2) if not np.isnan(lower[-1]) else None,
            "K": v(k), "D": v(d), "J": v(j),
            "ADX": v(adx), "PLUS_DI": v(plus_di), "MINUS_DI": v(minus_di),
            "CCI": v(cci), "WR": v(wr), "ATR": v(atr),
        }

        # ---- 近期涨跌幅 ----
        cl = close
        if len(cl) >= 5:
            result["近5日涨跌幅"] = round((cl[-1] / cl[-5] - 1) * 100, 2)
        if len(cl) >= 10:
            result["近10日涨跌幅"] = round((cl[-1] / cl[-10] - 1) * 100, 2)
        if len(cl) >= 20:
            result["近20日涨跌幅"] = round((cl[-1] / cl[-20] - 1) * 100, 2)

        # ---- 均线排列 ----
        mas = [v(ma5), v(ma10), v(ma20), v(ma60)]
        mas_clean = [m for m in mas if m is not None]
        if len(mas_clean) >= 3:
            if mas_clean == sorted(mas_clean, reverse=True):
                result["均线排列"] = "多头排列 📈"
            elif mas_clean == sorted(mas_clean, reverse=False):
                result["均线排列"] = "空头排列 📉"
            else:
                result["均线排列"] = "交叉震荡 ↔️"

        # ---- MACD 信号 ----
        dv, de = v(dif), v(dea)
        if dv is not None and de is not None:
            d_prev = dif[-2] if len(dif) > 1 and not np.isnan(dif[-2]) else None
            e_prev = dea[-2] if len(dea) > 1 and not np.isnan(dea[-2]) else None
            if d_prev is not None and e_prev is not None:
                if dif[-1] > dea[-1] and d_prev <= e_prev:
                    result["MACD信号"] = "金叉形成 ✨"
                elif dif[-1] < dea[-1] and d_prev >= e_prev:
                    result["MACD信号"] = "死叉形成 ⚠️"
                elif dif[-1] > dea[-1]:
                    result["MACD信号"] = "多头运行 ↗️"
                else:
                    result["MACD信号"] = "空头运行 ↘️"
            elif dif[-1] > dea[-1]:
                result["MACD信号"] = "多头运行 ↗️"
            else:
                result["MACD信号"] = "空头运行 ↘️"

        # ---- RSI 状态 ----
        rsiv = v(rsi14)
        if rsiv is not None:
            if rsiv > 80:
                result["RSI状态"] = "严重超买 🔴"
            elif rsiv > 70:
                result["RSI状态"] = "超买区间 🟠"
            elif rsiv < 20:
                result["RSI状态"] = "严重超卖 🟢"
            elif rsiv < 30:
                result["RSI状态"] = "超卖区间 🟡"
            else:
                result["RSI状态"] = "正常区间 ⚪"

        # ---- KDJ 信号 ----
        kv, dv2 = v(k), v(d)
        if kv is not None and dv2 is not None:
            if kv > 80 and dv2 > 80:
                result["KDJ状态"] = "超买区 🔴"
            elif kv < 20 and dv2 < 20:
                result["KDJ状态"] = "超卖区 🟢"
            elif kv > dv2:
                result["KDJ状态"] = "多头 ↗️"
            else:
                result["KDJ状态"] = "空头 ↘️"

        # ---- 量价关系 ----
        if len(close) >= 2 and len(volume) >= 2:
            price_up = close[-1] > close[-2]
            vol_up = volume[-1] > volume[-2]
            if price_up and vol_up:
                result["量价关系"] = "价涨量增 📈（健康上涨）"
            elif price_up and not vol_up:
                result["量价关系"] = "价涨量缩 ↗️（上涨乏力）"
            elif not price_up and vol_up:
                result["量价关系"] = "价跌量增 📉（抛压加大）"
            else:
                result["量价关系"] = "价跌量缩 ↘️（缩量调整）"

        # ---- ADX 趋势强度 ----
        adv = v(adx)
        if adv is not None:
            if adv > 40:
                result["ADX状态"] = "强趋势 🔥"
            elif adv > 25:
                result["ADX状态"] = "趋势运行 ➡️"
            elif adv > 20:
                result["ADX状态"] = "弱趋势 💤"
            else:
                result["ADX状态"] = "无趋势/震荡 🔄"
            # DI方向
            pdi, mdi = v(plus_di), v(minus_di)
            if pdi is not None and mdi is not None:
                result["DI方向"] = "多头主导 📈" if pdi > mdi else "空头主导 📉"

        # ---- CCI 信号 ----
        cciv = v(cci)
        if cciv is not None:
            if cciv > 200:
                result["CCI状态"] = "极度超买 🔴"
            elif cciv > 100:
                result["CCI状态"] = "超买区间 🟠"
            elif cciv < -200:
                result["CCI状态"] = "极度超卖 🟢"
            elif cciv < -100:
                result["CCI状态"] = "超卖区间 🟡"
            else:
                result["CCI状态"] = "正常区间 ⚪"

        # ---- WR 威廉指标 ----
        wrv = v(wr)
        if wrv is not None:
            if wrv > -20:
                result["WR状态"] = "超买区 🔴"
            elif wrv < -80:
                result["WR状态"] = "超卖区 🟢"
            else:
                result["WR状态"] = "正常区间 ⚪"

        # ---- 内部数据：供走势预测使用 ----
        result["_收盘序列"] = [round(float(x), 2) for x in close[-60:]]
        result["_最高序列"] = [round(float(x), 2) for x in high[-60:]]
        result["_最低序列"] = [round(float(x), 2) for x in low[-60:]]

        return result

    except Exception as e:
        return {"error": f"计算技术指标失败: {e}"}


# ==================== 深度财务 ====================

def get_deep_finance(code: str) -> dict:
    """获取财务数据摘要（通过东方财富财务API）"""
    try:
        secid = _code_to_secid(code)
        data = _fetch_json("https://datacenter.eastmoney.com/securities/api/data/v1/get", {
            "reportName": "RPT_DMSK_FN_MAININDICATOR",
            "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,NOTICE_DATE,REPORT_DATE,BASIC_EPS,WEIGHTAVG_ROE,TOTAL_OPERATE_INCOME,PARENT_NETPROFIT,GROSS_PROFIT_RATIO,NETPROFIT_MARGIN",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageSize": "4",
            "sortTypes": "-1",
            "sortColumns": "REPORT_DATE",
        })
        records = data.get("result", {}).get("data", [])
        if not records:
            return {"error": "未获取到财务数据"}

        latest = records[0]
        result = {"报告期": latest.get("REPORT_DATE", "未知")}

        field_map = {
            "TOTAL_OPERATE_INCOME": ("营业收入(元)", 1),
            "PARENT_NETPROFIT": ("净利润(元)", 1),
            "BASIC_EPS": ("每股收益", 1),
            "WEIGHTAVG_ROE": ("ROE(%)", 1),
            "GROSS_PROFIT_RATIO": ("毛利率(%)", 1),
            "NETPROFIT_MARGIN": ("净利率(%)", 1),
        }

        for field, (label, scale) in field_map.items():
            val = latest.get(field)
            if val is not None:
                try:
                    result[label] = round(float(val) * scale, 2)
                except (ValueError, TypeError):
                    result[label] = str(val)

        return result
    except Exception as e:
        return {"error": f"获取财务数据失败: {e}"}


# ==================== 技术指标计算（纯数学，无IO） ====================

def _calc_ma(data: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) >= window:
        for i in range(window - 1, len(data)):
            result[i] = np.mean(data[i - window + 1 : i + 1])
    return result


def _calc_rsi(data: np.ndarray, window: int = 14) -> np.ndarray:
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < window + 1:
        return result
    delta = np.diff(data)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.zeros_like(data, dtype=float)
    avg_loss = np.zeros_like(data, dtype=float)
    avg_gain[window] = np.mean(gain[:window])
    avg_loss[window] = np.mean(loss[:window])
    for i in range(window, len(data) - 1):
        avg_gain[i + 1] = (avg_gain[i] * (window - 1) + gain[i]) / window
        avg_loss[i + 1] = (avg_loss[i] * (window - 1) + loss[i]) / window
    for i in range(len(data)):
        if avg_loss[i] == 0:
            result[i] = 100.0 if avg_gain[i] > 0 else 50.0
        elif avg_gain[i] == 0:
            result[i] = 0.0
        elif not np.isnan(avg_gain[i]) and not np.isnan(avg_loss[i]):
            result[i] = 100.0 - 100.0 / (1.0 + avg_gain[i] / avg_loss[i])
    return result


def _calc_ema(data: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < window:
        return result
    with np.errstate(all="ignore"):
        seg = data[:window]
        seg_valid = seg[~np.isnan(seg)]
        result[window - 1] = np.mean(seg_valid) if len(seg_valid) > 0 else np.nan
    if np.isnan(result[window - 1]):
        for i in range(window, len(data)):
            seg = data[i - window + 1 : i + 1]
            seg_valid = seg[~np.isnan(seg)]
            if len(seg_valid) > 0:
                result[i] = np.mean(seg_valid)
                break
    multiplier = 2.0 / (window + 1)
    for i in range(window, len(data)):
        if not np.isnan(data[i]) and not np.isnan(result[i - 1]):
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _calc_macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _calc_ema(data, fast)
    ema_slow = _calc_ema(data, slow)
    dif = np.where(~np.isnan(ema_fast) & ~np.isnan(ema_slow), ema_fast - ema_slow, np.nan)
    dea = _calc_ema(dif, signal)
    macd_bar = np.where(~np.isnan(dif) & ~np.isnan(dea), 2 * (dif - dea), np.nan)
    return dif, dea, macd_bar


def _calc_boll(data: np.ndarray, window: int = 20, std_dev: int = 2):
    upper, mid, lower = np.full_like(data, np.nan), np.full_like(data, np.nan), np.full_like(data, np.nan)
    for i in range(window - 1, len(data)):
        seg = data[i - window + 1 : i + 1]
        mu, sigma = np.mean(seg), np.std(seg)
        mid[i], upper[i], lower[i] = mu, mu + std_dev * sigma, mu - std_dev * sigma
    return upper, mid, lower


def _calc_kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 9):
    k, d, j = np.full_like(close, np.nan), np.full_like(close, np.nan), np.full_like(close, np.nan)
    for i in range(window - 1, len(close)):
        hh, ll = np.max(high[i - window + 1 : i + 1]), np.min(low[i - window + 1 : i + 1])
        rsv = ((close[i] - ll) / (hh - ll)) * 100 if hh != ll else 50.0
        if i == window - 1:
            k[i] = d[i] = rsv
        else:
            k[i] = 2.0 / 3 * k[i - 1] + 1.0 / 3 * rsv
            d[i] = 2.0 / 3 * d[i - 1] + 1.0 / 3 * k[i]
        j[i] = 3 * k[i] - 2 * d[i]
    return k, d, j


def _calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """计算 ATR（平均真实波幅），用于止损止盈"""
    result = np.full_like(close, np.nan, dtype=float)
    if len(close) < period + 1:
        return result
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    # Wilder's smoothed ATR
    result[period] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        result[i + 1] = (result[i] * (period - 1) + tr[i]) / period
    return result


def _calc_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> tuple:
    """计算 ADX（趋势强度）+ DI+/DI-（方向）"""
    adx = np.full_like(close, np.nan, dtype=float)
    plus_di = np.full_like(close, np.nan, dtype=float)
    minus_di = np.full_like(close, np.nan, dtype=float)
    if len(close) < period * 2:
        return adx, plus_di, minus_di

    tr = np.zeros(len(close))
    plus_dm = np.zeros(len(close))
    minus_dm = np.zeros(len(close))
    for i in range(1, len(close)):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        plus_dm[i] = up if up > down and up > 0 else 0
        minus_dm[i] = down if down > up and down > 0 else 0

    # Wilder's smoothing
    tr_smooth = np.full(len(close), np.nan)
    pdm_smooth = np.full(len(close), np.nan)
    mdm_smooth = np.full(len(close), np.nan)
    tr_smooth[period] = np.sum(tr[1:period + 1])
    pdm_smooth[period] = np.sum(plus_dm[1:period + 1])
    mdm_smooth[period] = np.sum(minus_dm[1:period + 1])

    for i in range(period + 1, len(close)):
        tr_smooth[i] = tr_smooth[i - 1] - tr_smooth[i - 1] / period + tr[i]
        pdm_smooth[i] = pdm_smooth[i - 1] - pdm_smooth[i - 1] / period + plus_dm[i]
        mdm_smooth[i] = mdm_smooth[i - 1] - mdm_smooth[i - 1] / period + minus_dm[i]

    for i in range(period, len(close)):
        if tr_smooth[i] > 0:
            plus_di[i] = 100 * pdm_smooth[i] / tr_smooth[i]
            minus_di[i] = 100 * mdm_smooth[i] / tr_smooth[i]
            dx_sum = 0
            for j in range(max(0, i - period + 1), i + 1):
                if plus_di[j] + minus_di[j] > 0:
                    dx_sum += 100 * abs(plus_di[j] - minus_di[j]) / (plus_di[j] + minus_di[j])
            adx[i] = dx_sum / period

    return adx, plus_di, minus_di


def _calc_cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """计算 CCI（商品通道指数）"""
    result = np.full_like(close, np.nan, dtype=float)
    if len(close) < period:
        return result
    tp = (high + low + close) / 3.0
    for i in range(period - 1, len(close)):
        sma_tp = np.mean(tp[i - period + 1:i + 1])
        mad = np.mean(np.abs(tp[i - period + 1:i + 1] - sma_tp))
        if mad > 0:
            result[i] = (tp[i] - sma_tp) / (0.015 * mad)
    return result


def _calc_wr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """计算 WR（威廉指标），值范围 -100~0"""
    result = np.full_like(close, np.nan, dtype=float)
    if len(close) < period:
        return result
    for i in range(period - 1, len(close)):
        hh = np.max(high[i - period + 1:i + 1])
        ll = np.min(low[i - period + 1:i + 1])
        if hh != ll:
            result[i] = (hh - close[i]) / (hh - ll) * -100
        else:
            result[i] = -50
    return result


# ==================== 分析与汇总 ====================

def generate_trading_advice(realtime: dict, technical: dict) -> dict:
    """
    生成交易建议：综合评分 + 关键价位 + 操作建议 + 仓位参考
    基于多指标共振，纯数据驱动，仅供参考
    """
    price = realtime.get("最新价") or 0
    pe = realtime.get("市盈率-动态")
    pb = realtime.get("市净率")
    # ETF等品种PE/PB可能返回"-"字符串，转为None统一处理
    if isinstance(pe, str):
        pe = None
    if isinstance(pb, str):
        pb = None

    # ========== 一、多因子综合评分（百分制） ==========
    score_detail = {}
    total = 0

    # 因子1：趋势 (0-30分) — 均线 + MACD + ADX 趋势强度
    ma_arr = technical.get("均线排列", "")
    macd_sig = technical.get("MACD信号", "")
    adx = technical.get("ADX")
    adx_state = technical.get("ADX状态", "")
    di_dir = technical.get("DI方向", "")

    if "多头排列" in ma_arr:
        trend_score = 28
        trend_note = "均线多头排列"
    elif "空头排列" in ma_arr:
        trend_score = 5
        trend_note = "均线空头排列"
    else:
        trend_score = 18
        trend_note = "均线交叉震荡"

    # ADX 趋势强度修正
    if adx is not None:
        if adx > 40:
            trend_score += 4
            trend_note += f"，ADX={adx:.1f}强趋势"
        elif adx > 25:
            trend_score += 2
            trend_note += f"，ADX={adx:.1f}趋势明确"
        elif adx < 20:
            trend_score -= 3
            trend_note += f"，ADX={adx:.1f}趋势疲弱"

    # MACD 额外加成
    if "金叉" in macd_sig:
        trend_score = min(30, trend_score + 3)
        trend_note += "，MACD金叉"
    elif "死叉" in macd_sig:
        trend_score = max(0, trend_score - 3)
        trend_note += "，MACD死叉"

    trend_score = max(0, min(30, trend_score))
    score_detail["趋势因子"] = {"得分": trend_score, "满分": 30, "说明": trend_note}
    total += trend_score

    # 因子2：动量 (0-25分)
    rsi = technical.get("RSI14")
    kdj_s = technical.get("KDJ状态", "")
    chg_5 = technical.get("近5日涨跌幅")
    chg_20 = technical.get("近20日涨跌幅")

    momentum_score = 15  # 基准分
    momentum_parts = []

    if rsi is not None:
        if 40 <= rsi <= 60:
            momentum_score += 5
            momentum_parts.append(f"RSI({rsi})处于中性区间，动能均衡")
        elif 30 <= rsi < 40:
            momentum_score += 3
            momentum_parts.append(f"RSI({rsi})偏低，短期偏弱但有反弹空间")
        elif 60 < rsi <= 70:
            momentum_score += 0
            momentum_parts.append(f"RSI({rsi})偏高，上涨动能趋缓")
        elif rsi < 30:
            momentum_score -= 2
            momentum_parts.append(f"RSI({rsi})超卖，存在技术性反弹需求")
        elif rsi > 70:
            momentum_score -= 5
            momentum_parts.append(f"RSI({rsi})超买，回调风险加大")

    if chg_5 is not None:
        if 1 <= chg_5 <= 5:
            momentum_score += 3
            momentum_parts.append(f"近5日涨{chg_5}%，温和上涨")
        elif chg_5 > 10:
            momentum_score -= 2
            momentum_parts.append(f"近5日涨{chg_5}%，短线过热")
        elif chg_5 < -5:
            momentum_score += 2
            momentum_parts.append(f"近5日跌{abs(chg_5)}%，超跌反弹概率增大")

    if "超卖" in kdj_s:
        momentum_score += 3
        momentum_parts.append("KDJ超卖区，技术反弹信号")
    elif "超买" in kdj_s:
        momentum_score -= 4
        momentum_parts.append("KDJ超买区，技术回调信号")

    momentum_score = max(0, min(25, momentum_score))
    score_detail["动量因子"] = {"得分": momentum_score, "满分": 25, "说明": "；".join(momentum_parts) if momentum_parts else "动量中性"}
    total += momentum_score

    # 因子3：量价配合 (0-20分)
    vol_rel = technical.get("量价关系", "")
    hs = realtime.get("换手率") or 0

    if "健康上涨" in vol_rel:
        vol_score = 20
        vol_note = "价涨量增，量价配合良好"
    elif "缩量调整" in vol_rel:
        vol_score = 14
        vol_note = "缩量调整，抛压减轻"
    elif "上涨乏力" in vol_rel:
        vol_score = 10
        vol_note = "价涨量缩，上涨动力不足"
    elif "抛压加大" in vol_rel:
        vol_score = 6
        vol_note = "价跌量增，抛压明显"
    else:
        vol_score = 12
        vol_note = "量价关系中性"

    if hs < 0.3:
        vol_score -= 3
        vol_note += "（换手率极低，流动性偏弱）"
    elif hs > 15:
        vol_score -= 5
        vol_note += "（换手率过高，投机氛围浓）"

    vol_score = max(0, min(20, vol_score))
    score_detail["量价因子"] = {"得分": vol_score, "满分": 20, "说明": vol_note}
    total += vol_score

    # 因子4：估值 (0-15分)
    if pe is not None and pe > 0:
        if pe < 15:
            val_score = 15
            val_note = f"PE={pe}，估值偏低，安全边际充足"
        elif pe < 30:
            val_score = 12
            val_note = f"PE={pe}，估值合理"
        elif pe < 60:
            val_score = 8
            val_note = f"PE={pe}，估值中等偏高"
        elif pe < 100:
            val_score = 5
            val_note = f"PE={pe}，估值偏高需谨慎"
        else:
            val_score = 2
            val_note = f"PE={pe}，估值严重偏高"
    elif pe is not None and pe < 0:
        val_score = 2
        val_note = "公司亏损，PE为负"
    else:
        val_score = 10
        val_note = "PE数据缺失，按中性处理"

    if pb is not None and pb > 0:
        if pb < 1:
            val_score = min(15, val_score + 2)
            val_note += f"；PB={pb}，破净状态"
        elif pb > 10:
            val_score = max(0, val_score - 2)
            val_note += f"；PB={pb}，净资产溢价较高"

    score_detail["估值因子"] = {"得分": val_score, "满分": 15, "说明": val_note}
    total += val_score

    # 因子5：位置 (0-10分)
    boll_upper = technical.get("BOLL_UPPER")
    boll_mid = technical.get("BOLL_MID")
    boll_lower = technical.get("BOLL_LOWER")
    ma60 = technical.get("MA60")

    pos_score = 6
    pos_parts = []

    if boll_upper and boll_mid and boll_lower and price:
        if price >= boll_upper:
            pos_score = 3
            pos_parts.append(f"股价({price})触及布林上轨({boll_upper})，处于高位")
        elif price <= boll_lower:
            pos_score = 8
            pos_parts.append(f"股价({price})触及布林下轨({boll_lower})，处于低位")
        elif price > boll_mid:
            pos_score = 5
            pos_parts.append(f"股价({price})在布林中轨({boll_mid})上方")
        else:
            pos_score = 7
            pos_parts.append(f"股价({price})在布林中轨({boll_mid})下方")

    if ma60 and price:
        if price > ma60:
            pos_score = min(10, pos_score + 2)
            pos_parts.append(f"站上MA60({ma60})，中期趋势偏多")
        else:
            pos_score = max(0, pos_score - 2)
            pos_parts.append(f"低于MA60({ma60})，中期趋势偏空")

    pos_score = max(0, min(10, pos_score))
    score_detail["位置因子"] = {"得分": pos_score, "满分": 10, "说明": "；".join(pos_parts) if pos_parts else "位置中性"}
    total += pos_score

    # ========== 因子6：指标共振加分 (0-10分额外) ==========
    resonance_score = 0
    resonance_parts = []
    # 统计多头/空头信号数量
    bull_count = 0
    bear_count = 0

    # MA方向
    if "多头排列" in ma_arr: bull_count += 1
    elif "空头排列" in ma_arr: bear_count += 1

    # MACD方向
    if "金叉" in macd_sig or "多头运行" in macd_sig: bull_count += 1
    elif "死叉" in macd_sig or "空头运行" in macd_sig: bear_count += 1

    # RSI
    if rsi is not None:
        if rsi > 50: bull_count += 1
        else: bear_count += 1

    # KDJ
    if "多头" in kdj_s: bull_count += 1
    elif "空头" in kdj_s: bear_count += 1

    # CCI
    cci_val = technical.get("CCI")
    cci_state = technical.get("CCI状态", "")
    if cci_val is not None:
        if cci_val > 0: bull_count += 1
        else: bear_count += 1

    # DI方向
    if "多头主导" in di_dir: bull_count += 1
    elif "空头主导" in di_dir: bear_count += 1

    if bull_count >= 4:
        resonance_score = 10
        resonance_parts.append(f"🟢 {bull_count}指标共振多头（MA/MACD/RSI/KDJ/CCI/DI）")
    elif bull_count >= 3:
        resonance_score = 6
        resonance_parts.append(f"🟡 {bull_count}指标偏多共振")
    elif bear_count >= 4:
        resonance_score = -5
        resonance_parts.append(f"🔴 {bear_count}指标共振空头，注意风险")
    elif bear_count >= 3:
        resonance_score = -2
        resonance_parts.append(f"🟠 {bear_count}指标偏空共振")

    # CCI+MACD+BOLL 三指标特殊共振 (R36)
    if "超卖" in cci_state and price and boll_lower and price <= boll_lower * 1.02:
        resonance_score += 3
        resonance_parts.append("CCI+BOLL超卖共振，反弹概率增大")
    elif "超买" in cci_state and price and boll_upper and price >= boll_upper * 0.98:
        resonance_score -= 3
        resonance_parts.append("CCI+BOLL超买共振，回调风险加大")

    resonance_score = max(-5, min(10, resonance_score))
    if resonance_parts:
        score_detail["共振加成"] = {"得分": resonance_score, "满分": 10, "说明": "；".join(resonance_parts)}
        total += resonance_score

    total = round(total, 1)

    # 综合评级
    if total >= 80:
        rating = "强烈看好 🌟"
        rating_desc = "多维度指标共振向上，技术面信号较为积极"
    elif total >= 65:
        rating = "偏多 ✅"
        rating_desc = "多数指标偏积极，可适当关注"
    elif total >= 45:
        rating = "中性观望 ⏸️"
        rating_desc = "多空力量均衡，方向不明朗，建议等待明确信号"
    elif total >= 30:
        rating = "偏空 ⚠️"
        rating_desc = "多数指标偏弱，注意风险控制"
    else:
        rating = "谨慎回避 🔴"
        rating_desc = "技术面全面走弱，建议观望或减仓"

    # ========== 二、关键价位 ==========
    key_levels = {}

    # 支撑位
    supports = []
    if boll_lower:
        supports.append({"价位": boll_lower, "类型": "布林下轨"})
    if ma60:
        supports.append({"价位": ma60, "类型": "MA60均线"})

    # 取近期低点（从量价判断）
    supports.sort(key=lambda x: x["价位"], reverse=True)

    # 压力位
    resistances = []
    if boll_upper:
        resistances.append({"价位": boll_upper, "类型": "布林上轨"})
    if boll_mid and price and price < boll_mid:
        resistances.append({"价位": boll_mid, "类型": "布林中轨（已破转压）"})

    resistances.sort(key=lambda x: x["价位"])

    if not supports:
        supports.append({"价位": round(price * 0.95, 2), "类型": "估算支撑（5%下行）"})
    if not resistances:
        resistances.append({"价位": round(price * 1.05, 2), "类型": "估算压力（5%上行）"})

    # ATR 止损止盈
    atr_val = technical.get("ATR")
    if atr_val and price:
        stop_loss = round(price - atr_val * 3, 2)
        take_profit = round(price + atr_val * 5, 2)
        key_levels["ATR止损"] = [{"价位": stop_loss, "类型": f"ATR×3（{atr_val:.4f}）"}]
        key_levels["ATR止盈"] = [{"价位": take_profit, "类型": f"ATR×5（{atr_val:.4f}）"}]

    key_levels["支撑位"] = supports
    key_levels["压力位"] = resistances

    # ========== 三、操作建议 ==========
    # 基于评分和关键信号给出具体建议
    suggestions = []

    # 趋势判断
    if "多头排列" in ma_arr and total >= 65:
        suggestions.append("🔹 中期趋势向上，可沿MA10/MA20分批布局")
    elif "空头排列" in ma_arr:
        suggestions.append("🔹 空头趋势中，建议等待均线走平或金叉信号再考虑介入")
    else:
        suggestions.append("🔹 趋势不明，建议以观望为主，减少操作频率")

    # ADX 趋势强度
    if adx is not None:
        if adx > 40:
            suggestions.append(f"🔹 ADX={adx:.1f}，趋势强劲，顺势操作胜率较高")
        elif adx < 20:
            suggestions.append(f"🔹 ADX={adx:.1f}，处于无趋势震荡，宜高抛低吸")

    # MACD 信号
    if "金叉" in macd_sig:
        suggestions.append("🔹 MACD刚形成金叉，关注能否持续放量确认")
    elif "死叉" in macd_sig:
        suggestions.append("🔹 MACD死叉信号，短期注意回调风险")

    # RSI 信号
    if rsi and rsi < 30:
        suggestions.append("🔹 RSI进入超卖区，激进者可左侧分批试探，注意控制仓位")
    elif rsi and rsi > 70:
        suggestions.append("🔹 RSI超买，持有者可考虑分批止盈，追高需谨慎")

    # KDJ 信号
    if "超卖" in kdj_s:
        suggestions.append("🔹 KDJ超卖，短期存在技术反弹需求，可关注底部放量信号")
    elif "超买" in kdj_s:
        suggestions.append("🔹 KDJ超买且J值高位，短期调整压力增大")

    # CCI 信号
    if cci_state:
        if "极度超卖" in cci_state:
            suggestions.append("🔹 CCI极度超卖，罕见极端值，反弹概率极高")
        elif "极度超买" in cci_state:
            suggestions.append("🔹 CCI极度超买，罕见极端值，回调概率极高")

    # ATR 止损止盈
    atr_val = technical.get("ATR")
    if atr_val and price:
        sl = round(price - atr_val * 3, 2)
        tp = round(price + atr_val * 5, 2)
        suggestions.append(f"🎯 ATR止损: {sl}（ATR×3）| 止盈: {tp}（ATR×5）")

    # 估值信号
    if pb is not None and pb < 1:
        suggestions.append("🔹 PB破净，长期价值投资者可关注，但需确认资产质量")
    if pe is not None and pe < 0:
        suggestions.append("⚠️ 公司处于亏损状态，不建议价值投资逻辑介入")

    # ========== 四、仓位参考 ==========
    if total >= 75:
        position = "可适当重仓（60-80%）"
        position_note = "多指标共振向上，可相对积极"
    elif total >= 60:
        position = "中等仓位（40-60%）"
        position_note = "信号偏多但非全面共振，适度参与"
    elif total >= 45:
        position = "轻仓试探（20-40%）"
        position_note = "多空胶着，小仓位等待方向明确"
    elif total >= 30:
        position = "极轻仓或空仓（0-20%）"
        position_note = "信号偏弱，保护本金为上"
    else:
        position = "建议空仓观望（0%）"
        position_note = "技术面全面走弱，现金为王"

    # ========== 五、交易信号 ==========
    atr_val = technical.get("ATR")
    if total >= 80:
        signal = "🟢 强烈买入"
        signal_desc = "多维度共振向上，可积极建仓"
    elif total > 65:
        signal = "🟢 买入"
        signal_desc = "评分突破买入线(65)，可考虑入场"
    elif total >= 45:
        signal = "⏸️ 持有/观望"
        signal_desc = "未触发买卖信号，持仓观望或等待"
    elif total >= 40:
        signal = "🟡 减仓警戒"
        signal_desc = "接近卖出线(40)，注意风险，可适度减仓"
    else:
        signal = "🔴 卖出"
        signal_desc = "评分跌破卖出线(40)，建议离场"

    # ATR 风控价位
    if atr_val and price:
        stop_loss = round(price - atr_val * 3, 2)
        take_profit = round(price + atr_val * 5, 2)
    else:
        stop_loss = round(price * 0.95, 2)
        take_profit = round(price * 1.10, 2)

    return {
        "综合评分": total,
        "综合评级": rating,
        "评级说明": rating_desc,
        "评分明细": score_detail,
        "关键价位": key_levels,
        "操作建议": suggestions,
        "仓位参考": {
            "建议": position,
            "说明": position_note,
        },
        "交易信号": {
            "信号": signal,
            "说明": signal_desc,
            "止损价": stop_loss,
            "止盈价": take_profit,
        },
    }


# ==================== 回测引擎 ====================

def run_backtest(code: str, days: int = 500) -> dict:
    """
    历史回测：基于评分体系的买卖信号 + ATR止损止盈
    返回：绩效指标 + 逐笔交易记录
    """
    # 0. 获取股票名称
    stock_name = code
    try:
        rt = get_realtime_quote(code)
        if "error" not in rt:
            stock_name = rt.get("名称", code)
    except Exception:
        pass
    if stock_name == code:
        # 从 stocks.json 查找
        import os as _os2
        _cfg_path = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), "stocks.json")
        if _os2.path.exists(_cfg_path):
            try:
                with open(_cfg_path, "r") as _f2:
                    _cfg2 = json.loads(_f2.read())
                    for s in _cfg2.get("defaults", []):
                        if s["code"] == code:
                            stock_name = s["name"]
                            break
            except Exception:
                pass

    # 1. 获取扩展历史K线
    df = None
    for name, fetcher in [("腾讯", _fetch_kline_tencent), ("搜狐", _fetch_kline_sohu)]:
        try:
            df = fetcher(code, days + 120)
            if not df.empty:
                break
        except Exception:
            continue

    if df is None or df.empty:
        return {"error": "无法获取回测所需的历史K线数据"}

    close = df["收盘"].values.astype(float)
    high = df["最高"].values.astype(float)
    low = df["最低"].values.astype(float)
    volume = df["成交量"].values.astype(float)
    dates = df["日期"].values

    if len(close) < 180:
        return {"error": f"历史数据不足（仅{len(close)}日，需要≥180日）"}

    # 2. 预计算指标（一次性全序列计算，比逐日滑窗快得多）
    ma5 = _calc_ma(close, 5)
    ma10 = _calc_ma(close, 10)
    ma20 = _calc_ma(close, 20)
    ma60 = _calc_ma(close, 60)
    rsi14 = _calc_rsi(close, 14)
    dif, dea, macd_bar = _calc_macd(close)
    upper, mid, lower = _calc_boll(close, 20)
    k, d, j = _calc_kdj(high, low, close, 9)
    adx, plus_di, minus_di = _calc_adx(high, low, close, 14)
    cci = _calc_cci(high, low, close, 14)
    wr = _calc_wr(high, low, close, 14)
    atr = _calc_atr(high, low, close, 14)

    def _v(arr, idx):
        val = arr[idx]
        return round(float(val), 4) if val is not None and not np.isnan(val) else None

    # 3. 逐日评分 + 信号
    scores = []
    positions = []  # 持仓记录: (入场日, 入场价, 出场日, 出场价, 原因)
    holding = None  # 当前持仓

    for i in range(120, len(close)):  # 从第120天开始（保证指标有效）
        price = close[i]

        # 构建当日技术指标快照
        tech = {}
        mas = [_v(ma5,i), _v(ma10,i), _v(ma20,i), _v(ma60,i)]
        mas_clean = [m for m in mas if m is not None]

        # 均线排列
        if len(mas_clean) >= 3:
            if mas_clean == sorted(mas_clean, reverse=True):
                tech["均线排列"] = "多头排列 📈"
            elif mas_clean == sorted(mas_clean, reverse=False):
                tech["均线排列"] = "空头排列 📉"
            else:
                tech["均线排列"] = "交叉震荡 ↔️"

        # MACD 信号
        dv, dev = _v(dif,i), _v(dea,i)
        if dv is not None and dev is not None:
            if i > 0:
                d_prev = _v(dif, i-1)
                e_prev = _v(dea, i-1)
                if d_prev and e_prev:
                    if dif[i] > dea[i] and d_prev <= e_prev:
                        tech["MACD信号"] = "金叉形成 ✨"
                    elif dif[i] < dea[i] and d_prev >= e_prev:
                        tech["MACD信号"] = "死叉形成 ⚠️"
                    elif dif[i] > dea[i]:
                        tech["MACD信号"] = "多头运行 ↗️"
                    else:
                        tech["MACD信号"] = "空头运行 ↘️"

        # RSI
        rv = _v(rsi14, i)
        if rv is not None:
            tech["RSI14"] = rv
            if rv > 70: tech["RSI状态"] = "超买区间 🟠"
            elif rv < 30: tech["RSI状态"] = "超卖区间 🟡"
            else: tech["RSI状态"] = "正常区间 ⚪"

        # KDJ
        kv, dv2 = _v(k,i), _v(d,i)
        if kv is not None and dv2 is not None:
            if kv > 80 and dv2 > 80: tech["KDJ状态"] = "超买区 🔴"
            elif kv < 20 and dv2 < 20: tech["KDJ状态"] = "超卖区 🟢"
            elif kv > dv2: tech["KDJ状态"] = "多头 ↗️"
            else: tech["KDJ状态"] = "空头 ↘️"

        # ADX
        av = _v(adx, i)
        if av is not None:
            tech["ADX"] = av
            if av > 40: tech["ADX状态"] = "强趋势 🔥"
            elif av > 25: tech["ADX状态"] = "趋势运行 ➡️"
            elif av > 20: tech["ADX状态"] = "弱趋势 💤"
            else: tech["ADX状态"] = "无趋势/震荡 🔄"

        # CCI
        cv = _v(cci, i)
        if cv is not None:
            tech["CCI"] = cv

        # 量价
        if i >= 1:
            if close[i] > close[i-1] and volume[i] > volume[i-1]:
                tech["量价关系"] = "价涨量增 📈（健康上涨）"
            elif close[i] > close[i-1]:
                tech["量价关系"] = "价涨量缩 ↗️（上涨乏力）"
            elif volume[i] > volume[i-1]:
                tech["量价关系"] = "价跌量增 📉（抛压加大）"
            else:
                tech["量价关系"] = "价跌量缩 ↘️（缩量调整）"

        # 布林
        if not np.isnan(upper[i]):
            tech["BOLL_UPPER"] = round(float(upper[i]), 2)
            tech["BOLL_MID"] = round(float(mid[i]), 2)
            tech["BOLL_LOWER"] = round(float(lower[i]), 2)
        tech["MA60"] = _v(ma60, i)
        tech["ATR"] = _v(atr, i)

        # 构建虚拟 realtime
        rt = {"最新价": price, "换手率": None}
        if i >= 1:
            rt["涨跌幅"] = round((close[i] / close[i-1] - 1) * 100, 2)
        else:
            rt["涨跌幅"] = 0

        # 评分
        advice = generate_trading_advice(rt, tech)
        score = advice["综合评分"]
        scores.append((dates[i], score, price))

        # 交易信号
        prev_score = scores[-2][1] if len(scores) >= 2 else None

        atr_val = _v(atr, i)
        stop_loss = price - atr_val * 3 if atr_val else price * 0.9
        take_profit = price + atr_val * 5 if atr_val else price * 1.2

        if holding is None:
            # 买入信号：评分突破65 且 前日≤65
            if prev_score is not None and prev_score <= 65 and score > 65:
                holding = {"entry_day": i, "entry_price": price, "entry_date": dates[i], "entry_score": score}
        else:
            # 卖出信号：评分<40 或 触发止损/止盈
            sell_reason = None
            if score < 40:
                sell_reason = "评分破40"
            elif price <= stop_loss:
                sell_reason = f"ATR止损({stop_loss:.2f})"
            elif price >= take_profit:
                sell_reason = f"ATR止盈({take_profit:.2f})"

            if sell_reason:
                holding["exit_day"] = i
                holding["exit_price"] = price
                holding["exit_date"] = dates[i]
                holding["exit_score"] = score
                holding["reason"] = sell_reason
                holding["days_held"] = i - holding["entry_day"]
                holding["return_pct"] = round((price / holding["entry_price"] - 1) * 100, 2)
                positions.append(holding)
                holding = None

    # 平掉最后持仓
    if holding is not None:
        last_i = len(close) - 1
        holding["exit_day"] = last_i
        holding["exit_price"] = close[-1]
        holding["exit_date"] = dates[-1]
        holding["exit_score"] = scores[-1][1] if scores else 0
        holding["reason"] = "回测结束平仓"
        holding["days_held"] = last_i - holding["entry_day"]
        holding["return_pct"] = round((close[-1] / holding["entry_price"] - 1) * 100, 2)
        positions.append(holding)

    # 4. 绩效统计
    if not positions:
        return {"error": "回测期间无交易信号", "总交易日": len(close) - 120, "评分序列": scores[-30:]}

    returns = [p["return_pct"] for p in positions]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    total_return = sum(returns)
    win_rate = round(len(wins) / len(returns) * 100, 1) if returns else 0
    avg_win = round(np.mean(wins), 2) if wins else 0
    avg_loss = round(np.mean(losses), 2) if losses else 0
    profit_factor = round(abs(sum(wins) / sum(losses)), 2) if sum(losses) != 0 else float('inf')
    avg_days = round(np.mean([p["days_held"] for p in positions]), 1)

    # 年化收益
    total_days = len(close) - 120
    years = total_days / 252
    annual_return = round((1 + total_return / 100) ** (1 / max(years, 0.5)) - 1, 4) * 100 if years > 0 else 0

    # 最大回撤（基于评分序列的累计收益曲线）
    cumulative = [0]
    for s in scores:
        cumulative.append(cumulative[-1])
    cum_max = 0
    for i in range(len(cumulative)):
        cum_max = max(cum_max, cumulative[i])

    # 简化最大回撤：从交易记录计算
    peak = 0
    max_drawdown = 0
    running = 0
    for r in returns:
        running += r
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_drawdown:
            max_drawdown = dd

    # 夏普比率（简化）
    if len(returns) >= 2:
        sharpe = round((np.mean(returns) / 100) / max(np.std(returns) / 100, 0.001) * np.sqrt(252 / max(avg_days, 1)), 2)
    else:
        sharpe = 0

    # 评分信号统计
    score_values = [s[1] for s in scores]
    avg_score = round(np.mean(score_values), 1) if score_values else 0
    max_score = max(score_values) if score_values else 0
    min_score = min(score_values) if score_values else 0

    return {
        "股票名称": stock_name,
        "股票代码": code,
        "回测区间": f"{dates[120]} ~ {dates[-1]}",
        "总交易日": total_days,
        "交易次数": len(positions),
        "胜率": f"{win_rate}%",
        "总收益率": f"{total_return:+.2f}%",
        "年化收益率": f"{annual_return:+.2f}%",
        "夏普比率": sharpe,
        "最大回撤": f"-{max_drawdown:.2f}%",
        "平均盈利": f"{avg_win:+.2f}%",
        "平均亏损": f"{avg_loss:+.2f}%",
        "盈亏比": profit_factor,
        "平均持仓天数": avg_days,
        "平均评分": avg_score,
        "评分范围": f"{min_score}~{max_score}",
        "交易记录": positions,
        "评分序列": scores[-60:],
    }


# ==================== 走势预测 ====================


def _garch_forecast_var(returns: np.ndarray, horizon: int = 30) -> tuple:
    """GARCH(1,1)波动率预测。网格搜索MLE估计参数，预测未来horizon天条件方差路径。"""
    n = len(returns)
    if n < 30:
        return None, float(np.std(returns)), False

    mu = float(np.mean(returns))
    centered = returns - mu
    uncond_var = float(np.var(centered))

    if uncond_var < 1e-8:
        return None, float(np.sqrt(uncond_var)) if uncond_var > 0 else 0.01, False

    def _ll(omega, alpha, beta):
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 0.999:
            return -1e9
        sigma2 = np.zeros(n)
        sigma2[0] = uncond_var
        ll_val = -0.5 * np.log(2 * np.pi * sigma2[0]) - 0.5 * centered[0]**2 / sigma2[0]
        for t in range(1, n):
            sigma2[t] = omega + alpha * centered[t-1]**2 + beta * sigma2[t-1]
            if sigma2[t] <= 1e-10:
                return -1e9
            ll_val += -0.5 * np.log(2 * np.pi * sigma2[t]) - 0.5 * centered[t]**2 / sigma2[t]
        return ll_val

    # coarse grid search
    best_ll, best = -1e9, (1e-6, 0.08, 0.85)
    for omega in np.logspace(-7, -4, 12):
        for alpha in np.linspace(0.02, 0.25, 10):
            for beta in np.linspace(0.70, 0.97, 12):
                ll = _ll(omega, alpha, beta)
                if ll > best_ll:
                    best_ll, best = ll, (omega, alpha, beta)

    # fine grid around best
    o0, a0, b0 = best
    for omega in np.linspace(o0 * 0.3, o0 * 3, 8):
        for alpha in np.linspace(max(0.01, a0 - 0.05), min(0.30, a0 + 0.06), 8):
            for beta in np.linspace(max(0.65, b0 - 0.05), min(0.98, b0 + 0.05), 8):
                ll = _ll(omega, alpha, beta)
                if ll > best_ll:
                    best_ll, best = ll, (omega, alpha, beta)

    omega, alpha, beta = best
    if alpha + beta >= 0.999:
        return None, float(np.sqrt(uncond_var)), False

    # compute full sigma2 series
    sigma2 = np.zeros(n)
    sigma2[0] = uncond_var
    for t in range(1, n):
        sigma2[t] = omega + alpha * centered[t-1]**2 + beta * sigma2[t-1]

    sigma2_now = float(sigma2[-1])
    uncond_long = omega / (1 - alpha - beta)
    persistence = alpha + beta

    # forecast path: E[sigma^2_{t+h} | F_t], h=1..horizon
    var_path = np.zeros(horizon)
    var_path[0] = sigma2_now
    for h in range(1, horizon):
        var_path[h] = uncond_long + persistence ** h * (sigma2_now - uncond_long)

    return var_path, float(np.sqrt(uncond_long)), True


def generate_price_forecast(realtime: dict, technical: dict) -> dict:
    """
    基于历史波动率和趋势动量，生成1/5/10/30日价格预测区间。
    纯统计推演，不代表未来实际走势。
    """
    price = realtime.get("最新价")
    if not price:
        return {"error": "缺少当前价格"}

    closes = technical.get("_收盘序列", [])
    if len(closes) < 20:
        return {"error": "历史数据不足（需≥20个交易日）"}

    closes = np.array(closes, dtype=float)

    # ---- 基础统计量 ----
    daily_returns = np.diff(closes) / closes[:-1]           # 日收益率序列
    avg_return = float(np.mean(daily_returns[-20:]))         # 近20日均收益率
    std_return = float(np.std(daily_returns[-60:]))           # 60日波动率
    if std_return == 0:
        std_return = 0.01  # 防除零

    # GARCH(1,1) 波动率预测
    garch_var_path, garch_uncond_vol, garch_ok = _garch_forecast_var(daily_returns, 30)

    # ---- 趋势识别 ----
    ma5 = technical.get("MA5")
    ma20 = technical.get("MA20")
    ma60 = technical.get("MA60")
    chg_20d = technical.get("近20日涨跌幅") or 0

    # 趋势方向与强度
    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            trend_bias = 1.0       # 强上升趋势
            trend_label = "上升趋势 📈"
        elif ma5 > ma20:
            trend_bias = 0.5       # 短期偏多
            trend_label = "短期偏多 ↗️"
        elif ma5 < ma20 < ma60:
            trend_bias = -1.0      # 强下降趋势
            trend_label = "下降趋势 📉"
        elif ma5 < ma20:
            trend_bias = -0.5      # 短期偏空
            trend_label = "短期偏空 ↘️"
        else:
            trend_bias = 0.0
            trend_label = "横盘震荡 ↔️"
    else:
        trend_bias = 0.0
        trend_label = "趋势不明"

    # 近期动量（偏重近5日）
    if len(daily_returns) >= 5:
        recent_momentum = float(np.mean(daily_returns[-5:])) * 5  # 近5日累计收益
    else:
        recent_momentum = avg_return

    # ---- 多周期预测 ----
    horizons = [
        {"name": "明日(1日)", "days": 1, "key": "day1"},
        {"name": "短期(5日)", "days": 5, "key": "day5"},
        {"name": "中期(10日)", "days": 10, "key": "day10"},
        {"name": "月度(30日)", "days": 30, "key": "day30"},
    ]

    forecasts = {}
    for h in horizons:
        d = h["days"]

        # === 基准预测（趋势加权） ===
        # 近20日均收益 * 天数 + 趋势偏置 * 波动率 * sqrt(天数) * 0.3
        base_return = avg_return * d + trend_bias * std_return * np.sqrt(d) * 0.3
        base_price = round(price * (1 + base_return), 2)

        # === 置信区间（基于历史波动率） ===
        # 68% 置信区间 (±1σ)
        if garch_ok:
            total_var = max(sum(garch_var_path[:d]), 0.0001)
            sigma = np.sqrt(float(total_var))
        else:
            sigma = std_return * np.sqrt(d)
        ci68_low = round(price * (1 + base_return - sigma), 2)
        ci68_high = round(price * (1 + base_return + sigma), 2)
        # 95% 置信区间 (±2σ)
        ci95_low = round(price * (1 + base_return - 2 * sigma), 2)
        ci95_high = round(price * (1 + base_return + 2 * sigma), 2)

        # 区间下限不低于0
        ci68_low = max(0.01, ci68_low)
        ci95_low = max(0.01, ci95_low)

        # === 三情景推演 ===
        # 乐观：趋势 + 1.5σ
        bull_return = base_return + 1.5 * sigma
        bull_price = round(price * (1 + bull_return), 2)
        # 基准
        base = base_price
        # 悲观：趋势 - 1.5σ
        bear_return = base_return - 1.5 * sigma
        bear_price = round(price * (1 + bear_return), 2)
        bear_price = max(0.01, bear_price)

        # 情景概率（基于趋势方向调整）
        if trend_bias > 0.5:
            bull_prob, base_prob, bear_prob = 45, 35, 20
        elif trend_bias > 0:
            bull_prob, base_prob, bear_prob = 35, 40, 25
        elif trend_bias < -0.5:
            bull_prob, base_prob, bear_prob = 20, 35, 45
        elif trend_bias < 0:
            bull_prob, base_prob, bear_prob = 25, 40, 35
        else:
            bull_prob, base_prob, bear_prob = 30, 40, 30

        # 涨跌概率
        up_pct = round(base_return * 100, 2)

        forecasts[h["key"]] = {
            "周期": h["name"],
            "预测天数": d,
            "当前价": price,
            "基准预测": base,
            "预计涨跌": f"{'+' if up_pct >= 0 else ''}{up_pct}%",
            "68%置信区间": f"{ci68_low} ~ {ci68_high}",
            "95%置信区间": f"{ci95_low} ~ {ci95_high}",
            "情景分析": {
                "乐观": {"价格": bull_price, "概率": f"{bull_prob}%"},
                "基准": {"价格": base, "概率": f"{base_prob}%"},
                "悲观": {"价格": bear_price, "概率": f"{bear_prob}%"},
            },
        }

    # ---- 综合置信度评估 ----
    # 趋势越清晰 + 波动率越低 → 置信度越高（封顶75%，股市无绝对）
    trend_strength = abs(trend_bias)
    vol_rank = min(1.0, 0.015 / max(std_return, 0.005))  # 波动率越低越好，防除零
    raw_confidence = (trend_strength * 0.5 + vol_rank * 0.5) * 100
    # 历史数据量惩罚：不足60日打8折
    if len(closes) < 60:
        raw_confidence *= 0.8
    confidence = min(75, round(raw_confidence))  # 封顶75%

    if confidence >= 70:
        conf_label = "较高 ✅"
        conf_note = "趋势清晰且波动率适中，预测区间参考价值较高"
    elif confidence >= 40:
        conf_label = "一般 ⚪"
        conf_note = "趋势或波动率存在不确定性，预测区间仅供参考"
    else:
        conf_label = "较低 ⚠️"
        conf_note = "趋势不明或波动率偏高，价格随机波动主导，预测准确性有限"

    # ---- 关键观察点 ----
    observations = []
    if trend_bias > 0:
        observations.append(f"当前处于{trend_label}，顺势操作胜率较高")
    elif trend_bias < 0:
        observations.append(f"当前处于{trend_label}，不宜逆势做多")
    else:
        observations.append("趋势不明，短期价格以随机波动为主")

    current_vol = np.sqrt(float(garch_var_path[0])) if garch_ok else std_return
    if current_vol > 0.03:
        observations.append(f"日波动率{current_vol*100:.1f}%偏高（GARCH{'条件' if garch_ok else '历史'}), 短期波动风险较大")
    elif current_vol < 0.01:
        observations.append(f"日波动率{current_vol*100:.1f}%极低（GARCH{'条件' if garch_ok else '历史'}), 可能出现大幅波动")

    # 关键均线位置
    if ma20:
        observations.append(f"MA20={ma20}，是短期多空分界线")
    if ma60:
        observations.append(f"MA60={ma60}，是中期趋势生命线")

    return {
        "预测基准日": datetime.now().strftime("%Y-%m-%d"),
        "当前趋势": trend_label,
        "日波动率": f"{(np.sqrt(float(garch_var_path[0]))*100 if garch_ok else std_return*100):.2f}%",
        "预测置信度": f"{confidence}%（{conf_label}）",
        "置信度说明": conf_note,
        "各周期预测": forecasts,
        "观察要点": observations,
        "重要提示": "以上预测基于历史统计模型，实际走势受政策、资金、情绪等多因素影响，偏差可能很大。仅供参考，不构成投资建议。",
    }


def detect_risks(realtime: dict, technical: dict) -> list:
    risks = []
    hs = realtime.get("换手率") or 0
    if hs > 20:
        risks.append({"级别": "高", "信号": f"换手率 {hs:.1f}%（>20%），高度投机"})
    elif hs > 10:
        risks.append({"级别": "中", "信号": f"换手率 {hs:.1f}%（>10%），交投活跃注意风险"})

    pe = realtime.get("市盈率-动态") or 0
    if pe and isinstance(pe, str):
        pe = None  # ETF等品种PE为"-"，按无数据处理
    if pe and pe < 0:
        risks.append({"级别": "高", "信号": "动态PE为负，公司处于亏损状态"})
    elif pe and pe > 200:
        risks.append({"级别": "中", "信号": f"动态PE {pe:.1f}（>200），估值偏高"})

    rsi = technical.get("RSI14")
    if rsi is not None:
        if rsi > 80:
            risks.append({"级别": "高", "信号": f"RSI(14)={rsi}，严重超买"})
        elif rsi < 20:
            risks.append({"级别": "中", "信号": f"RSI(14)={rsi}，严重超卖"})

    chg_5d = technical.get("近5日涨跌幅")
    if chg_5d is not None:
        if chg_5d > 20:
            risks.append({"级别": "中", "信号": f"近5日涨幅 {chg_5d:.1f}%，短线过热"})
        elif chg_5d < -10:
            risks.append({"级别": "中", "信号": f"近5日跌幅 {chg_5d:.1f}%，短期超跌"})

    if not risks:
        risks.append({"级别": "低", "信号": "未检测到显著风险信号"})
    return risks


def generate_signals(realtime: dict, technical: dict) -> list:
    signals = []

    ma_arr = technical.get("均线排列", "")
    if "多头" in ma_arr:
        signals.append("✅ 均线多头排列，趋势向上")
    elif "空头" in ma_arr:
        signals.append("❌ 均线空头排列，趋势向下")

    macd = technical.get("MACD信号", "")
    if macd:
        icon = "✅" if ("金叉" in macd or "多头" in macd) else ("⚠️" if "死叉" in macd else "➡️")
        signals.append(f"{icon} MACD：{macd}")

    kdj = technical.get("KDJ状态", "")
    if kdj:
        icon = "🔴" if "超买" in kdj else ("🟢" if "超卖" in kdj else "➡️")
        signals.append(f"{icon} KDJ：{kdj}")

    rsi_s = technical.get("RSI状态", "")
    if rsi_s:
        icon = "🔴" if "超买" in rsi_s else ("🟢" if "超卖" in rsi_s else "➡️")
        signals.append(f"{icon} RSI：{rsi_s}")

    # ADX
    adx_state = technical.get("ADX状态", "")
    if adx_state:
        icon = "🔥" if "强趋势" in adx_state else ("💤" if "弱" in adx_state or "震荡" in adx_state else "➡️")
        signals.append(f"{icon} ADX：{adx_state}")

    # CCI
    cci_state = technical.get("CCI状态", "")
    if cci_state:
        icon = "🔴" if "超买" in cci_state else ("🟢" if "超卖" in cci_state else "➡️")
        signals.append(f"{icon} CCI：{cci_state}")

    # WR
    wr_state = technical.get("WR状态", "")
    if wr_state:
        icon = "🔴" if "超买" in wr_state else ("🟢" if "超卖" in wr_state else "➡️")
        signals.append(f"{icon} WR：{wr_state}")

    vol = technical.get("量价关系", "")
    if vol:
        icon = "📈" if "健康" in vol else ("⚠️" if "乏力" in vol or "抛压" in vol else "➡️")
        signals.append(f"{icon} {vol}")

    return signals


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="A股股票分析工具")
    parser.add_argument("code", nargs="?", help="6位股票代码，如 000001。不传则分析 stocks.json 中的默认股票")
    parser.add_argument("--deep", action="store_true", help="深度模式，含财务数据")
    parser.add_argument("--html", action="store_true", help="输出 HTML 报告")
    parser.add_argument("--text", action="store_true", help=argparse.SUPPRESS)  # 已废弃，兼容旧调用
    parser.add_argument("--all", action="store_true", help="批量分析 stocks.json 中的所有默认股票")
    parser.add_argument("--backtest", action="store_true", help="历史回测模式")
    parser.add_argument("--backtest-days", type=int, default=500, help="回测历史天数（默认500个交易日≈2年）")
    parser.add_argument("-o", "--output", help="HTML 报告输出路径（默认自动生成）")
    args = parser.parse_args()

    # 加载配置文件
    import os as _os
    _skill_dir = _os.path.dirname(_os.path.abspath(__file__))
    _config_path = _os.path.join(_skill_dir, "stocks.json")
    _default_stocks = []
    if _os.path.exists(_config_path):
        with open(_config_path, "r", encoding="utf-8") as _f:
            _cfg = json.loads(_f.read())
            _default_stocks = _cfg.get("defaults", [])

    # 解析要分析的股票列表
    codes_to_run = []
    if args.all or (not args.code and _default_stocks):
        # --all 或无参：分析配置中的所有默认股票
        codes_to_run = [(s["code"], s["name"]) for s in _default_stocks]
    elif args.code:
        code = args.code.strip()
        if len(code) != 6 or not code.isdigit():
            print(json.dumps({"error": "股票代码必须是6位数字"}, ensure_ascii=False))
            sys.exit(1)
        codes_to_run = [(code, None)]
    else:
        print(json.dumps({"error": "未指定股票代码，且 stocks.json 中无默认股票"}, ensure_ascii=False))
        sys.exit(1)

    # 导入报告生成器
    import os as _os
    _skill_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _skill_dir not in sys.path:
        sys.path.insert(0, _skill_dir)
    from stock_report import render_card, render as render_html, render_multi, render_backtest_card, render_backtest_html

    _date_str = datetime.now().strftime("%Y%m%d")
    _out_dir = _os.path.expanduser(f"~/Downloads/gupiao/{_date_str}")
    _os.makedirs(_out_dir, exist_ok=True)

    # 回测模式
    if args.backtest:
        for idx, (code, known_name) in enumerate(codes_to_run):
            _label = known_name or f"股票{code}"
            print(f"\n⏳ 回测 {code} {_label}...", file=sys.stderr)
            bt = run_backtest(code, days=args.backtest_days)
            if "error" in bt:
                print(f"❌ {code} {bt['error']}")
                continue
            # 保存 HTML
            bt_html = render_backtest_html(bt)
            _bt_path = _os.path.join(_out_dir, f"回测_{bt.get('股票名称',code)}_{code}.html")
            with open(_bt_path, "w", encoding="utf-8") as f:
                f.write(bt_html)
            # 输出文本卡
            card = render_backtest_card(bt)
            print(card)
            print(f"\n📎 HTML_FILE: {_bt_path}")
        sys.exit(0)

    is_batch = len(codes_to_run) > 1
    all_outputs = []  # 收集所有分析结果

    # 批量运行
    for idx, (code, known_name) in enumerate(codes_to_run):
        if is_batch:
            _label = known_name or code
            print(f"\n{'─'*36}\n  {idx+1}/{len(codes_to_run)}  {_label}（{code}）\n{'─'*36}\n", file=sys.stderr)

        # 1. 实时行情
        realtime = get_realtime_quote(code)
        if "error" in realtime:
            print(f"❌ {code} {realtime['error']}")
            continue

        # 2. K线 + 技术指标
        technical = get_kline_data(code, days=120)
        if isinstance(technical, dict) and "error" in technical:
            technical = {}

        # 3. 风险检测 + 信号汇总 + 交易建议 + 走势预测
        risks = detect_risks(realtime, technical)
        signals = generate_signals(realtime, technical)
        advice = generate_trading_advice(realtime, technical)
        forecast = generate_price_forecast(realtime, technical)

        technical_clean = {k: v for k, v in technical.items() if not k.startswith("_")}

        output = {
            "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "基本信息": realtime,
            "技术指标": technical_clean,
            "技术信号": signals,
            "交易建议": advice,
            "走势预测": forecast,
            "风险检测": risks,
        }

        if args.deep:
            output["财务数据"] = get_deep_finance(code)

        all_outputs.append(output)

        # 单只股票：保存独立 HTML + 输出卡片
        if not is_batch:
            _filename = f"{code}_{output['基本信息']['名称']}_分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            _out_path = _os.path.join(_out_dir, _filename)

            if args.html:
                html = render_html(output)
                with open(_out_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(html)
            else:
                html = render_html(output)
                with open(_out_path, "w", encoding="utf-8") as f:
                    f.write(html)
                card = render_card(output)
                print(card)
                print(f"\n📎 HTML_FILE: {_out_path}")

        if is_batch:
            time.sleep(0.5)

    # 多股票：生成合并 HTML（Tab 切换）+ 卡片输出
    if is_batch and all_outputs:
        _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _merged_name = f"自选股批量分析_{_ts}.html"
        _merged_path = _os.path.join(_out_dir, _merged_name)
        merged_html = render_multi(all_outputs)
        with open(_merged_path, "w", encoding="utf-8") as f:
            f.write(merged_html)

        if args.html:
            print(merged_html)
        else:
            # 默认：逐只输出卡片 + 合并文件路径
            for out in all_outputs:
                card = render_card(out)
                print(card)
            print(f"\n📎 HTML_FILE: {_merged_path}")


if __name__ == "__main__":
    main()
