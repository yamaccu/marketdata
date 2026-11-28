Github Actionsを実行することで、日経平均、日経平均先物、金先物、ビットコイン、TOPIX連動ETFと、`tickers.csv` に登録した日本株・米国株・米国ETFのローソク足データ（日足と1時間足）を取得します。  
Pythonのyfinanceを使用しています。  
[yfinance](https://ranaroussi.github.io/yfinance/)

## 固定で取得するデータ

- 日経平均: `^N225`
- 日経平均先物: `NIY=F`（CME・円建て日経225先物）
- 金先物: `GC=F`
- ビットコイン: `BTC-USD`
- TOPIX代理データ: `1306.T`（NF・TOPIX ETF）

`yfinance` ではTOPIX指数そのものを直接取得できないため、TOPIX連動ETFの `1306.T` を代理データとして使用します。

## 日本株・米国株の監視銘柄

`tickers.csv` の `ticker` 列に、日本株の証券コードまたは米国株・米国ETFのティッカーを記載します。これまでの `memo` 列はそのまま使用できます。

```csv
ticker,memo
7186,横浜FG
314A,ゴールドETF
NVDA,NVIDIA
MSTU,米国ETF
MSTZ,米国ETF
```

- 日本株は `7203` や `314A` のような4文字コードから自動的に `.T` を付けて取得します。`7203.T` の指定も可能です。
- 米国株・米国ETFは `NVDA`、`AAPL`、`SPY`、`MSTU`、`MSTZ` のようにティッカーをそのまま記載します。
- 米国クラス株の `BRK.B` はYahoo Finance形式の `BRK-B` として取得・保存します。
- 日本株・米国株ともに日足と1時間足を出力し、1時間足の日時は日本時間（JST）に統一します。
- 例えば `NVDA` は `data/NVDA.csv` と `data/NVDA_1h.csv` に保存します。

米国株の価格は米ドル建て、日本株の価格は円建てです。

## CSV出力

各銘柄について、日足は直近1年、1時間足は直近約60日を保存します。  
列は以下です。

- `Open`
- `High`
- `Low`
- `Close`
- `Volume`
- `RSI14`
- `MA5`
- `MA25`
- `MA75`
- `ADX14`（既存のCSV列名を維持。値はiSPEED標準のADX9＝DI14を用いたDXの9本単純平均）
- `+DI14`
- `-DI14`

数値は小数点第1位に四捨五入して保存します。

データ取得前に `data/` 配下の既存CSVをすべて削除してから、現在の固定5資産と `tickers.csv` に登録されている日本株・米国株・米国ETFを再取得します。監視対象から外した銘柄の古いCSVは次回実行時に削除されます。
