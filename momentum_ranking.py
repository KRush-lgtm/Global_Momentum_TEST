import os
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf


def main():
    # 1. Ticker einlesen
    csv_path = "ticker.csv"
    if not os.path.exists(csv_path):
        print(f"Fehler: {csv_path} nicht gefunden.")
        return

    df_ticker = pd.read_csv(csv_path)
    ticker_col = (
        "Ticker" if "Ticker" in df_ticker.columns else df_ticker.columns[0]
    )
    tickers = df_ticker[ticker_col].dropna().astype(str).str.strip().tolist()
    tickers = list(dict.fromkeys(tickers))

    # 2. Zeiträume bestimmen
    today = datetime.today()
    periods = {
        "1M": today - timedelta(days=30),
        "3M": today - timedelta(days=91),
        "6M": today - timedelta(days=182),
        "9M": today - timedelta(days=273),
    }
    start_date = min(periods.values()) - timedelta(days=10)

    # 3. Daten abrufen
    raw_data = yf.download(
        tickers, start=start_date, end=today, group_by="ticker"
    )

    results = []
    if len(tickers) == 1:
        raw_data = {tickers[0]: raw_data}

    for ticker in tickers:
        try:
            if len(tickers) > 1:
                if ticker not in raw_data.columns.levels[0]:
                    continue
                ticker_df = raw_data[ticker].dropna(subset=["Adj Close"])
            else:
                ticker_df = raw_data.dropna(subset=["Adj Close"])

            if ticker_df.empty:
                continue

            end_price = ticker_df["Adj Close"].iloc[-1]

            def get_historic_price(target_date):
                avail = ticker_df.index[ticker_df.index >= target_date]
                return ticker_df.loc[avail[0], "Adj Close"] if not avail.empty else None

            p_1m, p_3m, p_6m, p_9m = (
                get_historic_price(periods["1M"]),
                get_historic_price(periods["3M"]),
                get_historic_price(periods["6M"]),
                get_historic_price(periods["9M"]),
            )

            if any(p is None for p in [p_1m, p_3m, p_6m, p_9m]):
                continue

            ret_1m = ((end_price - p_1m) / p_1m) * 100
            ret_3m = ((end_price - p_3m) / p_3m) * 100
            ret_6m = ((end_price - p_6m) / p_6m) * 100
            ret_9m = ((end_price - p_9m) / p_9m) * 100
            score = ret_1m + ret_3m + ret_6m + ret_9m

            results.append(
                {
                    "Ticker": ticker,
                    "1M (%)": round(ret_1m, 2),
                    "3M (%)": round(ret_3m, 2),
                    "6M (%)": round(ret_6m, 2),
                    "9M (%)": round(ret_9m, 2),
                    "Gesamt-Score": round(score, 2),
                }
            )
        except:
            continue

    if not results:
        return

    ranking_df = pd.DataFrame(results).sort_values(
        by="Gesamt-Score", ascending=False
    )

    # 4. Schönes HTML-Dashboard generieren (CSS für Darkmode & tabellarische Ansicht)
    html_style = """
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; padding: 40px; }
        h1 { color: #ffffff; text-align: center; }
        .update-time { text-align: center; color: #888; margin-bottom: 30px; }
        table { border-collapse: collapse; margin: 25px auto; font-size: 0.9em; min-width: 400px; box-shadow: 0 0 20px rgba(0, 0, 0, 0.15); border-radius: 8px; overflow: hidden; }
        th { background-color: #1f1f1f; color: #ffffff; text-align: left; font-weight: bold; padding: 12px 15px; border-bottom: 2px solid #333; }
        td { padding: 12px 15px; border-bottom: 1px solid #222; }
        tr:nth-of-type(even) { background-color: #1a1a1a; }
        tr:hover { background-color: #252525; }
        .pos { color: #4caf50; font-weight: bold; }
        .neg { color: #f44336; font-weight: bold; }
    </style>
    """

    # Erzeuge die reine HTML-Tabelle aus Pandas
    table_html = ranking_df.to_html(index=False, classes="gtaa-table")

    # Farbliche Formatierung für positive/negative Werte hinzufügen
    table_html = table_html.replace("<td>-", '<td class="neg">-').replace(
        "<td>", '<td class="pos">'
    )
    table_html = table_html.replace(
        '<td class="pos">' + "Ticker" if "Ticker" in table_html else "",
        "<td>",
    )  # Ticker-Spalte neutral lassen

    # Finale HTML-Seite zusammensetzen
    full_html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>Momentum Dashboard</title>
        {html_style}
    </head>
    <body>
        <h1>📈 Global Momentum Leaderboard</h1>
        <div class="update-time">Letztes Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</div>
        {table_html}
    </body>
    </html>
    """

    # Als index.html abspeichern (Wichtig für GitHub Pages)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)


if __name__ == "__main__":
    main()
