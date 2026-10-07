# Notas del proyecto

## Commits

- **No incluir** trailers de herramientas (`Generated with …`,
  `Co-Authored-By: …`) ni firmas de agente en los mensajes de commit.
  Mensaje de commit limpio, enfocado en el porqué del cambio.

## Verificación

- Backend: `.venv/Scripts/python.exe -m pytest tests -q`
- Frontend: `cd frontend && npx tsc --noEmit && npm run lint && npm test && npm run build`
- Backend en vivo: `.venv/Scripts/python.exe -m uvicorn backend.main:app --reload --port 8001 --reload-dir backend` (desde la raíz; no dejar procesos corriendo)
