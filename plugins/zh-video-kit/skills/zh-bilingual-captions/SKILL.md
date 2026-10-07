---
name: zh-bilingual-captions
description: 把中文口說影片轉成「中文＋外語」雙語字幕並燒進影片。觸發詞：中文字幕、雙語字幕、中英字幕、幫影片上字幕、轉錄中文。流程包含本機中文語音辨識（繁體）、台灣字幕習慣斷句、Claude 翻譯、輸出 SRT／ASS、燒錄成 MP4。只處理字幕，不剪片、不加圖卡。
---

# 中文轉錄＋雙語字幕

輸入一支中文口說影片，輸出：`zh.srt`（純中文）、`bilingual.srt`（雙語）、`bilingual.ass`（排版好的雙語）、`output.mp4`（燒好字幕）。

## 環境（一次性）

```bash
pip install faster-whisper opencc-python-reimplemented
# ffmpeg 需在 PATH；第一次轉錄會自動下載 Whisper 模型
```

字型：預設使用隨套件附的開源字型 Noto Sans TC（SIL OFL，見 `fonts/`），不需要安裝任何字型；要換字型用 `--font` 指定名稱，並把字型檔放進 `fonts/` 或用 `burn.py` 第 4 個參數指定資料夾。

## 流程

1. **轉錄**（本機，不上傳）
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/zh-bilingual-captions/scripts/transcribe_zh.py" input.mp4 -o work/ --model small
   ```
   - 不可使用 `.en` 模型，會把中文翻成英文，腳本會直接拒絕。
   - 有專有名詞（品牌、工具名）時加 `--hotwords "Claude Code HeyGen"`，實測可把「CloudCode」修正為「Claude Code」。
   - 預設會用提示詞要求保留口語贅詞與重複（給剪片流程偵測用）。**只做字幕、不剪片**時加 `--no-verbatim`，字幕會更乾淨。
   - 電腦有顯示卡但缺 CUDA 函式庫時會自動退回 CPU，不會崩潰。
   - 嘈雜或口音重時改用 `--model medium`。
   - 做完先**讀一遍** `work/transcript.json`，若是亂碼、或結果明顯是在靜音處幻聽出的句子（如「謝謝收看」），停下來告訴使用者，不要繼續。

2. **斷句**
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/zh-bilingual-captions/scripts/make_segments.py" work/transcript.json -o work/
   ```
   產生 `segments.json`（含 id）與 `zh.srt`。預設每行 ≤16 字，直式短影音可 `--max 12`。

3. **校對中文**：讀 `segments.json`，修正明顯的同音錯字、專有名詞（人名、品牌、工具名）。只改 `zh` 欄位，**不要動 id 與時間**。

4. **翻譯**（由你這個 Claude 執行，不呼叫外部服務）
   讀 `segments.json`，寫出 `work/translations.json`，格式 `{"1": "...", "2": "..."}`。規則：
   - 每個 id 一句，對應該句字幕，**不合併、不拆分、不漏**。
   - 字幕要短：英文每句盡量 ≤ 42 字元，口語、自然，不要逐字直譯。
   - 專有名詞（Claude Code、品牌）保持原樣。
   - 目標語言預設英文；使用者指定日文、韓文等就照做。
   - 中文句子被斷在句中時，翻譯要能單獨讀懂，必要時用省略號銜接。

5. **合併排版**
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/zh-bilingual-captions/scripts/merge_bilingual.py" work/segments.json work/translations.json -o work/ --size 1080x1920
   ```
   橫式影片用 `--size 1920x1080`。缺少任何 id 的翻譯會報錯。

6. **燒錄**
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/zh-bilingual-captions/scripts/burn.py" input.mp4 work/bilingual.ass output.mp4
   ```

7. **驗收（必做）**：用 ffmpeg 在 20%、50%、80% 處各截一張圖，看字幕有沒有被切掉、中文字型有沒有退回預設、與畫面主體有沒有重疊。確認後才告訴使用者完成。

   ```bash
   ffmpeg -ss 5 -i output.mp4 -frames:v 1 check.png
   ```

## 已知限制

- 逐字稿來自 Whisper，專有名詞與同音字錯誤率不低，**校對步驟不能省**。
- 不處理多人對話的說話者標示。
- 字幕位置固定在畫面下方，若原片有硬字幕或下方有重要畫面，用 `--margin-v` 調整。
- 轉錄品質與速度取決於電腦；`small` 在一般筆電 CPU 上約為影片長度的 1～2 倍時間。（估計值，尚未在真實影片上實測）

## 測試狀態

- 已驗證（Windows，faster-whisper `small`，CPU）：用台灣中文合成語音（Microsoft Hanhan）轉錄 28 秒音檔約 18 秒完成，語言偵測 zh，輸出繁體；專有名詞靠 `--hotwords` 修正；斷句、中英間距、英文子詞合併（`Claude Code`）、寬度換行、缺翻譯報錯、ASS 排版、燒錄、中文字型渲染。
- **尚未驗證**：真人錄音（口音、環境雜音、語速變化）。合成語音很乾淨，真人的辨識錯誤率會比這次高，所以校對步驟更不能省。
- 實測發現並已修正的問題：GPU 缺函式庫崩潰；英文被切成「Cla ude」；剪片後殘留的逗號造成錯誤斷句；句子過長時硬切在詞中間。
