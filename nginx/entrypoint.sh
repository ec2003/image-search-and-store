#!/bin/sh
set -e

SSL_DIR="/etc/nginx/ssl"
CERT_FILE="${SSL_DIR}/cert.pem"
KEY_FILE="${SSL_DIR}/key.pem"

# Ensure SSL directory exists
mkdir -p "$SSL_DIR"

# Check if certificates already exist
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "Generating self-signed SSL certificates for ${NGINX_SERVER_NAME:-localhost}..."
    
    # Generate self-signed certificate
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=${NGINX_SERVER_NAME:-localhost}" \
        -addext "subjectAltName = DNS:${NGINX_SERVER_NAME:-localhost},DNS:${MINIO_SERVER_NAME:-minio.localhost},DNS:localhost,IP:127.0.0.1"
    
    echo "SSL certificates generated successfully."
    echo "  Certificate: $CERT_FILE"
    echo "  Key:         $KEY_FILE"
else
    echo "SSL certificates already exist. Using existing ones."
fi

# Substitute environment variables in nginx config template
echo "Configuring nginx with server names..."
export NGINX_SERVER_NAME="${NGINX_SERVER_NAME:-localhost}"
export MINIO_SERVER_NAME="${MINIO_SERVER_NAME:-minio.localhost}"

# Use envsubst to replace ${VAR} placeholders in the template
# Then write the result to the actual nginx config location
envsubst '${NGINX_SERVER_NAME} ${MINIO_SERVER_NAME}' \
    < /etc/nginx/templates/nginx.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "Nginx configured with:"
echo "  Django:  https://${NGINX_SERVER_NAME}"
echo "  MinIO:   https://${MINIO_SERVER_NAME}"

# Start nginx in foreground
echo "Starting Nginx..."
nginx -g "daemon off;"