import os
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

def main():
    print("--- START DES SKRIPTS ---")
    csv_path = "ticker.csv"
    
    if not os.path.exists(csv_path):
        print(f"CRITICAL ERROR: '{csv_path}' existiert nicht im Ordner!")
        return

    print("-> ticker.csv erfolgreich gefunden. Lese Zeilen ein...")
    df_ticker = pd.read_csv(csv_path)
    ticker_col = "Ticker" if "Ticker" in df_ticker.columns else df_ticker.columns[0]
    tickers = df_ticker[ticker_col].dropna().astype(str).str.strip().tolist()
    tickers = list(dict.fromkeys(tickers))
    print(f"-> {len(tickers)} eindeutige Ticker eingelesen.")

    today = datetime.today()
    start_date = today - timedelta(days=380)
    
    print(f"-> Starte Daten-Download von Yahoo Finance (Zeitraum: {start_date.date()} bis {today.date()})...")
    
    try:
        raw_data = yf.download(tickers, start=start_date, end=today, group_by='ticker')
        print("-> Download von Yahoo beendet. Verarbeite Sektoren...")
    except Exception as e:
        print(f"CRITICAL ERROR beim Yahoo-Download: {e}")
        return

    periods = {
        "1M": today - timedelta(days=30),
        "3M": today - timedelta(days=91),
        "6M": today - timedelta(days=182),
        "9M": today - timedelta(days=273)
    }

    results = []
    
    # Falls nur 1 Ticker in der Liste ist, Struktur anpassen
    if len(tickers) == 1:
        raw_data = {tickers[0]: raw_data}

    print("-> Berechne Momentum-Scores für die Tickerliste...")
    for i, ticker in enumerate(tickers):
        try:
            if len(tickers) > 1:
                if ticker not in raw_data.columns.levels[0]:
                    continue
                ticker_df = raw_data[ticker].dropna(subset=["Adj Close"])
            else:
                ticker_df = raw_data.dropna(subset=["Adj Close"])

            if ticker_df.empty or len(ticker_df) < 10:
                continue

            end_price = ticker_df["Adj Close"].iloc[-1]

            def get_historic_price(target_date):
                avail = ticker_df.index[ticker_df.index >= pd.Timestamp(target_date).date()]
                return ticker_df.loc[avail[0], "Adj Close"] if not avail.empty else None

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

            results.append({
                "Ticker": ticker,
                "1M (%)": round(ret_1m, 2),
                "3M (%)": round(ret_3m, 2),
                "6M (%)": round(ret_6m, 2),
                "9M (%)": round(ret_9m, 2),
                "Gesamt-Score": round(score, 2)
            })
        except Exception as e:
            # Fehler bei einzelnen Aktien ignorieren, einfach weitermachen
            continue

    print(f"-> Berechnung abgeschlossen. {len(results)} gültige Ergebnisse erzielt.")

    # Hier erstellen wir das DataFrame auf jeden Fall
    ranking_df = pd.DataFrame(results)
    if not ranking_df.empty:
        ranking_df = ranking_df.sort_values(by="Gesamt-Score", ascending=False)

    print("-> Generiere HTML-Code...")
    html_style = """
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #121212; color: #e0e0e0; padding: 40px; text-align: center; }
        table { border-collapse: collapse; margin: 25px auto; font-size: 0.9em; min-width: 600px; background: #1e1e1e; }
        th { background-color: #2d2d2d; color: white; padding: 12px 15px; }
        td { padding: 12px 15px; border-bottom: 1px solid #333; }
        tr:nth-of-type(even) { background-color: #1a1a1a; }
    </style>
    """
    
    table_html = ranking_df.to_html(index=False)
    full_html = f"<html><head>{html_style}</head><body><h1>📈 Global Momentum Leaderboard</h1><p>Letztes Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>{table_html}</body></html>"

    print("-> Versuche, index.html auf die Festplatte zu schreiben...")
    try:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("!!! ERFOLG: index.html wurde erfolgreich erstellt !!!")
    except Exception as e:
        print(f"CRITICAL ERROR beim Schreiben der HTML-Datei: {e}")

if __name__ == "__main__":
    main()
