# 其他電腦的首次設定

所有命令從專案根目錄 `AMB_Vibe` 執行。已驗證環境為 Windows、Python 3.14.6（含 Tkinter）、Arduino CLI 1.5.1 與 AmebaPro2 4.0.9-build20250805。

## Arduino CLI 與板卡套件

先安裝 Arduino CLI 並讓 `arduino-cli` 可從 PowerShell 執行。若使用 Arduino IDE 內附的 CLI，也可在 `upload.ps1` 傳入 `-CliPath` 指定完整路徑。

以下使用原開發環境的官方板卡索引及已驗證套件版本：

```powershell
$ambIndex = 'https://github.com/Ameba-AIoT/ameba-arduino-pro2/raw/dev/Arduino_package/package_realtek_amebapro2_early_index.json'
arduino-cli core update-index --additional-urls $ambIndex
arduino-cli core install realtek:AmebaPro2@4.0.9-build20250805 --additional-urls $ambIndex
arduino-cli core list
```

韌體直接使用這個 SDK 的 lwIP 介面，請先使用已驗證版本。`tools/upload.ps1` 負責編譯與燒錄，不會替你安裝板卡套件。官方來源：[Ameba Arduino Pro2](https://github.com/Ameba-AIoT/ameba-arduino-pro2)。

## 本機 Wi-Fi 設定

```powershell
Copy-Item .\hw1\firmware\amb82_voice_led\wifi_config.example.h .\hw1\firmware\amb82_voice_led\wifi_config.h
```

在新檔案填入 `WIFI_SSID` 與 `WIFI_PASSWORD`。此檔案已被 Git 忽略；每台電腦自行設定。不要提交編譯後的韌體，因為其中可能含 Wi-Fi 字串。

只編譯、暫不操作硬體：

```powershell
arduino-cli compile --fqbn realtek:AmebaPro2:Ameba_AMB82-MINI .\hw1\firmware\amb82_voice_led
```

準備燒錄時，先確認實際 COM 埠並讓板子進入 Download Mode，再執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\tools\upload.ps1 -Port COM3
```

燒錄後重新啟動板子，以 115200 baud 讀取當下 IP。供電、Wi-Fi、IP 與 COM 埠需依自己的環境確認。

## 桌面程式

先安裝 Windows x64 Python 與 Tkinter，再執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\hw1\desktop\setup.ps1
```

此步驟建立 `.venv`、安裝 `requirements.txt`，並下載約 500 MB 的 Whisper small。模型 revision 已固定在 `download_model.py`；模型與環境不存進 Git。首次安裝需網路，之後語音在本機辨識。

若找不到 Python，可在安裝命令加上 `-Python 'C:\path\to\python.exe'`。依賴中部分版本採範圍或由套件解析，因此不宣稱環境可逐位元重現。

雙擊 `hw1/desktop/start.cmd`，選擇麥克風、輸入板子 IP，驗證連線成功後再開始辨識。

## 測試

桌面測試不需要開啟使用者麥克風或連接實體板卡：

```powershell
.\hw1\desktop\.venv\Scripts\python.exe -m unittest discover -s hw1/desktop/tests -v
```

韌體解析器可用支援 C++11 的主機編譯器單獨測試。例如在已安裝 MSVC 的 Developer PowerShell 中執行：

```powershell
New-Item -ItemType Directory -Force .\hw1\firmware\tests\.build | Out-Null
cl /nologo /EHsc .\hw1\firmware\tests\protocol_test.cpp /Fe:.\hw1\firmware\tests\.build\protocol_test.exe /Fo:.\hw1\firmware\tests\.build\protocol_test.obj
.\hw1\firmware\tests\.build\protocol_test.exe
```

這只測試 JSON 解析；真人語音、網路與實際 LED 請依 `../readme.md` 與 `test-record.csv` 完成現場驗收。
