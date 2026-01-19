#!/bin/bash
# SSH port forwarding для 1С API
# Пробрасываем 172.16.77.34:80 на localhost:8080

ssh -N -L 8080:172.16.77.34:80 user@jump-host &
SSH_PID=$!
echo $SSH_PID > /tmp/ssh-forward.pid
