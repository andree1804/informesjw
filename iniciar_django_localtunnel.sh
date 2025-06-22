#!/bin/bash

# --- CONFIGURACIÓN ---
SUBDOMINIO="informejw"  # Cambia esto si quieres otro subdominio (opcional)
PUERTO=8080            # Puerto de tu servidor Django

# --- PASO 1: Iniciar servidor Django en segundo plano ---
echo "Iniciando servidor Django en http://localhost:$PUERTO ..."
nohup python3 manage.py runserver 0.0.0.0:$PUERTO > django.log 2>&1 &

# Esperar 3 segundos a que levante el servidor
sleep 3

# --- PASO 2: Iniciar LocalTunnel ---
echo "Iniciando LocalTunnel..."
lt --port $PUERTO --subdomain $SUBDOMINIO
