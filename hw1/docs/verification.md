# 開發檢查紀錄（2026-09-19）

以下保留 2026-09-19 的歷史開發檢查結果。真人語音與實際 LED 的 12 次驗收另填 [`test-record.csv`](test-record.csv)，目前結果欄仍留白。

後續已提供 [YouTube 示範影片](https://youtu.be/VF18OTqM3s0) 與 [GitHub 程式碼](https://github.com/breeze0305/AMB82-mini-VibeCoding-hw1)，成果 PDF 另行繳交，本機檔名為 `hw1/reports/HW1_繳交成果報告.pdf`。影片內容尚未逐項核對，不據此改寫下列歷史結果或宣稱 12 次驗收完成。

本文引用的 `hw1/logs/` 與完整對話／操作紀錄保留在原開發電腦，未納入 Git；clone 後不會包含這些歷史日誌。可重新執行測試與燒錄工具產生自己的紀錄。

| 檢查 | 結果 |
| --- | --- |
| 桌面環境 | Windows、Python 3.14.6、Tk 8.6、faster-whisper 1.2.1、CTranslate2 4.8.2、sounddevice 0.5.5、pypinyin 0.55.0；Whisper small 多語模型已安裝，本機 CPU int8 運算 |
| 桌面自動測試 | 42 項通過：同音／有限近音校正、否定與不同動作拒絕、原始文字保留、Silero 靜音判斷、PyAV 重取樣、錄音逾時及取消、整句語意保留、TCP 回覆驗證、操作鎖定、重連及舊回覆排序等 |
| 韌體 JSON 解析測試 | 原生 C++ 執行 93 項檢查通過，包括錯誤資料、長度、ID 邊界及截斷資料 |
| Arduino 編譯 | 成功；韌體 4,788,224 bytes，占 16 MB Flash 約 28% |
| 實際 COM3 燒錄 | Arduino CLI 回傳 `upload success`，結束碼 0；紀錄在 `hw1/logs/upload.log` |
| GUI 檢查 | 實際視窗中文正常顯示；尚未連線時語音與控制按鈕停用；輸入實機 IP 後成功連線，藍燈開按鈕顯示開發板 ACK 成功與回報狀態，最後按全部關燈 |
| 合成音訊辨識 | 更換 Whisper 後，Hanhan、Yating、Zhiwei 的左右開燈共 6 個樣本皆正確辨識；Hanhan 的否定語句及非控制語句也正確保留，共 8 個樣本符合預期 |
| 模型更換比較 | Vosk 將 Hanhan 的兩個開燈樣本誤認為「台燈」；Whisper small 在相同音訊正確辨識為「左边开灯」「右边开灯」，未靠模糊規則補救 |
| 實機 Wi-Fi／TCP 控制 | `192.168.49.201:8266` 的 HELLO、全部關燈、藍燈開、綠燈開、再全部關燈皆收到正確 ACK；尚未 HELLO 的控制與未知指令皆被拒絕且板端狀態不變；紀錄在 `hw1/logs/hardware-check.json` |
| 真人語音與實際燈光 | 當時尚待現場麥克風與肉眼驗收；上述 ACK 驗證不等於光學量測 |

工具版本：Arduino CLI 1.5.1、AmebaPro2 4.0.9-build20250805。FQBN：`realtek:AmebaPro2:Ameba_AMB82-MINI`。燒錄使用手動 Download Mode、2 Mbaud，沒有要求全片清除。

重新跑桌面測試（在專案根目錄）：

```powershell
.\hw1\desktop\.venv\Scripts\python.exe -m unittest discover -s hw1/desktop/tests -v
```

韌體解析測試原始碼：`hw1/firmware/tests/protocol_test.cpp`。它驗證解析器，不代表已量測實際 GPIO 或燈光。

語音辨識只在電腦本機運算，僅 TCP 控制指令傳到 AMB；測試沒有錄製使用者聲音，也没有把音訊傳送到雲端。

## 近音容錯更新

已加入使用者回報的 `有并开灯` → `GREEN_ON` 回歸測試，並測試同音字、bian／bin／bing 近音、簡單請求開頭。原始辨識文字保留，UI 另列校正後口令。`不要有并开灯`、`右邊關燈`、`右邊台燈`、問句與方向不明的語句皆不送指令。

不使用整句模糊相似度強行選左右；方向第一音節及開燈兩音節必須明確。拼音忽略聲調，同音字可能被接受，無法保證從錯誤文字還原所有原意。此次測試驗證文字判斷與 UI，不宣稱真人錄音辨識率已提高至特定數字；Arduino 韌體未變更。

## Whisper 模型更換

使用 `Systran/faster-whisper-small`，固定 revision `536b0662742c02347bc0e980a01041f333bce120`。下載後以 `local_files_only=True` 載入，不要求雲端服務或 API 金鑰。

在 i7-13700K、8 個推論執行緒、CPU int8 下，模型首次載入 1.09 秒，8 個短句樣本每句辨識 1.15～1.44 秒。數值來自合成 WAV，不包含實際錄音與等待句尾的時間，也不是對真人準確率的保證。詳細輸出：`hw1/logs/whisper-model-check.json`。

辨識不提供左右口令提示詞、不強制二選一，保留整句否定及其他語意；錄音先用本機 Silero VAD 判定完整語音及句尾，再交給 Whisper。

已再經正式 `OfflineRecognizer.transcribe_file` 驗證左右、否定及非控制 4 個樣本，並以測試 WAV 模擬麥克風輸入，通過完整錄音 → PyAV → Silero 句尾 → Whisper → 指令判斷。沒有開啟使用者麥克風；結果見 `hw1/logs/whisper-integration-check.json`。
