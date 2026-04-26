"""
Management command to seed the exercise catalog with real exercises,
downloading images from the internet and linking YouTube videos.
"""

import io
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from workouts.models import Equipment, Exercise, MuscleGroup

EXERCISES = [
    # ── PEITO (Chest) ──────────────────────────────────────────────
    {
        "name": "Supino Reto com Barra",
        "muscle_group": MuscleGroup.CHEST,
        "secondary_muscle": MuscleGroup.TRICEPS,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "8-12",
        "default_rest_seconds": 90,
        "description": (
            "Deite no banco reto, segure a barra com pegada um pouco mais larga que os ombros. "
            "Desça a barra controladamente até tocar o esterno e empurre de volta até a extensão dos cotovelos. "
            "Mantenha as escápulas retraídas e os pés firmes no chão durante todo o movimento."
        ),
        "tips": (
            "Não rebata a barra no peito. Mantenha os cotovelos a ~45° do corpo. "
            "Use um parceiro de treino para cargas pesadas."
        ),
        "video_url": "https://www.youtube.com/watch?v=rT7DgCr-3pg",
        "image_url": "https://images.unsplash.com/photo-1534368786749-b63e05c92717?w=600&q=80",
    },
    {
        "name": "Supino Inclinado com Halteres",
        "muscle_group": MuscleGroup.CHEST,
        "secondary_muscle": MuscleGroup.SHOULDERS,
        "equipment": Equipment.DUMBBELL,
        "default_sets": 4,
        "default_reps": "10-12",
        "default_rest_seconds": 75,
        "description": (
            "Sente no banco inclinado a 30-45°. Segure um halter em cada mão à altura do peito. "
            "Empurre os halteres para cima até os braços ficarem estendidos, depois desça controladamente."
        ),
        "tips": (
            "Não incline o banco mais que 45° para evitar sobrecarregar o ombro. "
            "Gire os punhos levemente para dentro no topo para maior contração."
        ),
        "video_url": "https://www.youtube.com/watch?v=8iPEnn-ltC8",
        "image_url": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=600&q=80",
    },
    {
        "name": "Crucifixo com Halteres",
        "muscle_group": MuscleGroup.CHEST,
        "secondary_muscle": "",
        "equipment": Equipment.DUMBBELL,
        "default_sets": 3,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Deite no banco reto segurando halteres com braços estendidos acima do peito. "
            "Abra os braços lateralmente com leve flexão nos cotovelos até sentir alongamento no peito, "
            "depois retorne à posição inicial."
        ),
        "tips": (
            "Mantenha sempre uma leve flexão nos cotovelos. "
            "Foque em sentir o alongamento do peitoral na fase excêntrica."
        ),
        "video_url": "https://www.youtube.com/watch?v=eozdVDA78K0",
        "image_url": "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?w=600&q=80",
    },
    {
        "name": "Crossover no Cabo",
        "muscle_group": MuscleGroup.CHEST,
        "secondary_muscle": "",
        "equipment": Equipment.CABLE,
        "default_sets": 3,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Posicione as polias na parte alta. Dê um passo à frente e, com leve inclinação do tronco, "
            "traga as mãos para frente e para baixo até se cruzarem, contraindo o peito. "
            "Retorne controladamente."
        ),
        "tips": (
            "Mantenha os cotovelos levemente flexionados. "
            "Varie a altura das polias para enfatizar diferentes porções do peito."
        ),
        "video_url": "https://www.youtube.com/watch?v=taI4XduLpTk",
        "image_url": "https://images.unsplash.com/photo-1597452485669-2c7bb5fef90d?w=600&q=80",
    },
    # ── COSTAS (Back) ──────────────────────────────────────────────
    {
        "name": "Barra Fixa (Pull-up)",
        "muscle_group": MuscleGroup.BACK,
        "secondary_muscle": MuscleGroup.BICEPS,
        "equipment": Equipment.BODYWEIGHT,
        "default_sets": 4,
        "default_reps": "6-10",
        "default_rest_seconds": 90,
        "description": (
            "Pendure-se na barra com pegada pronada (palmas para frente), mãos um pouco mais largas que os ombros. "
            "Puxe o corpo para cima até o queixo ultrapassar a barra. Desça controladamente."
        ),
        "tips": (
            "Evite balanço do corpo. Foque em puxar com os cotovelos para baixo e para trás. "
            "Use banda elástica se não conseguir o peso corporal completo."
        ),
        "video_url": "https://www.youtube.com/watch?v=eGo4IYlbE5g",
        "image_url": "https://images.unsplash.com/photo-1598971457999-ca4ef48a9a71?w=600&q=80",
    },
    {
        "name": "Remada Curvada com Barra",
        "muscle_group": MuscleGroup.BACK,
        "secondary_muscle": MuscleGroup.BICEPS,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "8-12",
        "default_rest_seconds": 90,
        "description": (
            "Segure a barra com pegada pronada na largura dos ombros. Incline o tronco a ~45°, "
            "joelhos levemente flexionados. Puxe a barra em direção ao abdômen inferior, "
            "apertando as escápulas no topo. Desça controladamente."
        ),
        "tips": (
            "Mantenha as costas retas e o core ativado. "
            "Não use impulso para levantar a barra."
        ),
        "video_url": "https://www.youtube.com/watch?v=FWJR5Ve8bnQ",
        "image_url": "https://images.unsplash.com/photo-1603287681836-b174ce5074c2?w=600&q=80",
    },
    {
        "name": "Remada Unilateral com Halter",
        "muscle_group": MuscleGroup.BACK,
        "secondary_muscle": MuscleGroup.BICEPS,
        "equipment": Equipment.DUMBBELL,
        "default_sets": 3,
        "default_reps": "10-12",
        "default_rest_seconds": 60,
        "description": (
            "Apoie um joelho e uma mão no banco. Com a outra mão segure o halter e puxe "
            "em direção ao quadril, apertando a escápula no topo. Desça controladamente."
        ),
        "tips": (
            "Não gire o tronco ao puxar. Foque na contração das costas, não no bíceps."
        ),
        "video_url": "https://www.youtube.com/watch?v=pYcpY20QaE8",
        "image_url": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600&q=80",
    },
    {
        "name": "Puxada Frontal no Cabo",
        "muscle_group": MuscleGroup.BACK,
        "secondary_muscle": MuscleGroup.BICEPS,
        "equipment": Equipment.CABLE,
        "default_sets": 4,
        "default_reps": "10-12",
        "default_rest_seconds": 75,
        "description": (
            "Sente na máquina de puxada com os joelhos travados. Segure a barra larga com pegada pronada. "
            "Puxe a barra até a altura do queixo/peito superior, apertando as escápulas. "
            "Retorne controladamente."
        ),
        "tips": (
            "Não incline o tronco excessivamente para trás. "
            "Inicie o movimento puxando as escápulas para baixo."
        ),
        "video_url": "https://www.youtube.com/watch?v=CAwf7n6Luuc",
        "image_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&q=80",
    },
    # ── OMBROS (Shoulders) ─────────────────────────────────────────
    {
        "name": "Desenvolvimento Militar com Barra",
        "muscle_group": MuscleGroup.SHOULDERS,
        "secondary_muscle": MuscleGroup.TRICEPS,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "8-10",
        "default_rest_seconds": 90,
        "description": (
            "Em pé ou sentado, segure a barra na altura dos ombros com pegada pronada. "
            "Empurre a barra acima da cabeça até a extensão completa dos braços. "
            "Desça controladamente até os ombros."
        ),
        "tips": (
            "Mantenha o core contraído para proteger a lombar. "
            "Não hiperextenda a coluna no topo do movimento."
        ),
        "video_url": "https://www.youtube.com/watch?v=2yjwXTZQDDI",
        "image_url": "https://images.unsplash.com/photo-1532029837206-abbe2b7620e3?w=600&q=80",
    },
    {
        "name": "Elevação Lateral com Halteres",
        "muscle_group": MuscleGroup.SHOULDERS,
        "secondary_muscle": "",
        "equipment": Equipment.DUMBBELL,
        "default_sets": 4,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Em pé, segure um halter em cada mão ao lado do corpo. "
            "Eleve os braços lateralmente até a altura dos ombros, mantendo leve flexão dos cotovelos. "
            "Desça controladamente."
        ),
        "tips": (
            "Não use impulso do corpo. Suba até a altura dos ombros, não acima. "
            "Imagine derramar água de um copo no topo do movimento."
        ),
        "video_url": "https://www.youtube.com/watch?v=3VcKaXpzqRo",
        "image_url": "https://images.unsplash.com/photo-1581009137042-c552e485697a?w=600&q=80",
    },
    {
        "name": "Elevação Frontal com Halteres",
        "muscle_group": MuscleGroup.SHOULDERS,
        "secondary_muscle": MuscleGroup.CHEST,
        "equipment": Equipment.DUMBBELL,
        "default_sets": 3,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Em pé, segure os halteres à frente das coxas com pegada pronada. "
            "Eleve os braços à frente até a altura dos ombros, alternando ou simultaneamente. "
            "Desça controladamente."
        ),
        "tips": (
            "Mantenha o tronco estável, não balance. Use peso moderado para focar na contração."
        ),
        "video_url": "https://www.youtube.com/watch?v=-t7fuZ0KhDA",
        "image_url": "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?w=600&q=80",
    },
    # ── BÍCEPS ─────────────────────────────────────────────────────
    {
        "name": "Rosca Direta com Barra",
        "muscle_group": MuscleGroup.BICEPS,
        "secondary_muscle": MuscleGroup.FOREARMS,
        "equipment": Equipment.BARBELL,
        "default_sets": 3,
        "default_reps": "10-12",
        "default_rest_seconds": 60,
        "description": (
            "Em pé, segure a barra reta com pegada supinada (palmas para cima) na largura dos ombros. "
            "Flexione os cotovelos levando a barra até os ombros sem mover os cotovelos da posição. "
            "Desça controladamente."
        ),
        "tips": (
            "Não balance o corpo. Mantenha os cotovelos fixos ao lado do corpo. "
            "Controle a fase excêntrica (descida)."
        ),
        "video_url": "https://www.youtube.com/watch?v=kwG2ipFRgFo",
        "image_url": "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?w=600&q=80",
    },
    {
        "name": "Rosca Alternada com Halteres",
        "muscle_group": MuscleGroup.BICEPS,
        "secondary_muscle": MuscleGroup.FOREARMS,
        "equipment": Equipment.DUMBBELL,
        "default_sets": 3,
        "default_reps": "10-12",
        "default_rest_seconds": 60,
        "description": (
            "Em pé, segure um halter em cada mão com palmas voltadas para dentro. "
            "Flexione um braço por vez, girando o punho (supinação) ao subir. "
            "Desça controladamente e alterne os braços."
        ),
        "tips": (
            "Faça a supinação do punho durante a subida para maior ativação do bíceps. "
            "Não balance o corpo para auxiliar a subida."
        ),
        "video_url": "https://www.youtube.com/watch?v=sAq_ocpRh_I",
        "image_url": "https://images.unsplash.com/photo-1586401100295-7a8096fd231a?w=600&q=80",
    },
    {
        "name": "Rosca Martelo",
        "muscle_group": MuscleGroup.BICEPS,
        "secondary_muscle": MuscleGroup.FOREARMS,
        "equipment": Equipment.DUMBBELL,
        "default_sets": 3,
        "default_reps": "10-12",
        "default_rest_seconds": 60,
        "description": (
            "Em pé, segure os halteres com pegada neutra (palmas voltadas uma para a outra). "
            "Flexione os cotovelos levando os halteres em direção aos ombros sem girar o punho. "
            "Desça controladamente."
        ),
        "tips": (
            "Ótimo para trabalhar o braquial e o braquiorradial. "
            "Pode ser feito alternado ou simultâneo."
        ),
        "video_url": "https://www.youtube.com/watch?v=zC3nLlEvin4",
        "image_url": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600&q=80",
    },
    # ── TRÍCEPS ────────────────────────────────────────────────────
    {
        "name": "Tríceps Pulley (Pushdown)",
        "muscle_group": MuscleGroup.TRICEPS,
        "secondary_muscle": "",
        "equipment": Equipment.CABLE,
        "default_sets": 3,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Em pé em frente à polia alta, segure a barra com pegada pronada. "
            "Mantendo os cotovelos fixos ao lado do corpo, empurre a barra para baixo "
            "até a extensão total. Retorne controladamente."
        ),
        "tips": (
            "Não deixe os cotovelos se abrirem. Experimente com barra reta, V ou corda "
            "para variar o estímulo."
        ),
        "video_url": "https://www.youtube.com/watch?v=2-LAMcpzODU",
        "image_url": "https://images.unsplash.com/photo-1597452485669-2c7bb5fef90d?w=600&q=80",
    },
    {
        "name": "Tríceps Testa com Barra EZ",
        "muscle_group": MuscleGroup.TRICEPS,
        "secondary_muscle": "",
        "equipment": Equipment.BARBELL,
        "default_sets": 3,
        "default_reps": "10-12",
        "default_rest_seconds": 60,
        "description": (
            "Deite no banco reto segurando a barra EZ com pegada fechada acima do peito. "
            "Flexione apenas os cotovelos, descendo a barra em direção à testa. "
            "Estenda os cotovelos de volta à posição inicial."
        ),
        "tips": (
            "Mantenha os cotovelos apontando para o teto, sem abrir. "
            "Use peso moderado para proteger os cotovelos."
        ),
        "video_url": "https://www.youtube.com/watch?v=d_KZxkY_0cM",
        "image_url": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=600&q=80",
    },
    {
        "name": "Mergulho em Paralelas",
        "muscle_group": MuscleGroup.TRICEPS,
        "secondary_muscle": MuscleGroup.CHEST,
        "equipment": Equipment.BODYWEIGHT,
        "default_sets": 3,
        "default_reps": "8-12",
        "default_rest_seconds": 75,
        "description": (
            "Segure nas barras paralelas com braços estendidos. Flexione os cotovelos "
            "descendo o corpo até os braços formarem ~90°. Empurre para cima retornando à posição inicial. "
            "Mantenha o tronco mais vertical para focar no tríceps."
        ),
        "tips": (
            "Incline o tronco para frente se quiser enfatizar o peito. "
            "Mantenha ereto para maior ativação do tríceps."
        ),
        "video_url": "https://www.youtube.com/watch?v=2z8JmcrW-As",
        "image_url": "https://images.unsplash.com/photo-1598971457999-ca4ef48a9a71?w=600&q=80",
    },
    # ── QUADRÍCEPS / PERNAS ────────────────────────────────────────
    {
        "name": "Agachamento Livre com Barra",
        "muscle_group": MuscleGroup.QUADRICEPS,
        "secondary_muscle": MuscleGroup.GLUTES,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "6-10",
        "default_rest_seconds": 120,
        "description": (
            "Posicione a barra nos trapézios, pés na largura dos ombros. "
            "Flexione quadris e joelhos simultaneamente, descendo até as coxas ficarem paralelas ao chão ou abaixo. "
            "Empurre o chão subindo de volta à posição inicial."
        ),
        "tips": (
            "Mantenha os joelhos alinhados com as pontas dos pés. "
            "Core sempre contraído. Olhar para frente. Não deixe os calcanhares saírem do chão."
        ),
        "video_url": "https://www.youtube.com/watch?v=bEv6CCg2BC8",
        "image_url": "https://images.unsplash.com/photo-1566241142559-40e1dab266c6?w=600&q=80",
    },
    {
        "name": "Leg Press 45°",
        "muscle_group": MuscleGroup.QUADRICEPS,
        "secondary_muscle": MuscleGroup.GLUTES,
        "equipment": Equipment.MACHINE,
        "default_sets": 4,
        "default_reps": "10-12",
        "default_rest_seconds": 90,
        "description": (
            "Sente na máquina de leg press com os pés na plataforma na largura dos ombros. "
            "Destrave o suporte e flexione os joelhos até ~90°. "
            "Empurre a plataforma estendendo as pernas (sem travar totalmente os joelhos)."
        ),
        "tips": (
            "Posicione os pés mais altos para enfatizar glúteos e posteriores. "
            "Mais baixo para maior foco em quadríceps. Não trave os joelhos no topo."
        ),
        "video_url": "https://www.youtube.com/watch?v=IZxyjW7MPJQ",
        "image_url": "https://images.unsplash.com/photo-1434608519344-49d77a699e1d?w=600&q=80",
    },
    {
        "name": "Cadeira Extensora",
        "muscle_group": MuscleGroup.QUADRICEPS,
        "secondary_muscle": "",
        "equipment": Equipment.MACHINE,
        "default_sets": 3,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Sente na cadeira com os tornozelos atrás do rolo. "
            "Estenda os joelhos levantando o peso até a extensão completa. "
            "Desça controladamente. Ótimo para isolamento do quadríceps."
        ),
        "tips": (
            "Segure a contração por 1-2 segundos no topo. "
            "Não use impulso, controle o peso na descida."
        ),
        "video_url": "https://www.youtube.com/watch?v=YyvSfVjQeL0",
        "image_url": "https://images.unsplash.com/photo-1434608519344-49d77a699e1d?w=600&q=80",
    },
    {
        "name": "Avanço (Passada) com Halteres",
        "muscle_group": MuscleGroup.QUADRICEPS,
        "secondary_muscle": MuscleGroup.GLUTES,
        "equipment": Equipment.DUMBBELL,
        "default_sets": 3,
        "default_reps": "10-12",
        "default_rest_seconds": 75,
        "description": (
            "Em pé, segure um halter em cada mão. Dê um passo largo à frente, "
            "flexionando ambos os joelhos até ~90°. Empurre com a perna da frente "
            "para retornar. Alterne as pernas."
        ),
        "tips": (
            "Mantenha o tronco ereto. O joelho da frente não deve ultrapassar a ponta do pé excessivamente. "
            "Foque em pisar sempre no mesmo ponto."
        ),
        "video_url": "https://www.youtube.com/watch?v=D7KaRcUTQeE",
        "image_url": "https://images.unsplash.com/photo-1434608519344-49d77a699e1d?w=600&q=80",
    },
    # ── POSTERIORES (Hamstrings) ───────────────────────────────────
    {
        "name": "Stiff (Levantamento Terra Romeno)",
        "muscle_group": MuscleGroup.HAMSTRINGS,
        "secondary_muscle": MuscleGroup.GLUTES,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "8-12",
        "default_rest_seconds": 90,
        "description": (
            "Em pé, segure a barra com pegada pronada. Mantendo as pernas quase estendidas, "
            "flexione o quadril empurrando-o para trás, descendo a barra ao longo das pernas. "
            "Desça até sentir alongamento nos posteriores e retorne contraindo glúteos."
        ),
        "tips": (
            "Mantenha a barra próxima ao corpo. Costas retas o tempo todo. "
            "Não é necessário descer até o chão — pare quando sentir o alongamento."
        ),
        "video_url": "https://www.youtube.com/watch?v=7AaaYhMqbz4",
        "image_url": "https://images.unsplash.com/photo-1517963879433-6ad2b056d712?w=600&q=80",
    },
    {
        "name": "Mesa Flexora",
        "muscle_group": MuscleGroup.HAMSTRINGS,
        "secondary_muscle": "",
        "equipment": Equipment.MACHINE,
        "default_sets": 3,
        "default_reps": "12-15",
        "default_rest_seconds": 60,
        "description": (
            "Deite de bruços na mesa flexora com os tornozelos sob o rolo. "
            "Flexione os joelhos puxando o rolo em direção aos glúteos. "
            "Retorne controladamente."
        ),
        "tips": (
            "Não levante o quadril da mesa. Segure a contração no topo por 1 segundo. "
            "Controle a fase excêntrica."
        ),
        "video_url": "https://www.youtube.com/watch?v=1Tq3QdYUuHs",
        "image_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&q=80",
    },
    # ── GLÚTEOS ────────────────────────────────────────────────────
    {
        "name": "Hip Thrust com Barra",
        "muscle_group": MuscleGroup.GLUTES,
        "secondary_muscle": MuscleGroup.HAMSTRINGS,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "10-12",
        "default_rest_seconds": 75,
        "description": (
            "Sente no chão com a parte superior das costas apoiada em um banco e a barra sobre o quadril. "
            "Empurre o quadril para cima até o corpo formar uma linha reta do ombro ao joelho. "
            "Aperte os glúteos no topo e desça controladamente."
        ),
        "tips": (
            "Use uma almofada na barra para conforto. Mantenha o queixo para baixo no topo. "
            "Foque em contrair os glúteos, não hiperextender a lombar."
        ),
        "video_url": "https://www.youtube.com/watch?v=SEdqd1n0cvg",
        "image_url": "https://images.unsplash.com/photo-1574680096145-d05b474e2155?w=600&q=80",
    },
    # ── PANTURRILHA (Calves) ───────────────────────────────────────
    {
        "name": "Panturrilha em Pé na Máquina",
        "muscle_group": MuscleGroup.CALVES,
        "secondary_muscle": "",
        "equipment": Equipment.MACHINE,
        "default_sets": 4,
        "default_reps": "15-20",
        "default_rest_seconds": 45,
        "description": (
            "Posicione os ombros sob as almofadas da máquina e as pontas dos pés no apoio. "
            "Suba na ponta dos pés contraindo a panturrilha e desça lentamente "
            "até sentir alongamento."
        ),
        "tips": (
            "Faça o movimento completo — alongue bem na descida e contraia forte no topo. "
            "Segure 1-2 segundos no topo para maior ativação."
        ),
        "video_url": "https://www.youtube.com/watch?v=gwLzBJYoWlI",
        "image_url": "https://images.unsplash.com/photo-1434608519344-49d77a699e1d?w=600&q=80",
    },
    # ── ABDÔMEN ────────────────────────────────────────────────────
    {
        "name": "Abdominal Crunch no Solo",
        "muscle_group": MuscleGroup.ABS,
        "secondary_muscle": "",
        "equipment": Equipment.BODYWEIGHT,
        "default_sets": 3,
        "default_reps": "15-20",
        "default_rest_seconds": 45,
        "description": (
            "Deite de costas com joelhos flexionados e pés no chão. "
            "Mãos atrás da cabeça ou cruzadas no peito. "
            "Eleve as escápulas do chão contraindo o abdômen. Desça controladamente."
        ),
        "tips": (
            "Não puxe a cabeça com as mãos. "
            "Concentre em enrolar a coluna, não em sentar totalmente."
        ),
        "video_url": "https://www.youtube.com/watch?v=Xyd_fa5zoEU",
        "image_url": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&q=80",
    },
    {
        "name": "Prancha (Plank)",
        "muscle_group": MuscleGroup.ABS,
        "secondary_muscle": MuscleGroup.SHOULDERS,
        "equipment": Equipment.BODYWEIGHT,
        "default_sets": 3,
        "default_reps": "30-60s",
        "default_rest_seconds": 45,
        "description": (
            "Apoie os antebraços e as pontas dos pés no chão. "
            "Mantenha o corpo em linha reta da cabeça aos pés. "
            "Contraia o abdômen e os glúteos e mantenha a posição pelo tempo determinado."
        ),
        "tips": (
            "Não deixe o quadril subir ou descer. Respire normalmente. "
            "Se for fácil, aumente o tempo ou adicione peso nas costas."
        ),
        "video_url": "https://www.youtube.com/watch?v=ASdvN_XEl_c",
        "image_url": "https://images.unsplash.com/photo-1566241142559-40e1dab266c6?w=600&q=80",
    },
    {
        "name": "Elevação de Pernas Suspenso",
        "muscle_group": MuscleGroup.ABS,
        "secondary_muscle": "",
        "equipment": Equipment.BODYWEIGHT,
        "default_sets": 3,
        "default_reps": "10-15",
        "default_rest_seconds": 60,
        "description": (
            "Pendure-se na barra fixa com braços estendidos. "
            "Eleve as pernas retas (ou com joelhos flexionados) até a altura do quadril ou acima. "
            "Desça controladamente sem balanço."
        ),
        "tips": (
            "Evite balanço usando o core. "
            "Para iniciantes, comece com joelhos flexionados. Avançados podem subir até a barra."
        ),
        "video_url": "https://www.youtube.com/watch?v=hdng3Nm1x_E",
        "image_url": "https://images.unsplash.com/photo-1598971457999-ca4ef48a9a71?w=600&q=80",
    },
    # ── LEVANTAMENTO TERRA (full body / back) ──────────────────────
    {
        "name": "Levantamento Terra (Deadlift)",
        "muscle_group": MuscleGroup.BACK,
        "secondary_muscle": MuscleGroup.HAMSTRINGS,
        "equipment": Equipment.BARBELL,
        "default_sets": 4,
        "default_reps": "5-8",
        "default_rest_seconds": 120,
        "description": (
            "Com a barra no chão, posicione os pés na largura dos ombros sob a barra. "
            "Agache segurando a barra com pegada mista ou pronada. Peito aberto, costas retas. "
            "Levante a barra estendendo joelhos e quadril simultaneamente. "
            "Desça controladamente invertendo o movimento."
        ),
        "tips": (
            "A barra deve subir rente ao corpo. Não arredonde as costas em hipótese alguma. "
            "Respire e prepare o core antes de cada repetição."
        ),
        "video_url": "https://www.youtube.com/watch?v=op9kVnSso6Q",
        "image_url": "https://images.unsplash.com/photo-1517963879433-6ad2b056d712?w=600&q=80",
    },
    # ── ANTEBRAÇO ──────────────────────────────────────────────────
    {
        "name": "Rosca de Punho com Barra",
        "muscle_group": MuscleGroup.FOREARMS,
        "secondary_muscle": "",
        "equipment": Equipment.BARBELL,
        "default_sets": 3,
        "default_reps": "15-20",
        "default_rest_seconds": 45,
        "description": (
            "Sente com os antebraços apoiados nas coxas, segurando a barra com pegada supinada. "
            "Flexione apenas os punhos levantando a barra, depois desça controladamente."
        ),
        "tips": (
            "Use peso leve e foque na contração. "
            "Pode ser feito com pegada pronada para trabalhar extensores."
        ),
        "video_url": "https://www.youtube.com/watch?v=M_FaG8kOMSE",
        "image_url": "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?w=600&q=80",
    },
]


class Command(BaseCommand):
    help = "Seed the exercise catalog with common gym exercises, images and videos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all existing global exercises before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Exercise.objects.filter(is_global=True, created_by__isnull=True).delete()
            self.stdout.write(self.style.WARNING(f"Removidos {deleted} exercícios globais existentes."))

        created = 0
        skipped = 0

        for data in EXERCISES:
            image_url = data.pop("image_url", None)

            name = data["name"]
            if Exercise.objects.filter(name=name, is_global=True).exists():
                self.stdout.write(f"  ⏭  {name} (já existe)")
                skipped += 1
                continue

            exercise = Exercise(
                is_global=True,
                created_by=None,
                **data,
            )
            exercise.save()  # generates slug

            # Download image
            if image_url:
                try:
                    self.stdout.write(f"  📥 Baixando imagem para {name}...")
                    req = urllib.request.Request(
                        image_url,
                        headers={"User-Agent": "Mozilla/5.0 (REVA Fitness App)"},
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        img_data = resp.read()
                        content_type = resp.headers.get("Content-Type", "image/jpeg")
                        ext = "jpg"
                        if "png" in content_type:
                            ext = "png"
                        elif "webp" in content_type:
                            ext = "webp"
                        filename = f"{exercise.slug}.{ext}"
                        exercise.image.save(filename, ContentFile(img_data), save=True)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  ⚠  Falha ao baixar imagem para {name}: {e}"))

            self.stdout.write(self.style.SUCCESS(f"  ✅ {name}"))
            created += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Pronto! {created} exercícios criados, {skipped} ignorados."))
