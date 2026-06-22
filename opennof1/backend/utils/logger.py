"""
Log configuration module
"""
import logging
import sys
from config.settings import config


def setup_logger(name: str = "AlphaTransformer") -> logging.Logger:
    """Setup log configuration"""
    log_level = getattr(config.system, 'log_level', 'INFO')
    
    # Clear existing handlers to avoid duplicates
    logger = logging.getLogger(name)
    logger.handlers.clear()
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True  # Force reconfiguration
    )
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)


# Create default logger instance
logger = setup_logger()