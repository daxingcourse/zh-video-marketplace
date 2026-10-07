# 第三方軟體與授權聲明

> 版本日期：2026-10-07（發布前請重新查證並更新日期）
> 本檔說明這套工具**用到**哪些第三方軟體，以及它們的授權。下列第三方軟體與模型**不隨本套件散布**，由使用者在自己的電腦上自行安裝或下載，各自適用其原授權條款。**唯一的例外是下方「隨套件散布的字型」**，它依其自己的授權（SIL OFL 1.1）隨套件提供。

## 本套件自有內容

下列資料夾與檔案由本套件作者自行撰寫：

`zh-video-pipeline/`、`zh-clean-cut/`、`zh-bilingual-captions/`、`kit-tutor/`、`content-calendar/`、`carousel-maker/`、`practice/`、`CLAUDE.md`

授權條款：專屬授權，見根目錄 `LICENSE`（會員個人使用，禁止轉散布與轉售）。版權人：daxingcourse（2026 年）。此為依 GitHub 帳號暫填，正式名稱請於對外發布前確認。

## 執行時使用的軟體（使用者自行安裝）

| 軟體 | 用途 | 授權 | 查證方式 |
|---|---|---|---|
| Python | 執行腳本 | PSF License | 一般公開資訊（未逐一查證） |
| faster-whisper 1.2.1 | 中文語音辨識 | MIT | 已讀取本機套件中繼資料 |
| CTranslate2 4.8.2 | 語音辨識引擎（faster-whisper 的相依套件） | MIT | 已讀取本機套件中繼資料 |
| opencc-python-reimplemented 0.1.7 | 簡體轉台灣繁體 | Apache License 2.0 | 已讀取本機套件中繼資料 |
| Pillow 11.3.0（選用，輪播圖產生器使用） | 繪製輪播圖 | MIT-CMU（SPDX 識別碼；Pillow 專案歷來稱為 HPND） | 已讀取本機套件中繼資料 |
| FFmpeg | 影音處理、字幕燒錄 | LGPL 或 GPL，依各人安裝的建置版本而定。作者測試用的建置版本啟用了 GPL | 已讀取本機建置設定 |
| Whisper 模型權重（由 faster-whisper 首次執行時自動下載） | 語音辨識模型 | 一般為 MIT（OpenAI Whisper） | **待確認**：尚未讀取模型頁面授權原文 |

說明：
- 本套件以**獨立程序**呼叫 FFmpeg，不連結、不內嵌，也不隨附其執行檔。**請勿把 FFmpeg 打包進本套件散布**，否則需遵守其授權義務。
- 使用者以 FFmpeg 輸出的影片，其內容權利屬於使用者，與 FFmpeg 授權無關。

## 可選：HyperFrames 系列技能（使用者自行從官方安裝）

部分進階功能（圖卡、特效字幕、動態圖形）可搭配 HyperFrames 系列技能，**不是本套件的必要條件，也不隨本套件散布**。

| 項目 | 內容 |
|---|---|
| 專案 | HyperFrames |
| 版權人 | HeyGen, Inc. |
| 授權 | Apache License 2.0 |
| 來源 | https://github.com/heygen-com/hyperframes |

- 本套件與 HeyGen, Inc. **沒有關聯，亦未獲其背書**。「HeyGen」、「HyperFrames」為其各自所有人的名稱或商標。
- 該系列技能內含的第三方元件（如 MIT 授權的 vtake-skills 改編內容、GSAP 動畫函式庫、各字型、音效素材）適用各自授權，使用者安裝時應依其隨附說明為準。
- 其雲端服務（例如 HeyGen CLI、線上素材、語音、數字人）適用 HeyGen 的服務條款，**與軟體授權不同**，請使用者自行閱讀並自行建立帳號。

## 隨套件散布的字型

| 檔案 | 字型 | 授權 | 備註 |
|---|---|---|---|
| `zh-bilingual-captions/fonts/NotoSansTC-Regular.ttf` | Noto Sans TC，字重 400 | SIL Open Font License 1.1 | 版權 © 2014–2021 Adobe，保留字型名稱「Source」 |
| `zh-bilingual-captions/fonts/NotoSansTC-Bold.ttf` | Noto Sans TC，字重 700 | 同上 | 同上 |
| `zh-bilingual-captions/fonts/OFL.txt` | 授權全文 | — | **必須隨字型一併散布，請勿刪除** |

- 這兩個檔案是用 `packaging/make_static_fonts.py` 從官方的 Noto Sans TC 可變字型**切出固定字重**，字形未經修改。原因與步驟見 `zh-bilingual-captions/fonts/README.md`。
- 可變字型原檔取自本機 Windows 字型資料夾（字型內嵌的授權資訊為 OFL 1.1）。**正式發布前，請從官方來源重新取得並比對**：Google Fonts 或 notofonts 專案。
- OFL 允許隨軟體散布與修改，但**不得單獨販售字型本身**，須附授權檔，修改後的版本不得使用保留字型名稱。
- **OFL 授權檔的內文**取自本機另一份 OFL 1.1 授權檔（隨其他字型附的），只替換了版權行。**發布前請對照官方文字確認一致**（https://openfontlicense.org/ ）。
- 這些字型是本套件的第三方內容，**不受本套件 `LICENSE` 的限制**；使用者依 OFL 另有權利。
- 輪播圖與雙語字幕預設使用這個字型，所以輸出的圖片與影片裡的字形來自開源字型。

## 使用者電腦上的系統資源

| 項目 | 說明 |
|---|---|
| 作業系統內建語音（`practice/make_practice.py`） | 在使用者電腦上即時產生練習用音訊，不隨本套件散布任何錄音檔。語音由使用者的作業系統供應商授權使用，輸出用途請依其條款 |
| 系統字型 | 預設**不再使用**，改用上方內附的開源字型。只有在使用者以 `--font` 指定時才會用到，授權由使用者自行負責 |

## 如何更新本檔

1. 新增相依套件或素材時，先在此登記名稱、用途、授權、來源。
2. 發布前逐一對照官方頁面確認授權沒有變動。
3. 不確定的項目保持標示「待確認」，不要猜。

## 免責聲明

本檔是整理資訊的紀錄，不是法律意見。商業使用前，請諮詢合格的法律專業人士。
