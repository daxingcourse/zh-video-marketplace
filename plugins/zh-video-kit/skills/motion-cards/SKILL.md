---
name: motion-cards
description: 在口播影片上疊加動態圖卡（標題卡、重點卡、數字卡、引言卡、下三分之一字卡），帶淡入與滑入動畫，位置避開雙語字幕。觸發詞：加圖卡、動態圖卡、重點字卡、標題字卡、讓影片更有重點、下三分之一。處理剪輯完成後的影片，圖卡之後才燒錄字幕。純本機處理，只用 ffmpeg 與 Pillow，不用第三方圖片。
---

# 動態圖卡

在剪好的口播影片上，於關鍵時刻疊上圖卡，帶來「這裡是重點」的視覺提示。**圖卡的文字必須來自使用者在影片裡說過的話**，不是替他加資訊。

## 你的角色與界線

- **不編造**：圖卡上的數字、名稱、頭銜、引言，都要是使用者說過或提供的。工具會把「字幕稿裡沒有的數字」標出來，請逐項確認。
- **下三分之一字卡**（名稱與頭銜）：身分由**使用者提供**，不可替他寫證照或頭銜。
- 引用客人的話要**匿名並取得同意**。
- 用語提示（保證、療效等）命中時逐項告訴使用者，**只是提示，不是法律判斷**。
- **你看不到講者的臉，也聽不到聲音。** 圖卡有沒有擋到臉、動畫順不順，要使用者自己看過預覽與成品。
- 不要濫用：建議一支影片 3 到 6 張，每張至少停留 2 秒。

## 時機

流程順序：`cut`（剪輯）→ **圖卡** → `finish`（燒字幕）。圖卡先疊上去，字幕最後燒，所以字幕會在圖卡之上。

時間軸是**剪後影片**的時間，與 `segments.json` 的時間相同。

## 流程

### 1. 挑時刻

讀 `work/segments.json`（有每句的起訖時間與內容），和使用者一起挑 3 到 6 個值得強調的時刻。常見的挑法：

| 時刻 | 適合的圖卡 |
|---|---|
| 影片開頭 | `title`（這支影片講什麼）；或 `lower`（名稱與頭銜，3 秒內） |
| 講到清單或步驟 | `point`（「技巧一」＋重點） |
| 講到一個數量 | `stat`（大字 + 一句說明） |
| 一句有力的原話 | `quote` |

建立草稿：

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/motion-cards/scripts/cards_overlay.py" init -o work/cards.json
```

內容寫法見 `${CLAUDE_PLUGIN_ROOT}/skills/motion-cards/examples/sample_cards.json`。

### 2. 檢查

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/motion-cards/scripts/cards_overlay.py" check work/cards.json --video work/cut.mp4 --segments work/segments.json
```

- **錯誤**要全部修掉（類型、時間、仍有【待補】）。
- **警告**逐項判斷：圖卡上不在字幕稿裡的數字、風險用語、停留太短、置中或置頂可能擋臉、圖卡重疊。

### 3. 預覽（必做）

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/motion-cards/scripts/cards_overlay.py" preview work/cards.json --video work/cut.mp4 -o work/card_preview/
```

輸出每張圖卡中段的畫面。**請使用者自己看：有沒有擋到臉、字夠不夠大、好不好讀。** 有問題就調 `position`（`lower`、`top`、`center`）或縮短文字。

### 4. 渲染

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/motion-cards/scripts/cards_overlay.py" render work/cards.json --video work/cut.mp4 --segments work/segments.json -o work/cut_cards.mp4
```

之後 `pipeline.py finish` 會**自動使用** `work/cut_cards.mp4`（有的話），再燒錄字幕。

## 圖卡類型

| type | 欄位 | 用途 |
|---|---|---|
| `title` | `text` | 標題字卡，一句話說這支講什麼 |
| `point` | `text`、`label`（預設「重點」） | 重點卡，例如「技巧一」＋一句重點 |
| `stat` | `number`（建議 8 字內）、`text` | 大字數字或短詞加一句說明 |
| `quote` | `text`、`by`（選填） | 引言卡 |
| `lower` | `name`、`title`（選填） | 下三分之一字卡，名稱與身分 |

通用欄位：`start`、`end`（剪後影片的秒數）、`position`（`lower` 預設、`top`、`center`）。主題用 `meta.theme`：`ink`、`paper`、`sage`。

## 動畫

進場 0.3 秒淡入並向上滑入，退場 0.25 秒淡出。**這些時間是固定的設計，沒有提供調整參數。** 想要不同的動畫風格，目前不支援。

## 位置與字幕

預設放在畫面下方、**字幕區之上**（直式約在高度 70% 以上不放，橫式約 77%）。這是依預設字幕設定估算的：若字幕設定被改過（`--margin-v`、字級），要重新用預覽確認。

## 已知限制

- **擋臉的風險只能靠預覽人工判斷。** 我們沒有做人臉偵測，而且測試用的練習影片沒有人臉，所以「不會擋臉」沒有被驗證過。
- 版型有限（5 種）、動畫固定、沒有圖示與圖片。
- 動態圖卡不含 B-roll、轉場或音效。
- 預設主題是通用設計，不是使用者的品牌識別。
- 在 Mac、Linux 沒有實測。
- 渲染時間：實測 22 秒、4 張圖卡的影片約 5 秒（Windows，這台電腦）。不同電腦與較長的影片會不同。

## 測試狀態

- 已驗證：四種圖卡的排版（目視）、淡入與滑入動畫（逐格檢查，進場前無、滑入中、完成、淡出、消失）、位置避開字幕區、時間與【待補】檢查、字幕稿外的數字警告、風險用語提示、輸出影片長度與音訊串流不變。
- **未驗證**：真人影片上的遮臉情形；較長影片與較多圖卡；Mac。
