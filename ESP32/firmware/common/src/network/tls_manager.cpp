#include "network/tls_manager.hpp"
#include "esp_log.h"
#include "esp_tls.h"
#include "mbedtls/x509_crt.h"
#include "mbedtls/pk.h"
#include "mbedtls/error.h"
#include <cstring>

static const char* TAG = "TLSManager";

namespace irene {

TLSManager::TLSManager()
    : tls_context_(nullptr)
    , initialized_(false)
    , handshake_timeout_ms_(10000)
    , verify_peer_(true) {
}

TLSManager::~TLSManager() {
    cleanup_tls_context();
}

ErrorCode TLSManager::initialize(const TLSConfig& config) {
    ESP_LOGI(TAG, "Initializing TLS manager...");
    
    config_ = config;
    
    // Load certificates
    ErrorCode result = load_ca_certificate(config.ca_cert_pem);
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to load CA certificate");
        return result;
    }
    
    result = load_client_certificate(config.client_cert_pem);
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to load client certificate");
        return result;
    }
    
    result = load_client_private_key(config.client_key_pem);
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to load client private key");
        return result;
    }
    
    // Validate certificates
    if (!validate_certificates()) {
        ESP_LOGE(TAG, "Certificate validation failed");
        return ErrorCode::TLS_FAILED;
    }
    
    // Setup TLS context
    result = setup_tls_context();
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to setup TLS context");
        return result;
    }
    
    handshake_timeout_ms_ = config.handshake_timeout_ms;
    initialized_ = true;
    
    ESP_LOGI(TAG, "TLS manager initialized successfully");
    ESP_LOGI(TAG, "Handshake timeout: %u ms, Verify peer: %s", 
             handshake_timeout_ms_, verify_peer_ ? "yes" : "no");
    
    return ErrorCode::SUCCESS;
}

ErrorCode TLSManager::load_ca_certificate(const char* ca_cert_pem) {
    if (!ca_cert_pem) {
        ESP_LOGE(TAG, "CA certificate PEM is null");
        return ErrorCode::TLS_FAILED;
    }
    
    ca_cert_ = std::string(ca_cert_pem);
    
    // Validate CA certificate format
    if (!is_certificate_valid(ca_cert_pem)) {
        ESP_LOGE(TAG, "Invalid CA certificate format");
        return ErrorCode::TLS_FAILED;
    }
    
    ESP_LOGI(TAG, "CA certificate loaded successfully (%d bytes)", ca_cert_.length());
    return ErrorCode::SUCCESS;
}

ErrorCode TLSManager::load_client_certificate(const char* client_cert_pem) {
    if (!client_cert_pem) {
        ESP_LOGE(TAG, "Client certificate PEM is null");
        return ErrorCode::TLS_FAILED;
    }
    
    client_cert_ = std::string(client_cert_pem);
    
    // Validate client certificate format
    if (!is_certificate_valid(client_cert_pem)) {
        ESP_LOGE(TAG, "Invalid client certificate format");
        return ErrorCode::TLS_FAILED;
    }
    
    ESP_LOGI(TAG, "Client certificate loaded successfully (%d bytes)", client_cert_.length());
    return ErrorCode::SUCCESS;
}

ErrorCode TLSManager::load_client_private_key(const char* client_key_pem) {
    if (!client_key_pem) {
        ESP_LOGE(TAG, "Client private key PEM is null");
        return ErrorCode::TLS_FAILED;
    }
    
    client_key_ = std::string(client_key_pem);
    
    // Basic validation of private key format
    if (client_key_.find("-----BEGIN") == std::string::npos ||
        client_key_.find("-----END") == std::string::npos) {
        ESP_LOGE(TAG, "Invalid private key format");
        return ErrorCode::TLS_FAILED;
    }
    
    ESP_LOGI(TAG, "Client private key loaded successfully (%d bytes)", client_key_.length());
    return ErrorCode::SUCCESS;
}

bool TLSManager::validate_certificates() const {
    ESP_LOGI(TAG, "Validating certificates...");
    
    // Validate CA certificate
    mbedtls_x509_crt ca_crt;
    mbedtls_x509_crt_init(&ca_crt);
    
    int ret = mbedtls_x509_crt_parse(&ca_crt, 
                                    reinterpret_cast<const unsigned char*>(ca_cert_.c_str()),
                                    ca_cert_.length() + 1);
    
    if (ret != 0) {
        char error_buf[256];
        mbedtls_strerror(ret, error_buf, sizeof(error_buf));
        ESP_LOGE(TAG, "CA certificate parsing failed: %s", error_buf);
        mbedtls_x509_crt_free(&ca_crt);
        return false;
    }
    
    ESP_LOGI(TAG, "CA certificate validation passed");
    
    // Validate client certificate
    mbedtls_x509_crt client_crt;
    mbedtls_x509_crt_init(&client_crt);
    
    ret = mbedtls_x509_crt_parse(&client_crt,
                                reinterpret_cast<const unsigned char*>(client_cert_.c_str()),
                                client_cert_.length() + 1);
    
    if (ret != 0) {
        char error_buf[256];
        mbedtls_strerror(ret, error_buf, sizeof(error_buf));
        ESP_LOGE(TAG, "Client certificate parsing failed: %s", error_buf);
        mbedtls_x509_crt_free(&ca_crt);
        mbedtls_x509_crt_free(&client_crt);
        return false;
    }
    
    ESP_LOGI(TAG, "Client certificate validation passed");
    
    // Validate client private key
    mbedtls_pk_context client_key;
    mbedtls_pk_init(&client_key);
    
    ret = mbedtls_pk_parse_key(&client_key,
                              reinterpret_cast<const unsigned char*>(client_key_.c_str()),
                              client_key_.length() + 1,
                              nullptr, 0);
    
    if (ret != 0) {
        char error_buf[256];
        mbedtls_strerror(ret, error_buf, sizeof(error_buf));
        ESP_LOGE(TAG, "Client private key parsing failed: %s", error_buf);
        mbedtls_x509_crt_free(&ca_crt);
        mbedtls_x509_crt_free(&client_crt);
        mbedtls_pk_free(&client_key);
        return false;
    }
    
    ESP_LOGI(TAG, "Client private key validation passed");
    
    // Check if client certificate and private key match
    ret = mbedtls_pk_check_pair(&client_crt.pk, &client_key);
    if (ret != 0) {
        ESP_LOGE(TAG, "Client certificate and private key do not match");
        mbedtls_x509_crt_free(&ca_crt);
        mbedtls_x509_crt_free(&client_crt);
        mbedtls_pk_free(&client_key);
        return false;
    }
    
    ESP_LOGI(TAG, "Certificate-key pair validation passed");
    
    // Cleanup
    mbedtls_x509_crt_free(&ca_crt);
    mbedtls_x509_crt_free(&client_crt);
    mbedtls_pk_free(&client_key);
    
    ESP_LOGI(TAG, "All certificates validated successfully");
    return true;
}

bool TLSManager::is_certificate_valid(const char* cert_pem) const {
    if (!cert_pem) return false;
    
    std::string cert_str(cert_pem);
    
    // Basic PEM format validation
    return (cert_str.find("-----BEGIN CERTIFICATE-----") != std::string::npos &&
            cert_str.find("-----END CERTIFICATE-----") != std::string::npos);
}

void TLSManager::set_handshake_timeout(uint32_t timeout_ms) {
    handshake_timeout_ms_ = timeout_ms;
    ESP_LOGI(TAG, "Handshake timeout set to: %u ms", timeout_ms);
}

void TLSManager::set_verify_mode(bool verify_peer) {
    verify_peer_ = verify_peer;
    ESP_LOGI(TAG, "Peer verification %s", verify_peer ? "enabled" : "disabled");
}

ErrorCode TLSManager::setup_tls_context() {
    ESP_LOGI(TAG, "Setting up TLS context...");
    
    // Create ESP-TLS configuration
    esp_tls_cfg_t* tls_cfg = static_cast<esp_tls_cfg_t*>(calloc(1, sizeof(esp_tls_cfg_t)));
    if (!tls_cfg) {
        ESP_LOGE(TAG, "Failed to allocate TLS configuration");
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Configure certificates
    tls_cfg->cacert_buf = reinterpret_cast<const unsigned char*>(ca_cert_.c_str());
    tls_cfg->cacert_bytes = ca_cert_.length() + 1;
    
    tls_cfg->clientcert_buf = reinterpret_cast<const unsigned char*>(client_cert_.c_str());
    tls_cfg->clientcert_bytes = client_cert_.length() + 1;
    
    tls_cfg->clientkey_buf = reinterpret_cast<const unsigned char*>(client_key_.c_str());
    tls_cfg->clientkey_bytes = client_key_.length() + 1;
    
    // Configure verification
    if (verify_peer_) {
        tls_cfg->skip_common_name = false;
        tls_cfg->common_name = "assistant.lan"; // Expected server name
    } else {
        tls_cfg->skip_common_name = true;
    }
    
    // Configure timeouts
    tls_cfg->timeout_ms = handshake_timeout_ms_;
    
    // Enable mutual TLS
    tls_cfg->use_secure_element = false;
    
    tls_context_ = tls_cfg;
    
    ESP_LOGI(TAG, "TLS context setup completed");
    return ErrorCode::SUCCESS;
}

void TLSManager::cleanup_tls_context() {
    if (tls_context_) {
        free(tls_context_);
        tls_context_ = nullptr;
    }
    
    // Clear sensitive data
    ca_cert_.clear();
    client_cert_.clear();
    client_key_.clear();
    
    initialized_ = false;
    ESP_LOGI(TAG, "TLS context cleaned up");
}

} // namespace irene 