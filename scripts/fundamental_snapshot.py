#!/usr/bin/env python3
"""
Build fundamental snapshot for each A-share ticker.
Reads data/stocks/{CODE}_info.json, calls akshare financial APIs.
Outputs data/stocks/{CODE}_fund.json
"""
import os, json
import akshare as ak
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


def find_col(df, *keywords):
    for col in df.columns:
        if any(kw in str(col) for kw in keywords):
            return col
    return None


def safe_float(val):
    if val is None:
        return None
    try:
        s = str(val).strip().replace(',', '').replace('%', '').replace('亿', '')
        if s in ('-', 'nan', 'None', '', '--', 'N/A'):
            return None
        return float(s)
    except Exception:
        return None


def load_info(c):
    path = f'data/stocks/{c}_info.json'
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_financial(c):
    result = {}
    try:
        df = ak.stock_financial_abstract(symbol=c)
        if df is None or df.empty:
            return result

        date_col = df.columns[0]
        df = df.sort_values(date_col, ascending=False).reset_index(drop=True)
        row = df.iloc[0].to_dict()

        mappings = {
            'revenue_yoy_pct':    ('营业总收入增长', '营收增长', '收入增长率'),
            'net_profit_yoy_pct': ('净利润增长', '净利润同比', '扣非净利润增长'),
            'eps':                ('每股收益', '基本每股收益'),
            'roe_pct':            ('净资产收益率', 'ROE'),
            'debt_ratio_pct':     ('资产负债率', '负债率'),
        }

        for key, keywords in mappings.items():
            col = find_col(df, *keywords)
            if col:
                result[key] = safe_float(row.get(col))

    except Exception as e:
        print(f'  [WARN] financial {c}: {e}')

    return result


def parse_info(info):
    result = {}
    for k, v in info.items():
        k_str = str(k)
        try:
            if any(x in k_str for x in ('PE', 'P/E', '市盈率', '静态')):
                result.setdefault('pe_ratio', safe_float(v))
            elif any(x in k_str for x in ('PB', 'P/B', '市净率')):
                result.setdefault('pb_ratio', safe_float(v))
            elif '总市值' in k_str:
                # value may be in 亿元 e.g. "12345.67亿"
                result['market_cap_bn_cny'] = safe_float(v)
            elif any(x in k_str for x in ('行业', '所属行业')):
                result['industry'] = str(v).strip()
            elif any(x in k_str for x in ('股票简称', '名称', '简称')):
                result.setdefault('name', str(v).strip())
        except Exception:
            pass
    return result


def snapshot(ticker):
    c = code(ticker)
    info = load_info(c)
    fin = get_financial(c)
    info_parsed = parse_info(info)

    name = info_parsed.get('name', '')
    is_st = 'ST' in name.upper()

    result = {
        'ticker': ticker,
        'code': c,
        'name': name,
        'is_st': is_st,
        'fetched_at': datetime.now().isoformat(),
    }
    result.update(info_parsed)
    result.update(fin)

    # derived: fundamentals_ok for iron rule 5
    rev_yoy = result.get('revenue_yoy_pct')
    result['fundamentals_ok'] = (
        not is_st and
        (rev_yoy is None or rev_yoy > -20)  # allow unknown, reject severe decline
    )

    return result


def main():
    os.makedirs('data/stocks', exist_ok=True)
    for ticker in UNIVERSE:
        c = code(ticker)
        print(f'  {ticker}...')
        data = snapshot(ticker)
        with open(f'data/stocks/{c}_fund.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print('Done.')


if __name__ == '__main__':
    main()
