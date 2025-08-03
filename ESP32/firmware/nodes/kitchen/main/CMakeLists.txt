idf_component_register(
    SRCS 
    "main.cpp"
    
    INCLUDE_DIRS 
    "."
    
    EMBED_FILES
    "certs/ca.pem"
    "certs/kitchen.pem" 
    "certs/kitchen.key"
    "models/jarvis_medium.tflite"
    
    REQUIRES
    common
    nvs_flash
    esp_wifi
    esp_psram
) 