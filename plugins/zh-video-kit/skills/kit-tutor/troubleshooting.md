# 常見問題對照

以下都是開發過程中**實際遇到**的問題，不是推測。依症狀找。

## 環境

| 症狀 | 原因 | 處理 |
|---|---|---|
| `找不到 ffmpeg` | 沒裝，或裝了但終端機沒重開 | Windows：`winget install Gyan.FFmpeg`；Mac：`brew install ffmpeg`。裝完**關掉終端機重開**，再跑 `doctor.py` |
| `缺少套件，請先執行：pip install faster-whisper…` | Python 套件沒裝 | `python "${CLAUDE_PLUGIN_ROOT}/skills/zh-video-pipeline/scripts/doctor.py" --fix`（會執行 pip install，先取得學員同意） |
| `Library cublas64_12.dll is not found` | 電腦有 NVIDIA 顯示卡但沒裝 CUDA 函式庫 | **不是錯誤**。腳本會自動改用 CPU，只是比較慢。不需要處理 |
| 第一次轉錄停很久沒動 | 正在下載 Whisper 模型（small 約 460MB） | 等待，確認網路正常。只會發生第一次 |
| `python` 指令找不到 | Python 沒裝或沒加入 PATH | 請學員到 python.org 安裝，安裝時勾選「Add to PATH」；Mac 試 `python3` |

## 轉錄

| 症狀 | 原因 | 處理 |
|---|---|---|
| 逐字稿是亂碼、英文、或一直重複同一句 | 音量太小、背景雜音、或影片根本沒有人聲 | 先聽原檔。改用 `--model medium` 再試。仍不行就請學員重錄，**不要硬做** |
| 結尾出現「謝謝收看」「訂閱」但影片裡沒講 | Whisper 在靜音處「幻聽」 | 在 `transcript.json` 刪掉該詞，或在剪輯計畫剪掉該段 |
| 專有名詞錯了（如把 Claude 聽成 Cloud） | 辨識不認得 | 重跑 `prepare` 加 `--hotwords "Claude Code"`，或在校對階段手動改 |
| 出現簡體字 | 沒裝 opencc | `doctor.py --fix` |
| 「嗯」被寫成「恩」、「呃」被寫成「二」 | 同音字誤辨 | 分析腳本會偵測。「二」會列入**待審核**，由你和學員看前後文決定 |

## 剪輯

| 症狀 | 原因 | 處理 |
|---|---|---|
| 剪太兇，節奏很趕 | `--gap` 太小 | 調大，例如 `--gap 0.8`，重跑 `prepare` |
| 剪不乾淨，還有長停頓 | `--gap` 太大 | 調小，例如 `--gap 0.35` |
| 口誤或重複的字沒被剪 | Whisper 會自動「修飾」口語，把口吃省略，逐字稿裡根本沒有 | 逐字稿看不到的，腳本剪不到。請用 `cut_plan.json` 手動加剪點（讀音檔聽時間） |
| 剪掉後句子不通順 | 把不是贅詞的詞剪掉了（例如「就是」是正文） | 在 `cut_plan.json` 把該項 `auto` 改回 `false`，重跑 `cut` |
| 剪點聽起來有「吃字」 | 逐字稿時間戳有誤差 | 重跑時加大保留空間：`analyze.py … --keep 0.25` |
| `所有內容都被剪掉了` | `cut_plan.json` 被設錯 | 重跑 `prepare` 產生新的計畫 |

## 字幕

| 症狀 | 原因 | 處理 |
|---|---|---|
| 字幕顯示成方框或奇怪的字型 | 找不到內附字型，或指定的字型名稱不對 | 預設會用 `${CLAUDE_PLUGIN_ROOT}/skills/zh-bilingual-captions/fonts/` 內的開源字型 Noto Sans TC，確認該資料夾的檔案沒被刪掉；要換字型，把檔案放進該資料夾並用 `--font` 指定名稱 |
| `錯誤：缺少翻譯的句子 id：[…]` | `translations.json` 少了某幾句 | 補上缺的 id，每句都要有 |
| 英文單字中間被空白切開（如 `Cla ude`） | 舊版問題 | 確認使用最新版本；轉錄時要用本套件的腳本（會記錄詞界） |
| 字幕擋到畫面重要內容 | 位置固定在下方 | 在 `merge_bilingual.py` 加 `--margin-v 數字` 調整 |
| 一行字太長、被切掉 | 單句太長 | 在 `segments.json` 手動把長句拆成兩個 id（同時在 translations 補上） |
| 一個詞被拆到兩行 | 斷句規則 | 重跑 `make_segments.py --max 12`（直式短影音建議） |

## 成品

| 症狀 | 原因 | 處理 |
|---|---|---|
| 成品聲音有「啪」的爆音 | 剪點接合 | 重跑時加大淡入淡出：`render_cut.py --fade 0.03` |
| 成品比原片模糊 | 轉檔壓縮 | `render_cut.py --crf 16`（數字越小畫質越好、檔案越大） |
| 成品很大 | 同上 | `--crf 22` |
| 音畫不同步 | 原片是變動幀率（手機錄影常見） | 先轉成固定幀率：`ffmpeg -i in.mp4 -r 30 out.mp4`，再用 out.mp4 重跑 |

## 都不是上面的情況

1. 請學員貼**完整錯誤文字**（最後 20 行）。
2. 執行 `support_report.py` 並檢查內容。
3. 一次只改一件事。
4. 嘗試 3 次仍失敗，請學員到社群發問，附上支援報告。
