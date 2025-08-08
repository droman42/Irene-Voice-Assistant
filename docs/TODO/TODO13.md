## 13. Binary WebSocket Optimization for External Devices

**Status:** Open  
**Priority:** Low  
**Components:** WebSocket endpoints, ESP32 integration, Audio streaming

### Problem

While Irene already supports WebSocket-initiated ASR workflows for external devices like ESP32 through base64-encoded audio chunks, the current implementation could be optimized for binary streaming to reduce latency and improve performance for continuous audio streams from external hardware.

### Current State

- ✅ WebSocket ASR support via `/ws` and `/asr/stream` endpoints
- ✅ ESP32 can stream audio and receive transcriptions
- ✅ Voice trigger bypass with `ContinuousListeningWorkflow`
- ❌ Base64 encoding adds unnecessary overhead for binary audio data
- ❌ No ESP32-specific optimized endpoints
- ❌ No binary WebSocket support for raw PCM streaming

### Proposed Enhancement

**Phase 1: Binary WebSocket Endpoint**
- Add dedicated binary WebSocket endpoint for external devices
- Support raw PCM audio data (16kHz, 16-bit, mono)
- Eliminate base64 encoding/decoding overhead
- Optimize for continuous audio streaming

**Phase 2: ESP32-Specific Protocol**
```javascript
// Enhanced binary streaming protocol
WebSocket: /ws/audio/binary
- Audio session initiation and configuration
- Raw PCM binary frames
- Stream control messages (start/stop/pause)
- Audio format negotiation
```

**Phase 3: Session Management**
- Audio session lifecycle management
- Quality monitoring and adaptive streaming
- Connection recovery and reconnection logic
- Multi-device session support

### Technical Implementation

**Binary WebSocket Endpoint**
```python
@app.websocket("/ws/audio/binary")
async def binary_audio_stream(websocket: WebSocket):
    """Optimized binary audio streaming for ESP32/external devices"""
    await websocket.accept()
    
    # Session setup
    config = await websocket.receive_json()  # Initial config
    
    try:
        while True:
            # Receive raw PCM binary data
            audio_data = await websocket.receive_bytes()
            
            # Direct ASR processing (no base64 overhead)
            text = await asr.transcribe_audio(audio_data)
            
            # Send binary or JSON response
            if text.strip():
                await websocket.send_json({
                    "type": "transcription",
                    "text": text,
                    "timestamp": time.time()
                })
```

**ESP32 Integration Benefits**
- **Reduced Latency**: Direct binary streaming vs base64 encoding
- **Lower CPU Usage**: No encoding/decoding overhead on ESP32
- **Better Performance**: Optimized for continuous audio streams
- **Memory Efficiency**: Smaller memory footprint for audio buffers

### Current ESP32 Compatibility

The existing ESP32 firmware already supports:
- WebSocket connectivity with TLS
- Raw PCM audio streaming
- Audio session management
- Binary data transmission

### Benefits

- **Performance**: Significantly reduced latency for real-time audio
- **Efficiency**: Lower CPU and memory usage on both ESP32 and server
- **Scalability**: Better support for multiple simultaneous ESP32 devices
- **Battery Life**: Reduced processing overhead improves ESP32 battery efficiency
- **Quality**: Higher audio quality with direct binary transmission

### Impact

- **Low Breaking Change**: Additive enhancement to existing WebSocket support
- **Backward Compatibility**: Existing base64 endpoints remain unchanged
- **Optional Enhancement**: ESP32 devices can choose optimal endpoint
- **Infrastructure**: Minimal changes to existing workflow system

### Related Files

- `irene/runners/webapi_runner.py` (WebSocket endpoint definitions)
- `irene/components/asr_component.py` (ASR WebSocket endpoints)
- `irene/inputs/web.py` (WebSocket audio handling)
- `ESP32/firmware/common/src/network/network_manager.cpp` (ESP32 audio streaming)
- `ESP32/firmware/common/src/audio/audio_manager.cpp` (ESP32 audio processing)
