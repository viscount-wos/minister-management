"""Run the MCP server: ``python -m wos_mcp`` (config from env, see docs/MCP.md)."""
import logging

import uvicorn

from .app import build_app
from .config import Config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    # httpx logs request URLs only, but keep HTTP client chatter out of the logs entirely.
    for noisy in ('httpx', 'httpx2', 'httpcore'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    config = Config.from_env()
    logging.getLogger('wos_mcp').info('wos-events MCP on %s:%s -> %s (admin endpoint %s)', config.host,
                                      config.port, config.api_base,
                                      'enabled' if config.admin_enabled else 'disabled')
    # access_log=False: uvicorn's access log is harmless (no headers) but noisy; app logs suffice.
    uvicorn.run(build_app(config), host=config.host, port=config.port, access_log=False,
                proxy_headers=config.trust_proxy, log_level='info')


if __name__ == '__main__':
    main()
