# SSO - API JMV

## Google OIDC Setup

1. Ir a Google Cloud Console
2. Crear OAuth Client ID
3. Configurar redirect:
   http://localhost:8000/auth/google/callback

## Flujo

/auth/google → redirect Google  
/auth/google/callback → login + JWT

## Claims Mapping

| Claim Google | Campo API      |
| ------------ | -------------- |
| email        | Usuario.email  |
| name         | Usuario.nombre |

## Group Sync

Configurado en config.py:

engineering@empresa.com → editor  
admin@empresa.com → admin

Se sincroniza en cada login.
