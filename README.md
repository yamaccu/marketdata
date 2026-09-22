日経平均、金先物、ビットコイン、TOPIX連動ETFと、`tickers.csv` に登録した日本株のローソク足データ（日足と1時間足）を、1日1回、17:15に取得します。  
Pythonのyfinanceを使用しています。  
[yfinance](https://ranaroussi.github.io/yfinance/)

## 固定で取得するデータ

- 日経平均: `^N225`
- 金先物: `GC=F`
- ビットコイン: `BTC-USD`
- TOPIX代理データ: `1306.T`（NF・TOPIX ETF）

`yfinance` ではTOPIX指数そのものを直接取得できないため、TOPIX連動ETFの `1306.T` を代理データとして使用します。  
出力ファイルは `data/topix_etf.csv` と `data/topix_etf_1h.csv` です。

## 日本株の監視銘柄

`tickers.csv` の `ticker` 列に4文字の証券コードを記載します。

```csv
ticker
7186
5016
7011
```

日本株は自動的に `.T` を付けてYahoo Financeから取得します。  
例えば `7186` は `7186.T` として取得し、`data/7186.csv` と `data/7186_1h.csv` に保存します。

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

数値は小数点第1位に四捨五入して保存します。

データ取得前に `data/` 配下の既存CSVをすべて削除してから、現在の固定4資産と `tickers.csv` に登録されている日本株を再取得します。監視対象から外した銘柄の古いCSVは次回実行時に削除されます。
