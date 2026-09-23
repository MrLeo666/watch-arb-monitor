# 錶市套利監控台 Watch Auction Arbitrage Monitor

私人用途:監控目標品牌(F.P. Journe / Patek Philippe / Cartier / 限量獨立製錶)在各拍賣平台的
上拍與成交,支援「小平台買入 → 大行出貨」的跨市場套利決策。

## 架構

```
GitHub Actions(每日 06:00 HKT cron)
  └─ build.py
       ├─ adapters/phillips.py    ← 已實地驗證:自動發現 08 系列鐘錶專場,解析頁內 lot tiles
       ├─ adapters/loupethis.py   ← 已實地驗證:公開 JSON API,含實時出價與 10% 買家佣金
       ├─ adapters/crott.py       ← Auktionen Dr. Crott (uhren-muser.de):公開 JSON,估價推斷為 EUR
       ├─ 匯率正規化(open.er-api.com,免費)→ USD / HKD
       ├─ 套利評分(landed cost vs 公允價;香港進口稅 0%)
       ├─ 變更偵測(新標的 is_new)→ Telegram 通知(可選)
       └─ docs/lots.json + docs/meta.json
GitHub Pages(docs/)
  └─ index.html 繁中儀表板:品牌分組、搜尋、平台/狀態篩選、新標的高亮
```

## 部署步驟(一次性,約 10 分鐘)

1. **建 repo(建議 Private)**:GitHub 新建 repo,如 `watch-arb-monitor`,把本目錄全部檔案推上去:
   ```bash
   cd watch-arb-monitor
   git init && git add -A && git commit -m "init"
   git branch -M main
   git remote add origin git@github.com:<你的帳號>/watch-arb-monitor.git
   git push -u origin main
   ```
2. **開 Pages**:repo → Settings → Pages → Source 選 `Deploy from a branch`,
   Branch 選 `main` / `/docs`。私有 repo 的 Pages 需 GitHub Pro(你應已有);
   或改用 public repo(資料僅為公開拍賣目錄摘要,風險有限,自行斟酌)。
3. **開 Actions 寫入權限**:Settings → Actions → General → Workflow permissions →
   勾 `Read and write permissions`。
4. **手動跑第一次**:Actions → `watch-arb-scrape` → Run workflow。
   之後每日 06:00 HKT 自動更新(GitHub cron 常延遲 10–30 分鐘,屬正常)。
5. **(可選)Telegram 通知**:向 @BotFather 建 bot 取得 token;向 bot 發一句話後用
   `https://api.telegram.org/bot<TOKEN>/getUpdates` 查你的 chat id。
   repo → Settings → Secrets and variables → Actions 加入 `TG_TOKEN`、`TG_CHAT`。
   之後每有白名單新標的即時推送。
6. **(可選)WatchCharts 公允價**:訂閱 WatchCharts API 後把 key 存為
   `WATCHCHARTS_API_KEY` secret,並補完 `build.py` 內 `enrich_fair_value()` 的查價邏輯
   (兩步:search → uuid → price;限 1 req/s;授權僅限內部使用,故儀表板請保持私有)。
   公允價一旦有值,毛利欄與「套利標記」自動生效。

## 本地測試

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v  # 離線回歸測試，不抓取或發通知
node tests/test_dashboard.cjs  # 出價幣種、資料渲染與篩選檢查
python build.py          # 產生 docs/lots.json
cd docs && python -m http.server 8000   # 瀏覽 http://localhost:8000
```

## 目前覆蓋與路線圖

評分口徑：0% 買家佣金按零計算，只有缺失值才使用預設 25%；未知幣種不換算、不產生套利訊號。
一般公允價扣除 12% 賣方成本；Chrono24 掛牌價 × 0.85 已是模型淨回款，不再重複扣除。
已結束拍品保留成交換算，但不列為套利機會。以上均為模型假設，並非可成交報價。
當所有抓取結果均為空時，更新會失敗並保留現有資料；部分平台缺失仍需人工核查。

| 階段 | 內容 | 狀態 |
|---|---|---|
| Phase 1 | Phillips(全部鐘錶專場,含過往成交作公允價參照)+ Loupe This(實時出價) | ✅ 已驗證 |
| Phase 2a | Bezel(0% 買家佣金、實時出價、圖片)+ Antiquorum(自動發現場次、EUR 估價、圖片);儀表板加入縮圖欄 | ✅ 已驗證 |
| Phase 2b | 已實測被 WAF/JS 擋、暫緩:Catawiki、the-saleroom、Bukowskis、Heritage(403)、Watches of Knightsbridge、Fortuna(202 challenge)、Dorotheum / Poly HK / Artcurial(JS 渲染);替代:官方 email 提醒或付費 Apify | 🔜 |
| Phase 3a | 內部比價引擎(comps.py):以自家成交檔案(docs/archive.json,每日自動累積、永久保存)推算公允價與毛利;含離散度與合理性雙重守衛防錯配 | ✅ 已上線 |
| Phase 3b | Chrono24 參考編號定價(c24.py):同 ref 最低要價×0.85 作保守出貨淨得,7 天緩存,優先於 comps | ✅ 已上線 |
| Phase 3c | WatchCharts 接入、賣出情境比較 | 🔜 |
| Phase 4 | Watch Collecting(Algolia SSR,實時出價)+ Monaco Legend(自動發現場次,CHF/EUR 估價)+ Allu(日本 Valuence 拍賣,JPY 估價;出價需會員資格,僅作行情參照)+ Dr. Crott(uhren-muser.de JSON,估價推斷 EUR,無佣金欄位則不填) | ✅ 已驗證 |

## 已知限制(誠實聲明)

- Phillips 未公佈拍品的場次(HIGHLIGHTS_ONLY)抓不到 lot,公佈後自動出現。
- Catawiki、the-saleroom、Bukowskis 等對機房 IP 有 WAF 封鎖,GitHub Actions 大概率同樣被擋;
  這些平台建議用其官方關鍵字提醒(免費)作為補充,或評估付費 Apify。
- 佣金/稅費為簡化模型(買家佣金取平台首檔、賣方成本 12%、運保 3%、匯兌 1.5%),
  實際以各場 Conditions of Sale 及議定條款為準。
- 過往成交價未經品相調整,作公允價參照時須自行判斷(品相、配件、來源對錶價影響巨大)。
- Daniel Roth / Gérald Genta 因品牌名被 Bulgari 復用,標「須人工核對」。

## 檔案結構

```
adapters/base.py        # Lot 資料模型 + 品牌白名單與別名匹配
adapters/phillips.py    # Phillips adapter(已驗證)
adapters/loupethis.py   # Loupe This adapter(已驗證)
adapters/bezel.py       # Bezel adapter(已驗證,0% BP + 實時出價)
adapters/antiquorum.py  # Antiquorum adapter(已驗證,自動發現場次)
adapters/watchcollecting.py  # Watch Collecting adapter(已驗證,Algolia SSR 實時出價)
adapters/monacolegend.py     # Monaco Legend adapter(已驗證,自動發現場次)
adapters/allu.py        # Allu adapter(已驗證,日本 Valuence 拍賣,JPY)
adapters/crott.py       # Dr. Crott adapter(uhren-muser.de JSON; currency inferred EUR)
build.py                # 主程式:抓取→匯率→評分→變更偵測→通知→輸出
comps.py                # 內部比價引擎:以 archive.json 成交檔案推算公允價
c24.py                  # Chrono24 參考編號定價(7 天緩存)
docs/index.html         # 繁中儀表板(GitHub Pages)
docs/lots.json          # 資料(由 build.py 產生,Actions 每日提交)
docs/archive.json       # 成交檔案(每日累積、永久保存,comps 公允價基礎)
docs/c24_cache.json     # Chrono24 查價緩存
.github/workflows/scrape.yml
requirements.txt
```

## 決策台試用版（2026-09-23）

- 收藏清單及逐件報價參數只寫入瀏覽器 localStorage；不提交至 GitHub、不跨裝置同步。清除網站資料會刪除收藏及参数。
- 報價試算全程使用拍品原幣：`(出售淨回款 - 固定成本 - 最低利潤) / (1 + 買家佣金率 + 其他費率)`，按輸入步幅向下取整。所有成本均須輸入；預填佣金仍須核實。尚不支援階梯佣金、特殊競價檔位或品相自動估價。
- 價格核驗超過 30 分鐘時停用套利標記篩選及毛利顯示；每日抓取頻率尚未改變。此時應直接核對官方頁面，試算結果僅是使用者假設。
- Loupe This / Bezel / Watch Collecting 保留來源的逐件 `ends_at`；只有附時區的完整時間（或來源明確 UTC 的欄位）才生成倒計時。舊資料日期不會被猜測為午夜。
- 已收藏且 24 小時內結標的拍品顯示於頁面概覽，每分鐘重算。這是頁內提醒，關閉頁面不會推送；尚未新增電郵、Telegram 或後台排程。
- 下次抓取產生 `meta.sources`，記錄各適配器返回數量及疑似失敗。既有適配器可能吞掉異常，`returned` 不代表來源完整；未有記錄時明確顯示未知。

測試：`python -m unittest discover -s tests -v` 及 `node tests/test_dashboard.cjs`。

周邊過濾：抓取後排除標題可明確識別的獨立表盒、上鏈盒、書籍、配件、禮品和座鐘；完整手表附盒、證書、表帶不因附件關鍵字被排除。模糊標題保留，懷表保留。歷史檔案原件不刪除，但比價引擎跳過周邊記錄。
