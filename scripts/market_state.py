#!/usr/bin/env python3
"""
Assess overall A-share market state.
- CSI300 Stage 2 check (price > MA50 > MA200, MA200 trending up)
- Northbound fund 5-day net flow
- Limit-up/down sentiment ratio
Outputs data/market/market_state.json
"""
import os, json
import pandas as pd
import numpy as np
from datetime import datetime


def load_csi300():
    path = 'data/stocks/000300_price.csv'
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=['date'])
    return df.sort_values('date').reset_index(drop=True)


def csi300_stage2(df):
    if df is None or len(df) < 200:
        return False, {}

    close = df['close']
    ma50  = float(close.rolling(50).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])
    price = float(close.iloc[-1])

    ma200_series = close.rolling(200).mean().dropna()
    x = np.arange(20)
    slope_200 = float(np.polyfit(x, ma200_series.tail(20).values, 1)[0])

    c1 = price > ma50 and price > ma200
    c2 = ma50 > ma200
    c3 = slope_200 > 0

    detail = {
        'price':      round(price, 2),
        'ma50':       round(ma50, 2),
        'ma200':      round(ma200, 2),
        'ma200_slope': round(slope_200, 4),
        'c1_price_above_mas': c1,
        'c2_ma50_above_ma200': c2,
        'c3_ma200_up': c3,
    }
    is_stage2 = c1 and c2 and c3
    return is_stage2, detail


def parse_north_flow():
    path = 'data/market/north_flow.json'
    if not os.path.exists(path):
        return None, 'no file'

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    north = data.get('north', [])
    if not north:
        return None, 'no data'

    total_flow = 0.0
    count = 0
    for record in north:
        for k, v in record.items():
            if any(x in str(k) for x in ('净买入', '净流入', 'net', '资金')):
                try:
                    val = float(str(v).replace(',', '').replace('亿', ''))
                    total_flow += val
                    count += 1
                    break
                except Exception:
                    pass

    if count == 0:
        return None, 'parse failed'

    return round(total_flow, 2), f'{count} records parsed'


def parse_sentiment():
    path = 'data/market/sentiment.json'
    if not os.path.exists(path):
        return None, None, 'no file'

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    records = data.get('data', [])
    up_count = dn_count = 0

    for rec in records:
        for k, v in rec.items():
            k_str = str(k)
            try:
                if '涨停' in k_str and '家' in k_str:
                    up_count = int(float(str(v)))
                elif '跌停' in k_str and '家' in k_str:
                    dn_count = int(float(str(v)))
            except Exception:
                pass

    return up_count or None, dn_count or None, 'parsed'


def main():
    os.makedirs('data/market', exist_ok=True)

    csi_df = load_csi300()
    stage2, csi_detail = csi300_stage2(csi_df)

    north_flow_5d, north_note = parse_north_flow()
    limit_up, limit_down, _ = parse_sentiment()

    # Market status decision
    if stage2:
        status = 'NEW_ENTRY_ALLOWED'
    else:
        status = 'CASH_PRIORITY'

    # Note: north flow is extra context, not a hard gate
    north_signal = None
    if north_flow_5d is not None:
        if north_flow_5d > 50:
            north_signal = 'strong_inflow'
        elif north_flow_5d > 0:
            north_signal = 'mild_inflow'
        elif north_flow_5d > -50:
            north_signal = 'mild_outflow'
        else:
            north_signal = 'strong_outflow'

    result = {
        'date':               datetime.now().strftime('%Y-%m-%d'),
        'market_status':      status,
        'csi300_stage2':      stage2,
        'csi300_detail':      csi_detail,
        'north_flow_5d_bn':   north_flow_5d,
        'north_flow_signal':  north_signal,
        'north_note':         north_note,
        'limit_up_count':     limit_up,
        'limit_down_count':   limit_down,
        'fetched_at':         datetime.now().isoformat(),
    }

    with open('data/market/market_state.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'Market status: {status}')
    print(f'CSI300 Stage 2: {stage2}')
    if north_flow_5d is not None:
        print(f'North flow 5d: {north_flow_5d}B CNY ({north_signal})')
    print('Done.')


if __name__ == '__main__':
    main()
