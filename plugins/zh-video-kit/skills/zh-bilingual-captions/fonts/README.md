# 內附字型

| 檔案 | 字型 | 授權 |
|---|---|---|
| `NotoSansTC-Regular.ttf` | Noto Sans TC，字重 400 | SIL Open Font License 1.1（見 `OFL.txt`） |
| `NotoSansTC-Bold.ttf` | Noto Sans TC，字重 700 | 同上 |

- 版權：© 2014–2021 Adobe。**字形未經修改。**
- 這兩個檔案是用 `packaging/make_static_fonts.py` 從官方的 Noto Sans TC **可變字型**切出固定字重得到的。原因：字幕燒錄使用的 libass 只會用可變字型的預設字重（最細的 Thin），字在影片上太細。
- 可變字型原檔取自本機 Windows 字型資料夾，字型內嵌的授權資訊為 OFL 1.1，未附在套件內。要重新產生，或想改用官方的固定字重檔，請從官方來源取得並比對：
  - Google Fonts：https://fonts.google.com/noto/specimen/Noto+Sans+TC
  - Noto 專案：https://github.com/notofonts
- OFL 允許隨軟體一併散布與修改，但**不得單獨販售字型本身**，須附上授權檔（`OFL.txt`），修改後的版本不得使用保留字型名稱「Source」。請勿刪除 `OFL.txt`。
- 想換成其他字型：把檔案放進這個資料夾，字幕用 `--font` 指定名稱、輪播圖用 `--font` 指定檔案。
