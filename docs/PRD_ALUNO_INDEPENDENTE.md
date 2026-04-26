# PRD REVA - Aluno independente com IA

Data: 25/04/2026  
Status: rascunho para decisao de produto  
Produto: REVA  
Escopo: reposicionar a plataforma para que o aluno exista e receba valor de forma totalmente independente, com o professor como camada opcional de acompanhamento, personalizacao e autoridade profissional.

## 1. Resumo executivo

A REVA deve evoluir de uma plataforma centrada no vinculo treinador-aluno para uma plataforma onde o aluno consegue iniciar, usar, evoluir e manter seu historico de treino por conta propria. O professor deixa de ser uma dependencia estrutural e passa a ser um diferencial: uma camada de acompanhamento humano, prescricao personalizada, revisao tecnica, agenda e relacionamento.

Essa mudanca altera o centro do produto. O aluno passa a ser dono da propria conta, do proprio perfil, do historico, dos treinos, das execucoes e das conversas com IA. O professor pode entrar depois, por convite, solicitacao, assinatura, equipe, academia ou relacao direta. A plataforma precisa suportar os dois modos com clareza:

1. **Aluno independente**: cria conta, preenche objetivos, usa IA, registra treinos, acompanha progresso e pode criar ou receber sugestoes de planos.
2. **Aluno acompanhado**: mantem sua autonomia, mas compartilha parte dos dados com um professor e pode receber planos, ajustes, aulas e feedback humano.
3. **Professor**: opera melhor quando conectado a alunos, mas sua existencia nao deve limitar a jornada do aluno.

## 2. Mudanca de tese

### Tese anterior

O aluno existia operacionalmente como parte da carteira de um professor. A relacao principal era: professor cadastra ou vincula aluno, cria plano, acompanha progresso e usa IA para operar melhor.

### Nova tese

O aluno e a unidade principal de valor da plataforma. Ele pode existir sem professor, treinar sem professor, falar com IA sem professor e manter seu historico sem professor. O professor aumenta qualidade, seguranca, personalizacao e responsabilidade profissional, mas nao e prerequisito para a experiencia.

### Implicacoes

- O perfil do aluno deve ser proprio, nao apenas um registro operacional do treinador.
- O vinculo com professor deve ser opcional, reversivel e baseado em permissao/consentimento.
- Treinos podem ter diferentes origens: criados pelo aluno, sugeridos pela IA, importados de templates ou prescritos por professor.
- O historico do aluno deve sobreviver a troca, perda ou ausencia de professor.
- A IA precisa funcionar para o aluno independente com limites claros, sem assumir papel medico ou responsabilidade profissional indevida.
- A plataforma deve explicar visualmente quando uma informacao e pessoal, quando e compartilhada e quando foi criada por professor.

## 3. Problema

Muitas pessoas treinam sem professor fixo, mas ainda precisam de orientacao, organizacao, progresso e respostas rapidas. Elas usam planilhas, notas, aplicativos genericos, videos soltos e memoria. Isso gera baixa consistencia, dificuldade para entender evolucao, pouca clareza sobre carga, falta de historico confiavel e duvidas recorrentes sobre execucao.

Ao mesmo tempo, professores continuam sendo extremamente valiosos, mas nem sempre estao presentes desde o primeiro dia. A plataforma perde alcance se exigir que o aluno dependa de um professor para existir. A oportunidade e permitir que o aluno entre sozinho e, quando fizer sentido, converta para uma relacao acompanhada.

## 4. Objetivos do produto

### Objetivos principais

- Permitir que qualquer aluno crie conta e use a REVA sem depender de professor.
- Fazer da IA um assistente pessoal do aluno para duvidas, organizacao, leitura de progresso e preparacao de treinos.
- Preservar a camada de professor como diferencial de qualidade, acompanhamento e responsabilidade.
- Tornar o historico do aluno portavel dentro da plataforma, mesmo se ele trocar ou remover professor.
- Separar claramente dados pessoais do aluno, dados compartilhados com professor e conteudo criado pelo professor.
- Criar uma jornada de conversao natural: aluno independente pode convidar, encontrar ou aceitar um professor depois.

### Objetivos de curto prazo

- Redefinir o modelo de dominio para separar perfil do aluno de vinculo com professor.
- Criar onboarding completo para aluno independente.
- Ajustar permissoes para que telas essenciais do aluno nao dependam de `Athlete.trainer`.
- Permitir treino, execucao, progresso e assistente IA em modo independente.
- Definir estados de relacionamento com professor: sem professor, convite pendente, acompanhado, pausado, encerrado.

### Objetivos de medio prazo

- Criar planos sugeridos por IA com revisao opcional.
- Permitir templates publicos ou internos de treino.
- Criar relatorios para aluno independente e para aluno acompanhado.
- Criar mecanismo de convite/solicitacao entre aluno e professor.
- Implementar consentimento granular de compartilhamento de dados.
- Explorar assinatura individual do aluno e/ou monetizacao por professor.

## 5. Nao objetivos neste momento

- Marketplace publico completo de professores antes de validar o modelo independente.
- Diagnostico medico, prescricao clinica ou recomendacao terapeutica.
- IA substituindo professor em decisoes profissionais sensiveis.
- Rede social, ranking publico ou feed de competicao.
- App nativo antes de consolidar a experiencia web/PWA.
- Multi-academia complexo antes de estabilizar aluno independente e professor opcional.

## 6. Personas e roles

### 6.1 Aluno independente

Pessoa que quer organizar treinos, registrar evolucao, tirar duvidas e melhorar consistencia sem depender de um professor dentro da plataforma.

Necessidades:

- Comecar rapidamente.
- Informar objetivo, nivel, restricoes, disponibilidade e equipamentos.
- Ter uma tela inicial que diga o que fazer hoje.
- Registrar treino real com carga, repeticoes, series, RPE/RIR e observacoes.
- Entender progresso com linguagem simples.
- Perguntar para a IA sobre exercicios, cargas, planejamento e uso da plataforma.
- Manter historico proprio e seguro.

Permissoes:

- Criar e editar seu perfil.
- Criar, importar ou aceitar sugestoes de planos de treino.
- Registrar execucoes e progresso.
- Usar IA com acesso aos proprios dados.
- Convidar ou aceitar professor.
- Controlar compartilhamento de dados com professor, se houver.

### 6.2 Aluno acompanhado

Aluno que mantem sua autonomia, mas possui um professor vinculado para acompanhamento.

Necessidades:

- Receber planos e ajustes do professor.
- Entender o que foi prescrito e o que foi executado.
- Saber quais dados estao sendo vistos pelo professor.
- Pedir ajuda ao professor ou a IA no contexto do proprio treino.
- Continuar usando a plataforma mesmo se o vinculo terminar.

Permissoes:

- Todas as permissoes do aluno independente.
- Visualizar planos prescritos pelo professor.
- Compartilhar execucoes, progresso, anamnese e agenda conforme permissao.
- Encerrar ou pausar vinculo, respeitando regras comerciais definidas.

### 6.3 Professor

Profissional que acompanha alunos, cria planos, analisa progresso, agenda aulas e usa IA para operar melhor.

Necessidades:

- Receber alunos por convite, solicitacao ou cadastro assistido.
- Ver apenas dados autorizados pelo aluno ou pertencentes ao vinculo.
- Criar planos e ajustes com eficiencia.
- Acompanhar aderencia, carga, faltas e alertas.
- Diferenciar alunos ativos, pendentes, pausados e ex-alunos.
- Usar IA para acelerar analise e tarefas, sempre dentro do seu escopo.

Permissoes:

- Gerenciar alunos vinculados e autorizados.
- Criar planos prescritos pelo professor.
- Ver execucoes/progresso compartilhados.
- Registrar aulas, notas e avaliacoes dentro do vinculo.
- Nao tomar posse do historico pessoal do aluno fora do que foi compartilhado.

### 6.4 Administrador da plataforma

Papel operacional futuro para SaaS.

Necessidades:

- Gerenciar usuarios, planos, custos de IA e seguranca.
- Auditar acoes sensiveis.
- Definir limites, politicas e modelos.

## 7. Modelo de dominio proposto

### 7.1 Conceitos centrais

- **User**: identidade de login. Pode ter papel principal `student` ou `trainer` no modelo atual.
- **StudentProfile**: perfil proprio do aluno, independente de professor. Deve conter objetivos, nivel, restricoes, medidas, preferencias, disponibilidade e dados pessoais de treino.
- **TrainerProfile**: perfil profissional do professor, independente da lista de alunos.
- **StudentTrainerRelationship**: vinculo opcional entre aluno e professor, com status, permissoes, origem e datas.
- **TrainingPlan**: plano de treino que pode ser criado pelo aluno, pela IA, por template ou por professor.
- **WorkoutSession**: execucao real feita pelo aluno.
- **AssistantSession**: historico de IA, sempre com escopo por usuario e contexto.

### 7.2 Estados do aluno

- **Sem perfil completo**: conta criada, onboarding pendente.
- **Independente ativo**: usa treinos/progresso/IA sem professor.
- **Convite pendente**: professor convidou ou aluno solicitou professor.
- **Acompanhado**: possui vinculo ativo com professor.
- **Vinculo pausado**: relacao temporariamente inativa, dados preservados.
- **Vinculo encerrado**: professor nao acessa novos dados, historico do aluno permanece.

### 7.3 Origem dos planos e treinos

Todo plano deve indicar origem:

- `self_created`: criado pelo aluno.
- `ai_suggested`: sugerido pela IA e aceito pelo aluno.
- `trainer_prescribed`: prescrito por professor.
- `template`: criado a partir de modelo.
- `imported`: importado de fonte externa, futuro.

Essa origem e importante para UX, permissao, auditoria e responsabilidade.

### 7.4 Propriedade dos dados

Regra base: o aluno e dono do proprio historico pessoal. O professor tem acesso ao que foi criado dentro do vinculo ou compartilhado pelo aluno.

Categorias recomendadas:

- **Dados pessoais do aluno**: perfil, objetivos, restricoes, historico proprio, conversas pessoais com IA.
- **Dados compartilhados**: execucoes, progresso, agenda e anamnese visivel ao professor.
- **Dados do professor**: notas internas, templates privados, configuracoes profissionais.
- **Dados de vinculo**: planos prescritos, aulas, feedbacks, avaliacoes e relatorios do acompanhamento.

## 8. Experiencia do aluno independente

### 8.1 Onboarding

Fluxo recomendado:

1. Criar conta.
2. Escolher objetivo principal: hipertrofia, forca, emagrecimento, saude, performance, retorno, outro.
3. Informar nivel: iniciante, intermediario, avancado.
4. Informar disponibilidade semanal.
5. Informar equipamentos/acesso: academia completa, casa, halteres, peso corporal, outros.
6. Informar restricoes e dores relevantes.
7. Escolher caminho inicial:
   - montar treino com IA;
   - criar treino manualmente;
   - usar template;
   - conectar professor.

### 8.2 Tela Hoje do aluno

A tela inicial do aluno deve responder: "o que eu faco agora?"

Conteudos recomendados:

- Proximo treino sugerido ou planejado.
- Botao principal para iniciar treino.
- Ultima execucao e resumo rapido.
- Progresso recente.
- Alertas simples: treino atrasado, carga estagnada, dor relatada, descanso insuficiente.
- Atalho para perguntar a IA.
- Status do professor, se houver.

### 8.3 Criacao e ajuste de treino

O aluno independente deve conseguir:

- Criar treino manual.
- Pedir sugestao da IA com base no perfil.
- Editar sugestoes antes de salvar.
- Registrar exercicios com series, reps, descanso e carga inicial.
- Ajustar plano ao longo do tempo.
- Duplicar, arquivar e trocar exercicios.

### 8.4 Progresso

Progresso deve ir alem de grafico de carga.

Indicadores recomendados:

- Consistencia semanal.
- Volume por grupo muscular.
- Evolucao de carga por exercicio.
- PRs ou melhores marcas.
- Carga percebida/RPE.
- Observacoes de dor ou desconforto.
- Tendencias explicadas pela IA em linguagem simples.

## 9. Experiencia com professor como diferencial

### 9.1 Entrada do professor na jornada

Modelos possiveis:

- Professor convida aluno por email/link.
- Aluno solicita vinculo com professor por codigo/link.
- Aluno independente decide conectar um professor depois.
- Professor cadastra aluno e o aluno ativa a conta, mantendo propriedade do perfil.

### 9.2 Valor adicional do professor

O professor deve oferecer recursos claramente superiores ao modo independente:

- Prescricao profissional.
- Revisao periodica.
- Ajuste fino de carga, volume e exercicios.
- Agenda/aulas.
- Feedback humano.
- Relatorios comentados.
- Responsabilidade e acompanhamento de longo prazo.

### 9.3 UX do aluno acompanhado

O aluno deve enxergar:

- Quem e o professor atual.
- Quais dados o professor consegue ver.
- Quais planos foram prescritos pelo professor.
- O que foi alterado pelo professor.
- Como pedir ajuda.
- Como pausar ou encerrar vinculo, se permitido.

### 9.4 UX do professor

O professor deve enxergar:

- Alunos vinculados ativos.
- Solicitacoes pendentes.
- Alunos independentes que pediram acompanhamento, se esse fluxo existir.
- Dados compartilhados pelo aluno.
- Alertas de aderencia, execucao, dor e progresso.
- Origem do plano atual de cada aluno.

## 10. IA integrada

### 10.1 Papel da IA para aluno independente

A IA deve ser o principal acelerador da experiencia independente, sem prometer substituir professor.

Ela deve ajudar a:

- Explicar exercicios e termos.
- Sugerir estrutura inicial de treino com base no perfil.
- Interpretar progresso.
- Identificar inconsistencias simples.
- Preparar ajustes de treino para aprovacao do aluno.
- Responder duvidas sobre a plataforma.
- Gerar resumos de treino e proximos passos.

### 10.2 Limites da IA

- A IA nao deve diagnosticar lesoes ou doencas.
- A IA deve recomendar procurar profissional quando houver dor, sintomas, lesao ou risco.
- A IA deve diferenciar sugestao de prescricao profissional.
- A IA deve pedir confirmacao antes de criar, editar ou excluir dados.
- A IA deve respeitar escopo de permissao e compartilhamento.

### 10.3 Papel da IA para professor

Para o professor, a IA continua como copiloto operacional:

- Resumir aluno.
- Sugerir ajustes.
- Preparar planos.
- Encontrar alunos em risco.
- Gerar relatorios.
- Agendar ou preparar tarefas com confirmacao.

## 11. Permissoes e seguranca

### 11.1 Principios

- O aluno acessa todos os proprios dados essenciais, com ou sem professor.
- O professor acessa apenas dados dos alunos vinculados e autorizados.
- Vínculo nao deve transferir propriedade total dos dados ao professor.
- Encerramento de vinculo deve preservar historico do aluno e limitar acesso futuro do professor.
- Conversas pessoais do aluno com IA sao sempre privadas e nao devem ser visiveis ao professor.
- Agenda nao deve ser compartilhada integralmente; apenas compromissos ligados ao acompanhamento devem ser visiveis ao professor.
- Acoes de IA com escrita devem ter preview, confirmacao e auditoria.

### 11.2 Decisoes tecnicas esperadas

- Separar perfil independente do aluno do modelo de vinculo com professor.
- Remover dependencias de `Athlete.trainer` para telas essenciais do aluno.
- Introduzir status e permissoes no relacionamento aluno-professor.
- Marcar origem e responsavel por planos, treinos, avaliacoes e notas.
- Revisar queries para evitar vazamento entre professores e entre modos.

## 12. MVP proposto

### Fase 1 - Decisoes e dominio

- Fechar decisoes de produto listadas neste documento.
- Definir nomes finais dos modelos.
- Definir estados de relacionamento.
- Definir propriedade e compartilhamento de dados.

### Fase 2 - Aluno independente basico

- Onboarding do aluno sem professor.
- Perfil proprio do aluno.
- Dashboard Hoje independente.
- Treinos e execucao real funcionando sem professor.
- Progresso proprio funcionando sem professor.

### Fase 3 - IA do aluno independente

- Assistente contextual para aluno.
- Sugestoes de treino com confirmacao.
- Resumos de progresso.
- Guardrails de seguranca e linguagem.

### Fase 4 - Professor opcional

- Convite iniciado pelo professor, com aceite explicito do aluno.
- Permissoes de compartilhamento.
- Professor visualiza e acompanha alunos vinculados.
- Planos prescritos pelo professor com origem clara.

### Fase 5 - Operacao e monetizacao

- Relatorios.
- Notificacoes.
- Assinaturas ou limites por plano.
- Templates publicos/privados.
- Possivel marketplace ou descoberta de professores.

## 13. Metricas de sucesso

### Aluno independente

- Percentual de alunos que completam onboarding.
- Percentual que registra primeiro treino.
- Retencao em 7, 14 e 30 dias.
- Numero medio de execucoes por semana.
- Uso da IA por aluno ativo.
- Percentual que cria ou aceita um plano.

### Conversao para professor

- Percentual de alunos independentes que conectam professor.
- Tempo medio ate primeiro vinculo.
- Taxa de aceitacao de convites.
- Retencao de alunos acompanhados vs independentes.

### Professor

- Tempo para criar plano.
- Numero de alunos acompanhados ativos.
- Frequencia de revisao de planos.
- Uso da IA em tarefas operacionais.

## 14. Riscos

- Aluno interpretar sugestao de IA como prescricao profissional sem contexto.
- Modelo de permissao ficar complexo demais cedo.
- Migração do modelo atual `Athlete` causar regressao em treinos, agenda e progresso.
- Professor sentir que a plataforma diminui seu papel, se a comunicacao nao for bem posicionada.
- Experiencia independente virar generica se a IA nao for realmente contextual.
- Monetizacao ficar confusa se aluno e professor forem clientes possiveis ao mesmo tempo.

## 15. Perguntas de decisao antes da implementacao

### 15.1 Posicionamento

1. A REVA sera primeiro um app para aluno com camada opcional de professor, ou uma plataforma para professores que tambem aceita aluno independente?
2. Queremos comunicar a IA como "assistente de treino" ou como "copiloto da plataforma"?
3. O professor deve ser apresentado como upgrade premium, como servico separado ou como parte natural da jornada?

### 15.2 Conta e roles

4. Um usuario pode ser aluno e professor ao mesmo tempo no futuro?
5. Devemos manter `student` e `trainer` como roles exclusivas agora, ou preparar suporte para multiplos papeis?
6. O aluno independente precisa de um perfil obrigatorio antes de acessar treinos, ou pode explorar a plataforma com perfil incompleto?

### 15.3 Vinculo aluno-professor

7. Quem inicia o vinculo: aluno, professor, ambos?
8. O professor pode cadastrar um aluno do zero, ou sempre deve convidar uma conta que o aluno ativa?
9. O aluno pode ter mais de um professor ao mesmo tempo?
10. Se puder ter mais de um professor, os professores veem dados separados por vinculo ou um historico compartilhado?
11. O aluno pode encerrar o vinculo sozinho?
12. O professor pode encerrar o vinculo e manter acesso ao historico antigo?

### 15.4 Propriedade e privacidade

13. Quais dados sao sempre privados do aluno?
14. Quais dados sao automaticamente compartilhados com professor ativo?
15. O aluno pode esconder treinos independentes do professor?
16. Conversas do aluno com IA devem ser visiveis ao professor em algum caso?
17. Notas internas do professor devem ser invisiveis ao aluno?

### 15.5 Treinos e responsabilidade

18. A IA pode criar um plano completo para o aluno independente, ou apenas sugerir um rascunho que o aluno confirma?
19. Devemos diferenciar visualmente treino "sugerido pela IA" de treino "prescrito por professor"?
20. O aluno pode editar um treino prescrito pelo professor?
21. Se editar, isso vira uma copia pessoal ou altera o plano do professor?
22. Como tratar dor ou lesao relatada: bloquear sugestoes, reduzir escopo ou recomendar professor/medico?

### 15.6 Monetizacao

23. Quem paga primeiro: aluno, professor ou ambos?
24. O modo aluno independente sera gratuito, freemium ou pago?
25. Recursos de IA terao limite por plano?
26. Professor paga por numero de alunos, por assento, por uso de IA ou por assinatura fixa?
27. Aluno conectado a professor consome limite de quem?

### 15.7 Produto e UX

28. A tela inicial padrao para aluno deve ser "Hoje", "Treinos" ou "Assistente"?
29. O onboarding deve ser curto e progressivo, ou completo antes de liberar plano?
30. Devemos permitir templates prontos antes da IA criar planos?
31. A agenda e obrigatoria para aluno independente ou apenas para alunos acompanhados?
32. Aluno independente precisa de metas e check-ins semanais desde o MVP?

### 15.8 Implementacao

33. Preferimos migrar o modelo atual `Athlete` para um perfil independente ou criar novos modelos e manter compatibilidade temporaria?
34. Devemos renomear conceitos no produto de "atleta" para "aluno"?
35. Queremos preservar dados atuais como alunos acompanhados por seus professores atuais?
36. O proximo trabalho deve ser discovery tecnico de dominio ou prototipo UX da nova jornada do aluno?

## 16. Recomendacao inicial

Minha recomendacao para reduzir risco, manter velocidade e preparar escala para alunos, professores e academias:

1. Posicionar a REVA como uma plataforma centrada no aluno, com camadas profissionais para professores e academias.
2. Tratar o aluno como dono da identidade, perfil, historico e conversas pessoais com IA.
3. Permitir que um usuario tenha mais de uma capacidade no futuro, como aluno e professor, mesmo que a interface inicial ainda separe os modos.
4. Criar um perfil independente do aluno separado do vinculo com professor.
5. Tratar o vinculo com professor como relacionamento opcional, iniciado pelo professor e aceito pelo aluno.
6. Permitir apenas um professor ativo por aluno no MVP.
7. Para academias, modelar uma organizacao/equipe acima do professor, sem permitir que isso vire varios professores independentes acessando tudo sem regra.
8. Fazer o aluno independente funcionar primeiro em: onboarding, Hoje, treino, execucao, progresso e IA.
9. Depois reconectar o professor como upgrade profissional, sem quebrar o dashboard operacional ja criado.
10. Deixar marketplace publico e multiplos professores independentes para depois.

## 17. Decisoes registradas

Decisoes tomadas em 25/04/2026:

1. **Posicionamento**: a REVA deve escalar como plataforma centrada no aluno, com professor e academia como camadas profissionais opcionais. Na pratica, o aluno e a unidade principal de dados e valor; professores e academias entram como operadores autorizados.
2. **Usuario com multiplos papeis**: sim, no futuro uma pessoa pode ser aluno e professor. O produto deve se preparar para capacidades ou perfis multiplos, nao apenas role unica fixa para sempre.
3. **Onboarding do aluno**: recomendado onboarding progressivo. O aluno pode explorar a plataforma com perfil incompleto, mas para a IA criar um plano completo ou para iniciar um plano estruturado deve existir um perfil minimo: objetivo, nivel, disponibilidade, equipamentos e restricoes/dor.
4. **Inicio do vinculo**: professor inicia o convite, mas o aluno precisa aceitar. O professor nao deve ganhar acesso automatico sem consentimento.
5. **Quantidade de professores**: aluno nao deve ter mais de um professor ativo no MVP.
6. **Fim do vinculo**: professor perde acesso aos dados do aluno quando o vinculo termina. O aluno preserva o proprio historico. Dados legais, financeiros ou auditoria interna podem ser preservados pela plataforma, mas nao devem permanecer como acesso operacional do professor.
7. **Privacidade da IA**: conversas pessoais do aluno com IA sao sempre privadas.
8. **Compartilhamento com professor**: professor ativo pode ver dados de treino, execucao, progresso, anamnese e informacoes relevantes do acompanhamento. Agenda nao deve ser compartilhada integralmente; apenas compromissos relacionados ao acompanhamento.
9. **IA criando treino**: IA pode criar plano completo para aluno independente, com confirmacao do aluno antes de salvar e com linguagem clara de que e sugestao automatizada.
10. **Treino prescrito pelo professor**: aluno nao pode editar diretamente um treino prescrito. Alteracoes devem virar solicitacoes, que o professor aprova, rejeita ou transforma em ajuste.
11. **Monetizacao**: ambos podem pagar. A plataforma deve suportar B2C para aluno e B2B/B2B2C para professores e academias.
12. **Implementacao ideal**: podemos redesenhar o dominio idealmente, sem depender de manter o banco atual como restricao principal. Ainda assim, dados existentes devem ter plano de migracao quando a implementacao comecar.

## 18. Modelo recomendado para escala

Para escalar para alunos, professores e academias, o melhor desenho e uma plataforma multi-lado com identidade do aluno no centro.

### 18.1 Camadas da plataforma

1. **Camada aluno**  
   Conta, perfil, historico, treinos, execucoes, progresso, IA pessoal e privacidade.

2. **Camada professor**  
   Acompanhamento profissional, prescricoes, revisoes, feedback, agenda de compromissos e dashboard operacional.

3. **Camada academia/organizacao**  
   Gestao de equipe, carteira de alunos, convites, permissao de profissionais, indicadores agregados e operacao comercial.

### 18.2 Por que esse modelo escala melhor

- Evita duplicar o mesmo aluno em varias carteiras quando ele troca de professor ou academia.
- Permite crescimento B2C: aluno entra sozinho e recebe valor imediato.
- Permite crescimento B2B: professor usa a plataforma para operar melhor.
- Permite crescimento B2B2C: academia convida alunos e professores, mas o aluno continua com identidade propria.
- Cria caminho natural de conversao: aluno independente pode virar aluno acompanhado; professor pode trazer carteira; academia pode trazer equipe.
- Mantem privacidade defensavel: acesso profissional depende de vinculo ativo e consentimento.

### 18.3 Como respeitar "um professor ativo" em academias

Mesmo em academias, a regra do MVP deve continuar simples: um aluno tem um professor responsavel ativo. A academia pode ter equipe, mas o acesso deve ser mediado por papel operacional:

- professor responsavel: acompanha e prescreve;
- substituto ou equipe: acesso temporario ou limitado, se autorizado pela academia e pelas regras do produto;
- gestor da academia: ve indicadores agregados e operacao, nao conversas privadas de IA nem dados sensiveis sem necessidade.

### 18.4 Produto recomendado por fase

1. **MVP aluno independente**: onboarding minimo, Hoje, IA, treino, execucao e progresso.
2. **Professor upgrade**: convite, aceite, plano prescrito, solicitacao de ajuste e dashboard do professor.
3. **Academia/equipe**: organizacao, professores, alunos vinculados, permissoes e indicadores.
4. **Monetizacao**: plano individual do aluno, plano profissional do professor e plano organizacional da academia.
