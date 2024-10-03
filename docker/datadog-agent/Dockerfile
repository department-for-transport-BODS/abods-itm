FROM public.ecr.aws/datadog/agent:7.55.0

COPY files/configure_datadog.py /usr/local/bin/configure_datadog.py
RUN chmod +x /usr/local/bin/configure_datadog.py

CMD ["sh", "-c", "/usr/local/bin/configure_datadog.py && /bin/entrypoint.sh"]