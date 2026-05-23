import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def get_ticker_name(ticker, ticker_names):
    if ticker in ticker_names:
        return ticker_names[ticker]

    name = ""
    try:
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName") or ""
    except Exception:
        name = ""

    ticker_names[ticker] = name
    return name


def get_price_on_or_after(ticker_df, target_date):
    avail = ticker_df.index[ticker_df.index >= target_date]
    return ticker_df.loc[avail[0], "Price"] if not avail.empty else None


def get_price_on_or_before(ticker_df, target_date):
    avail = ticker_df.index[ticker_df.index <= target_date]
    return ticker_df.loc[avail[-1], "Price"] if not avail.empty else None


def calculate_weighted_performance(tickers, ticker_names):
    period1_start = pd.Timestamp("2024-12-31")
    period1_end = pd.Timestamp("2025-06-30")
    period2_start = pd.Timestamp("2025-06-30")
    period2_end = pd.Timestamp("2026-12-31")

    weight1 = 0.3333
    weight2 = 0.6667

    results = []
    price_history = {}
    chunk_size = 50

    print(f"-> Starte gewichtete Zeitraum-Analyse (Zeiträume: {period1_start.date()} - {period1_end.date()} und {period2_start.date()} - {period2_end.date()})...")

    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]

        try:
            raw_data = yf.download(chunk, start=period1_start, end=period2_end + timedelta(days=1), progress=False)
        except Exception as e:
            print(f"   Fehler bei Download: {e}")
            continue

        adj_close_col = None
        for col in ["Adj Close", "Adj. Close", "Close"]:
            if col in raw_data.columns:
                adj_close_col = col
                break

        if not adj_close_col:
            continue

        for ticker in chunk:
            try:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if ticker in raw_data[adj_close_col].columns:
                        ticker_df = pd.DataFrame({"Price": raw_data[adj_close_col][ticker]}).dropna()
                    else:
                        continue
                else:
                    ticker_df = pd.DataFrame({"Price": raw_data[adj_close_col]}).dropna()

                if ticker_df.empty or len(ticker_df) < 5:
                    continue

                dates = [d.strftime("%Y-%m-%d") for d in ticker_df.index]
                prices = [float(p) for p in ticker_df["Price"].tolist()]
                price_history[ticker] = {"dates": dates, "prices": prices}

                p1_start = get_price_on_or_after(ticker_df, period1_start)
                p1_end = get_price_on_or_before(ticker_df, period1_end)
                p2_start = get_price_on_or_after(ticker_df, period2_start)
                p2_end = get_price_on_or_before(ticker_df, period2_end)

                if any(p is None for p in [p1_start, p1_end, p2_start, p2_end]):
                    continue

                ret1 = ((p1_end - p1_start) / p1_start) * 100
                ret2 = ((p2_end - p2_start) / p2_start) * 100
                weighted_score = (ret1 * weight1) + (ret2 * weight2)
                ticker_name = ticker_names.get(ticker, "")
                if not ticker_name:
                    ticker_name = get_ticker_name(ticker, ticker_names)

                results.append({
                    "Ticker": ticker,
                    "Name": ticker_name,
                    "31.12.24-30.06.25 (%)": round(ret1, 2),
                    "30.06.25-31.12.26 (%)": round(ret2, 2),
                    "Gewichteter Score": round(weighted_score, 2)
                })
            except Exception:
                continue

    return results, price_history


def main():
    print("\n==========================================")
    print("!!! START: KORRIGIERTER LIVE-RUN !!!")
    print("==========================================\n")
    
    csv_path = "ticker.csv"
    if not os.path.exists(csv_path):
        print(f"CRITICAL ERROR: '{csv_path}' fehlt!")
        return

    df_ticker = pd.read_csv(csv_path)
    ticker_col = "Ticker" if "Ticker" in df_ticker.columns else df_ticker.columns[0]
    tickers = df_ticker[ticker_col].dropna().astype(str).str.strip().tolist()
    tickers = list(dict.fromkeys(tickers))
    print(f"-> {len(tickers)} Ticker aus CSV eingelesen.")

    today = datetime.today()
    start_date = today - timedelta(days=380)
    periods = {
        "1M": today - timedelta(days=30),
        "3M": today - timedelta(days=91),
        "6M": today - timedelta(days=182),
        "9M": today - timedelta(days=273)
    }

    results = []
    ticker_names = {}
    chunk_size = 50
    
    print(f"-> Starte paketweisen Download (Größe: {chunk_size})...\n")
    
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        print(f"[Paket {i//chunk_size + 1}/{len(tickers)//chunk_size + 1}] Verarbeite Ticker {i} bis {i+len(chunk)}...")
        
        try:
            raw_data = yf.download(chunk, start=start_date, end=today, progress=False)
        except Exception as e:
            print(f"   Fehler bei Paket-Download: {e}")
            continue

        adj_close_col = None
        for col in ["Adj Close", "Adj. Close", "Close"]:
            if col in raw_data.columns:
                adj_close_col = col
                break

        if not adj_close_col:
            continue

        for ticker in chunk:
            try:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if ticker in raw_data[adj_close_col].columns:
                        ticker_df = pd.DataFrame({"Price": raw_data[adj_close_col][ticker]}).dropna()
                    else:
                        continue
                else:
                    ticker_df = pd.DataFrame({"Price": raw_data[adj_close_col]}).dropna()

                if ticker_df.empty or len(ticker_df) < 10:
                    continue

                end_price = ticker_df["Price"].iloc[-1]

                def get_historic_price(target_date):
                    target_timestamp = pd.Timestamp(target_date)
                    avail = ticker_df.index[ticker_df.index >= target_timestamp]
                    return ticker_df.loc[avail[0], "Price"] if not avail.empty else None

                p_1m = get_historic_price(periods["1M"])
                p_3m = get_historic_price(periods["3M"])
                p_6m = get_historic_price(periods["6M"])
                p_9m = get_historic_price(periods["9M"])

                if any(p is None for p in [p_1m, p_3m, p_6m, p_9m]):
                    continue

                ret_1m = ((end_price - p_1m) / p_1m) * 100
                ret_3m = ((end_price - p_3m) / p_3m) * 100
                ret_6m = ((end_price - p_6m) / p_6m) * 100
                ret_9m = ((end_price - p_9m) / p_9m) * 100
                score = ret_1m + ret_3m + ret_6m + ret_9m
                ticker_name = get_ticker_name(ticker, ticker_names)

                results.append({
                    "Ticker": ticker,
                    "Name": ticker_name,
                    "1M (%)": round(ret_1m, 2),
                    "3M (%)": round(ret_3m, 2),
                    "6M (%)": round(ret_6m, 2),
                    "9M (%)": round(ret_9m, 2),
                    "Gesamt-Score": round(score, 2)
                })
            except:
                continue

    print(f"\n-> Berechnung fertig! {len(results)} Ergebnisse erzielt.")

    ranking_df = pd.DataFrame(results)
    if not ranking_df.empty:
        ranking_df = ranking_df.sort_values(by="Gesamt-Score", ascending=False)

    weighted_results, price_data = calculate_weighted_performance(tickers, ticker_names)
    weighted_df = pd.DataFrame(weighted_results)
    if not weighted_df.empty:
        weighted_df = weighted_df.sort_values(by="Gewichteter Score", ascending=False)

    price_data_json = json.dumps(price_data, ensure_ascii=False).replace('</script>', '<\\/script>')
    ticker_names_json = json.dumps(ticker_names, ensure_ascii=False).replace('</script>', '<\\/script>')
    html_style = '''
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #121212; color: #e0e0e0; padding: 40px; text-align: center; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; justify-content: center; flex-wrap: wrap; }
        .tab-button { padding: 12px 24px; background: #0a4f6c; color: #f0f9ff; border: none; cursor: pointer; border-radius: 8px; font-weight: 600; transition: background 0.3s; }
        .tab-button.active { background: #1f7a8c; }
        .tab-button:hover { background: #1f7a8c; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .momentum-table { border-collapse: collapse; margin: 25px auto; width: 95%; max-width: 1100px; font-size: 0.95em; background: #1e1e1e; box-shadow: 0 0 30px rgba(0,0,0,0.35); border-radius: 12px; overflow: hidden; }
        .momentum-table thead { background: linear-gradient(90deg, #0a4f6c, #1f7a8c); }
        .momentum-table th, .momentum-table td { padding: 14px 18px; border-bottom: 1px solid #2c2c2c; }
        .momentum-table th { color: #f0f9ff; font-weight: 700; text-transform: uppercase; font-size: 0.85em; letter-spacing: 0.08em; }
        .momentum-table td { color: #e7e7e7; }
        .momentum-table tbody tr:nth-of-type(odd) { background-color: #171717; }
        .momentum-table tbody tr:nth-of-type(even) { background-color: #1f1f1f; }
        .momentum-table tbody tr:hover { background-color: #2e5f7c; color: #fff; }
        .momentum-table td:first-child { text-align: left; font-weight: 600; }
        .momentum-table td:not(:first-child) { text-align: right; }
        .momentum-table caption { caption-side: top; text-align: left; color: #99d0ff; padding: 12px 18px 0; font-size: 1em; }
        .table-footer { margin-top: 12px; color: #b0c7d6; font-size: 0.92em; }
    </style>
    <script type="application/json" id="price-data">{price_data_json}</script>
    <script type="application/json" id="ticker-names">{ticker_names_json}</script>
    <script>
        const priceData = JSON.parse(document.getElementById('price-data').textContent || '{}');
        const tickerNames = JSON.parse(document.getElementById('ticker-names').textContent || '{}');

        function showTab(tabName, button) {
            const tabs = document.querySelectorAll('.tab-content');
            tabs.forEach(tab => tab.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');

            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
        }

        function getFirstAvailablePriceOnOrAfter(ticker, targetDate) {
            const history = priceData[ticker];
            if (!history) return null;
            for (let i = 0; i < history.dates.length; i++) {
                if (history.dates[i] >= targetDate) {
                    return history.prices[i];
                }
            }
            return null;
        }

        function getLastAvailablePriceOnOrBefore(ticker, targetDate) {
            const history = priceData[ticker];
            if (!history) return null;
            for (let i = history.dates.length - 1; i >= 0; i--) {
                if (history.dates[i] <= targetDate) {
                    return history.prices[i];
                }
            }
            return null;
        }

        function safePercentChange(startPrice, endPrice) {
            if (startPrice === null || endPrice === null || startPrice === 0) return null;
            return ((endPrice / startPrice) - 1) * 100;
        }

        window.addEventListener('DOMContentLoaded', () => {
            const inputIds = ['period1_start', 'period1_end', 'period2_start', 'period2_end', 'weight1', 'weight2'];
            inputIds.forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.addEventListener('change', buildDynamicWeightedTable);
                    element.addEventListener('input', buildDynamicWeightedTable);
                }
            });
            buildDynamicWeightedTable();
        });

        function buildDynamicWeightedTable() {
            const period1Start = document.getElementById('period1_start').value;
            const period1End = document.getElementById('period1_end').value;
            const period2Start = document.getElementById('period2_start').value;
            const period2End = document.getElementById('period2_end').value;
            const weight1 = parseFloat(document.getElementById('weight1').value) || 0;
            const weight2 = parseFloat(document.getElementById('weight2').value) || 0;
            const output = document.getElementById('dynamic-weighted-output');
            const rows = [];

            output.innerHTML = '';
            if (!period1Start || !period1End || !period2Start || !period2End) {
                output.innerHTML = '<p style="color:#ff8080;">Bitte alle Datumsfelder ausfüllen.</p>';
                return;
            }

            Object.keys(priceData).forEach(ticker => {
                const price1Start = getFirstAvailablePriceOnOrAfter(ticker, period1Start);
                const price1End = getLastAvailablePriceOnOrBefore(ticker, period1End);
                const price2Start = getFirstAvailablePriceOnOrAfter(ticker, period2Start);
                const price2End = getLastAvailablePriceOnOrBefore(ticker, period2End);

                const perf1 = safePercentChange(price1Start, price1End);
                const perf2 = safePercentChange(price2Start, price2End);
                const weighted = perf1 !== null && perf2 !== null ? (perf1 * weight1 + perf2 * weight2) : null;

                rows.push({
                    ticker,
                    name: tickerNames[ticker] || '',
                    perf1,
                    perf2,
                    weighted
                });
            });

            const validRows = rows.filter(row => row.perf1 !== null && row.perf2 !== null);
            if (validRows.length === 0) {
                output.innerHTML = '<p style="color:#ff8080;">Keine gültigen Daten für den gewählten Zeitraum gefunden.</p>';
                return;
            }

            validRows.sort((a, b) => (b.weighted || -Infinity) - (a.weighted || -Infinity));

            let html = '<table class="momentum-table">';
            html += '<thead><tr><th>Ticker</th><th>Name</th><th>Period 1 (%)</th><th>Period 2 (%)</th><th>Gewichtet (%)</th></tr></thead><tbody>';
            validRows.forEach(row => {
                const perf1Text = row.perf1 !== null ? row.perf1.toFixed(2) + '%' : 'n/a';
                const perf2Text = row.perf2 !== null ? row.perf2.toFixed(2) + '%' : 'n/a';
                const weightedText = row.weighted !== null ? row.weighted.toFixed(2) + '%' : 'n/a';
                const nameText = row.name ? row.name : 'n/a';
                html += `<tr><td>${row.ticker}</td><td>${nameText}</td><td>${perf1Text}</td><td>${perf2Text}</td><td>${weightedText}</td></tr>`;
            });
            html += '</tbody></table>';
            output.innerHTML = html;
        }
    </script>
    '''
    html_style = html_style.replace('{price_data_json}', price_data_json)
    html_style = html_style.replace('{ticker_names_json}', ticker_names_json)
    if 'ranking_df' in locals() and not ranking_df.empty:
        table_html = ranking_df.to_html(index=False, border=0, classes='momentum-table')
    else:
        table_html = '<p style="color:#ff8080;">Keine Momentum-Ergebnisse vorhanden.</p>'

    if 'weighted_df' in locals() and not weighted_df.empty:
        table_html_weighted = weighted_df.to_html(index=False, border=0, classes='momentum-table')
    else:
        table_html_weighted = '<p style="color:#ff8080;">Keine gewichteten Ergebnisse vorhanden.</p>'
    full_html = f"""<html><head><title>Momentum Ranking</title>{html_style}</head><body>
    <h1>📈 Global Momentum Leaderboard</h1>
    <p>Letztes Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    <div class=\"tabs\">
        <button class=\"tab-button active\" onclick=\"showTab('tab-main', this)\">9-Monats Momentum</button>
        <button class=\"tab-button\" onclick=\"showTab('tab-weighted', this)\">Gewichtete Zeiträume</button>
    </div>
    <div id=\"tab-main\" class=\"tab-content active\">
        <h2>9-Monats Momentum Ranking</h2>
        {table_html}
    </div>
    <div id=\"tab-weighted\" class=\"tab-content\">
        <h2>Gewichtete Performance (2 Zeiträume)</h2>
        <div style=\"max-width: 1100px; margin: 0 auto 20px; text-align: left;\">
            <div style=\"display:flex; flex-wrap:wrap; gap:12px; align-items:center;\">
                <label>Start 1: <input id=\"period1_start\" type=\"date\" value=\"2024-12-31\"></label>
                <label>Ende 1: <input id=\"period1_end\" type=\"date\" value=\"2025-06-30\"></label>
                <label>Start 2: <input id=\"period2_start\" type=\"date\" value=\"2025-06-30\"></label>
                <label>Ende 2: <input id=\"period2_end\" type=\"date\" value=\"2026-12-31\"></label>
                <label>Gewicht 1: <input id=\"weight1\" type=\"number\" step=\"0.0001\" min=\"0\" max=\"1\" value=\"0.3333\"></label>
                <label>Gewicht 2: <input id=\"weight2\" type=\"number\" step=\"0.0001\" min=\"0\" max=\"1\" value=\"0.6667\"></label>
                <button class=\"tab-button\" style=\"margin-left:auto;\" onclick=\"buildDynamicWeightedTable()\">Neu berechnen</button>
            </div>
            <p style=\"margin-top:12px; color:#b0c7d6; font-size:0.95em;\">Wähle frei Deine Zeiträume und berechne die gewichtete Performance dynamisch im Browser.</p>
        </div>
        <h3>Interaktive Berechnung</h3>
        <div id=\"dynamic-weighted-output\"></div>
        <h3 style=\"margin-top:32px;\">Vorberechnete Standardwerte</h3>
        {table_html_weighted}
    </div>
    </body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("!!! ERFOLG: index.html ENTHÄLT JETZT ALLE LIVE-DATEN !!!\n")

if __name__ == "__main__":
    main()
