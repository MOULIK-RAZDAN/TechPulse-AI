import logging
import json
import socket
from datetime import datetime
from typing import Any, Dict
import logging.handlers 
import sys


class LogstashFormatter(logging.Formatter):
    """Format logs as JSON for Logstash"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": getattr(record, 'service_name', 'unknown'),  # Get from logger name
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "path": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class TCPLogstashHandler(logging.Handler):
    """Custom TCP handler that sends JSON strings to Logstash"""
    
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = None
        self._connect()
    
    def _connect(self):
        """Establish TCP connection"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
        except Exception as e:
            self.sock = None
            raise
    
    def emit(self, record):
        """Send formatted log record"""
        try:
            msg = self.format(record) + '\n'
            if self.sock:
                self.sock.sendall(msg.encode('utf-8'))
        except Exception:
            # Try to reconnect on failure
            try:
                self._connect()
                msg = self.format(record) + '\n'
                if self.sock:
                    self.sock.sendall(msg.encode('utf-8'))
            except Exception:
                pass  # Silently fail to avoid blocking application
    
    def close(self):
        """Close the socket connection"""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        super().close()


def setup_logging(service_name: str, logstash_host: str = None, logstash_port: int = 5000):
    """
    Setup structured logging with optional Logstash output
    
    Args:
        service_name: Name of the service (e.g., 'backend', 'scraper')
        logstash_host: Logstash hostname (optional)
        logstash_port: Logstash port (default: 5000)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    # Console handler (always enabled for debugging)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Human-readable format for console
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Logstash handler (optional)
    if logstash_host:
        try:
            # Create custom TCP handler for Logstash
            logstash_handler = TCPLogstashHandler(
                logstash_host, 
                logstash_port
            )
            logstash_handler.setLevel(logging.INFO)
            
            # Use custom JSON formatter for Logstash
            logstash_formatter = LogstashFormatter()
            logstash_handler.setFormatter(logstash_formatter)
            logger.addHandler(logstash_handler)
            
            logger.info(f"Logstash handler enabled: {logstash_host}:{logstash_port}")
        except Exception as e:
            logger.warning(f"⚠ Could not connect to Logstash: {e}")
    else:
        logger.info("Logstash disabled - logging to console only")
    
    return logger