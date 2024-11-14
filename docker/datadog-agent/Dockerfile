FROM public.ecr.aws/datadog/agent:7.55.0

COPY files/configure_datadog.py /usr/local/bin/configure_datadog.py
RUN chmod +x /usr/local/bin/configure_datadog.py
COPY files/custom_queries.yaml /tmp/custom_queries.yaml

CMD ["sh", "-c", "/usr/local/bin/configure_datadog.py && /bin/entrypoint.sh"]