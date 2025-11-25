#!/bin/bash
set -e

GREEN="\033[38;2;80;250;123m"       # green
CYAN="\033[38;2;139;233;253m"       # cyan
PINK="\033[38;2;255;102;217m"       # pink
PURPLE="\033[38;2;178;102;255m"     # purple
ORANGE="\033[38;2;255;184;108m"     # orange
RED="\033[38;2;255;85;85m"          # red
RESET="\033[0m"                     # reset

SERVICE="stacks"
FORCE=false
COMPOSE="docker compose"
NO_CACHE=false
VERSION=$(cat ./VERSION)

# Used to make sure we're stopping and removing the right images and containers
# I don't recommend changing this unless you know what you're doing!
FINGERPRINT="dfb58278-7000-469c-91be-84466af5f8e9"

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --force|-f)
            FORCE=true
        ;;
        --no-cache|-n)
            NO_CACHE=true
        ;;
    esac
done

echo -e "${PURPLE}----------------------------------------${RESET}"
echo -e "${PINK}[${PURPLE}Ʌ${PINK}] Building STɅCKS${RESET}"
echo -e "${PURPLE}----------------------------------------${RESET}"

if [ "$FORCE" = true ]; then
    echo -e "${ORANGE}[${RED}!${ORANGE}] FORCE MODE ENABLED - fingerprint checks disabled!${RESET}"
fi

# -- Check if container is running and stops it
if docker ps --format '{{.Names}}' | grep -qx "$SERVICE"; then
    CONTAINER_FINGERPRINT=$(docker inspect -f '{{ index .Config.Labels "fingerprint" }}' "$SERVICE" 2>/dev/null || echo "")
    if [ "$CONTAINER_FINGERPRINT" = "$FINGERPRINT" ] || [ "$FORCE" = true ]; then
        echo -e "${PURPLE}▸ Stopping running container...${RESET}"
        docker stop "$SERVICE" > /dev/null || true
    else
        echo -e "${ORANGE}[${RED}!${ORANGE}] There is already a container named '$SERVICE' running, but it is not ours.${RESET}"
        echo -e "${ORANGE}Please stop and remove this container manually and try again, or build using ${CYAN}--force${ORANGE}.${RESET}"
        exit 1
    fi
fi

# -- Check if container exists and deletes it
if docker ps -a --format '{{.Names}}' | grep -qx "$SERVICE"; then
    CONTAINER_FINGERPRINT=$(docker inspect -f '{{ index .Config.Labels "fingerprint" }}' "$SERVICE" 2>/dev/null || echo "")
    if [ "$CONTAINER_FINGERPRINT" = "$FINGERPRINT" ] || [ "$FORCE" = true ]; then
        echo -e "${PURPLE}▸ Removing existing container...${RESET}"
        docker rm "$SERVICE" > /dev/null || true
    else
        echo -e "${ORANGE}[${RED}!${ORANGE}] There is already a container named '$SERVICE', but it is not ours.${RESET}"
        echo -e "${ORANGE}Please remove this container manually and try again, or build using ${CYAN}--force${ORANGE}.${RESET}"
        exit 1
    fi
fi

# -- Check if image exists and deletes it
if docker image inspect "$SERVICE" >/dev/null 2>&1; then
    IMAGE_FINGERPRINT=$(docker image inspect -f '{{ index .Config.Labels "fingerprint" }}' "$SERVICE" 2>/dev/null || echo "")
    if [ "$IMAGE_FINGERPRINT" = "$FINGERPRINT" ] || [ "$FORCE" = true ]; then
        echo -e "${PURPLE}▸ Removing old image...${RESET}"
        docker image rm "$SERVICE" > /dev/null || true
    else
        echo -e "${ORANGE}[${RED}!${ORANGE}] There is already an image named '$SERVICE', but it is not ours.${RESET}"
        echo -e "${ORANGE}Please delete this container manually and try again, or build using ${CYAN}--force${ORANGE}.${RESET}"
        exit 1
    fi
fi

if [ "$NO_CACHE" = true ]; then
    echo -e "${ORANGE}► Building image (without cache)...${RESET}"
    $COMPOSE build --no-cache "$SERVICE" \
        --build-arg VERSION=$VERSION \
        --build-arg FINGERPRINT=$FINGERPRINT
else
    echo -e "${PURPLE}► Building image...${RESET}"
    $COMPOSE build "$SERVICE" \
        --build-arg VERSION=$VERSION \
        --build-arg FINGERPRINT=$FINGERPRINT
fi

echo -e "${PURPLE}► Starting all services...${RESET}"
$COMPOSE up -d

if docker ps --format '{{.Names}}' | grep -qx "$SERVICE"; then
    echo -e "${GREEN}[√] Service started successfully!${RESET}"
else
    echo -e "${RED}[${ORANGE}!${RED}] Something has gone wrong: ${SERVICE} is not running!"
    exit 1
fi

echo -e "\n\n${ORANGE}► Attaching logs (Ctrl+C to exit)...${RESET}"
docker logs -f "$SERVICE"