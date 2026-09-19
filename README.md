# AMB Vibe：電腦語音控制 AMB82-MINI

在 Windows 電腦上辨識「左邊開燈」與「右邊開燈」，透過 Wi-Fi 控制 AMB82-MINI 的藍燈與綠燈。桌面程式顯示原始辨識文字、指令判斷、通訊結果及開發板回覆。

語音與 UI 全部在電腦執行：Python Tkinter、Whisper small 本機辨識、Silero VAD 句尾判斷及有限近音校正。開發板透過 TCP 8266 接收 JSON 指令，完成操作後回傳 ACK。

## 專案結構

| 路徑 | 內容 |
| --- | --- |
| [`hw1/desktop/`](hw1/desktop/) | 桌面程式、環境安裝與語音模型下載腳本 |
| [`hw1/firmware/`](hw1/firmware/) | Arduino 韌體、Wi-Fi 設定範本及解析器測試 |
| [`hw1/tools/`](hw1/tools/) | 編譯燒錄與序列埠 IP 讀取工具 |
| [`hw1/docs/`](hw1/docs/) | 開發驗證摘要與現場測試表 |
| [`hw1/reports/`](hw1/reports/) | 14 頁報告簡報、PDF、講稿與介面截圖 |

## 第一次使用

完整操作說明見 [`hw1/readme.md`](hw1/readme.md)。以下命令均在專案根目錄執行。

1. 準備 Windows x64、含 Tkinter 的 Python 與 Arduino CLI；已驗證版本為 Python 3.14.6、Arduino CLI 1.5.1。安裝 AmebaPro2 SDK 的步驟見 [首次設定](hw1/docs/setup.md)。
2. 複製 Wi-Fi 設定範本，在本機填入名稱與密碼：

   ```powershell
   Copy-Item .\hw1\firmware\amb82_voice_led\wifi_config.example.h .\hw1\firmware\amb82_voice_led\wifi_config.h
   ```

3. 安裝桌面環境與約 500 MB 的語音模型：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\hw1\desktop\setup.ps1
   ```

4. 讓板子進入 Download Mode，使用實際 COM 埠燒錄；例如：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\hw1\tools\upload.ps1 -Port COM3
   ```

5. 重啟板子，確認電腦與板子在同一網路。雙擊 `hw1/desktop/start.cmd`，輸入板子當下的 IP，連線成功後再辨識語音。

## 測試與報告

```powershell
.\hw1\desktop\.venv\Scripts\python.exe -m unittest discover -s hw1/desktop/tests -v
```

開發紀錄包含 42 項桌面測試、93 項韌體解析檢查與 8 段合成音訊。合成音訊結果不代表真人辨識率；板端 ACK 不等於肉眼確認 LED。驗證範圍見 [`verification.md`](hw1/docs/verification.md)，現場結果填入 [`test-record.csv`](hw1/docs/test-record.csv)。

- [報告簡報 PPTX](hw1/reports/HW1_語音控制系統簡報.pptx) / [PDF](hw1/reports/HW1_語音控制系統簡報.pdf)
- [逐頁講稿與 3 分鐘 demo 步驟](hw1/reports/HW1_報告與Demo講稿.md)

## Git 收錄範圍

Git 收錄程式、測試、設定範本、文件與正式簡報。Wi-Fi 密碼檔、模型、虛擬環境、韌體 binary、建置暫存、原始日誌，以及完整對話／操作紀錄與 ZIP 保留在原電腦並排除。韌體 binary 可能含編入的 Wi-Fi 資料，不應強制加入 Git。

其他電腦 clone 後需依上述步驟建立環境與設定，不會取得本機密碼或語音模型。本機歷史測試中的 IP／COM 埠不是所有環境的固定值。
