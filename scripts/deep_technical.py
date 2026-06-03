#!/usr/bin/env python3
"""
Technical analysis for each A-share ticker.
Computes Minervini 7 criteria, Stage 2, RS vs CSI300, volume analysis.
Reads data/stocks/{CODE}_price.csv + 000300_price.csv
Outputs data/stocks/{CODE}_tech.json
"""
import os, json
import pandas as pd
import numpy as np
from datetime import datetime

UNIVERSE = [
    '688981.SS', '603501.SS', '002371.SZ', '688008.SS', '603986.SS',
    '688111.SS', '002230.SZ', '300496.SZ',
    '300015.SZ', '603259.SS', '300760.SZ', '002821.SZ', '300347.SZ',
    '300750.SZ', '002594.SZ', '300274.SZ', '300014.SZ', '601012.SS',
    '000858.SZ', '000568.SZ', '603288.SS', '002304.SZ',
    '601888.SS', '300059.SZ',
    '600519.SS',
]


def code(ticker):
    return ticker.split('.')[0]


def load_price(c):
    path = f'data/stocks/{c}_price.csv'
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=['date'])
    return df.sort_values('date').reset_index(drop=True)


def load_csi300():
    path = 'data/stocks/000300_price.csv'
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=['date'])
    return df.sort_values('date').reset_index(drop=True)


def ma_slope(series, window=20):
    if len(series) < window + 1:
        return 0.0
    recent = series.iloc[-window:]
    x = np.arange(len(recent))
    slope = np.polyfit(x, recent.values, 1)[0]
    return float(slope)


def minervini_score(df):
    """
    Check Minervini 7 template criteria.
    Returns (score, detail_dict)
    """
    if len(df) < 60:
        return 0, {}

    close = df['close']
    ma50  = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    ma200 = close.rolling(200).mean()

    price   = float(close.iloc[-1])
    ma50_v  = float(ma50.iloc[-1])
    ma150_v = float(ma150.iloc[-1])
    ma200_v = float(ma200.iloc[-1])

    high_52w = float(close.tail(252).max())
    low_52w  = float(close.tail(252).min())

    slope_200 = ma_slope(ma200.dropna())

    criteria = {
        'c1_price_above_ma150_ma200': price > ma150_v and price > ma200_v,
        'c2_ma150_above_ma200':       ma150_v > ma200_v,
        'c3_ma200_trending_up':       slope_200 > 0,
        'c4_ma50_above_ma150_ma200':  ma50_v > ma150_v and ma50_v > ma200_v,
        'c5_price_above_ma50':        price > ma50_v,
        'c6_price_30pct_above_52w_low': price >= low_52w * 1.30,
        'c7_price_within_25pct_52w_high': price >= high_52w * 0.75,
    }
    score = sum(criteria.values())
    return score, criteria


def calc_rs(df, csi300_df, periods=63):
    """Relative strength vs CSI300 over ~3 months (63 trading days)."""
    if df is None or len(df) < periods + 1:
        return None
    if csi300_df is None or len(csi300_df) < periods + 1:
        return None

    stock_now  = float(df['close'].iloc[-1])
    stock_then = float(df['close'].iloc[-(periods + 1)])
    csi_now    = float(csi300_df['close'].iloc[-1])
    csi_then   = float(csi300_df['close'].iloc[-(periods + 1)])

    if stock_then == 0 or csi_then == 0:
        return None

    stock_ret = (stock_now - stock_then) / stock_then * 100
    csi_ret   = (csi_now - csi_then) / csi_then * 100
    return round(stock_ret - csi_ret, 2)


def volume_analysis(df):
    if len(df) < 50:
        return {}
    vol = df['volume']
    avg50 = float(vol.tail(50).mean())
    avg5  = float(vol.tail(5).mean())
    vol_ratio = round(avg5 / avg50, 2) if avg50 > 0 else 1.0

    up_days  = df.tail(10)[df.tail(10)['pct_change'] > 0]
    dn_days  = df.tail(10)[df.tail(10)['pct_change'] < 0]
    avg_vol_up = float(up_days['volume'].mean()) if len(up_days) > 0 else 0
    avg_vol_dn = float(dn_days['volume'].mean()) if len(dn_days) > 0 else 1
    vol_quality = round(avg_vol_up / avg_vol_dn, 2) if avg_vol_dn > 0 else 1.0

    return {
        'vol_ratio_5d_vs_50d': vol_ratio,
        'vol_quality_up_vs_dn': vol_quality,
    }


def find_pivot_high(df, lookback=60):
    if len(df) < lookback:
        return None
    window = df.tail(lookback)
    return float(window['high'].max())


def analyze(ticker, csi300_df):
    c = code(ticker)
    df = load_price(c)
    if df is None or len(df) < 50:
        return {'ticker': ticker, 'code': c, 'error': 'insufficient data',
                'fetched_at': datetime.now().isoformat()}

    close = float(df['close'].iloc[-1])
    high_52w = float(df['close'].tail(252).max()) if len(df) >= 252 else float(df['close'].max())
    low_52w  = float(df['close'].tail(252).min()) if len(df) >= 252 else float(df['close'].min())

    pct_from_52w_high = round((close - high_52w) / high_52w * 100, 1)
    pct_from_52w_low  = round((close - low_52w) / low_52w * 100, 1)

    mv_score, mv_criteria = minervini_score(df)
    rs_3m = calc_rs(df, csi300_df)
    vol   = volume_analysis(df)
    pivot = find_pivot_high(df)
    pct_from_pivot = round((close - pivot) / pivot * 100, 1) if pivot else None

    stage2 = (
        mv_criteria.get('c1_price_above_ma150_ma200', False) and
        mv_criteria.get('c2_ma150_above_ma200', False) and
        mv_criteria.get('c3_ma200_trending_up', False)
    )

    result = {
        'ticker':               ticker,
        'code':                 c,
        'close':                close,
        'high_52w':             high_52w,
        'low_52w':              low_52w,
        'pct_from_52w_high':    pct_from_52w_high,
        'pct_from_52w_low':     pct_from_52w_low,
        'pivot_high_60d':       pivot,
        'pct_from_pivot':       pct_from_pivot,
        'stage2_confirmed':     stage2,
        'minervini_score':      mv_score,
        'minervini_criteria':   mv_criteria,
        'rs_3m':                rs_3m,
        'fetched_at':           datetime.now().isoformat(),
    }
    result.update(vol)
    return result


def main():
    os.makedirs('data/stocks', exist_ok=True)
    csi300_df = load_csi300()
    if csi300_df is None:
        print('[WARN] CSI300 price data not found, RS scores will be null')

    for ticker in UNIVERSE:
        c = code(ticker)
        print(f'  {ticker}...')
        data = analyze(ticker, csi300_df)
        with open(f'data/stocks/{c}_tech.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print('Done.')


if __name__ == '__main__':
    main()
