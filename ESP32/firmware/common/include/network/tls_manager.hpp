#pragma once

#include "core/types.hpp"
#include <string>

namespace irene {

/**
 * TLS manager for mutual authentication with local CA
 * Handles certificate validation and secure connections
 */
class TLSManager {
public:
    TLSManager();
    ~TLSManager();
    
    // Initialize with certificates
    ErrorCode initialize(const TLSConfig& config);
    
    // Certificate management
    ErrorCode load_ca_certificate(const char* ca_cert_pem);
    ErrorCode load_client_certificate(const char* client_cert_pem);
    ErrorCode load_client_private_key(const char* client_key_pem);
    
    // Validation
    bool validate_certificates() const;
    bool is_certificate_valid(const char* cert_pem) const;
    
    // TLS context for connections
    void* get_tls_context() const { return tls_context_; }
    
    // Configuration
    void set_handshake_timeout(uint32_t timeout_ms);
    void set_verify_mode(bool verify_peer);
    
    // Status
    bool is_initialized() const { return initialized_; }
    const char* get_last_error() const { return last_error_.c_str(); }

private:
    ErrorCode setup_tls_context();
    void cleanup_tls_context();
    
    TLSConfig config_;
    void* tls_context_;
    bool initialized_;
    uint32_t handshake_timeout_ms_;
    bool verify_peer_;
    
    std::string ca_cert_;
    std::string client_cert_;
    std::string client_key_;
    std::string last_error_;
};

} // namespace irene 