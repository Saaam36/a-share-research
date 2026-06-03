#!/usr/bin/env python3
"""
CANSLIM-based screener for A-share universe.
Reads {CODE}_fund.json + {CODE}_tech.json + market_state.json.
Outputs data/screener_results.json — ranked candidates with iron-rule flags.
"""
import os, json
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


def load_json(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def canslim_score(fund, tech, market):
    score = 0.0
    detail = {}

    # C — Current earnings growth (EPS YoY)
    eps_yoy = fund.get('eps_yoy_pct') or fund.get('net_profit_yoy_pct')
    if eps_yoy is not None:
        if eps_yoy >= 25:   score += 2.0; detail['C'] = f'EPS+{eps_yoy}%✓'
        elif eps_yoy >= 10: score += 1.0; detail['C'] = f'EPS+{eps_yoy}%'
        elif eps_yoy >= 0:  score += 0.5; detail['C'] = f'EPS+{eps_yoy}%'
        else:               detail['C'] = f'EPS{eps_yoy}%✗'
    else:
        score += 0.5; detail['C'] = 'EPS未知'

    # A — Annual revenue growth
    rev_yoy = fund.get('revenue_yoy_pct')
    if rev_yoy is not None:
        if rev_yoy >= 25:   score += 2.0; detail['A'] = f'营收+{rev_yoy}%✓'
        elif rev_yoy >= 10: score += 1.0; detail['A'] = f'营收+{rev_yoy}%'
        elif rev_yoy >= 0:  score += 0.5; detail['A'] = f'营收+{rev_yoy}%'
        else:               detail['A'] = f'营收{rev_yoy}%✗'
    else:
        score += 0.5; detail['A'] = '营收未知'

    # N — New highs (near 52-week high)
    pct_52w = tech.get('pct_from_52w_high')
    if pct_52w is not None:
        if pct_52w >= -5:   score += 1.0; detail['N'] = f'距高点{pct_52w}%✓'
        elif pct_52w >= -15: score += 0.5; detail['N'] = f'距高点{pct_52w}%'
        else:                detail['N'] = f'距高点{pct_52w}%✗'
    else:
        detail['N'] = '高点未知'

    # S — Supply/demand: recent volume vs 50d avg
    vol_ratio = tech.get('vol_ratio_5d_vs_50d')
    if vol_ratio is not None:
        if vol_ratio >= 1.5:  score += 1.0; detail['S'] = f'量比{vol_ratio}x✓'
        elif vol_ratio >= 1.0: score += 0.5; detail['S'] = f'量比{vol_ratio}x'
        else:                  detail['S'] = f'量比{vol_ratio}x✗'
    else:
        detail['S'] = '成交量未知'

    # L — Leader: RS vs CSI300
    rs = tech.get('rs_3m')
    if rs is not None:
        if rs >= 15:   score += 2.0; detail['L'] = f'RS超跑+{rs}%✓'
        elif rs >= 5:  score += 1.0; detail['L'] = f'RS超跑+{rs}%'
        elif rs >= 0:  score += 0.5; detail['L'] = f'RS超跑+{rs}%'
        else:          detail['L'] = f'RS落后{rs}%✗'
    else:
        detail['L'] = 'RS未知'

    # I — Institutional: north flow signal
    north_signal = market.get('north_flow_signal')
    if north_signal in ('strong_inflow', 'mild_inflow'):
        score += 1.0; detail['I'] = f'北向净流入({north_signal})'
    elif north_signal is not None:
        detail['I'] = f'北向净流出({north_signal})'
    else:
        detail['I'] = '北向未知'

    # M — Market direction
    if market.get('market_status') == 'NEW_ENTRY_ALLOWED':
        score += 1.0; detail['M'] = '大盘Stage2✓'
    else:
        detail['M'] = '大盘非Stage2✗'

    return round(score, 1), detail


def iron_rules_check(fund, tech, market):
    """
    Returns dict of 5 iron rule statuses.
    Rule 3 (buy point ≤+3%) and rule 4 (stop loss -8%, T+1) are noted but
    depend on real-time price vs pivot — flagged for CCR manual check.
    """
    rules = {}

    # Rule 1: CSI300 Stage 2
    rules['r1_csi300_stage2'] = market.get('csi300_stage2', False)

    # Rule 2: Minervini >= 6/7
    mv = tech.get('minervini_score', 0)
    rules['r2_minervini'] = mv >= 6
    rules['r2_minervini_score'] = f'{mv}/7'

    # Rule 3: Within 3% of buy point (pivot high) — flag for manual check
    pct_pivot = tech.get('pct_from_pivot')
    if pct_pivot is not None:
        rules['r3_buy_point_ok'] = -3 <= pct_pivot <= 3
        rules['r3_pct_from_pivot'] = pct_pivot
    else:
        rules['r3_buy_point_ok'] = None  # unknown
        rules['r3_pct_from_pivot'] = None

    # Rule 4: Stop loss -8%, T+1 (informational)
    rules['r4_stop_loss'] = '-8%，次日起有效'

    # Rule 5: Non-ST + fundamentals not weak
    rules['r5_not_st'] = not fund.get('is_st', True)
    rules['r5_fundamentals_ok'] = fund.get('fundamentals_ok', False)
    rules['r5_pass'] = rules['r5_not_st'] and rules['r5_fundamentals_ok']

    # Overall: all checkable rules pass
    checkable = [
        rules['r1_csi300_stage2'],
        rules['r2_minervini'],
        rules['r3_buy_point_ok'],  # None counts as uncertain
        rules['r5_pass'],
    ]
    rules['all_hard_rules_pass'] = all(x is True for x in checkable)

    return rules


def screen_all():
    market = load_json('data/market/market_state.json')
    results = []

    for ticker in UNIVERSE:
        c = code(ticker)
        fund = load_json(f'data/stocks/{c}_fund.json')
        tech = load_json(f'data/stocks/{c}_tech.json')

        if not fund and not tech:
            continue

        canslim, canslim_detail = canslim_score(fund, tech, market)
        rules = iron_rules_check(fund, tech, market)

        entry = {
            'ticker':           ticker,
            'code':             c,
            'name':             fund.get('name', c),
            'industry':         fund.get('industry', ''),
            'close':            tech.get('close'),
            'canslim_score':    canslim,
            'canslim_detail':   canslim_detail,
            'minervini_score':  tech.get('minervini_score'),
            'rs_3m':            tech.get('rs_3m'),
            'pct_from_52w_high': tech.get('pct_from_52w_high'),
            'pct_from_pivot':   tech.get('pct_from_pivot'),
            'stage2':           tech.get('stage2_confirmed', False),
            'revenue_yoy_pct':  fund.get('revenue_yoy_pct'),
            'eps_yoy_pct':      fund.get('eps_yoy_pct') or fund.get('net_profit_yoy_pct'),
            'roe_pct':          fund.get('roe_pct'),
            'pe_ratio':         fund.get('pe_ratio'),
            'is_st':            fund.get('is_st', False),
            'iron_rules':       rules,
            'entry_signal':     '✅ 可关注' if rules['all_hard_rules_pass'] else '⛔ 规则未通过',
        }
        results.append(entry)

    results.sort(key=lambda x: x['canslim_score'], reverse=True)

    output = {
        'date':          datetime.now().strftime('%Y-%m-%d'),
        'market_status': market.get('market_status', 'UNKNOWN'),
        'total_screened': len(results),
        'candidates':    results,
        'generated_at':  datetime.now().isoformat(),
    }

    with open('data/screener_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    passed = [r for r in results if r['iron_rules']['all_hard_rules_pass']]
    print(f'Screened {len(results)} stocks, {len(passed)} passed all iron rules.')
    for r in results[:5]:
        print(f"  {r['name']}({r['code']}) CANSLIM={r['canslim_score']} {r['entry_signal']}")
    print('Done.')


if __name__ == '__main__':
    screen_all()
