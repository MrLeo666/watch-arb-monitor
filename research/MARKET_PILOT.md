# 新市場試接：2026-09-23（分頁已補齊）

已獲授權部署試接來源；網站標示不評分，GitHub Actions 開啟每日抓取。

## Sotheby's

已從官網目錄實際請求確認公開 GraphQL 分頁方式：`lotCardsConnection(offset, limit, filter: ALL)`。以場次頁取得 auctionId，再逐頁讀取，不依賴固定 UUID。

巴黎 Fine Watches PF2660 完整取得 107 件：offset 0 / 48 / 96，分別 48 / 48 / 11 件，唯一 lotId 合計 107。按既有品牌及完整手表規則保留 26 件，比首批目錄小樣增加 7 件。

每頁校驗 totalCount、hasNextPage、拍品唯一編號；重複／空頁無進展、總數變動、提前結束、接口 errors、場次不符及超過安全頁數均報錯，不輸出半份場次。最終 0 件表示接口當時未提供目錄，不能推論該場沒有拍品。

仍是試接：僅接納已驗證的 Published/pre-bid 狀態；成交與即時競價狀態尚未接入，逐件 closingTime 不能取代官方臨場延時核驗。已抓取總數指原始目錄覆蓋，不代表所有狀態都顯示在本地列表。

## Bonhams

部門頁本輪發現 4 場，當時目錄共只返回 5 件，均未通過目標品牌／完整手表篩選。另以 Weekly: Watches 31990 作歷史對照，兩頁取得 86 件，保留 3 件已成交手表。落槌價 hammerPrice 與含佣价 hammerPremium 分開；流拍、撤拍、未識別狀態不冒充成交。

## 使用與限制

小樣及逐場覆蓋報告為 market-pilot-lots.json、market-pilot.json（包含時間、來源、分頁統計）。所有試接拍品 scoring_enabled=false，不進套利評分、C24 查價或歷史比價索引。佣金留空。

```bash
.venv/bin/python scripts/market_pilot.py
python3 -m http.server 8766 --bind 127.0.0.1 --directory research/preview
```

主流程僅在明確設置 EXPERIMENTAL_MARKETS=1 時加入兩個適配器，此開關已加入 GitHub Actions。

測試包含完整分頁、重複頁、重疊去重、總數變動、空目錄、接口錯誤、頁數上限及價格口徑。當日重複抓取只能證明本次可重現；跨日穩定性及 GitHub Actions 網絡環境尚待驗證。歷史成交未用第二獨立來源核驗，本輪為資料管道驗證，不構成估值依據。
