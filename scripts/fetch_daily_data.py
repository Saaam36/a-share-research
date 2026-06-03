#!/usr/bin/env python3
"""
Fetch daily market data for A-share universe via akshare.
Saves: data/stocks/{CODE}_price.csv, {CODE}_info.json
       data/market/north_flow.json, sentiment.json
"""
import os, json, time
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta


def with_retry(fn, *args, retries=3, base_delay=3, **kwargs):
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                print(f'    [retry {attempt+1}] {e} — waiting {wait}s')
                time.sleep(wait)
            else:
                raise

UNIVERSE = [
    '688981.SS', '603501.SS', '002371.SZ', '688008.SS', '603986.SS',
    '688111.SS', '002230.SZ', '300496.SZ',
    '300015.SZ', '603259.SS', '300760.SZ', '002821.SZ', '300347.SZ',
    '300750.SZ', '002594.SZ', '300274.SZ', '300014.SZ', '601012.SS',
    '000858.SZ', '000568.SZ', '603288.SS', '002304.SZ',
    '601888.SS', '300059.SZ',
    '600519.SS',
]

PRICE_RENAME = {
    '日期': 'date', '开盘': 'open', '收盘': 'close',
    '最高': 'high', '最低': 'low', '成交量': 'volume',
    '成交额': 'amount', '涨跌幅': 'pct_change', '换手率': 'turnover',
}


def code(ticker):
    return ticker.split('.')[0]


def fetch_price(ticker, days=400):
    c = code(ticker)
    end = datetime.today().strftime('%Y%m%d')
    start = (datetime.today() - timedelta(days=days)).strftime('%Y%m%d')
    try:
        df = with_retry(ak.stock_zh_a_hist, symbol=c, period='daily',
                        start_date=start, end_date=end, adjust='qfq')
        if df is None or df.empty:
            return None
        df = df.rename(columns=PRICE_RENAME)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f'  [WARN] price {ticker}: {e}')
        return None


def fetch_csi300(days=400):
    end = datetime.today().strftime('%Y%m%d')
    start = (datetime.today() - timedelta(days=days)).strftime('%Y%m%d')
    try:
        df = with_retry(ak.index_zh_a_hist, symbol='000300', period='daily',
                        start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df = df.rename(columns=PRICE_RENAME)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f'  [WARN] CSI300: {e}')
        return None


def fetch_info(ticker):
    c = code(ticker)
    try:
        df = with_retry(ak.stock_individual_info_em, symbol=c)
        if df is None or df.empty:
            return {}
        return dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(str)))
    except Exception as e:
        print(f'  [WARN] info {ticker}: {e}')
        return {}


def fetch_north_flow():
    results = {'fetched_at': datetime.now().isoformat()}
    for label, symbol in [('north', '北向资金'), ('sh', '沪股通'), ('sz', '深股通')]:
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol=symbol)
            if df is not None and not df.empty:
                tail = df.tail(5)
                records = []
                for _, row in tail.iterrows():
                    records.append({str(k): str(v) for k, v in row.items()})
                results[label] = records
        except Exception as e:
            results[f'{label}_error'] = str(e)
    return results


def fetch_sentiment():
    results = {'fetched_at': datetime.now().isoformat()}
    try:
        df = ak.stock_limit_up_down_em()
        if df is not None and not df.empty:
            records = []
            for _, row in df.head(20).iterrows():
                records.append({str(k): str(v) for k, v in row.items()})
            results['data'] = records
            # count limit-up vs limit-down from column names if available
            cols = df.columns.tolist()
            results['columns'] = [str(c) for c in cols]
    except Exception as e:
        results['error'] = str(e)
    return results


def main():
    os.makedirs('data/stocks', exist_ok=True)
    os.makedirs('data/market', exist_ok=True)

    print(f'[{datetime.now():%H:%M}] Fetching CSI300...')
    csi = fetch_csi300()
    if csi is not None:
        csi.to_csv('data/stocks/000300_price.csv', index=False)
        print(f'  CSI300 {len(csi)} rows')

    for ticker in UNIVERSE:
        c = code(ticker)
        print(f'  {ticker}...')
        df = fetch_price(ticker)
        if df is not None:
            df.to_csv(f'data/stocks/{c}_price.csv', index=False)
        time.sleep(0.8)
        info = fetch_info(ticker)
        if info:
            with open(f'data/stocks/{c}_info.json', 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        time.sleep(0.8)

    print('Fetching north flow...')
    nf = fetch_north_flow()
    with open('data/market/north_flow.json', 'w', encoding='utf-8') as f:
        json.dump(nf, f, ensure_ascii=False, indent=2)

    print('Fetching limit up/down sentiment...')
    sent = fetch_sentiment()
    with open('data/market/sentiment.json', 'w', encoding='utf-8') as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)

    print('Done.')


if __name__ == '__main__':
    main()
