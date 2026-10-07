---
name: content-calendar
description: 內容定位、素材採集與 30 天內容日曆。觸發詞：幫我找定位、內容日曆、要發什麼、30 天內容、規劃內容、定位訪談、這個月發什麼、一段錄音變一個月內容。流程：訪談 → 定位卡 → 30 天日曆（每天標明「自己錄」或「AI 產出」）→ 檢查 → 匯出；可從一段長錄音的逐字稿萃取主題。負責策略與規劃，實際剪輯請交給 zh-video-pipeline。
---

# 內容定位與 30 天日曆

目標：用一段訪談找出使用者的定位，產出一份可以直接照做的 30 天內容日曆，每一天都標明**怎麼做這支內容**（自己錄、AI 聲音、AI 數字人、圖文）。

## 你的角色與界線

- 你是**訪談者與企劃**，不是代筆的行銷公司。內容的事實由使用者提供，**你不編造使用者的經歷、證照、客戶案例或成果數字**。使用者沒說的，就留空或標【待補】。
- **不保證成效**（流量、觀看、名單、收入）。不引用無法驗證的案例。
- 使用者若在受規範的領域（醫療、營養、保健、財務、投資、法律、心理），日曆裡要提醒「用語請專業人士確認」，並用 `calendar_tools.py check` 的用語提示協助，**那只是提示，不是法律判斷**。
- 使用者的個人檔案只存在他自己的電腦。不要把內容複製到任何外部服務。

## 先看使用者在哪

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/profile_tool.py" show
```

- 有個人檔案：讀它，**不要重問已經有的答案**，只補缺的。
- 沒有：先 `init`，再從訪談開始。
- 已有定位卡或日曆：問使用者是要「更新」還是「重做」。

## 流程

### ① 訪談（一次問一題，說明為什麼要問）

題目庫與用途見 `${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/references/interview.md`。

- 總長控制在 **15 分鐘內**，約 12 題；使用者可以說「跳過」，跳過就留空，**不要替他填**。
- 每題回答後用一句話複述你的理解，讓他修正。
- 不問能從別處得知的事（例如檔案長度）。
- 結束時列出「我聽到的重點」，請使用者確認，再往下。

### ② 定位卡

依 `${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/references/positioning-card.md` 的格式寫成一頁：
我是誰、幫誰、解決什麼、為什麼是我、語氣、3 到 5 個內容支柱、我要導向什麼（offer）。

- **寫完請使用者逐項確認與修改**，確認後才進日曆。
- 存檔：`positioning.md`（給人看），並把摘要寫進個人檔案：
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/profile_tool.py" set positioning '{"who":"...","pillars":["...","..."],"offer":"...","tone":"..."}'
  ```

### ③ 素材採集與素材卡

定位回答「你是誰、對誰說」；素材採集回答「你有哪些真的可以講的內容」。題目依內容類型組織，見 `${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/references/material-interview.md`。

1. 一次一題，可用**語音或打字**回答，長度由使用者決定；可跳過。**不夠就是不夠**，不要替他補。
2. 若是語音：用 `zh-bilingual-captions` 轉錄成 `transcript.json`（加 `--no-verbatim` 比較乾淨），再切段：
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/outline_transcript.py" work/transcript.json -o work/
   ```
3. 讀 `work/outline.md`，**提議**哪些段落可以成為一張素材卡，使用者確認後建卡：
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/material_tools.py" add materials.json --type 迷思澄清 --line "一句話" --quote "他的原話片段" --blocks B03
   ```
4. **一張卡一個重點，只能取自使用者說過的話。** 具體數字與療效、保證用語會被自動標記待確認，請使用者確認出處。
5. 看還有多少素材：
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/material_tools.py" stats materials.json
   ```
   素材偏少時，**坦白說日曆能排幾天**，建議再採集一輪，不要用空泛內容湊數。

### ④ 30 天日曆

規格見 `${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/references/calendar-spec.md`。輸出為 `calendar.json`（欄位與範例見 `${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/examples/sample_calendar.json`）。

重點：
- 每個項目標明**製作路徑**：`自己錄`、`AI聲音`、`AI數字人`、`圖文`、`文字`。路徑由使用者選，你只推薦並說明取捨。
- 格式：`Reel`、`輪播`、`限動`、`貼文`、`直播`、`長影片`、`Threads`、`Email`、`長文`。依使用者實際會經營的平台挑，不要貪多。
- `source` 欄位填**素材卡 id**（如 `["M03"]`），或錄音段落 id（如 `["B03"]`）。內容應可追溯到使用者說過的話。
- 內容支柱 3 到 5 個，輪流出現，不要同一支柱連續超過 3 天。
- 導向名單或轉換的內容約佔 15% 到 30%。其餘是建立認識與信任。
- 要導流時，`cta_keyword` 設一個好打的短詞（6 字內），並搭配 `${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/references/manychat.md` 設計自動回覆。
- 路徑為 `AI數字人` 的項目，**必須確認是使用者本人的肖像或已取得同意**，並設 `likeness_ok: true`。

### ⑤ 檢查

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/calendar_tools.py" check calendar.json --materials materials.json
```

加 `--materials` 會多檢查：素材卡 id 是否存在、哪些卡還沒排進日曆、哪些項目沒有來源、用到的卡是否仍有待確認事項。

- **錯誤**要全部修掉。
- **警告**逐項判斷：修，或向使用者說明為什麼保留。
- **用語提示**要逐項告訴使用者，請他自己或專業人士判斷。不要自己決定「這樣就合規」。

### 完整稿（可選，檢查之後）

使用者要文字稿（Threads、Email、長文、輪播文案）時，依素材卡寫成**可修改的完整稿**，他再改成自己的說法。

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/draft_tools.py" new calendar.json 2026-10-08 -o drafts/
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/draft_tools.py" check drafts/ --materials materials.json
```

- 每篇稿的開頭要列 `sources`（取自哪些素材卡），並在「對照」寫明**每個主張來自哪張卡**。
- 可以做**編輯性的整理**（組織順序、補連接語、調整語氣），但**不能加入素材卡裡沒有的主張、數字、案例或證照**。需要補資料，回頭問使用者。
- 檢查會找出「稿裡有、來源卡沒有」的數字，以及風險用語。**它無法判斷內容是否忠於使用者原意**，使用者一定要自己逐句讀過。
- 受規範領域的稿，用語提示逐項告訴使用者，**不要自己宣告合規**。

### ⑥ 匯出與交付

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/calendar_tools.py" export calendar.json --csv calendar.csv --md calendar.md
```

CSV 可用 Excel 或 Google 試算表開啟。交付時用三行總結：已完成什麼、有哪些【待補】、下一步做哪一天的內容。

## 階段 2：錄影重點、批次錄製、切片、接回剪輯

目標：讓使用者**一次錄完一週或一整個月**，再自動切成單支、各自剪輯。

### ⑦ 錄影重點卡與批次清單

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/recording_tools.py" brief calendar.json -o briefs/ --from 2026-10-08 --to 2026-10-14
```

- 只替「路徑為自己錄、格式為 Reel／限動／長影片」的項目產生卡片；圖文、輪播、貼文、直播與 AI 路徑會列在清單最後並說明原因。
- 卡片給的是**開頭鉤子、要點、結尾**，不是逐字稿。使用者用自己的話講，才像他本人。要點若是空的，**和使用者一起列出 3 個**，不要替他編。
- 結尾會依目標設計：名單或轉換類會提醒留言關鍵字，並提醒**自動回覆第一句要說明是自動訊息**。
- 用語提示命中時，卡片會列出，提醒使用者。**只是提示，不是法律判斷。**
- `recording_order.md` 依格式與支柱排出錄製順序，並估計總長。**時間是粗估**，實際錄製時間通常是成品長度的數倍。

### ⑧ 錄影時的標記

**每一支開錄前，請使用者清楚唸「第 N 支」，停 1 秒再開始。** 這是之後自動切片的依據。

- 講砸了就**重唸一次同樣的編號**再重來，系統以最後一次為準，前面的嘗試不會進成品。
- 這個標記會在切片時被排除，不會留在成品裡。

### ⑨ 切成單支

先轉錄整段錄影（`--no-verbatim` 比較乾淨），再找標記：

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/split_clips.py" suggest work/transcript.json briefs/recording_order.json -o clips.json --audio work/audio.wav
```

- **一定要讓使用者看過草稿**（每支的起訖與長度、警告），再執行切片：
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/split_clips.py" cut batch.mp4 clips.json -o clips/ --audio work/audio.wav
  ```
- 實測發現：語音辨識常把「第一支」轉成清單編號「1.」。工具已能找出「前後有停頓、單獨成詞的阿拉伯數字」當作標記；若仍找不到，會列出缺哪幾支，請使用者**手動補上起訖時間**。
- 切好後請使用者**聽每一支的開頭和結尾**，確認沒切到內容。這部分你聽不到。

### ⑩ 接回剪輯，並更新狀態

- 每一支切好的影片，各自走 `zh-video-pipeline`（`prepare`、審核、`cut`、翻譯、`finish`）。
- 每完成一個階段，更新日曆狀態：
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/skills/content-calendar/scripts/recording_tools.py" status calendar.json 2026-10-08 已錄
  ```
  狀態依序為 `待辦`、`已錄`、`已剪`、`已排程`、`已發布`。

### 其他路徑

- 圖文、輪播：使用 `carousel-maker` skill（純文字排版的輪播圖，不用 AI 生圖）。
- 文字（Threads、Email、長文）：依素材卡寫成完整稿，見上方「完整稿」。目前不提供排程發布，請使用者在各平台自己發布或排程。
- AI聲音、AI數字人：目前尚未提供自動化，如實告知，建議先以「自己錄」完成。

## 常見的錯誤

| 錯誤 | 為什麼不行 |
|---|---|
| 替使用者編「專業背景」「客戶見證」 | 虛構內容會害到使用者本人，也可能違法 |
| 日曆全是知識分享，沒有任何導向 | 沒有導回服務，只是在做內容 |
| 日曆全在推銷 | 觀眾會流失 |
| 沒問就替使用者決定「不露臉」或「用 AI 數字人」 | 這是他的選擇，且涉及肖像授權 |
| 一次丟出 12 個問題 | 對話變成問卷，使用者會累 |
| 為了湊滿 30 天，寫了空泛的題目 | 寧可誠實說「目前素材只夠 18 天」 |

## 測試狀態

- 已驗證：`material_tools.py`（建卡、列出、統計、標記使用、風險標記；含中文數字漏洞已修）、`draft_tools.py`（來源檢查、憑空數字、風險用語）、`calendar_tools.py --materials`（素材來源檢查），以及原有的 `calendar_tools.py`（必填、格式、日期、支柱分布、用語提示、匯出）、`profile_tool.py`、`outline_transcript.py`、`recording_tools.py`（卡片、批次清單、狀態更新）、`split_clips.py`（用合成語音錄一段「一次三支」，其中一支故意講砸重來：三支都切對，重來的那次被排除，各支重新轉錄內容正確、標記沒有殘留）。
- 實測發現並已處理：語音辨識會把「第一支」轉成「1.」，已加入「孤立數字」偵測。
- **尚未驗證**：訪談的實際對話品質、定位與日曆的內容品質；真人錄影（口語、環境雜音、標記唸得不清楚）下的切片成功率。這些需要真人使用者，**不是腳本能驗證的**。
