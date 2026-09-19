# AMB Vibe：電腦語音控制 AMB82-MINI

在 Windows 桌面程式輸入開發板 IP，連線成功後，說「左邊開燈」開啟藍燈，說「右邊開燈」開啟綠燈。介面會顯示原始辨識文字、語句判斷、傳輸結果與開發板回覆。

語音辨識與介面全部在電腦執行：Python Tkinter、Whisper small 本機辨識、Silero VAD 句尾判斷及有限近音校正。AMB82-MINI 連接現有 Wi-Fi，透過 TCP 8266 接收控制指令，執行後回傳 ACK。音訊不會上傳雲端。

- [YouTube 示範影片](https://youtu.be/VF18OTqM3s0)
- [GitHub 程式碼](https://github.com/breeze0305/AMB82-mini-VibeCoding-hw1)
- 成果 PDF 另行繳交，僅保留於本機：`hw1/reports/HW1_繳交成果報告.pdf`，不納入 GitHub。

## 程式位置

| 位置 | 用途 |
| --- | --- |
| [hw1/desktop/](hw1/desktop/) | 桌面程式、安裝與啟動腳本、模型下載程式 |
| [hw1/firmware/amb82_voice_led/](hw1/firmware/amb82_voice_led/) | Arduino 韌體與 Wi-Fi 設定範本 |
| [hw1/tools/upload.ps1](hw1/tools/upload.ps1) | 編譯並燒錄開發板 |
| [hw1/tools/read_ip.ps1](hw1/tools/read_ip.ps1) | 從序列埠讀取開發板 IP |

已安裝好環境且板子已燒錄時，直接雙擊 [hw1/desktop/start.cmd](hw1/desktop/start.cmd)，再依下方「日常操作」使用。

## 第一次安裝

以下 PowerShell 命令都在專案根目錄 `AMB_Vibe` 執行。

### 1. 準備 Python 與 Arduino SDK

準備 Windows x64、含 Tkinter 的 Python，以及可從 PowerShell 執行的 Arduino CLI。原開發環境使用 Python 3.14.6、Arduino CLI 1.5.1 與 AmebaPro2 4.0.9-build20250805。

安裝指定版本的 AmebaPro2 板卡套件：

```powershell
$ambIndex = 'https://github.com/Ameba-AIoT/ameba-arduino-pro2/raw/dev/Arduino_package/package_realtek_amebapro2_early_index.json'
arduino-cli core update-index --additional-urls $ambIndex
arduino-cli core install realtek:AmebaPro2@4.0.9-build20250805 --additional-urls $ambIndex
```

韌體使用此 SDK 的 lwIP 介面，請使用上述版本。板卡識別為 `realtek:AmebaPro2:Ameba_AMB82-MINI`。SDK 官方來源：[Ameba Arduino Pro2](https://github.com/Ameba-AIoT/ameba-arduino-pro2)。

### 2. 設定開發板 Wi-Fi

第一次設定時，複製範本：

```powershell
Copy-Item .\hw1\firmware\amb82_voice_led\wifi_config.example.h .\hw1\firmware\amb82_voice_led\wifi_config.h
```

在新建的 `wifi_config.h` 填入 `WIFI_SSID` 與 `WIFI_PASSWORD`。若已有本機設定，直接修改即可。電腦與開發板需在能互相連線的同一個區域網路。

### 3. 安裝桌面程式與語音模型

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\desktop\setup.ps1
```

腳本會建立 `hw1/desktop/.venv`、安裝套件，並下載約 500 MB 的 Whisper small 模型至 `hw1/desktop/models/faster-whisper-small`。首次安裝需要網路，安裝後可在本機辨識；控制開發板仍需要區域網路連線。請保留 `.venv` 與模型資料夾，程式執行時會用到。

找不到 Python 時，可在命令後加上 `-Python "C:\path\to\python.exe"`，指定已安裝的 Python。

### 4. 燒錄並取得 IP

USB 連接開發板，確認實際 COM 埠，讓 AMB82-MINI 進入 Download Mode，並關閉占用該埠的序列埠工具。以下以 `COM3` 為例：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\tools\upload.ps1 -Port COM3
```

腳本會先編譯再燒錄，不會自動安裝 Arduino SDK。若找不到 CLI，可加上 `-CliPath "C:\path\to\arduino-cli.exe"`。

燒錄完成後離開 Download Mode，重啟開發板，再讀取 IP：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\tools\read_ip.ps1 -Port COM3
```

開發板以 115200 baud 輸出 IP，每 30 秒回報一次，也可從路由器裝置清單查看。IP 可能改變，桌面程式要輸入當下的位址。USB 用於供電、燒錄及查看訊息，日常控制使用 Wi-Fi。

## 日常操作

1. 雙擊 `hw1/desktop/start.cmd`，或執行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\hw1\desktop\start.ps1
   ```

2. 輸入「AMB IP」並按「連線」。程式驗證 HELLO 回覆成功後，才啟用語音與控制按鈕。
3. 在「麥克風」選擇實際使用的裝置，並確認 Windows 允許桌面應用程式使用麥克風。
4. 按「開始辨識一句」，等畫面提示可以說話後再說口令，說完停頓約 1 秒。第一次需要載入模型，之後會重複使用。
5. 查看原始辨識文字、語句判斷與傳輸結果。超過 12 秒未完成或按「取消辨識」，都不會送出未完成的指令。

| 語句／操作 | 指令 | LED 動作 |
| --- | --- | --- |
| 「左邊開燈」或藍燈開按鈕 | `BLUE_ON` | 藍燈亮，綠燈維持原狀 |
| 「右邊開燈」或綠燈開按鈕 | `GREEN_ON` | 綠燈亮，藍燈維持原狀 |
| 「全部關燈」按鈕 | `ALL_OFF` | 兩顆燈熄滅 |

板上藍燈為 pin 23／PF9，綠燈為 pin 24／PE6，HIGH 亮、LOW 滅，開機先關閉兩燈。

程式接受有限的同音／近音，例如「有并开灯」校正成「右邊開燈」、「佐邊開燈」校正成「左邊開燈」，並保留原始文字。否定句、問句、轉述、方向不明或其他動作不送指令，例如「不要左邊開燈」「右邊開燈嗎」「右邊開門」。這是文字規則與有限拼音校正；辨識器若漏掉否定詞，仍可能誤判。

## 通訊與故障處理

通訊使用 TCP 8266，每則 JSON 後接換行。`HELLO` 驗證裝置與版本，`STATUS` 取得板子回報狀態。控制回覆必須與請求的 `id`、`command` 對應且 `ok=true`，介面才顯示成功。

| 狀況 | 處理方式 |
| --- | --- |
| 無法連線 | 確認供電、當下 IP、同一區域網路及 TCP 8266 可達。板子一次只接受一台桌面連線。 |
| 沒有辨識到語音 | 確認麥克風選擇與 Windows 權限，等提示後再說一句，句尾稍作停頓。 |
| 非控制語句 | 不送控制指令，LED 維持原狀，重新說明確的單一口令。 |
| 通訊失敗、回覆不符或 3 秒逾時 | 介面將 LED 狀態標為未知，檢查網路後重新連線。 |
| 無法開啟 COM 埠 | 確認埠號，關閉其他占用該埠的序列埠工具。 |

畫面的 LED 狀態來自板子回報的控制狀態，實際燈光仍需親眼確認。指令送出後若斷線，板子可能已改變燈號，不能把「未知」當成熄滅。

## 本機設定與 GitHub

GitHub 收錄程式、設定範本、必要腳本與這份 README。`wifi_config.h`、`.venv`、Whisper 模型及最終成果 PDF 僅保留在本機。其他電腦 clone 後需重新安裝環境並設定 Wi-Fi。編譯後的韌體可能包含 Wi-Fi 設定，也不應提交到 GitHub。
