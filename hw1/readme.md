# HW1：電腦語音控制 AMB82-MINI 的 LED

在電腦桌面程式輸入開發板 IP，連線成功後，說「左邊開燈」開啟藍燈，說「右邊開燈」開啟綠燈。

**原開發電腦已安裝完成，2026-09-19 曾透過 Arduino CLI 成功燒入 COM3，並與 `192.168.49.201` 實機通訊成功。** 原電腦可直接雙擊 `desktop/start.cmd`；其他電腦 clone 後先依 [首次設定](docs/setup.md) 安裝環境與建立本機 Wi-Fi 設定。IP 與 COM 埠以當下環境為準。歷史檢查範圍見 [開發檢查紀錄](docs/verification.md)。

**介面、麥克風錄音與中文語音辨識都在電腦上。** 目前使用 **Whisper small 多語模型**，以 CPU int8 在本機辨識中文；開發板連接現有 Wi-Fi，只負責接收指令、控制 LED、回傳結果。

```text
桌面程式輸入 IP → 驗證連線成功 → 按「開始辨識一句」→ 說話
  → 顯示原始辨識文字 → 排除非控制意思 → 同音／近音校正
      ├─ 符合 → Wi-Fi 傳給 AMB → 控制 LED → 回傳成功 → 更新畫面
      └─ 不符合 → 顯示非控制指令，LED 不變
```

## 檔案位置

| 位置 | 用途 |
| --- | --- |
| `desktop/` | Python Tkinter 桌面介面、Whisper 離線中文辨識 |
| `desktop/setup.ps1`、`desktop/start.ps1` | 安裝桌面環境、啟動程式 |
| `firmware/amb82_voice_led/` | AMB82-MINI 的 Arduino 程式 |
| `firmware/amb82_voice_led/wifi_config.example.h` | Wi-Fi 設定範本 |
| `firmware/amb82_voice_led/wifi_config.h` | 本機 Wi-Fi 設定，不納入版本控制 |
| `tools/upload.ps1` | 透過 arduino-cli 編譯及燒錄 |
| `tools/read_ip.ps1` | 從 COM3 讀取開發板回報的 IP |
| `docs/test-record.csv` | 12 次現場測試的空白結果表 |
| `reports/HW1_繳交成果報告.pdf` | 本機正式成果報告，另行繳交，不納入 GitHub |
| `reports/HW1_繳交成果報告.md` | 報告的本機可編輯來源，不納入 GitHub |

## 1. 讓開發板連上 Wi-Fi

1. 使用 **AMB82-MINI**。Wi-Fi 設定放在 `firmware/amb82_voice_led/wifi_config.h`；需要重新設定時，依同資料夾範本填入 `WIFI_SSID` 與 `WIFI_PASSWORD`。
2. USB 連接電腦，讓開發板進入 Download Mode。關閉占用 `COM3` 的序列埠工具，在專案根目錄 `AMB_Vibe` 執行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\hw1\tools\upload.ps1 -Port COM3
   ```

3. 燒錄完成後，離開 Download Mode，重啟開發板，讓它正常執行程式。
4. 用序列埠工具以 **115200 baud** 查看開機訊息，取得連上 Wi-Fi 後的 IP；也可查看路由器裝置清單。
5. 電腦連到同一個區域網路，確認兩台裝置可以互相連線。IP 可能在重新連線後改變，桌面程式要輸入當下的 IP。

也可以用以下指令讀取 IP（板子每 30 秒回報一次，先關閉其他序列埠工具）：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\tools\read_ip.ps1 -Port COM3
```

USB 用於供電、燒錄與查看訊息；日常控制使用 Wi-Fi。編譯使用已安裝的 AmebaPro2 SDK，板卡識別為 `realtek:AmebaPro2:Ameba_AMB82-MINI`。

板上 LED 依官方 SDK 定義：**藍燈 pin 23／PF9、綠燈 pin 24／PE6，HIGH 亮、LOW 滅**；開機先將兩燈關閉。實際亮滅仍需依第 5 步現場確認。

## 2. 安裝並啟動桌面程式

在專案根目錄 `AMB_Vibe` 開啟 PowerShell，第一次執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\desktop\setup.ps1
```

這會建立 Python 虛擬環境、安裝套件，並下載約 500 MB 的 Whisper small 多語模型。**首次安裝需要網路；安裝完成後，語音辨識可離線執行，不上傳錄音。** 電腦仍需與開發板保持區域網路連線。

如果腳本找不到 Python，可加上 `-Python "C:\path\to\python.exe"`，指定已安裝的 Python。之後只要執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\desktop\start.ps1
```

## 3. 先確認連線，再說話

1. 在「AMB IP」輸入開發板 IP，按「連線」。程式會驗證開發板回覆，**成功後才啟用操作**。
2. 先按「左邊／藍燈開」、「右邊／綠燈開」，觀察實際 LED 與介面回覆，確認網路控制正常。按「全部關燈」重設。
3. 在程式的「麥克風」下拉選單選擇實際使用的麥克風，並確認 Windows 已允許桌面應用程式使用麥克風。
4. 按「開始辨識一句」，等畫面提示可以說話，再說「左邊開燈」或「右邊開燈」。說完停頓約 1 秒，程式偵測語音結束後交給 Whisper 辨識；這台電腦短句約再等 1～2 秒。超過 12 秒仍未完整說完的錄音會取消。
5. 查看辨識文字、是否為控制語句，以及開發板是否回覆成功。需要停止錄音時按「取消辨識」。

現在支援同音字與有限近音，不需要辨識文字一字不差。例如「有并开灯」「又邊開燈」會校正為「右邊開燈」，「佐邊開燈」會校正為「左邊開燈」；也接受「請」「幫我」「麻煩」等簡單請求開頭。

畫面會保留**原始辨識文字**，在「語句判斷」另外顯示 **近音校正 → 右邊開燈**。只有方向清楚、動作為開燈的單一口令才會送出，仍需收到板子回覆才顯示傳輸成功。

| 辨識文字範例 | 處理 |
| --- | --- |
| `有并开灯`、`又邊開燈` | 校正為右邊開燈 |
| `佐邊開燈`、`左并开灯` | 校正為左邊開燈 |
| `不要有并开灯`、`右邊不開燈` | 否定句，不傳送 |
| `右邊關燈`、`右邊台燈`、`右邊開門` | 動作或對象不同，不傳送 |
| `右邊開燈嗎`、`他說右邊開燈`、`左右邊開燈` | 問句、轉述或方向不明，不傳送 |
| `今天天氣很好` | 非控制語句，不傳送 |

可先用「輸入語句測試」確認上述規則；正式驗收仍要使用麥克風。這是本機拼音校正加上拒絕規則，並非完整語意理解；如果辨識器連「不要」都漏掉，僅靠剩下的文字仍可能誤判。

本次更新只改電腦程式，**不用重新燒錄 AMB**。這台電腦已裝好新增的拼音套件；其他電腦更新後重跑 `desktop/setup.ps1`。

Whisper 會辨識整句話，再交由上述規則判斷，不會強制把所有聲音選成左或右。第一次按辨識需要載入模型，之後會重複使用同一個模型。

## 4. 看懂結果與失敗提示

| 畫面結果 | 代表什麼／怎麼處理 |
| --- | --- |
| 非控制指令、沒有辨識到語音 | 不送控制指令，LED 維持原狀；重新錄一句 |
| 等待開發板回覆 | 尚未確認成功，等待回覆 |
| 收到開發板成功回覆 | 板子已處理該指令；畫面依回傳資訊更新 LED 狀態 |
| 通訊失敗或逾時 | 不宣稱執行成功，LED 狀態改為未知；檢查供電、IP、Wi-Fi 後重新連線 |

介面的 LED 狀態來自開發板回報的控制狀態，不是光學感測；現場仍需親眼確認燈是否亮起。若指令送出後斷線，燈可能已改變，重新連線後再確認狀態。

## 5. 現場測試並記錄

目前 `docs/test-record.csv` 的實測結果留白，請操作後照實填入。示範影片連結已提供，影片內容尚未逐項核對，因此不直接據此填入驗收結果。

1. 每次開燈測試前按「全部關燈」，確認兩顆燈熄滅。
2. 用麥克風說「左邊開燈」**5 次**，再說「右邊開燈」**5 次**。每次記錄辨識文字、介面提示、兩顆 LED 實際反應及成功／失敗。
3. 說「今天天氣很好」**1 次**：應顯示非控制指令，不傳送控制命令，LED 維持原狀。另可用「不要左邊開燈」確認不會因包含關鍵字而誤觸發。
4. 連線成功後關閉電腦 Wi-Fi，再操作 **1 次**：應提示通訊失敗或逾時，LED 狀態改為未知。恢復網路後重新連線。

基本驗收完成後，再考慮閃爍三次、中英文指令或語音回覆等加分功能。

## 通訊約定（需要修改程式時再看）

使用 TCP `8266`，每則 JSON 後接一個換行。`id` 是整數，回覆必須對應同一個 `id` 與 `command`。

```json
{"id":1,"command":"BLUE_ON"}
{"device":"AMB82-MINI","protocol":1,"id":1,"command":"BLUE_ON","ok":true,"blue":true,"green":false}
```

| 指令 | 用途 |
| --- | --- |
| `HELLO` | 驗證裝置身分與通訊版本，建立可操作的連線 |
| `STATUS` | 取得板子回報的 LED 狀態 |
| `BLUE_ON` | 藍燈開，綠燈保持原狀 |
| `GREEN_ON` | 綠燈開，藍燈保持原狀 |
| `ALL_OFF` | 兩顆燈都關閉 |

未支援的指令不改變 LED。開發時以 AI 協助逐步生成、測試與修正，先確認單項功能，再連接語音與硬體。

參考：[AMB82-MINI 官方 SDK](https://github.com/Ameba-AIoT/ameba-arduino-pro2)、[官方 LED 控制範例](https://ameba-doc-arduino-sdk.readthedocs-hosted.com/en/latest/ameba_pro2/amb82-mini/Example_Guides/WiFi/Simple%20Http%20Server%20to%20Control%20LED.html)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[使用的模型](https://huggingface.co/Systran/faster-whisper-small)。

## 繳交項目

1. **成果 PDF 另行繳交**：系統架構圖、操作說明、AI 協作簡述、截至軟體完成的可見對話附錄與本人學習心得。
2. [YouTube 示範影片](https://youtu.be/VF18OTqM3s0)。
3. [GitHub 程式碼](https://github.com/breeze0305/AMB82-mini-VibeCoding-hw1)。

正式報告為本機的 `reports/HW1_繳交成果報告.pdf`，同名 `.md` 保留文字內容，兩者均不納入 GitHub。完整對話與操作紀錄也僅保留在原開發電腦；成果報告包含 AI 協作簡述與截至軟體完成的可見對話附錄。
