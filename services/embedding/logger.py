import logging
import json
import socket
from datetime import datetime
from typing import Any, Dict
import sys

class LogstashFormatter(logging.Formatter):
    """Format logs as JSON for Logstash"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "embedding",
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


def setup_logging(service_name: str = "embedding", logstash_host: str = None, logstash_port: int = 5000):
    """Setup logging with both console and Logstash handlers"""
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    # Logstash handler (JSON over TCP)
    if logstash_host:
        try:
            logstash_handler = TCPLogstashHandler(logstash_host, logstash_port)
            logstash_handler.setFormatter(LogstashFormatter())
            logger.addHandler(logstash_handler)
            logger.info(f"Logstash logging enabled: {logstash_host}:{logstash_port}")
        except Exception as e:
            logger.warning(f"Could not connect to Logstash: {e}")
    
    return logger