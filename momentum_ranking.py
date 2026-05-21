cat << 'EOF' > momentum_ranking.py
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def main():
    print("\n==========================================")
    print("!!! START: LIVE-RUN MIT AKTIENNAMEN !!!")
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

                # Hier holen wir den echten Firmennamen ab
                try:
                    yf_ticker_obj = yf.Ticker(ticker)
                    company_name = yf_ticker_obj.info.get('longName', ticker)
                except:
                    company_name = ticker # Fallback falls Yahoo blockiert

                results.append({
                    "Ticker": ticker,
                    "Name": company_name,
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
        # Sortieren und Spaltenreihenfolge fixieren, damit Name direkt neben dem Ticker steht
        ranking_df = ranking_df.sort_values(by="Gesamt-Score", ascending=False)
        cols = ["Ticker", "Name", "1M (%)", "3M (%)", "6M (%)", "9M (%)", "Gesamt-Score"]
        ranking_df = ranking_df[cols]

    html_style = """
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #121212; color: #e0e0e0; padding: 40px; text-align: center; }
        .momentum-table { border-collapse: collapse; margin: 25px auto; width: 95%; max-width: 1200px; font-size: 0.95em; background: #1e1e1e; box-shadow: 0 0 30px rgba(0,0,0,0.35); border-radius: 12px; overflow: hidden; }
        .momentum-table thead { background: linear-gradient(90deg, #0a4f6c, #1f7a8c); }
        .momentum-table th, .momentum-table td { padding: 14px 18px; border-bottom: 1px solid #2c2c2c; }
        .momentum-table th { color: #f0f9ff; font-weight: 700; text-transform: uppercase; font-size: 0.85em; letter-spacing: 0.08em; text-align: center; }
        .momentum-table td { color: #e7e7e7; text-align: center; }
        .momentum-table tbody tr:nth-of-type(odd) { background-color: #171717; }
        .momentum-table tbody tr:nth-of-type(even) { background-color: #1f1f1f; }
        .momentum-table tbody tr:hover { background-color: #2e5f7c; color: #fff; }
        
        /* Ticker und Name linksbündig ausrichten */
        .momentum-table td:nth-child(1), .momentum-table td:nth-child(2) { text-align: left; font-weight: 600; }
        .momentum-table td:nth-child(2) { font-weight: 400; color: #b0c7d6; } /* Name etwas dezenter */
    </style>
    """
    
    table_html = ranking_df.to_html(index=False, border=0, classes='momentum-table')
    full_html = f"<html><head><title>Momentum Ranking</title>{html_style}</head><body><h1>📈 Global Momentum Leaderboard</h1><p>Letztes Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>{table_html}</body></html>"

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("!!! ERFOLG: index.html ENTHÄLT JETZT ALLE LIVE-DATEN INKLUSIVE AKTIENNAMEN !!!\n")

if __name__ == "__main__":
    main()
EOF
