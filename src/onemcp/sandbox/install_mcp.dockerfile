FROM ubuntu:24.04
ARG SCRIPT_PATH

RUN --mount=from=scriptctx,src=${SCRIPT_PATH},target=/tmp/install_mcp.sh \
    cp /tmp/install_mcp.sh /install_mcp.sh \
    && chmod +x /install_mcp.sh \
    && /install_mcp.sh

ENTRYPOINT ["/run_mcp.sh"]
