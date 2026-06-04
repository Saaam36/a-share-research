#!/usr/bin/env python3
"""
Fetch daily market data for A-share universe.
Price data (individual stocks + CSI300): baostock — works from overseas IPs.
North flow + sentiment: akshare (East Money) — may fail from overseas.
Saves: data/stocks/{CODE}_price.csv, {CODE}_info.json
       data/market/north_flow.json, sentiment.json
"""
import os, json, time
import pandas as pd
import akshare as ak
import baostock as bs
from datetime import datetime, timedelta


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


def bs_code(ticker):
    """Convert '600519.SS' → 'sh.600519', '000858.SZ' → 'sz.000858'"""
    c, market = ticker.split('.')
    prefix = 'sh' if market == 'SS' else 'sz'
    return f'{prefix}.{c}'


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


def fetch_price(ticker, days=400):
    """Fetch individual stock OHLCV via baostock (overseas-IP friendly)."""
    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    fields = 'date,open,high,low,close,volume,amount,turn,pctChg'
    try:
        rs = bs.query_history_k_data_plus(
            bs_code(ticker), fields,
            start_date=start, end_date=end,
            frequency='d', adjustflag='3'   # 3 = 不复权，与交易软件显示价格一致
        )
        if rs.error_code != '0':
            print(f'  [WARN] price {ticker}: {rs.error_msg}')
            return None
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=rs.fields)
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.rename(columns={'turn': 'turnover', 'pctChg': 'pct_change'})
        df = df.dropna(subset=['close'])
        return df.sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f'  [WARN] price {ticker}: {e}')
        return None


def fetch_csi300(days=400):
    """Fetch CSI300 index OHLCV via baostock."""
    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    fields = 'date,open,high,low,close,volume,amount,pctChg'
    try:
        rs = bs.query_history_k_data_plus(
            'sh.000300', fields,
            start_date=start, end_date=end,
            frequency='d', adjustflag='3'   # 3 = 不复权，指数用原始点位
        )
        if rs.error_code != '0':
            print(f'  [WARN] CSI300: {rs.error_msg}')
            return None
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=rs.fields)
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.rename(columns={'pctChg': 'pct_change'})
        df = df.dropna(subset=['close'])
        return df.sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f'  [WARN] CSI300: {e}')
        return None


def fetch_info(ticker):
    """Fetch stock name/industry via baostock."""
    try:
        rs = bs.query_stock_basic(code=bs_code(ticker))
        if rs.error_code != '0':
            return {}
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return {}
        row = dict(zip(rs.fields, rows[0]))
        return {
            '股票简称': row.get('code_name', ''),
            '所属行业': row.get('industry', ''),
            '上市状态': row.get('status', ''),
        }
    except Exception as e:
        print(f'  [WARN] info {ticker}: {e}')
        return {}


def fetch_north_flow():
    """Fetch northbound fund flow via akshare (East Money).
    May fail from overseas IPs — failure is non-fatal."""
    results = {'fetched_at': datetime.now().isoformat()}
    for label, symbol in [('north', '北向资金'), ('sh', '沪股通'), ('sz', '深股通')]:
        try:
            df = with_retry(ak.stock_hsgt_hist_em, symbol=symbol)
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
    """Fetch limit-up/down count via akshare (East Money).
    May fail from overseas IPs — failure is non-fatal."""
    results = {'fetched_at': datetime.now().isoformat()}
    try:
        df = ak.stock_limit_up_down_em()
        if df is not None and not df.empty:
            records = []
            for _, row in df.head(20).iterrows():
                records.append({str(k): str(v) for k, v in row.items()})
            results['data'] = records
            results['columns'] = [str(c) for c in df.columns.tolist()]
    except Exception as e:
        results['error'] = str(e)
    return results


def main():
    os.makedirs('data/stocks', exist_ok=True)
    os.makedirs('data/market', exist_ok=True)

    print('Logging in to baostock...')
    lg = bs.login()
    if lg.error_code != '0':
        print(f'  [ERROR] baostock login failed: {lg.error_msg}')
        return

    try:
        print(f'[{datetime.now():%H:%M}] Fetching CSI300...')
        csi = fetch_csi300()
        if csi is not None:
            csi.to_csv('data/stocks/000300_price.csv', index=False)
            print(f'  CSI300 {len(csi)} rows')
        else:
            print('  CSI300 fetch failed')

        for ticker in UNIVERSE:
            c = code(ticker)
            print(f'  {ticker}...')
            df = fetch_price(ticker)
            if df is not None:
                df.to_csv(f'data/stocks/{c}_price.csv', index=False)
            time.sleep(0.5)
            info = fetch_info(ticker)
            if info:
                with open(f'data/stocks/{c}_info.json', 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
            time.sleep(0.5)

    finally:
        bs.logout()
        print('baostock logged out.')

    print('Fetching north flow (akshare/East Money — may fail from overseas)...')
    nf = fetch_north_flow()
    with open('data/market/north_flow.json', 'w', encoding='utf-8') as f:
        json.dump(nf, f, ensure_ascii=False, indent=2)
    if any('error' in k for k in nf):
        print('  [WARN] North flow fetch failed (overseas IP blocked by East Money)')
    else:
        print('  North flow OK')

    print('Fetching sentiment (akshare/East Money — may fail from overseas)...')
    sent = fetch_sentiment()
    with open('data/market/sentiment.json', 'w', encoding='utf-8') as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)

    print('Done.')


if __name__ == '__main__':
    main()
