from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf


OUTPUT_DIR = Path("data")
JST = "Asia/Tokyo"

ASSETS = {
    "nikkei225": {
        "ticker": "^N225",
        "source_timezone": "Asia/Tokyo",
    },
    "gold_futures": {
        "ticker": "GC=F",
        "source_timezone": "America/Chicago",
    },
    "bitcoin": {
        "ticker": "BTC-USD",
        "source_timezone": "UTC",
    },
}

PRICE_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
    "Volume",
]


def download_data(
    ticker: str,
    interval: str,
    period: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Yahoo Financeから価格データを取得する。"""

    data = yf.download(
        tickers=ticker,
        period=period,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        timeout=30,
        prepost=False,
        multi_level_index=False,
    )

    if data is None or data.empty:
        raise RuntimeError(
            f"{ticker}の{interval}データを取得できませんでした"
        )

    # yfinanceのバージョン差に対応
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return data


def select_price_columns(data: pd.DataFrame) -> pd.DataFrame:
    """存在する価格列だけを取り出す。"""

    columns = [
        column
        for column in PRICE_COLUMNS
        if column in data.columns
    ]

    return data[columns].copy()


def save_daily_data(
    file_name: str,
    ticker: str,
) -> None:
    """取得可能な全期間の日足をCSVへ上書き保存する。"""

    print(f"{ticker}の日足を取得します")

    data = download_data(
        ticker=ticker,
        period="1y",
        interval="1d",
    )

    data = select_price_columns(data)
    data.index.name = "Date"

    output = data.reset_index()

    output["Date"] = pd.to_datetime(
        output["Date"]
    ).dt.strftime("%Y-%m-%d")

    output_path = OUTPUT_DIR / f"{file_name}.csv"

    output.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        float_format="%.6f",
    )

    print(
        f"{ticker} 日足: {len(output)}行を保存しました "
        f"({output_path})"
    )


def convert_index_to_jst(
    data: pd.DataFrame,
    source_timezone: str,
) -> pd.DataFrame:
    """時刻インデックスを日本時間に変換する。"""

    result = data.copy()
    index = pd.DatetimeIndex(
        pd.to_datetime(result.index)
    )

    if index.tz is None:
        # 通常、yfinanceの日中足はタイムゾーン付きだが、
        # 付いていない場合は市場のタイムゾーンとして扱う
        index = index.tz_localize(
            source_timezone,
            ambiguous="infer",
            nonexistent="shift_forward",
        )

    result.index = index.tz_convert(JST)

    return result


def remove_incomplete_hour(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """まだ確定していない最新の1時間足を除外する。"""

    now_jst = pd.Timestamp.now(tz=JST)

    completed = (
        data.index + pd.Timedelta(hours=1)
        <= now_jst
    )

    return data.loc[completed].copy()


def save_hourly_data(
    file_name: str,
    ticker: str,
    source_timezone: str,
) -> None:
    """直近約60日の1時間足をCSVへ上書き保存する。"""

    print(f"{ticker}の1時間足を取得します")

    # yfinanceの日中足は直近60日までなので、
    # 境界エラーを避けるため59日前から取得する
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=59)

    data = download_data(
        ticker=ticker,
        start=start,
        end=end,
        interval="1h",
    )

    data = convert_index_to_jst(
        data,
        source_timezone=source_timezone,
    )

    data = remove_incomplete_hour(data)
    data = select_price_columns(data)

    data.index.name = "Datetime"
    output = data.reset_index()

    # ISO形式の日本時間として保存
    output["Datetime"] = (
        pd.to_datetime(output["Datetime"], utc=True)
        .dt.tz_convert(JST)
        .dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    )

    output_path = OUTPUT_DIR / f"{file_name}_1h.csv"

    output.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
        float_format="%.6f",
    )

    print(
        f"{ticker} 1時間足: {len(output)}行を保存しました "
        f"({output_path})"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    errors: list[str] = []

    for file_name, config in ASSETS.items():
        ticker = config["ticker"]

        try:
            save_daily_data(
                file_name=file_name,
                ticker=ticker,
            )

            save_hourly_data(
                file_name=file_name,
                ticker=ticker,
                source_timezone=config["source_timezone"],
            )

        except Exception as exc:
            message = f"{ticker}: {exc}"
            errors.append(message)
            print(f"エラー: {message}")

    if errors:
        raise RuntimeError(
            "一部のデータ取得に失敗しました:\n"
            + "\n".join(errors)
        )

    print("すべての市場データを正常に保存しました")


if __name__ == "__main__":
    main()
