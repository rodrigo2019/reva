# REVA — MVP v1

Plataforma de acompanhamento de treino com foco em evolução visível e mensurável.

## Stack

- Backend: Django (monólito)
- Frontend: Templates Django + DaisyUI
- IA: LangChain/LangGraph (estrutura inicial pronta)

## Módulos MVP implementados (base)

- Landing pública
- Login com redirecionamento por perfil (treinador/aluno)
- Gestão de treinos (criação de treino, exercícios, atualização de carga)
- Histórico automático de cargas
- Tela de progresso com gráfico por exercício
- Chat IA contextualizado por histórico de carga

## Estrutura

- `accounts`: usuário customizado com papéis
- `athletes`: vínculo treinador ↔ aluno
- `workouts`: prescrição e histórico de carga
- `progress`: visualização da evolução
- `ai_chat`: sessão de chat e integração IA
- `core`: landing e redirecionamento inicial

## Como rodar

1. Instale dependências:
   - `pip install -r requirements.txt`
2. Crie `.env` a partir de `.env.example`
3. Aplique migrações:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
4. Crie usuário admin:
   - `python manage.py createsuperuser`
5. Suba servidor:
   - `python manage.py runserver`

## Observações IA

- O serviço em `ai_chat/services.py` usa `REVA_LLM_MODEL`.
- Sem provedor configurado, o chat retorna resposta fallback para manter o fluxo funcional no MVP.
