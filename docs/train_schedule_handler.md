# Train Schedule Intent Handler

The Train Schedule Intent Handler provides integration with Yandex.Schedules API to get real-time train departure information. This is a conversion of the original v12 Yandex Schedules plugin to the new intent-based architecture.

## Features

- 🚂 **Real-time train schedules** from Yandex.Schedules API
- 🇷🇺 **Russian language support** with natural voice commands
- ⚙️ **Configurable stations** for departure and destination
- 🔄 **Async/await architecture** with non-blocking API calls
- 📝 **Natural language responses** in Russian
- 🛡️ **Error handling** with graceful fallbacks

## Requirements

### Dependencies
- `requests` library for HTTP requests
- Valid Yandex.Schedules API key

### API Key Setup
1. Get a free API key from [Yandex.Schedules](https://yandex.ru/dev/rasp/raspapi/)
2. Free tier allows up to 500 requests per day
3. Configure the API key in your configuration file

### Station IDs
Station IDs can be found in the URL when searching for schedules on Yandex:
- Example: `s9600681` (Moscow Leningradsky Station)
- Example: `s2000002` (Sergiev Posad)

## Configuration

### Environment Variables
```bash
# Train Schedule Configuration
export IRENE_INTENTS__TRAIN_SCHEDULE__ENABLED=true
export IRENE_INTENTS__TRAIN_SCHEDULE__API_KEY="your-api-key-here"
export IRENE_INTENTS__TRAIN_SCHEDULE__FROM_STATION="s9600681"
export IRENE_INTENTS__TRAIN_SCHEDULE__TO_STATION="s2000002"
export IRENE_INTENTS__TRAIN_SCHEDULE__MAX_RESULTS=3
```

### Configuration File (TOML)
```toml
[intents.train_schedule]
enabled = true
api_key = "your-api-key-here"
from_station = "s9600681"    # Moscow Leningradsky
to_station = "s2000002"      # Sergiev Posad
max_results = 3
timeout_seconds = 10
```

### Configuration File (JSON)
```json
{
  "intents": {
    "train_schedule": {
      "enabled": true,
      "api_key": "your-api-key-here",
      "from_station": "s9600681",
      "to_station": "s2000002",
      "max_results": 3,
      "timeout_seconds": 10
    }
  }
}
```

## Usage

### Voice Commands (Russian)
The handler responds to these Russian voice commands:

- `"электричка"` - general train request
- `"электрички"` - plural trains
- `"ближайший поезд"` - nearest train
- `"поезд"` - train
- `"расписание поездов"` - train schedule
- `"расписание электричек"` - electric train schedule

### Example Interactions

**User:** "Когда ближайшая электричка?"  
**Assistant:** "Ближайшая электричка в 14 25. Следующая в 14 55. Дальше в 15 25."

**User:** "Электричка расписание"  
**Assistant:** "Ближайшая электричка в 09 15. Следующая в 09 45. Дальше в 10 15."

## Intent Patterns

The handler processes these intent patterns:

| Intent Name | Pattern | Description |
|-------------|---------|-------------|
| `transport.train_schedule` | `transport.train_schedule` | Direct train schedule request |
| `transport.get_trains` | `transport.get_trains` | Get trains action |
| General | `transport.*` | All transport domain intents |
| Keyword-based | Text contains train keywords | Russian train terms detection |

## Entities

The handler supports these entities:

- `from_station`: Departure station ID (falls back to config default)
- `to_station`: Destination station ID (falls back to config default)

## Response Format

The handler returns natural Russian responses:

```
"Ближайшая электричка в {hour} {minute}. Следующая в {hour} {minute}. Дальше в {hour} {minute}."
```

If no trains are found:
```
"Не найдено поездов на сегодня"
```

## Integration Example

### Basic Setup
```python
from irene.intents.handlers.train_schedule import TrainScheduleIntentHandler
from irene.intents.registry import IntentRegistry
from irene.intents.orchestrator import IntentOrchestrator

# Configuration
config = {
    "api_key": "your-api-key",
    "from_station": "s9600681",
    "to_station": "s2000002",
    "max_results": 3
}

# Create handler
handler = TrainScheduleIntentHandler(config)

# Register with registry
registry = IntentRegistry()
registry.register_handler("transport.*", handler)
registry.register_handler("электричка", handler)

# Use with orchestrator
orchestrator = IntentOrchestrator(registry)
```

### Using the Demo
```bash
cd irene/examples
python train_schedule_demo.py
```

## API Integration

### Yandex.Schedules API
- **Endpoint**: `https://api.rasp.yandex.net/v3.0/search/`
- **Method**: GET
- **Format**: JSON
- **Rate Limit**: 500 requests/day (free tier)

### Request Parameters
- `from`: Departure station ID
- `to`: Destination station ID
- `date`: Date in ISO format (YYYY-MM-DD)
- `format`: Response format (json)
- `apikey`: Your API key

### Response Processing
The handler:
1. Filters departures to only future times
2. Extracts hour and minute from departure time
3. Formats response in natural Russian
4. Limits results to configured maximum

## Error Handling

The handler gracefully handles:

- **Missing API Key**: Returns configuration error message
- **Network Errors**: Logs error and returns service unavailable message  
- **Invalid Station IDs**: API returns empty results
- **Rate Limiting**: API returns error status
- **Missing Dependencies**: Checks for `requests` library availability

Error messages are in Russian for user-facing responses:
- `"Нужен ключ API для получения расписания"` - API key required
- `"Проблемы с расписанием. Посмотрите логи"` - Schedule problems, check logs
- `"Не удалось получить расписание поездов"` - Failed to get train schedule

## Logging

The handler uses structured logging:

```python
logger.info("Train schedule request processed successfully")
logger.warning("Train schedule handler unavailable: missing API key")
logger.error("API request failed: {error}")
logger.exception("Error in train schedule handler")
```

Log levels:
- **INFO**: Successful operations
- **WARNING**: Configuration issues, availability problems
- **ERROR**: API failures, processing errors
- **DEBUG**: API responses, detailed flow information

## Development

### Running Tests
```bash
# Run the demo with test configuration
python irene/examples/train_schedule_demo.py

# Check handler capabilities
python -c "
from irene.intents.handlers.train_schedule import TrainScheduleIntentHandler
handler = TrainScheduleIntentHandler()
print(handler.get_capabilities())
"
```

### Handler Interface
The handler implements the standard `IntentHandler` interface:

- `async def can_handle(intent: Intent) -> bool`
- `async def execute(intent: Intent, context: ConversationContext) -> IntentResult`
- `async def is_available() -> bool`
- `def get_supported_domains() -> List[str]`
- `def get_supported_actions() -> List[str]`
- `def get_capabilities() -> Dict[str, Any]`

## Migration from v12 Plugin

This handler replaces the old `plugin_yandex_schedules.py` from v12 architecture:

### Changes Made
1. **Architecture**: Plugin → Intent Handler
2. **Async Support**: Synchronous → Async/await
3. **Configuration**: Plugin options → Structured config
4. **Error Handling**: Enhanced with proper logging
5. **Interface**: Legacy plugin interface → Standard intent handler interface

### Migration Steps
1. Remove old plugin references
2. Add new intent handler to registry
3. Update configuration format
4. Test with new voice commands

The functionality remains the same - Russian voice commands for train schedules via Yandex API.

## Troubleshooting

### Common Issues

**"Handler not available"**
- Check API key configuration
- Verify `requests` library is installed
- Check network connectivity

**"No trains found"**
- Verify station IDs are correct
- Check if stations have service today
- Confirm API key is valid and not rate-limited

**"API request failed"**
- Check internet connection
- Verify API endpoint is accessible
- Check API key permissions

**Import errors**
- Ensure all dependencies are installed
- Check Python path includes project root
- Verify handler is properly registered

### Debug Mode
Enable debug logging to see detailed API interactions:

```python
import logging
logging.getLogger("irene.intents.handlers.train_schedule").setLevel(logging.DEBUG)
```

## License

This handler is part of the Irene Voice Assistant project and follows the same license terms.

## Support

For issues, questions, or contributions related to the train schedule handler:

1. Check the demo example in `irene/examples/train_schedule_demo.py`
2. Review the handler implementation in `irene/intents/handlers/train_schedule.py`
3. Consult the main project documentation
4. File issues in the project repository 