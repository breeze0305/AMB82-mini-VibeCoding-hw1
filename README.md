# AMB82-MINI 語音燈光控制

使用中文語音控制 AMB82-MINI 板上 LED 的 Windows 桌面應用程式。「左邊開燈」對應藍燈，「右邊開燈」對應綠燈，並提供手動控制、辨識結果與連線狀態顯示。

桌面端採用 Python Tkinter、Whisper small 與 Silero VAD，在本機完成收音、句尾偵測與語音辨識。開發板透過 Wi-Fi 接收 TCP 指令，控制 LED 後回傳執行結果。音訊不會上傳雲端。

[示範影片](https://youtu.be/VF18OTqM3s0)

## 功能

- 本機中文語音辨識與麥克風選擇。
- 有限近音校正，並過濾否定句、問句與非控制語句。
- 顯示原始辨識文字、指令判斷、板端回覆與 LED 狀態。
- 提供手動開燈、全部關燈、取消辨識與連線錯誤提示。

## 專案結構

| 位置 | 用途 |
| --- | --- |
| [hw1/desktop/](hw1/desktop/) | 桌面程式、安裝與啟動腳本、模型下載程式 |
| [hw1/firmware/amb82_voice_led/](hw1/firmware/amb82_voice_led/) | Arduino 韌體與 Wi-Fi 設定範本 |
| [hw1/tools/upload.ps1](hw1/tools/upload.ps1) | 編譯並燒錄開發板 |
| [hw1/tools/read_ip.ps1](hw1/tools/read_ip.ps1) | 從序列埠讀取開發板 IP |

完成安裝與燒錄後，可透過 [start.cmd](hw1/desktop/start.cmd) 啟動桌面程式。

## 安裝

以下命令在專案根目錄以 PowerShell 執行。

### 1. 環境與板卡套件

| 元件 | 版本 |
| --- | --- |
| 作業系統 | Windows x64 |
| Python | 3.14.6，含 Tkinter |
| Arduino CLI | 1.5.1 |
| AmebaPro2 SDK | 4.0.9-build20250805 |

安裝 Python 與 Arduino CLI，確認命令列可執行後，安裝 AmebaPro2 板卡套件：

```powershell
$ambIndex = 'https://github.com/Ameba-AIoT/ameba-arduino-pro2/raw/dev/Arduino_package/package_realtek_amebapro2_early_index.json'
arduino-cli core update-index --additional-urls $ambIndex
arduino-cli core install realtek:AmebaPro2@4.0.9-build20250805 --additional-urls $ambIndex
```

韌體使用 AmebaPro2 4.0.9 的 lwIP 介面，板卡識別為 `realtek:AmebaPro2:Ameba_AMB82-MINI`。SDK 來源：[Ameba Arduino Pro2](https://github.com/Ameba-AIoT/ameba-arduino-pro2)。

### 2. 設定開發板 Wi-Fi

首次設定時，從範本建立 Wi-Fi 設定檔：

```powershell
Copy-Item .\hw1\firmware\amb82_voice_led\wifi_config.example.h .\hw1\firmware\amb82_voice_led\wifi_config.h
```

在 `wifi_config.h` 填入 `WIFI_SSID` 與 `WIFI_PASSWORD`。此檔案已排除於版本控制；已有設定時可直接修改。電腦與開發板需位於可互通的區域網路。

### 3. 安裝桌面程式與語音模型

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\desktop\setup.ps1
```

安裝腳本會建立 `hw1/desktop/.venv`、安裝相依套件，並下載約 500 MB 的 Whisper small 模型至 `hw1/desktop/models/faster-whisper-small`。首次安裝需要網際網路；執行時使用本機模型，透過區域網路控制開發板。

可使用 `-Python "C:\path\to\python.exe"` 指定 Python 執行檔。

### 4. 燒錄並取得 IP

以 USB 連接開發板並進入 Download Mode，關閉占用序列埠的工具後執行燒錄。`COM3` 為範例埠號，需替換成實際裝置的埠號：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\tools\upload.ps1 -Port COM3
```

燒錄腳本使用已安裝的 Arduino SDK 編譯韌體，再上傳至開發板。可使用 `-CliPath "C:\path\to\arduino-cli.exe"` 指定 CLI 執行檔。

燒錄完成後離開 Download Mode，重啟開發板，再讀取 IP：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\tools\read_ip.ps1 -Port COM3
```

開發板以 115200 baud 輸出 IP，每 30 秒回報一次；也可從路由器裝置清單查詢。IP 可能隨網路環境改變。USB 用於供電、燒錄與序列埠輸出，燈光控制使用 Wi-Fi。

## 使用方式

1. 雙擊 `hw1/desktop/start.cmd`，或執行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\hw1\desktop\start.ps1
   ```

2. 輸入「AMB IP」並按「連線」。HELLO 驗證成功後，語音與控制按鈕會啟用。
3. 選擇麥克風，確認 Windows 已允許桌面應用程式使用麥克風。
4. 按「開始辨識一句」，依畫面提示說出口令，句尾停頓約 1 秒。首次辨識會載入模型。
5. 從介面查看辨識結果與板端回覆。錄音超過 12 秒或取消辨識時，不會送出未完成的指令。

| 語句／操作 | 指令 | LED 動作 |
| --- | --- | --- |
| 「左邊開燈」或藍燈開按鈕 | `BLUE_ON` | 藍燈亮，綠燈維持原狀 |
| 「右邊開燈」或綠燈開按鈕 | `GREEN_ON` | 綠燈亮，藍燈維持原狀 |
| 「全部關燈」按鈕 | `ALL_OFF` | 兩顆燈熄滅 |

板上藍燈為 pin 23／PF9，綠燈為 pin 24／PE6，HIGH 亮、LOW 滅，開機先關閉兩燈。

近音校正支援「有并开灯」對應「右邊開燈」、「佐邊開燈」對應「左邊開燈」等情況，介面仍保留原始文字。否定句、問句、轉述、方向不明或其他動作會被排除，例如「不要左邊開燈」「右邊開燈嗎」「右邊開門」。校正依據為辨識文字與有限拼音規則；辨識器遺漏否定詞時仍可能誤判。

## 通訊與故障處理

通訊使用 TCP 8266，每則 JSON 後接換行。`HELLO` 驗證裝置與版本，`STATUS` 取得板子回報狀態。控制回覆必須與請求的 `id`、`command` 對應且 `ok=true`，介面才顯示成功。

| 狀況 | 處理方式 |
| --- | --- |
| 無法連線 | 確認供電、當下 IP、同一區域網路及 TCP 8266 可達。板子一次只接受一台桌面連線。 |
| 沒有辨識到語音 | 確認麥克風選擇與 Windows 權限，等提示後再說一句，句尾稍作停頓。 |
| 非控制語句 | 不送控制指令，LED 維持原狀，重新說明確的單一口令。 |
| 通訊失敗、回覆不符或 3 秒逾時 | 介面將 LED 狀態標為未知，檢查網路後重新連線。 |
| 無法開啟 COM 埠 | 確認埠號，關閉其他占用該埠的序列埠工具。 |

介面顯示的是板子回報的 LED 控制狀態。指令送出後若連線中斷，板子可能已執行命令，因此「未知」表示無法確認目前狀態，不代表燈已熄滅。
