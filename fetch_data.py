from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re

import pandas as pd
import yfinance as yf


OUTPUT_DIR = Path("data")
TICKERS_FILE = Path("tickers.csv")
JST = "Asia/Tokyo"
RSI_PERIOD = 14
MA_PERIODS = (5, 25, 75)

FIXED_ASSETS = {
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
    "Volume",
]


def load_japanese_stocks() -> dict[str, dict[str, str]]:
    """tickers.csvから日本株の監視銘柄を読み込む。"""

    if not TICKERS_FILE.exists():
        raise FileNotFoundError(
            f"{TICKERS_FILE}が見つかりません"
        )

    config = pd.read_csv(
        TICKERS_FILE,
        dtype=str,
    )

    if "ticker" not in config.columns:
        raise ValueError(
            "tickers.csvにはticker列が必要です"
        )

    assets: dict[str, dict[str, str]] = {}

    for raw_ticker in config["ticker"].dropna():
        code = raw_ticker.strip().upper()

        if not code:
            continue

        # 誤って .T を付けても受け付ける
        if code.endswith(".T"):
            code = code[:-2]

        # 日本の証券コードは数字または英数字4文字を想定
        if not re.fullmatch(r"[0-9A-Z]{4}", code):
            raise ValueError(
                f"日本株の銘柄コードとして不正です: {raw_ticker}"
            )

        if code in assets:
            continue

        assets[code] = {
            "ticker": f"{code}.T",
            "source_timezone": JST,
        }

    return assets


def clear_old_csvs() -> None:
    """新しいデータ取得前にdata配下の既存CSVをすべて削除する。"""

    deleted = 0

    for csv_path in OUTPUT_DIR.glob("*.csv"):
        csv_path.unlink()
        deleted += 1

    print(f"既存CSVを{deleted}件削除しました")


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


def round_half_up_1(value: float) -> float:
    """小数点第2位以下を四捨五入し、小数点第1位までのfloatにする。"""

    if pd.isna(value):
        return value

    return float(
        Decimal(str(value)).quantize(
            Decimal("0.1"),
            rounding=ROUND_HALF_UP,
        )
    )


def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """終値からRSI(14)と単純移動平均(5/25/75)を計算して追加する。"""

    result = data.copy()
    close = result["Close"]

    # Wilder方式のRSI（14期間）
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / RSI_PERIOD,
        adjust=False,
        min_periods=RSI_PERIOD,
    ).mean()
    avg_loss = loss.ewm(
        alpha=1 / RSI_PERIOD,
        adjust=False,
        min_periods=RSI_PERIOD,
    ).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # 値動きがない場合などのゼロ除算を明示的に処理
    rsi = rsi.mask(
        (avg_gain == 0) & (avg_loss == 0),
        50.0,
    )
    rsi = rsi.mask(
        (avg_gain > 0) & (avg_loss == 0),
        100.0,
    )
    rsi = rsi.mask(
        (avg_gain == 0) & (avg_loss > 0),
        0.0,
    )

    result[f"RSI{RSI_PERIOD}"] = rsi

    for period in MA_PERIODS:
        result[f"MA{period}"] = close.rolling(
            window=period,
            min_periods=period,
        ).mean()

    # CSVへ出力する全数値列を小数点第1位に四捨五入する
    for column in result.columns:
        result[column] = result[column].map(round_half_up_1)

    return result


def save_daily_data(
    file_name: str,
    ticker: str,
) -> None:
    """直近1年の日足をCSVへ保存する。"""

    print(f"{ticker}の日足を取得します")

    data = download_data(
        ticker=ticker,
        period="1y",
        interval="1d",
    )

    data = select_price_columns(data)
    data = add_technical_indicators(data)
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
        float_format="%.1f",
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
    """直近約60日の1時間足をCSVへ保存する。"""

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
    data = add_technical_indicators(data)

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
        float_format="%.1f",
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

    # 設定ミスで既存データを消さないよう、先に設定ファイルを検証する
    japanese_stocks = load_japanese_stocks()

    assets = {
        **FIXED_ASSETS,
        **japanese_stocks,
    }

    print(
        f"固定3資産 + 日本株{len(japanese_stocks)}銘柄を取得します"
    )

    clear_old_csvs()

    errors: list[str] = []

    for file_name, config in assets.items():
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
