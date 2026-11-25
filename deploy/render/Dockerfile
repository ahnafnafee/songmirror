FROM ghcr.io/ahnafnafee/songmirror:latest

USER root
COPY --chmod=0755 deploy/render/start.sh /usr/local/bin/songmirror-render
ENTRYPOINT ["/usr/local/bin/songmirror-render"]
CMD ["/app/.venv/bin/uvicorn", "songmirror.web:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8080"]
