#!/bin/bash

# Certificate Generation for Irene Voice Assistant ESP32 Nodes
# Based on the specification in docs/irene_firmware.md

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/../certs"
NODES_DIR="${SCRIPT_DIR}/../nodes"

# Configuration
CA_KEY="ca.key"
CA_CERT="ca.crt"
CA_DAYS=1825  # 5 years
CERT_DAYS=825  # ~2 years
SERVER_NAME="assistant.lan"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create certificates directory
mkdir -p "${CERTS_DIR}"
cd "${CERTS_DIR}"

# 1. Create the private CA (once)
create_ca() {
    log_info "Creating Certificate Authority..."
    
    if [[ -f "${CA_KEY}" && -f "${CA_CERT}" ]]; then
        log_warn "CA already exists. Use --force to recreate."
        return 0
    fi
    
    # Generate CA private key
    openssl genpkey -algorithm ed25519 -out "${CA_KEY}"
    
    # Generate CA certificate
    openssl req -x509 -new -nodes -key "${CA_KEY}" -days ${CA_DAYS} \
        -subj "/CN=HomeVoice Root CA" -out "${CA_CERT}"
    
    log_info "CA created: ${CA_CERT}"
    
    # Set restrictive permissions
    chmod 600 "${CA_KEY}"
    chmod 644 "${CA_CERT}"
}

# 2. Issue server certificate (nginx host)
create_server_cert() {
    log_info "Creating server certificate for ${SERVER_NAME}..."
    
    local server_key="server.key"
    local server_csr="server.csr"
    local server_cert="server.crt"
    
    # Generate server private key
    openssl genpkey -algorithm ed25519 -out "${server_key}"
    
    # Generate server certificate signing request
    openssl req -new -key "${server_key}" -subj "/CN=${SERVER_NAME}" -out "${server_csr}"
    
    # Sign server certificate
    openssl x509 -req -in "${server_csr}" -CA "${CA_CERT}" -CAkey "${CA_KEY}" -CAcreateserial \
        -days ${CERT_DAYS} -out "${server_cert}"
    
    # Cleanup CSR
    rm "${server_csr}"
    
    log_info "Server certificate created: ${server_cert}"
    
    # Set permissions
    chmod 600 "${server_key}"
    chmod 644 "${server_cert}"
}

# 3. Issue client certificate per node
create_node_cert() {
    local node_name="$1"
    
    if [[ -z "${node_name}" ]]; then
        log_error "Node name required"
        return 1
    fi
    
    log_info "Creating client certificate for node: ${node_name}..."
    
    local node_key="${node_name}.key"
    local node_csr="${node_name}.csr"
    local node_cert="${node_name}.crt"
    local node_bundle="${node_name}_bundle.pem"
    
    # Generate node private key
    openssl genpkey -algorithm ed25519 -out "${node_key}"
    
    # Generate node certificate signing request
    openssl req -new -key "${node_key}" -subj "/CN=${node_name}" -out "${node_csr}"
    
    # Sign node certificate
    openssl x509 -req -in "${node_csr}" -CA "${CA_CERT}" -CAkey "${CA_KEY}" \
        -days ${CERT_DAYS} -out "${node_cert}"
    
    # Create bundle (key + cert)
    cat "${node_key}" "${node_cert}" > "${node_bundle}"
    
    # Cleanup CSR
    rm "${node_csr}"
    
    log_info "Node certificate created: ${node_cert}"
    log_info "Node bundle created: ${node_bundle}"
    
    # Copy certificates to node directory
    local node_certs_dir="${NODES_DIR}/${node_name}/main/certs"
    mkdir -p "${node_certs_dir}"
    
    cp "${CA_CERT}" "${node_certs_dir}/ca.pem"
    cp "${node_cert}" "${node_certs_dir}/${node_name}.pem"
    cp "${node_key}" "${node_certs_dir}/${node_name}.key"
    
    log_info "Certificates copied to ${node_certs_dir}"
    
    # Set permissions
    chmod 600 "${node_key}" "${node_bundle}"
    chmod 644 "${node_cert}"
    chmod -R 600 "${node_certs_dir}"/*
}

# Validate certificate
validate_cert() {
    local cert_file="$1"
    
    if [[ ! -f "${cert_file}" ]]; then
        log_error "Certificate file not found: ${cert_file}"
        return 1
    fi
    
    log_info "Validating certificate: ${cert_file}"
    
    # Check certificate validity
    openssl x509 -in "${cert_file}" -text -noout
    
    # Verify against CA if it's not the CA cert
    if [[ "${cert_file}" != "${CA_CERT}" ]]; then
        openssl verify -CAfile "${CA_CERT}" "${cert_file}"
    fi
}

# List all certificates
list_certs() {
    log_info "Listing certificates in ${CERTS_DIR}:"
    
    for cert in *.crt *.pem; do
        if [[ -f "${cert}" ]]; then
            echo -n "  ${cert}: "
            openssl x509 -in "${cert}" -subject -noout | sed 's/subject=//'
        fi
    done
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND [ARGS]

Commands:
  init                  Initialize CA and server certificates
  node NODE_NAME        Create certificates for a node
  validate CERT_FILE    Validate a certificate
  list                  List all certificates
  clean                 Remove all certificates (use with caution)

Options:
  -f, --force          Force recreation of existing certificates
  -h, --help           Show this help message

Examples:
  $0 init               # Create CA and server certificates
  $0 node kitchen       # Create certificates for kitchen node
  $0 node living_room   # Create certificates for living_room node
  $0 validate kitchen.crt
  $0 list

Note: Run 'init' first to create the CA, then create node certificates.
EOF
}

# Main script logic
main() {
    local force=false
    local command=""
    local args=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                if [[ -z "${command}" ]]; then
                    command="$1"
                else
                    args+=("$1")
                fi
                shift
                ;;
        esac
    done
    
    # Handle force flag
    if [[ "${force}" == true ]]; then
        log_warn "Force mode enabled - existing certificates may be overwritten"
    fi
    
    # Execute command
    case "${command}" in
        init)
            if [[ "${force}" == true ]]; then
                rm -f "${CA_KEY}" "${CA_CERT}" server.*
            fi
            create_ca
            create_server_cert
            log_info "Initialization complete. Create node certificates with: $0 node NODE_NAME"
            ;;
        node)
            if [[ ${#args[@]} -eq 0 ]]; then
                log_error "Node name required"
                usage
                exit 1
            fi
            
            if [[ ! -f "${CA_CERT}" ]]; then
                log_error "CA not found. Run '$0 init' first."
                exit 1
            fi
            
            create_node_cert "${args[0]}"
            ;;
        validate)
            if [[ ${#args[@]} -eq 0 ]]; then
                log_error "Certificate file required"
                usage
                exit 1
            fi
            validate_cert "${args[0]}"
            ;;
        list)
            list_certs
            ;;
        clean)
            read -p "Are you sure you want to delete all certificates? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f *.key *.crt *.csr *.pem *.srl
                log_info "All certificates deleted"
            fi
            ;;
        *)
            log_error "Unknown command: ${command}"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 