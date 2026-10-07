---
name: zh-video-pipeline
description: 中文口播影片一條龍：剪掉贅詞、口吃、停頓與重錄，加上中文＋外語雙語字幕，輸出成品 MP4。觸發詞：處理這支口播、幫我剪片加字幕、口播剪輯、雙語字幕影片、一條龍剪片。內部依序呼叫 zh-clean-cut 與 zh-bilingual-captions，每個階段停下來讓使用者確認。只做字幕不剪片時也可使用。
---

# 中文口播一條龍

**你的角色**：流程主持人。腳本負責機械工作；**審核剪點、校對中文、翻譯**這三件事由你做，不能略過，也不能在使用者沒確認前直接出成品。

## 一律遵守

- 剪點、校對、翻譯三個階段都要讓使用者確認，不直接出成品。
- 你聽不到音訊，剪接點的聽感必須請使用者自己確認，並如實說明。
- 不覆蓋使用者的原始影片。
- 不代替使用者輸入密碼、金鑰、付款資料，也不安裝系統層級軟體。
- 影片與逐字稿只在使用者自己的電腦上處理，不傳到外部服務。
- 只處理使用者自己的臉與聲音，或已取得同意的素材。
- 不保證任何流量、觀看或收入成果。
- 使用者是新手、說「幫我開始」或遇到錯誤時，改用 `kit-tutor` skill 一步一步帶。

## 開始前

1. 執行 `python "${CLAUDE_PLUGIN_ROOT}/skills/zh-video-pipeline/scripts/doctor.py"`。有 ❌ 就先解決（缺 Python 套件可用 `--fix`；缺 ffmpeg 只能請使用者自己安裝，提供指令）。
2. 問使用者（一次問完，不要分次問）：
   - 影片檔路徑
   - 直式（1080x1920）還是橫式（1920x1080）
   - 雙語的另一種語言（預設英文）
   - 要不要剪片，還是只上字幕
   - 影片裡有沒有專有名詞（品牌、工具名），用於 `--hotwords`
3. 專案資料夾建議放在影片旁，名稱用影片名。**不要覆蓋使用者原檔**，腳本會複製一份。

## 四個階段

### ① prepare：轉錄＋分析
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/zh-video-pipeline/scripts/pipeline.py" prepare <專案資料夾> --video <影片> --hotwords "<專有名詞>"
# 只要字幕、不剪片：加 --no-cut
```
完成後**停下來審核**（見 `${CLAUDE_PLUGIN_ROOT}/skills/zh-clean-cut/SKILL.md` 步驟 4）：抽查逐字稿是否亂碼或幻聽，審核 `auto:false` 的剪點，讀 `sentences.txt` 找重錄。剪掉比例超過 40% 要再檢查。

### ② cut：剪輯＋斷句
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/zh-video-pipeline/scripts/pipeline.py" cut <專案資料夾>
```
完成後讀 `segments.json`，**校對中文**（專有名詞、同音字），只改 `zh`，不動 id 與時間。

### ③ 翻譯（你親自做）
寫 `work/translations.json`，規則見 `${CLAUDE_PLUGIN_ROOT}/skills/zh-bilingual-captions/SKILL.md` 步驟 4：一句一個 id、不合併不漏、口語自然、專有名詞保留原文。

### ④ finish：合併排版＋燒錄
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/zh-video-pipeline/scripts/pipeline.py" finish <專案資料夾> --size 1080x1920
```
隨時可用 `python "${CLAUDE_PLUGIN_ROOT}/skills/zh-video-pipeline/scripts/pipeline.py" status <專案資料夾>` 看進度與下一步。

## 驗收（必做）
- `ffprobe` 確認長度合理。
- 在 20%、50%、80% 各截一張圖，看字幕有沒有被切到、字型有沒有退回預設。
- 明講：**剪輯接點的聽感你無法確認，請使用者聽過。**
- 把「剪掉了什麼」摘要給使用者（時長前後、剪了幾個停頓／贅詞／重錄），讓他知道可以回頭調整。

## 失敗時
- 轉錄亂碼或幻聽：換 `--model medium` 再試一次；仍不行就回報，不要硬做。
- 缺 CUDA 函式庫：腳本自動改用 CPU，不是錯誤。
- 任何階段失敗：看 `status`，從失敗的那一階段重跑即可，前面的產出會保留。

## 測試狀態
已用合成中文語音完整跑通 prepare → 審核 → cut → 翻譯 → finish，並通過重新轉錄驗證。**尚未用真人口播驗證。**
