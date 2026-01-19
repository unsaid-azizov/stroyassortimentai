#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для вывода справки
show_help() {
    echo "Использование: ./run.sh [ОПЦИИ]"
    echo ""
    echo "Опции:"
    echo "  --ai       Запустить только AI сервис (FastAPI)"
    echo "  --bot      Запустить только Telegram бота"
    echo "  --gmail    Запустить только Gmail сервис"
    echo "  --all      Запустить всё вместе"
    echo "  --help     Показать это сообщение"
    echo ""
    echo "Пример: ./run.sh --all"
}

# Функция для остановки всех процессов при выходе
cleanup() {
    echo -e "\n${RED}🛑 Останавливаем сервисы...${NC}"
    if [ ! -z "$AI_PID" ]; then kill $AI_PID 2>/dev/null; fi
    if [ ! -z "$BOT_PID" ]; then kill $BOT_PID 2>/dev/null; fi
    if [ ! -z "$GMAIL_PID" ]; then kill $GMAIL_PID 2>/dev/null; fi
    exit
}

# Перехватываем Ctrl+C
trap cleanup SIGINT

# Переменные для отслеживания запуска
START_AI=false
START_BOT=false
START_GMAIL=false

# Разбор аргументов
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --ai)
            START_AI=true
            shift
            ;;
        --bot)
            START_BOT=true
            shift
            ;;
        --gmail)
            START_GMAIL=true
            shift
            ;;
        --all)
            START_AI=true
            START_BOT=true
            START_GMAIL=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Неизвестная опция: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Запуск AI сервиса
if [ "$START_AI" = true ]; then
    echo -e "${BLUE}🚀 Запуск AI сервиса (FastAPI)...${NC}"
    # Используем порт 5537, который ожидает бот
    uv run uvicorn api:app --host 0.0.0.0 --port 5537 --reload > api.log 2>&1 &
    AI_PID=$!
    echo -e "${GREEN}✅ AI сервис запущен (PID: $AI_PID, лог: api.log)${NC}"
    # Небольшая пауза, чтобы API успело подняться перед запуском бота
    sleep 2
fi

# Запуск Бота
if [ "$START_BOT" = true ]; then
    echo -e "${BLUE}🤖 Запуск Telegram бота...${NC}"
    uv run bot.py > bot.log 2>&1 &
    BOT_PID=$!
    echo -e "${GREEN}✅ Бот запущен (PID: $BOT_PID, лог: bot.log)${NC}"
fi

# Запуск Gmail сервиса
if [ "$START_GMAIL" = true ]; then
    echo -e "${BLUE}📧 Запуск Gmail сервиса...${NC}"
    uv run gmail_service.py > gmail_service.log 2>&1 &
    GMAIL_PID=$!
    echo -e "${GREEN}✅ Gmail сервис запущен (PID: $GMAIL_PID, лог: gmail_service.log)${NC}"
fi

echo -e "\n${GREEN}Все выбранные сервисы запущены. Нажмите Ctrl+C для остановки.${NC}"
echo -e "Используйте 'tail -f api.log', 'tail -f bot.log' или 'tail -f gmail_service.log' для просмотра логов.\n"

# Ожидаем завершения фоновых процессов
wait

