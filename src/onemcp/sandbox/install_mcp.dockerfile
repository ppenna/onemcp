# TODO: make the bae image configurable to support multi-language MCPs
FROM onemcp/base/python:v1
ARG SCRIPT_PATH

RUN --mount=from=scriptctx,src=${SCRIPT_PATH},target=/tmp/install_mcp.sh \
    cp /tmp/install_mcp.sh /install_mcp.sh \
    && chmod +x /install_mcp.sh \
    && /install_mcp.sh

ENTRYPOINT ["/run_mcp.sh"]
