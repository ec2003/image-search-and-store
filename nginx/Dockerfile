FROM nginx:alpine

# Install OpenSSL for generating self-signed certificates and gettext for envsubst
RUN apk add --no-cache openssl gettext

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config template
COPY nginx.conf /etc/nginx/templates/nginx.conf.template

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

# Generate SSL certs (if needed) then substitute env vars and start nginx
ENTRYPOINT ["/entrypoint.sh"]