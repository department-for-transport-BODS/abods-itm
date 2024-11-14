FROM dpage/pgadmin4:8

ARG POSTGRES_PORT POSTGRES_USER POSTGRES_HOST

USER root

# Configure servers.json using dynamic values
RUN cat <<EOF > /pgadmin4/servers.json
{
  "Servers": {
      "1": {
          "Name": "postgres",
          "Group": "Servers",
          "Port": ${POSTGRES_PORT},
          "Username": "${POSTGRES_USER}",
          "Host": "${POSTGRES_HOST}", 
          "SSLMode": "prefer",
          "MaintenanceDB": "postgres"
      }
  }
}
EOF

USER pgadmin