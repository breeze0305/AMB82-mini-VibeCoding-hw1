# HW1 報告與 Demo 講稿

報告約 8 分 55 秒，另安排 3 分鐘 demo。備註同步收錄於 PPTX。

## 1. 一句話，控制板上 LED（20 秒）

這份專題把語音辨識和操作介面放在電腦，開發板只處理簡單的燈號控制。我會先介紹操作流程，再說明辨識與通訊的設計，最後用三分鐘展示連線、語音、拒絕非控制語句及斷線提示。現有紀錄已驗證軟體與板端回覆，真人語音和實際燈光仍需要 demo 來確認。

依據：`hw1/readme.md`、`hw1/docs/verification.md`

## 2. 目標與操作規則（30 秒）

基本需求只有兩個語音口令：左邊開藍燈，右邊開綠燈。每個口令只操作對應的燈，所以如果先開藍燈再開綠燈，兩顆可以同時亮。全部關燈使用介面按鈕，方便每次測試前重設。連線尚未驗證時，控制和語音按鈕停用。

依據：`hw1/readme.md`、`hw1/desktop/app.py`、`hw1/firmware/amb82_voice_led/amb82_voice_led.ino`

## 3. 系統分工（45 秒）

資料處理都從電腦開始。麥克風錄到的音訊先判斷句尾，再由 Whisper 轉成中文。文字經過規則判斷，只有明確的單一開燈口令才轉成控制命令。電腦透過區域網路的 TCP 8266 送到開發板，板子執行後回覆。音訊不需要傳給開發板，也不會上傳雲端辨識服務。

依據：`hw1/desktop/speech.py`、`hw1/desktop/commands.py`、`hw1/desktop/protocol.py`、`hw1/firmware/amb82_voice_led/amb82_voice_led.ino`

## 4. 桌面操作與回饋（35 秒）

介面分成連線、錄音和結果。先輸入板子當下的 IP，成功握手後才能操作。結果區保留原始辨識文字，所以觀眾可以看到辨識器實際聽成什麼。語句判斷另外說明是否經過近音校正。傳輸結果與通訊狀態也分開呈現，送出指令本身不等於執行成功。

依據：`hw1/desktop/app.py`、`hw1/desktop/protocol.py`、`hw1/readme.md`

## 5. 辨識模型調整（45 秒）

最初使用 Vosk，但 Hanhan 的兩個開燈音訊被辨識成台燈。台燈屬於不同對象，因此原本規則拒絕執行，這個拒絕是正確的保護。接著用相同音訊換成 Whisper small，辨識回開燈，並測試三種聲音的左右命令與另外兩句否定、非控制語句，共八個樣本都符合預期。這不是八個真人，也不能宣稱百分之百準確。

依據：`hw1/docs/verification.md`、`hw1/logs/whisper-model-check.json`

## 6. 本機錄音與句尾判斷（40 秒）

錄音不是固定切出片段就直接猜命令。程式先用 PyAV 轉成 16 kHz，再以 Silero VAD 判斷是否有完整語音及句尾，約停頓一秒後才交給 Whisper。Whisper 保留整句文字，避免只挑出開燈片段而漏掉後面的否定。取消或超過十二秒都不執行未完成語句。合成 WAV 在測試機的模型推論時間約一點一五到一點四四秒，這不包含錄音與句尾等待。

依據：`hw1/desktop/speech.py`、`hw1/logs/whisper-model-check.json`、`hw1/docs/verification.md`

## 7. 有限近音校正與拒絕規則（50 秒）

使用者曾回報有并开灯，所以這裡加入有限的拼音容錯。方向第一音節只能是 zuo 或 you，邊允許 bian、bin、bing，最後兩音必須是 kai、deng。判斷之前先拒絕否定、取消、問句、轉述和其他動作，並且保留原始文字。這不是完整語意模型，也不是整句相似度二選一。如果辨識器完全漏掉不要，規則仍可能無法恢復原意，這是需要揭露的限制。

依據：`hw1/desktop/commands.py`、`hw1/desktop/tests/test_commands.py`、`hw1/readme.md`

## 8. TCP 連線與 ACK 確認（45 秒）

電腦先送 HELLO，驗證裝置名稱 AMB82-MINI 和 protocol 1，再啟用操作。每個請求帶整數 id，回覆必須是相同 id 和 command，且 ok、blue、green 必須是布林值。三秒未收到完整且有效回覆就視為通訊失敗，不能直接說燈已成功亮起。程式每五秒會用 STATUS 確認狀態。ACK 表示韌體已處理指令，不代表光學量測。

依據：`hw1/desktop/protocol.py`、`hw1/desktop/app.py`、`hw1/firmware/amb82_voice_led/amb82_voice_led.ino`

## 9. AMB82-MINI 韌體與燒錄（40 秒）

這個版本使用 AMB82-MINI，不能套用其他 Ameba 型號的腳位。官方 SDK 定義藍燈在 23、PF9，綠燈在 24、PE6，HIGH 亮、LOW 滅。開機先關兩燈，開啟其中一顆不影響另一顆。Arduino CLI 已透過 COM3 成功燒錄，韌體大小 4,788,224 bytes。Wi-Fi 名稱與密碼保留在本機設定檔，簡報不展示。重新燒錄需要 Download Mode，重啟後才執行網路服務。

依據：`hw1/firmware/amb82_voice_led/amb82_voice_led.ino`、`hw1/logs/upload.log`、`hw1/logs/compile.log`、`hw1/tools/upload.ps1`、`hw1/tools/read_ip.ps1`

## 10. 已完成的檢查與實機回覆（45 秒）

檢查分成幾層。桌面程式有四十二項回歸測試，韌體解析器有九十三項檢查。合成 WAV 有八筆模型比較，加上五筆正式流程整合檢查，其中包含模擬麥克風輸入。硬體方面，歷史測試 IP 192.168.49.201 的開發板已回覆 HELLO、藍燈、綠燈和關燈。也確認握手前的控制以及未知命令都遭拒絕。這些數字只代表對應測試範圍，不等於真人辨識率。

依據：`hw1/docs/verification.md`、`hw1/logs/whisper-model-check.json`、`hw1/logs/whisper-integration-check.json`、`hw1/logs/hardware-check.json`

## 11. 現場驗收與目前限制（35 秒）

目前 test-record.csv 留有十二筆空白結果。正式驗收要左邊與右邊各五次，再做非控制語句及通訊中斷。每次都要記錄原始文字、畫面提示與兩顆燈實際反應，失敗也照實記。現有限制有兩個：辨識器漏掉否定詞時，後續規則可能沒有足夠資訊拒絕；ACK 只反映韌體寫入的 GPIO 狀態，所以仍需要眼睛確認燈光。

依據：`hw1/docs/test-record.csv`、`hw1/docs/verification.md`、`hw1/desktop/commands.py`

## 12. 3 分鐘 demo 錄製順序（3 分鐘 demo）

錄影前先暖機載入 Whisper，確認當下 IP 和麥克風。畫面需同時拍到桌面結果區與開發板 LED，可以用螢幕錄影搭配攝影機小視窗。先展示未連線的按鈕停用，再連線。左右口令各操作一次，兩次之間可全部關燈。接著用今天天氣很好與不要左邊開燈展示拒絕。近音規則用文字輸入有并开灯，明確說這是在測文字容錯，不假裝真人錄音。最後斷 Wi-Fi 展示失敗，恢復連線並關燈。若等待超過預計時間，保留原始錄影並如實說明。這段三分鐘展示不代替十二次正式驗收。

依據：`hw1/readme.md`、`hw1/desktop/app.py`、`hw1/docs/test-record.csv`

## 13. Demo 失敗時的排查順序（40 秒）

失敗時先判斷哪一層有問題。連線失敗先查供電、IP 和網路，板子一次只接受一台桌面。錄音問題先查裝置與權限，等載入完成再說。辨識錯誤要先看原始文字，避免把規則正確拒絕誤認為通訊失敗。通訊逾時則重新連線後確認狀態，不能直接把未知當作熄滅。展示失敗可以照實說明，不必掩蓋。

依據：`hw1/readme.md`、`hw1/desktop/app.py`、`hw1/desktop/speech.py`、`hw1/desktop/protocol.py`、`hw1/firmware/amb82_voice_led/amb82_voice_led.ino`

## 14. 成果與下一步（25 秒）

目前已經完成可啟動的電腦端介面、離線中文辨識、近音判斷、通訊確認和開發板韌體，也已完成燒錄與實機 ACK 檢查。下一步就是用實際麥克風與肉眼觀察，把十二項現場結果填完整。日常操作只要啟動 start.cmd，輸入板子當下的 IP，再開始說話。

依據：`hw1/readme.md`、`hw1/docs/verification.md`、`hw1/docs/test-record.csv`
