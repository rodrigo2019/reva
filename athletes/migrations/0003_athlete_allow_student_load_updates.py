from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("athletes", "0002_anamnesis_physical_assessment"),
    ]

    operations = [
        migrations.AddField(
            model_name="athlete",
            name="allow_student_load_updates",
            field=models.BooleanField(
                default=False,
                help_text="Quando ativo, o aluno pode registrar a propria evolucao de carga nos treinos.",
                verbose_name="Permitir atualizacao de carga pelo aluno",
            ),
        ),
    ]