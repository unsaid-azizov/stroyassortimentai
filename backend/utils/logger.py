import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging(service_name: str, log_dir: Path = Path("logs")):
    """Настройка логирования в файл для сервиса."""
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{service_name}.log"
    
    # Создаем handler с ротацией (макс 10MB, 5 файлов)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024, 
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Настраиваем root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    # Также выводим в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logging.getLogger(service_name)



