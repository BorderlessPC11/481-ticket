# Como rodar o projeto

## Pré-requisitos

- Python 3.10+ (no Windows, se `python` não funcionar, use os `.cmd` abaixo ou o interpretador em `backend\.venv` / `pos_system\.venv`)

## 1. Configurar `.env`

- **Backend:** copie `backend\.env.example` para `backend\.env`
- **POS:** copie `pos_system\.env.example` para `pos_system\.env`  
- O `API_TOKEN` do POS deve ser igual ao `BACKEND_API_TOKEN` do backend (ex.: `dev-static-token`).

## 2. Instalar dependências (uma vez por pasta)

```text
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

cd ..\pos_system
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

(Se não tiver `python` no PATH, use o caminho completo do `python.exe` instalado no sistema.)

## 3. Subir a API (terminal 1)

Na raiz do repositório:

```text
run-backend.cmd
```

A API fica em `http://127.0.0.1:8000` (docs em `http://127.0.0.1:8000/docs`).

## 4. Subir o POS (terminal 2)

Na raiz do repositório:

```text
run-pos.cmd
```

Ou, dentro de `pos_system\`:

```text
run-pos.cmd
```

## 5. Se a porta 8000 estiver em uso

Feche o outro processo que usa a 8000 ou use outro terminal/só um backend a correr.

## Alternativa manual (sem `.cmd`)

**Backend:** em `backend\`, com o venv ativo:

```text
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**POS:** em `pos_system\`:

```text
.\.venv\Scripts\python.exe run.py
```

O `pos_system\.env` deve ter `API_BASE_URL=http://127.0.0.1:8000` (ou o endereço onde a API correr).
