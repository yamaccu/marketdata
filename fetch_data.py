from pathlib import Path

import pandas as pd
import yfinance as yf


# 保存する市場データ
ASSETS = {
    "nikkei225": "^N225",
    "gold_futures": "GC=F",
    "bitcoin": "BTC-USD",
}

# CSVの保存先
OUTPUT_DIR = Path("data")


def download_asset(file_name: str, ticker: str) -> None:
    """Yahoo Financeから日足データを取得してCSVに保存する。"""

    print(f"{ticker} の取得を開始します")

    data = yf.download(
        tickers=ticker,
        period="1y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
        timeout=30,
        multi_level_index=False,
    )

    if data is None or data.empty:
        raise RuntimeError(f"{ticker} のデータを取得できませんでした")

    # yfinanceのバージョン差異に備えて、MultiIndexなら単一階層にする
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()

    # 日足では通常Dateだが、念のためDatetimeにも対応
    if "Datetime" in data.columns and "Date" not in data.columns:
        data = data.rename(columns={"Datetime": "Date"})

    if "Date" not in data.columns:
        raise RuntimeError(f"{ticker} の日付列が見つかりません")

    # 日付を YYYY-MM-DD に統一
    data["Date"] = pd.to_datetime(data["Date"]).dt.strftime("%Y-%m-%d")

    # 列の並びを整理
    preferred_columns = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]

    available_columns = [
        column for column in preferred_columns if column in data.columns
    ]

    data = data[available_columns]

    output_path = OUTPUT_DIR / f"{file_name}.csv"

    data.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        float_format="%.6f",
    )

    latest_date = data["Date"].iloc[-1]

    print(
        f"{ticker}: {len(data)}行を保存しました "
        f"(最新日: {latest_date}, 保存先: {output_path})"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []

    for file_name, ticker in ASSETS.items():
        try:
            download_asset(file_name, ticker)
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            print(f"エラー: {ticker}: {exc}")

    # 1銘柄でも失敗したらActionsを失敗扱いにする
    if errors:
        error_message = "\n".join(errors)
        raise RuntimeError(
            "一部のデータ取得に失敗しました:\n"
            f"{error_message}"
        )

    print("すべての市場データを正常に保存しました")


if __name__ == "__main__":
    main()
