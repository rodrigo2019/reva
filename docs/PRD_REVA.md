# PRD REVA - Plataforma de acompanhamento de treino com IA

Data: 25/04/2026  
Status: proposta inicial  
Produto: REVA  
Stack atual: Django monolito, templates Django, DaisyUI, Chart.js, LangChain/LangGraph para IA

## 1. Resumo executivo

A REVA deve evoluir de uma plataforma de cadastro, treino e progresso para um sistema operacional inteligente para treinadores e alunos. O diferencial central será uma IA integrada a todos os fluxos: um assistente pessoal que entende a tela atual, os dados do usuário, o histórico de treino, a agenda e as regras de permissão, ajudando a responder dúvidas e executar tarefas de forma segura.

Hoje a plataforma já possui uma base relevante: papéis de treinador e aluno, vínculo treinador-aluno, dashboard, planos de treino, treinos, prescrições de exercícios, catálogo, alternativas, atualização de carga, histórico, gráficos de progresso, agenda semanal, anamnese, avaliações físicas, chat IA do aluno e assistente global com contexto de tela, streaming e voz.

O próximo passo é consolidar a experiência em torno de três ideias:

1. **Clareza operacional para o treinador**: ver quem precisa de atenção, criar/ajustar treinos rapidamente, acompanhar aderência e evolução.
2. **Experiência diária simples para o aluno**: abrir o app e saber o que fazer hoje, registrar execução real, entender evolução e pedir ajuda.
3. **IA como camada de ação**: não apenas responder perguntas, mas preparar formulários, sugerir decisões, executar comandos com confirmação, gerar relatórios e alertar riscos.

## 2. Problema

Treinadores lidam com muitas tarefas repetitivas: cadastrar alunos, analisar anamnese, criar treinos, atualizar cargas, remarcar aulas, acompanhar progresso e responder dúvidas. Alunos, por sua vez, frequentemente têm dúvidas sobre execução, progresso, próximos treinos e ajustes de carga.

Sem uma camada inteligente, a plataforma pode virar apenas mais um painel de cadastro. O valor real está em reduzir trabalho manual e transformar dados em orientação prática.

## 3. Objetivos do produto

### Objetivos principais

- Centralizar o acompanhamento de treino, agenda, perfil físico e evolução do aluno.
- Reduzir o tempo do treinador para criar, revisar e ajustar planos de treino.
- Melhorar a aderência do aluno com uma experiência mobile-first e orientada ao treino do dia.
- Transformar o assistente IA em copiloto real da plataforma, capaz de responder, orientar e executar tarefas.
- Gerar insights acionáveis sobre progresso, presença, risco de baixa aderência e necessidade de ajuste de carga.

### Objetivos de curto prazo

- Unificar a experiência de IA entre `ai_chat` e `ai_assistant`.
- Corrigir riscos de segurança do contexto das tools de IA.
- Melhorar onboarding do aluno e convite/acesso.
- Separar prescrição de treino de execução real.
- Melhorar dashboard do treinador com alertas e próximos passos.

### Objetivos de médio prazo

- Implementar RPE/RIR e sugestão de progressão de carga.
- Modelar periodização por ciclos/fases.
- Criar relatórios de evolução para treinador e aluno.
- Implementar notificações e lembretes.
- Preparar PWA/mobile para uso diário no treino.

## 4. Não objetivos neste momento

- Prescrição médica, diagnóstico clínico ou orientação terapêutica fora do escopo de treinamento.
- Marketplace público de treinadores ou venda de planos.
- Rede social, feed público ou ranking competitivo.
- App nativo completo antes de validar a experiência PWA/mobile.
- Substituir o treinador pela IA. A IA deve amplificar a capacidade do treinador, não assumir responsabilidade profissional autônoma.

## 5. Estado atual do produto

### Módulos ativos

- `accounts`: usuário customizado com papéis `trainer` e `student`, dashboards por papel e perfil do aluno.
- `athletes`: vínculo treinador-aluno, lista, detalhe, anamnese e avaliação física.
- `workouts`: planos, treinos, catálogo de exercícios, prescrições, alternativas, carga e histórico.
- `progress`: visualização do progresso do aluno por exercício.
- `schedule`: agenda semanal do treinador e agenda do aluno.
- `ai_chat`: chat contextual antigo voltado ao aluno.
- `ai_assistant`: assistente global com contexto da página, streaming, voz e tools ORM.
- `core`: landing e redirecionamento inicial.

### Pontos fortes atuais

- Fluxo treinador/aluno já existe.
- A plataforma já registra cargas e gera gráficos simples.
- Existe catálogo de exercícios com grupo muscular, equipamento, imagem e vídeo.
- Há alternativas de exercícios, úteis para contexto real de academia.
- A agenda semanal já está visualmente próxima de uma ferramenta operacional.
- O assistente global já captura contexto da página, incluindo formulários, tabelas, cards e estatísticas.
- O backend de IA já suporta streaming, voz, histórico por sessão e chamadas de tools.

### Lacunas atuais

- UI mistura português e inglês em várias telas.
- A IA tem duas experiências sobrepostas: `ai_chat` e `ai_assistant`.
- O endpoint de ação do assistente ainda não executa ações reais com confirmação.
- Há risco conhecido no isolamento de contexto das tools de IA por uso de estado global mutável.
- A sessão de treino atual altera a prescrição, mas não registra execução real separada.
- Progresso ainda é muito focado em carga bruta, com pouca interpretação.
- Agenda não valida conflitos de horário nem gera indicadores operacionais suficientes.
- Onboarding do aluno precisa ser mais claro, com convite, ativação e status de acesso.
- `ai_engine` parece legado/orfão no produto ativo e confunde manutenção/testes.

## 6. Personas e roles

### 6.1 Treinador

Responsável por cadastrar/vincular alunos, coletar anamnese, criar planos, ajustar treinos, acompanhar evolução, organizar agenda e responder dúvidas.

Necessidades:

- Entender rapidamente quais alunos precisam de atenção.
- Criar treinos com menos fricção.
- Ajustar carga com base em histórico e percepção de esforço.
- Ver aderência, faltas, progresso e alertas em um só lugar.
- Gerar relatórios claros para acompanhamento e retenção.
- Usar IA para acelerar tarefas repetitivas.

Permissões:

- Gerenciar seus próprios alunos.
- Criar, editar e arquivar planos/treinos dos seus alunos.
- Registrar avaliações, anamnese, aulas e progresso.
- Autorizar ou bloquear atualização de carga pelo aluno.
- Usar IA para consultar e alterar apenas dados do próprio escopo.

### 6.2 Aluno

Usuário que segue o plano, consulta treinos, registra execução quando permitido, acompanha progresso e tira dúvidas.

Necessidades:

- Saber o treino de hoje.
- Entender como executar exercícios.
- Registrar carga, reps, esforço e observações sem fricção.
- Ver progresso de forma motivadora e simples.
- Saber próximas aulas e mudanças.
- Perguntar à IA sobre treino, execução e uso da plataforma.

Permissões:

- Ver apenas seus próprios dados.
- Editar dados permitidos do próprio perfil, quando habilitado.
- Registrar execução de treino e carga, conforme política do treinador.
- Usar IA com escopo restrito aos próprios treinos, progresso, perfil e agenda.

### 6.3 Administrador da plataforma

Papel necessário para operação SaaS, ainda não modelado no produto ativo.

Necessidades:

- Gerenciar usuários, treinadores e configuração global.
- Monitorar uso de IA, custos, erros e saúde da plataforma.
- Configurar modelos LLM, limites e políticas.
- Acessar logs administrativos sem violar privacidade indevida.

Permissões:

- Acesso administrativo global.
- Gestão de modelos e custos de IA.
- Auditoria de ações sensíveis.

### 6.4 Dono de academia/equipe, futuro

Papel útil se a REVA evoluir para multi-tenant com equipes de treinadores.

Necessidades:

- Ver indicadores agregados de treinadores e alunos.
- Distribuir alunos entre treinadores.
- Acompanhar ocupação, agenda e retenção.

Permissões futuras:

- Gerenciar equipe dentro de uma organização.
- Ver dados agregados e operacionais da própria organização.

## 7. Princípios de UX

1. **A tela inicial deve responder “o que eu faço agora?”**  
   Para treinador: alunos em risco, aulas de hoje, treinos pendentes, atualizações recentes. Para aluno: treino de hoje, próxima aula, progresso recente e dúvidas rápidas.

2. **Mobile-first para aluno e sessão de treino**  
   Aluno usa a plataforma na academia, geralmente no celular. A UI deve ser rápida, com poucos toques, botões grandes e registro incremental.

3. **Desktop eficiente para treinador**  
   Treinador precisa comparar, filtrar, editar e revisar muitos dados. A UI deve ser densa, organizada e com atalhos claros.

4. **IA visível, contextual e segura**  
   O assistente deve entender a tela atual, mas ações que alteram dados precisam de preview, confirmação, permissão e auditoria.

5. **Progressivo, não assustador**  
   Anamnese e avaliação física devem ser blocos progressivos, não um formulário enorme sem contexto.

6. **Consistência de idioma e tom**  
   Escolher português brasileiro como idioma principal da aplicação. Manter labels, mensagens e assistente consistentes.

7. **Dados viram decisão**  
   Gráficos devem explicar tendência, variação, aderência e recomendação, não apenas exibir pontos.

## 8. Arquitetura de experiência recomendada

### 8.1 Navegação do treinador

- **Hoje**: resumo diário, aulas, alertas, tarefas e alunos que exigem atenção.
- **Alunos**: lista, filtros, perfil 360, anamnese, avaliações, treinos, progresso e histórico.
- **Planos e treinos**: construtor de planos, treinos, periodização, templates e biblioteca.
- **Agenda**: calendário semanal/mensal, presença, remarcações e conflitos.
- **Exercícios**: catálogo, filtros, vídeos, alternativas e restrições.
- **Relatórios**: evolução por aluno, exportação e resumo gerado por IA.
- **IA**: histórico, comandos, automações, uso e preferências.

### 8.2 Navegação do aluno

- **Hoje**: treino atual, próxima aula, progresso recente e ação principal.
- **Treinos**: planos ativos, treino do dia, execução e histórico.
- **Progresso**: cargas, medidas, consistência, metas e conquistas.
- **Agenda**: próximas aulas e histórico.
- **Perfil**: dados pessoais, anamnese visível, avaliações e permissões.
- **Assistente**: perguntas sobre treino, exercícios, plataforma e progresso.

### 8.3 Perfil 360 do aluno

O perfil do aluno deve virar o centro de decisão do treinador.

Abas recomendadas:

- **Visão geral**: status, objetivo, aderência, alertas, próxima aula, plano ativo.
- **Plano**: ciclo atual, treinos, volume, exercícios e ajustes recentes.
- **Execuções**: sessões realizadas, RPE/RIR, cargas reais, observações.
- **Progresso**: evolução de carga, medidas, fotos futuras, frequência e comparação por período.
- **Saúde/anamnese**: histórico médico, limitações, dores, objetivo, experiência.
- **Agenda**: aulas futuras, faltas, cancelamentos e presença.
- **Relatórios**: relatórios gerados, exportações e notas do treinador.
- **IA insights**: resumo automático, riscos, sugestões e perguntas úteis.

## 9. Assistente IA integrado

### 9.1 Visão

O assistente REVA deve funcionar como um copiloto pessoal dentro da plataforma. Ele deve responder dúvidas, interpretar dados e executar tarefas com segurança.

Exemplos:

- “Crie um treino de peito e tríceps para a Maria com foco em hipertrofia.”
- “Quais alunos estão sem treinar há mais de 7 dias?”
- “Resuma a evolução do João no supino nos últimos 60 dias.”
- “Agende aula com a Ana amanhã às 8h.”
- “Preencha essa anamnese a partir deste texto.”
- “Esse aluno teve dor no ombro. Sugira substituições seguras para exercícios de ombro.”
- “Explique para mim como fazer esse exercício.”
- “Gere um relatório mensal para enviar ao aluno.”

### 9.2 Modos do assistente

1. **Responder**  
   Tira dúvidas sobre plataforma, treino, execução, progresso e conceitos.

2. **Analisar**  
   Resume dados, encontra padrões, compara períodos e destaca riscos.

3. **Preparar**  
   Preenche formulários, monta rascunhos de treino, sugere carga e organiza anamnese.

4. **Executar**  
   Cria/edita registros com confirmação explícita quando houver escrita sensível.

5. **Monitorar**  
   Gera alertas proativos de aderência, risco e oportunidades de ajuste.

### 9.3 Requisitos funcionais da IA

#### Contexto

- Capturar tela atual, URL, título, formulários, campos, tabelas, cards e estatísticas.
- Enviar contexto para o backend em toda mensagem.
- Identificar papel do usuário e escopo de dados permitido.
- Respeitar o idioma do usuário; padrão recomendado: pt-BR.

#### Tools e ações

- Listar, criar, atualizar e remover alunos dentro do escopo do treinador.
- Consultar e atualizar anamnese e avaliações físicas.
- Listar exercícios, sugerir alternativas e criar exercícios no catálogo.
- Criar planos, treinos e prescrições.
- Atualizar carga e registrar motivo.
- Consultar agenda, criar aula, atualizar status e remarcar.
- Gerar resumo de progresso e relatório por período.

#### Segurança

- Não usar contexto global mutável para tools.
- Toda tool deve receber contexto seguro por requisição/sessão.
- Toda query deve filtrar por usuário autenticado e papel.
- Ações destrutivas exigem confirmação.
- Ações de escrita devem gerar registro de auditoria.
- O assistente deve explicar quando não tem permissão.

#### UX da IA

- Painel lateral/flutuante disponível em todas as telas autenticadas.
- Sugestões contextuais por tela.
- Botões de ação após resposta: “Aplicar”, “Editar antes”, “Abrir tela”, “Cancelar”.
- Preview antes de criar ou alterar dados.
- Histórico de conversas por usuário.
- Entrada por texto e voz.
- Indicação clara quando a IA está consultando dados ou preparando uma ação.

### 9.4 Fluxo seguro de execução por IA

1. Usuário pede uma tarefa.
2. Assistente entende contexto e dados necessários.
3. Backend prepara uma proposta de ação estruturada.
4. UI exibe preview com campos que serão alterados.
5. Usuário confirma, edita ou cancela.
6. Backend executa usando service/domain layer, não lógica duplicada na IA.
7. Sistema registra auditoria.
8. Assistente confirma resultado e oferece próximo passo.

### 9.5 Memória e personalização

Memória de IA deve ser tratada com cuidado e consentimento.

Possíveis memórias úteis:

- Preferências do treinador: estilo de treino, equipamentos comuns, nomenclatura.
- Preferências do aluno: horários, limitações, exercícios que geram desconforto.
- Padrões de progressão aprovados pelo treinador.
- Templates de relatórios e comunicação.

Requisitos:

- Usuário deve poder ver e limpar memórias relevantes.
- Memórias não devem vazar entre treinadores/alunos.
- Dados sensíveis de saúde devem ter tratamento explícito e escopo rígido.

## 10. Requisitos por área

### 10.1 Onboarding e acesso

#### Requisitos

- Aluno deve conseguir criar conta própria.
- Treinador deve vincular aluno por e-mail.
- Sistema deve mostrar status do aluno: convidado, cadastrado, vinculado, ativo, inativo.
- Treinador deve poder reenviar convite.
- Aluno sem vínculo deve ver estado claro explicando o próximo passo.
- E-mail deve ser obrigatório para fluxos de convite e vínculo.

#### Melhorias de UX

- Tela de “Link Student” deve explicar claramente que o treinador vincula uma conta existente.
- Adicionar indicador “aguardando aceite/ativação”.
- Criar checklist de perfil: conta, anamnese, avaliação, plano ativo e próxima aula.

### 10.2 Dashboard do treinador

#### Requisitos

- Mostrar aulas de hoje e próximas.
- Mostrar alunos sem atividade recente.
- Mostrar alunos com perfil incompleto.
- Mostrar alertas de faltas, queda de performance e salto excessivo de carga.
- Mostrar tarefas sugeridas pela IA.
- Permitir filtros por período e status.

#### Cards recomendados

- Alunos ativos.
- Aulas hoje.
- Alunos sem treino há X dias.
- Planos a revisar.
- Perfis incompletos.
- Atualizações de carga recentes.

#### Ações rápidas

- Criar plano.
- Agendar aula.
- Gerar relatório.
- Revisar alertas.
- Perguntar à IA sobre a carteira de alunos.

### 10.3 Dashboard do aluno

#### Requisitos

- Exibir o treino principal do dia.
- Exibir próxima aula.
- Exibir progresso recente e consistência.
- Exibir permissão de atualização de carga.
- Abrir assistente com sugestões específicas.

#### Melhorias de UX

- Trocar dashboard genérico por tela “Hoje”.
- Colocar uma ação principal: “Iniciar treino”, “Ver treino”, “Registrar execução” ou “Falar com assistente”.
- Mostrar pequenas conquistas e progresso sem excesso de gráficos.

### 10.4 Planos, treinos e periodização

#### Requisitos atuais a preservar

- Criar plano por aluno.
- Criar treinos dentro ou fora de um plano.
- Adicionar exercícios do catálogo ou customizados.
- Definir séries, reps, descanso, carga e notas.
- Adicionar alternativas por exercício.

#### Novos requisitos

- Criar templates de treino reutilizáveis.
- Duplicar plano/treino para outro aluno.
- Modelar ciclos/fases: objetivo, duração, início, fim e status.
- Diferenciar treino ativo, arquivado, rascunho e concluído.
- Sugerir volume semanal por grupo muscular.
- Validar coerência de volume, descanso e objetivo.

#### UX recomendada

- Construtor de treino com três áreas:
  - árvore do plano/ciclo;
  - lista de exercícios prescritos;
  - catálogo com busca/filtros e sugestões IA.
- Adicionar modo “rascunho gerado por IA” antes de salvar.
- Mostrar resumo do treino: grupos musculares, séries totais, duração estimada e equipamentos.

### 10.5 Execução real de treino

#### Problema atual

A sessão de treino edita a prescrição. Isso mistura o que foi planejado com o que aconteceu de fato.

#### Requisitos

- Criar entidade de sessão realizada.
- Registrar data, início/fim, aluno, treino, status e observações.
- Para cada exercício executado, registrar séries reais, reps reais, carga real, RPE/RIR, dor/desconforto e notas.
- Permitir aluno registrar execução quando autorizado.
- Permitir treinador revisar e aprovar ajustes.
- Usar execução real para progresso, relatórios e IA.

#### UX recomendada

- Fluxo mobile com um exercício por vez.
- Botões rápidos de carga.
- Timer de descanso opcional.
- RPE/RIR em controle simples.
- Finalização com resumo: volume total, PRs, exercícios pulados e observações.

### 10.6 Progressão de carga e RPE/RIR

#### Requisitos

- Registrar RPE ou RIR por exercício/série.
- Sugerir próxima carga com base em carga anterior, reps realizadas, RPE/RIR e objetivo.
- Mostrar recomendação e valor realmente aplicado.
- Permitir treinador aceitar, editar ou ignorar sugestão.
- Criar histórico auditável das recomendações.

#### Regra inicial sugerida

- Se aluno completou reps alvo com RIR alto, sugerir aumento pequeno.
- Se completou reps alvo com RIR adequado, manter ou aumentar levemente.
- Se falhou reps alvo ou RPE muito alto, manter/reduzir e alertar treinador.
- Sempre exibir que a recomendação é apoio à decisão do treinador.

### 10.7 Progresso e relatórios

#### Requisitos

- Filtros por período, treino, exercício, grupo muscular e tipo de métrica.
- Métricas agregadas: frequência, volume total, maior carga, variação percentual, aderência e presença.
- Evolução física: peso, gordura, medidas, IMC, massa magra/gorda estimada.
- Relatório por aluno com resumo gerado por IA.
- Exportação/visualização pronta para PDF.

#### UX recomendada

- Tela de progresso com cards de insight antes dos gráficos.
- Gráficos comparáveis por período.
- Explicação textual simples: “O supino evoluiu 12% em 45 dias”.
- Visão do treinador e visão do aluno com densidades diferentes.

### 10.8 Agenda

#### Requisitos

- Validar conflito de horário por treinador.
- Impedir ou alertar agendamento no passado.
- Registrar presença, falta, cancelamento e remarcação.
- Manter histórico mínimo de remarcações.
- Exibir indicadores semanais: agendadas, realizadas, canceladas e faltas.
- Permitir criar aula a partir do perfil do aluno ou por comando da IA.

#### UX recomendada

- Agenda semanal atual mantida como base.
- Adicionar resumo superior com contadores e conflitos.
- Criar modal rápido para editar status.
- Adicionar visão lista em mobile para dias com muitos eventos.

### 10.9 Catálogo inteligente de exercícios

#### Requisitos

- Busca por nome, grupo muscular, equipamento e objetivo.
- Alternativas por músculo, equipamento e restrição.
- Sinalizar exercícios inadequados para limitações do aluno.
- Permitir vídeos e instruções claras.
- IA deve sugerir substituições com motivo.

#### UX recomendada

- Filtros laterais no desktop.
- Chips de grupo muscular/equipamento.
- Preview com imagem, vídeo, instrução e dicas.
- Botão “Usar no treino”.

### 10.10 Notificações

#### Requisitos

- Lembrete de aula.
- Mudança/cancelamento de agenda.
- Novo treino liberado.
- Solicitação de atualização de carga.
- Perfil/anamnese pendente.
- Alerta de inatividade.

#### Canais sugeridos por fase

1. Notificação interna.
2. E-mail.
3. WhatsApp/SMS após validação de valor.

## 11. Backlog priorizado

### P0 - Estabilização obrigatória

- Corrigir isolamento de contexto das tools de IA.
- Definir oficialmente `ai_assistant` como experiência principal de IA ou unificar com `ai_chat`.
- Isolar/remover `ai_engine` do caminho crítico se continuar órfão.
- Garantir autorização por role em todas as queries e actions.
- Corrigir onboarding/acesso do aluno com fluxo de convite/vínculo.
- Padronizar idioma da interface em pt-BR.

### P1 - IA útil e segura

- Criar camada de ações estruturadas para o assistente.
- Implementar preview/confirmação antes de escrita.
- Executar ações reais no endpoint de ação.
- Criar auditoria para ações via IA.
- Adicionar sugestões contextuais melhores por tela.
- Criar resumos automáticos no perfil do aluno.

### P2 - Produto de treino completo

- Modelar execução real de treino.
- Adicionar RPE/RIR.
- Sugerir progressão de carga.
- Melhorar construtor de treino.
- Criar templates e duplicação de planos.
- Iniciar periodização simples por fases.

### P3 - Operação e retenção

- Alertas de aderência e risco.
- Relatórios de evolução.
- Melhorias de agenda: conflito, presença, remarcação.
- Notificações internas/e-mail.
- Dashboard do treinador orientado a tarefas.

### P4 - Escala e diferenciação

- PWA/mobile refinado.
- Multi-tenant/equipes.
- Integrações externas.
- Biblioteca inteligente de exercícios avançada.
- Analytics administrativo e custos de IA.

## 12. Requisitos técnicos e dados

### 12.1 Services de domínio

Criar services compartilhados para evitar duplicação entre UI tradicional e IA.

Services recomendados:

- `AthleteService`: vínculo, convite, status, perfil.
- `WorkoutService`: criação, duplicação, prescrição, arquivamento.
- `WorkoutExecutionService`: sessão realizada, exercícios executados, RPE/RIR.
- `ProgressService`: métricas, agregações, tendências.
- `ScheduleService`: criar, remarcar, validar conflito, presença.
- `AssistantActionService`: preview, validação, execução e auditoria.
- `ReportService`: resumo e exportação.

### 12.2 Novas entidades sugeridas

- `StudentInvite`: convite, token, status, expiração, enviado_em, aceito_em.
- `WorkoutSession`: execução real de treino.
- `WorkoutSessionExercise`: exercício executado dentro da sessão.
- `WorkoutSetLog`: séries reais, reps, carga, RPE/RIR.
- `AssistantAction`: ação proposta/executada pela IA, status, payload e auditoria.
- `Alert`: alertas de aderência, risco e revisão.
- `Notification`: notificações internas.
- `TrainingCycle` ou extensão de `TrainingPlan`: fases e periodização.

### 12.3 Auditoria

Eventos a auditar:

- Criação/remoção de aluno.
- Alterações de anamnese e avaliação física.
- Alterações de treino e carga.
- Ações executadas via IA.
- Exclusões.
- Mudanças de agenda e presença.

Campos mínimos:

- usuário executor;
- papel;
- entidade afetada;
- antes/depois quando aplicável;
- origem: UI, IA, importação, admin;
- timestamp;
- request/session id.

## 13. Métricas de sucesso

### Produto

- Tempo médio para criar um plano de treino completo.
- Percentual de alunos com perfil completo.
- Percentual de alunos com treino ativo.
- Frequência de registro de execução de treino.
- Redução de alunos inativos sem ação do treinador.
- Número de relatórios gerados por mês.

### IA

- Mensagens por usuário ativo.
- Taxa de respostas com ação executada.
- Taxa de ações confirmadas vs canceladas.
- Erros de tool por 100 ações.
- Tempo médio economizado em tarefas assistidas.
- Custo de IA por usuário ativo e por ação útil.

### UX

- Tempo para aluno iniciar treino do dia.
- Tempo para registrar uma execução.
- Taxa de conclusão da anamnese.
- Uso mobile vs desktop.
- Retenção semanal de alunos ativos.

## 14. Riscos e mitigação

### Risco: IA alterar dados incorretos

Mitigação:

- Preview obrigatório.
- Confirmação explícita para escrita.
- Auditoria.
- Validação em services.
- Rollback transacional.

### Risco: vazamento de dados entre usuários

Mitigação:

- Remover estado global mutável das tools.
- Contexto por requisição/sessão.
- Testes de isolamento.
- Filtros por papel e dono em todas as queries.

### Risco: excesso de complexidade antes de estabilizar MVP

Mitigação:

- Executar roadmap por fases.
- Priorizar segurança, dados e IA útil antes de features avançadas.
- Validar fluxos principais manualmente e com testes.

### Risco: recomendações de treino interpretadas como conduta médica

Mitigação:

- Guardrails no prompt e backend.
- Mensagens claras para casos de dor, lesão ou condição médica.
- Encaminhar para profissional de saúde quando necessário.

## 15. Critérios de aceite por marco

### Marco 1 - Base confiável

- Testes dos apps ativos rodam sem falha causada por código legado.
- IA não compartilha contexto entre usuários.
- Onboarding do aluno tem fluxo claro.
- Autorização por papel revisada nos endpoints principais.

### Marco 2 - IA acionável

- Assistente exibe preview de ações.
- Ações simples funcionam: criar aula, criar treino, atualizar carga, consultar aluno.
- Ações sensíveis exigem confirmação.
- Toda ação via IA gera auditoria.

### Marco 3 - Treino realizado

- Aluno/treinador registra execução real sem alterar prescrição original.
- RPE/RIR é registrado.
- Progresso usa dados de execução real.
- IA consegue resumir execução e sugerir próxima carga.

### Marco 4 - Operação inteligente

- Dashboard destaca alertas e tarefas.
- Agenda valida conflitos e presença.
- Relatórios de evolução são gerados por período.
- Notificações internas funcionam.

## 16. Perguntas em aberto

1. A REVA será single-tenant por enquanto ou precisa nascer preparada para academias/equipes?
2. O treinador pode criar conta de aluno ou apenas vincular aluno já cadastrado por e-mail?
3. O aluno poderá editar anamnese diretamente ou isso será apenas do treinador?
4. Qual será a regra padrão para aluno atualizar cargas: bloqueado, liberado ou aprovação pendente?
5. A IA deve executar ações imediatamente após confirmação no chat ou preencher a tela para o usuário revisar?
6. Qual canal de notificação vem primeiro: interno, e-mail ou WhatsApp?
7. Quais métricas são mais importantes para retenção: presença, cargas, medidas, engajamento ou relatórios?
8. Haverá cobrança por treinador, por aluno ativo ou por uso de IA?

## 17. Próxima sequência recomendada

1. Corrigir segurança e isolamento do assistente.
2. Unificar IA em uma experiência principal.
3. Criar camada de actions com preview/confirmação.
4. Padronizar idioma pt-BR nas telas críticas.
5. Implementar convite/vínculo do aluno.
6. Criar modelo de execução real de treino.
7. Adicionar RPE/RIR e progressão sugerida.
8. Reformular dashboard do treinador para tarefas e alertas.
9. Melhorar progresso e relatórios.
10. Evoluir mobile/PWA.

## 18. Decisão de produto recomendada

A REVA deve se posicionar como **plataforma inteligente de acompanhamento e evolução de treino**, não apenas como cadastro de treinos. O produto deve ser construído em torno de uma promessa simples:

> O treinador sabe exatamente quem precisa de atenção e consegue agir rápido. O aluno sabe exatamente o que fazer hoje e entende sua evolução. A IA conecta tudo isso, respondendo, sugerindo e executando tarefas com segurança.
