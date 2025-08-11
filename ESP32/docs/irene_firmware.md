## Implementation Specification

**Mic-Node Firmware with Local-CA, Mutual-TLS, Raw-PCM Streaming & Per-Node Wake-Word**
*(revision 2 – 31 Jul 2025)*

---

### 0  Scope

| Item                | Decision                                                                                                                           |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **MCU / board**     | ESP32‑S3‑R8 round‑display dev‑board (16 MB flash + 8 MB PSRAM, ES8311/AC101 codec, 412 px TFT).                                                                         |
| **Language / SDK**  | C++17 • **ESP-IDF v5.3**                                                                                                           |
| **Wake-word**       | On‑device **medium‑size microWakeWord** model (multi‑speaker, PSRAM‑resident)                                                                |
| **Audio path**      | 16 kHz, 16-bit, mono **raw PCM**                                                                                                   |
| **Network**         | **WebSocket over TLS 1.2 (wss)** • mandatory **mutual TLS** signed by a **local Certificate Authority (CA)**                       |
| **Backend**         | Ubuntu 24.04 host running Irene’s `runva_webapi.py` behind an **nginx reverse-proxy** that terminates TLS & validates client certs |
| **OTA**             | IDF dual-image (factory + OTA0/1) with HTTPS pull from your LAN server                                                             |
| **Resource budget** | ≤ 460 kB flash / ≤ 160 kB RAM (fits 4 MB, 520 kB boards)                                                                        |
| **Interactive UI**  | idle clock, outdoor temperature, Wi‑Fi strength; animated state ring; OTA progress bar.
|

---

### 0.1 Hardware Summary

| Block       | Details                                             |
| ----------- | --------------------------------------------------- |
| MCU         | [Espressif ESP32‑S3R8 (Xtensa LX7 @ 240 MHz, 2 core)](https://aliexpress.ru/item/1005008549932733.html?sku_id=12000045663995013&spm=a2g2w.productlist.search_results.0.5b3c6624xldHS9) |
| Memory      | 512 kB SRAM + 8 MB PSRAM (Octal 80 MHz)             |
| Flash       | 16 MB QSPI                                          |
| Audio       | **ES8311** (I²S, I²C 0x18) ↔ MEMS mic               |
| Display     | 1.46″ IPS, 412×412, SPI 40 MHz                      |
| Inputs      | Side BTN\_L, BTN\_R; capacitive touch FT6236        |
| Peripherals | PCF85063 RTC, IMU, µSD slot                         |

---

### 0.2 Resource Budget

| Resource                           | Flash        | Int RAM      | PSRAM                 |
| ---------------------------------- | ------------ | ------------ | --------------------- |
| Core (FreeRTOS + app)              | 300 kB       | 96 kB        | —                     |
| mbedTLS + WS                       | 90 kB        | 32 kB        | —                     |
| **LVGL 9** (minimal theme + fonts) | 180 kB       | 30 kB        | 100 kB                |
| Wake‑word model (medium‑12‑bn)     | 140 kB       | —            | 160 kB                |
| VAD + audio buffers                | 9 kB         | 12 kB        | 64 kB                 |
| Assets (SVG icons, Wi‑Fi frames)   | 60 kB        | —            | —                     |
| **Totals**                         | **≈ 770 kB** | **≈ 180 kB** | **≈ 324 kB** (≪ 8 MB) |

---
## 1  Local CA & Mutual TLS

### 1.1  Create the private CA (once)

```bash
openssl genpkey -algorithm ed25519 -out ca.key
openssl req -x509 -new -nodes -key ca.key -days 1825 \
    -subj "/CN=HomeVoice Root CA" -out ca.crt
```

### 1.2  Issue **server** certificate (nginx host)

```bash
openssl genpkey -algorithm ed25519 -out server.key
openssl req -new -key server.key -subj "/CN=assistant.lan" -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days 825 -out server.crt
```

### 1.3  Issue **client** certificate per node

```bash
NODE=kitchen
openssl genpkey -algorithm ed25519 -out ${NODE}.key
openssl req -new -key ${NODE}.key -subj "/CN=${NODE}" -out ${NODE}.csr
openssl x509 -req -in ${NODE}.csr -CA ca.crt -CAkey ca.key \
    -days 825 -out ${NODE}.crt
```

Export node bundle in PEM:

```bash
cat ${NODE}.key ${NODE}.crt > ${NODE}_bundle.pem
```

### 1.4  Nginx reverse-proxy (excerpt)

```nginx
server {
    listen 443 ssl;
    server_name assistant.lan;

    ssl_certificate     /etc/ssl/server.crt;
    ssl_certificate_key /etc/ssl/server.key;
    ssl_client_certificate /etc/ssl/ca.crt;
    ssl_verify_client on;                    # mutual TLS

    location /stt {
        proxy_pass http://127.0.0.1:5003;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

### 1.5  ESP32 TLS provisioning

*Place files in `components/certs/`:*

| File           | Contents                                  | Flash impact |
| -------------- | ----------------------------------------- | ------------ |
| `ca_pem.h`     | Root CA (`ca.crt`) converted via `xxd -i` | 1.3 kB       |
| `client_pem.h` | Node cert (`*.crt`)                       | 1.0 kB       |
| `client_key.h` | Node key (`*.key`)                        | 1.0 kB       |

```cpp
esp_websocket_client_config_t cfg = {
    .uri       = "wss://assistant.lan/stt",
    .cert_pem  = ca_pem_start,
    .client_cert_pem = client_pem_start,
    .client_key_pem  = client_key_start,
    .transport = WEBSOCKET_TRANSPORT_OVER_SSL
};
```

---

## 2  Firmware Architecture

```
FreeRTOS
├─ AudioTask          (I²S DMA → RingBuf)         20 ms
│   └─ WebRTC-VAD     (gate silence)
├─ WakeWordTask       (microWakeWord stream)      30 ms
│   └─ back-buffer (300 ms)
├─ StreamTask         (TLS WebSocket)             ~1 ms
│   └─ End-detect (700 ms silence or 8 s max)
├─ Wi-Fi Manager
├─ OTA Service        (HTTPS, signed)
└─ LED / Watchdog
```

* **Flash**: 260 kB core + 90 kB mbedTLS + 60 kB WW-model + 40 kB app + 9 kB VAD = **≈ 459 kB**
* **RAM**: 70 kB WW + 32 kB TLS + 54 kB buffers/tasks = **≈ 156 kB**

---

## 3  Wake-Word Model per Node (microWakeWord “medium-12-bn” (12 × Conv1D + BatchNorm))

1. **Record** ≥ 200 positives + ≥ 4 h negatives at 16 kHz WAV.
* Create a shared script: “Say ‘Jarvis’ five times, normal voice. Then five times softly. Then turn away and say it twice…”
* Record at least 4 speakers × 50 clips = 200 WAVs (16 kHz) in the target room for acoustic realism.
* Expand negatives: 2 h idle room noise + 2 h conversational speech, ideally in the same bit-rate/s.

2. **Train**

   ```bash
    # Using the integrated Irene trainer
    irene-train-wake-word jarvis \
    --epochs 55 \
    --batch_size 16 \
    --model_size medium
    
    # Or directly with Python
    python wake_word_training/scripts/tensorflow_trainer.py jarvis \
    --epochs 55 \
    --batch_size 16 \
    --model_size medium
   ```
The ESP32-compatible TensorFlow trainer automatically enforces the 140KB size limit and produces models optimized for microcontroller deployment.

2.1 **Validation targets**

| Metric            | Pass threshold                            |
| ----------------- | ----------------------------------------- |
| **Recall** (TPR)  | ≥ 95 % (>= 190 / 200 test positives)      |
| **False Accepts** | ≤ 2 per hour on 3 h negative stream       |
| **Wake latency**  | ≤ 140 ms (averaged) on ESP32-S3 @ 240 MHz |

2.2 **INT8 Validation Pass Requirements**

After INT8 quantization and optimization, the model must be re-validated to ensure it still meets the firmware acceptance criteria. This validation is critical because quantization can impact accuracy and detection thresholds.

**Validation Protocol:**
1. **Threshold Re-tuning**: INT8 models may require adjusted confidence thresholds due to quantization effects on the output distribution
   - Run systematic threshold sweep from 0.3 to 0.8 in 0.05 increments
   - Select optimal threshold that maximizes recall while maintaining false accept rate
   - Document threshold change from FP32 baseline (expected: ±0.1-0.2)

2. **Recall Validation**: Test with same 200 positive samples used for FP32 validation
   - **Target**: ≥95% recall (≥190/200 detections)
   - **Method**: Automated batch processing through ESP32 firmware
   - **Environment**: Target room acoustics with background noise

3. **False Accept Validation**: Extended negative stream testing
   - **Target**: ≤2 false accepts per hour over 3-hour continuous stream
   - **Test data**: Mix of silence, conversation, music, and environmental noise
   - **Method**: Continuous ESP32 deployment logging all detections

4. **Latency Validation**: Real-time performance on target hardware
   - **Target**: ≤140ms average detection latency (≤25ms inference + ≤115ms trigger duration)
   - **Method**: High-resolution timing on ESP32-S3 @ 240MHz
   - **Include**: MFCC preprocessing overhead (INT8 optimization should reduce this)

**Acceptance Criteria:**
- All three metrics must pass simultaneously
- If any metric fails, requires model re-training or threshold adjustment
- Document performance delta from FP32 baseline (expected degradation: <2% recall, <10% latency increase)

**Validation Log Requirements:**
```
=== INT8 Model Validation Report ===
Model: kitchen_ww_model_int8.tflite (140KB)
Threshold: 0.65 (adjusted from FP32: 0.55)

Recall Test (200 samples):
✓ PASS: 196/200 detected (98.0% recall)

False Accept Test (3h stream):
✓ PASS: 1 false accept (0.33/hour rate)  

Latency Test (100 detections):
✓ PASS: 128ms average (18ms inference + 110ms trigger)

Result: ACCEPTED for deployment
```


2.3 **Integrating the larger model**

* Convert to C array → ww_model_medium.h.
* Place model tensor + layer weights in PSRAM:

    ```cpp
    ESP_PSRAM_INIT();
    static const uint8_t model_data[] DRAM_ATTR = {
    #include "ww_model_medium.h"
    };
    WakeWordDetector detector(model_data, sizeof(model_data), /*use_psram=*/true);
    ```
* Ram impact: +90 kB in PSRAM (none in internal RAM).
* Loop in `WakeWordTask` (30 ms):

    ```cpp
    vad_get_frame(pcm_buf);
    if(detector.Process(pcm_buf)) trigger_stream();
    ```
3. **Convert**

   ```bash
   xxd -i model_jarvis.tflite > firmware/nodes/kitchen/ww_model.h
   ```

4. **Build**

   ```bash
   export ROOM_ID=kitchen
   idf.py set-target esp32
   idf.py build
   ```

---

## 4  Communication Protocol

| Direction         | Payload                                                    | Notes                  |
| ----------------- | ---------------------------------------------------------- | ---------------------- |
| **Node → Server** | `{"config":{"sample_rate":16000,"room":"kitchen"}}` (text) | once per session       |
|                   | 320-byte raw PCM frames                                    | only while VAD = voice |
|                   | `{"eof":1}` then close                                     | session end            |
| **Server → Node** | `{"partial":"…"}`, `{"text":"…"}`                          | optional; ignored      |

---

## 5  State Machine

| State             | Enter                         | Exit                          |
| ----------------- | ----------------------------- | ----------------------------- |
| **IdleListening** | Boot / cooldown               | Wake-word prob ≥ 0.9 (450 ms) |
| **Streaming**     | Open TLS → send 300 ms buffer | 700 ms silence **or** 8 s     |
| **Cooldown**      | send `eof`; close             | 400 ms                        |
| **Wi-FiRetry**    | TLS fail                      | reconnect → Idle              |

---

## 6  User-Interface on the 1.46″ round TFT

We’ll use **LVGL 9.x** (IDF component) because it’s:

* hardware-accelerated on the ESP32-S3 (LCD-RGB peripheral),
* supports full 60 FPS with PSRAM frame-buffer, and
* weighs \~180 kB flash + 30 kB IRAM when minimal theme is enabled.

### 6.1  Scene hierarchy

| Layer           | Widget                       | Function                                                                                  |
| --------------- | ---------------------------- | ----------------------------------------------------------------------------------------- |
| **Background**  | `lv_arc` (270°)              | **State ring**: colour = idle (grey), listening (blue), streaming (green), error (red).   |
| **Centre**      | `lv_label` large             | Shows **keyword** when last triggered (“JARVIS”) for 1 s then fades.                      |
| **Top-right**   | `lv_label` tiny + Wi-Fi icon | Updates every 3 s: RSSI (-dBm) and IP addr.                                               |
| **Bottom-left** | `lv_bar` hidden by default   | **OTA progress** appears only during esp\_https\_ota: `on_progress` → `lv_bar_set_value`. |

Animation: `lv_anim_t` with 300 ms ease-out when state colour changes.

### 6.2  Event hooks

| Firmware event                | UI call                                    |
| ----------------------------- | ------------------------------------------ |
| Wake-word detected            | `ui_show_keyword("JARVIS")`; ring → blue   |
| Stream start                  | ring → green                               |
| Stream end                    | ring → grey                                |
| TLS error / no Wi-Fi          | ring → red; label “OFFLINE”                |
| OTA start / progress / finish | `ui_show_ota(percent)`; auto-hide on 100 % |

### 6.3  Frame-buffer allocation

```cpp
    #define TFT_W  412
    #define TFT_H  412
    static lv_disp_draw_buf_t draw_buf;
    static lv_color_t *buf = (lv_color_t *)heap_caps_malloc(
                        TFT_W * 80 * sizeof(lv_color_t),
                        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);   // 80-line partial FB
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, TFT_W * 80);
```

Partial buffer (80 lines) keeps internal RAM usage under 25 kB.

### 6.4  Touch & buttons

* *Touch double-tap*: toggle **mic gain** (-6 dB ↔ +18 dB).
* *Left side-button*: momentary **push-to-talk** (bypasses wake-word).

Use LVGL’s indev driver for FT6236 if present, else fallback to GPIO-IRQ.

### 6.5 Idle-screen requirements

| Item                    | Spec                                                                                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Local time**          | 24 h HH : MM, centred, updates each minute. Source: RTC (PCF85063) or SNTP fallback.                                                        |
| **Outside temperature** | “⛅ 18 °C” under the clock. Source: MQTT topic `home/weather/outdoor/temp` (payload °C). Update every 5 min; if stale > 15 min show “-- °C”. |
| **Wi-Fi status**        | 3-bar icon + RSSI in dBm (e.g. “-58 dBm”) at top-right. Colour: green ≥ -65, amber -80…-65, red < -80. Refresh every 3 s.                   |

### 6.6 LVGL layout

```
    ╭────────────── round 412×412 ───────────────╮
    │                      HH:MM                 │  <- lv_label (style clock_l)
    │                  ⛅ 18 °C                  │  <- lv_label (style temp_l)
    │                                            │
    │                                            │
    │                                            │
    │        (ring arc shows node state)         │
    │                                            │
    │                                            │
    │                      Wi-Fi ▮▮▮ -58 dBm     │  <- lv_label + lv_img
    ╰────────────────────────────────────────────╯
```

### 6.7 Implementation notes

* **Ring arc** (state indicator) already exists – colour only, no text.
* **Clock update**: in `TimeTask` subscribe to `LV_EVENT_REFRESH`; on minute change call `lv_label_set_text_fmt(clock_l, "%02u:%02u", h, m)`.
* **Weather update**: in MQTT callback parse payload, cache timestamp; set label text and colour (`lv_color_hex(0xAAAAAA)` when stale).
* **Wi-Fi RSSI**: `esp_wifi_sta_get_ap_info()` every 3 s; map RSSI to icon frame and colour.

---

## 7  Build, Flash, OTA

*Default partition-table:*

| Name              | Size      | Purpose      |
| ----------------- | --------- | ------------ |
| `factory`         | 1 MB      | first flash  |
| `ota_0` / `ota_1` | 1 MB each | dual OTA     |
| `spiffs`          | 512 kB    | logs & dumps |

*Flash*:

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

*OTA*:

```bash
idf.py build
esp-idf.py ota --url https://fw.lan/kitchen.bin --cacert ca.crt \
               --clientcert kitchen.crt --clientkey kitchen.key
```

---

## 8  Testing Matrix

| Test                    | Expectation                                                           |
| ----------------------- | --------------------------------------------------------------------- |
| **TLS handshake**       | Completes < 600 ms; CN = assistant.lan; client cert accepted          |
| **Bad cert**            | Server **rejects** node with wrong cert; node auto-retries (back-off) |
| **Wake-word latency**   | ≤ 150 ms trigger                                                      |
| **End-to-MQTT latency** | ≤ 700 ms                                                              |
| **False accepts**       | ≤ 2 /hour in 2 h silence                                              |
| **Bandwidth**           | Speech: \~70 kB/s TLS; silence: < 200 B/s                             |
| **OTA**                 | Verify A→B swap & rollback on CRC fail                                |
| **Temperature**         | < 75 °C after 5 min continuous streaming                              |

---

## 9  Open Points Resolved

* **TLS**: local CA + mutual auth integrated.
* **PCM**: raw 16 kHz retained.
* **Per-node wake word**: unique micro-model per firmware build.

---

### Ready for implementation

If this spec meets your needs, the next steps are:

1. Generate CA & certs as above.
2. Stand-up nginx TLS gateway.
3. Fork firmware template & train the first wake-word model.
4. **Implement Client Registry integration** - See `docs/CLIENT_REGISTRY.md` for detailed implementation guide

#### Client Registry Integration

The firmware must register with the server's Client Registry system to enable context-aware processing:

- **Registration**: Send client ID, room name, and device list on startup
- **Heartbeat**: Periodic presence updates (every 5 minutes)
- **Device Updates**: Report device status changes in real-time
- **Russian Support**: Use Russian room/device names as primary language

See complete integration guide: [`docs/CLIENT_REGISTRY.md`](../../docs/CLIENT_REGISTRY.md)

Let me know if any detail still needs tightening!
