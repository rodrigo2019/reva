"""
Mixins compartilhados para controle de acesso baseado em roles.

Importar esses mixins ao invés de redefinir localmente em cada app.
"""

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


class TrainerRequiredMixin(UserPassesTestMixin):
    """Permite acesso apenas a usuários autenticados com role de treinador."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_trainer


class StudentRequiredMixin(UserPassesTestMixin):
    """Permite acesso apenas a usuários autenticados com role de aluno."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_student


class LinkedStudentRequiredMixin(StudentRequiredMixin):
    """Permite acesso apenas a alunos com perfil de treino criado."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_student:
            return self.handle_no_permission()
        if request.user.get_athlete_profile() is None:
            messages.warning(request, "Your training profile is not available yet.")
            return redirect("student-dashboard")
        return super().dispatch(request, *args, **kwargs)
