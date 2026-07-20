# 錶市套利監控台 Watch Auction Arbitrage Monitor

私人用途:監控目標品牌(F.P. Journe / Patek Philippe / Cartier / 限量獨立製錶)在各拍賣平台的
上拍與成交,支援「小平台買入 → 大行出貨」的跨市場套利決策。

## 架構

```
GitHub Actions(每日 06:00 HKT cron)
  └─ build.py
       ├─ adapters/phillips.py    ← 已實地驗證:自動發現 08 系列鐘錶專場,解析頁內 lot tiles
       ├─ adapters/loupethis.py   ← 已實地驗證:公開 JSON API,含實時出價與 10% 買家佣金
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
pip install -r requirements.txt
python build.py          # 產生 docs/lots.json
cd docs && python -m http.server 8000   # 瀏覽 http://localhost:8000
```

## 目前覆蓋與路線圖

| 階段 | 內容 | 狀態 |
|---|---|---|
| Phase 1 | Phillips(全部鐘錶專場,含過往成交作公允價參照)+ Loupe This(實時出價) | ✅ 已上線,已驗證 |
| Phase 2 | 區域行/聚合器:Fellows(可直連,待寫 parser)、Antiquorum、Dorotheum、Poly HK;the-saleroom / Catawiki / Invaluable 有 WAF,需 Playwright + 住宅代理或付費 Apify actor,或改用其官方 email 提醒 | 🔜 |
| Phase 3 | WatchCharts 公允價接入 → 毛利計算與套利標記全自動;賣出情境比較(Phillips vs Sotheby's vs 經銷寄售) | 🔜 |

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
build.py                # 主程式:抓取→匯率→評分→變更偵測→通知→輸出
docs/index.html         # 繁中儀表板(GitHub Pages)
docs/lots.json          # 資料(由 build.py 產生,Actions 每日提交)
.github/workflows/scrape.yml
requirements.txt
```
