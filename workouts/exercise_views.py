from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.mixins import TrainerRequiredMixin

from .forms import ExerciseCatalogForm
from .models import Equipment, Exercise, MuscleGroup


class ExerciseCatalogListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
    model = Exercise
    template_name = "exercises/catalog_list.html"
    context_object_name = "exercises"
    paginate_by = 24

    def get_queryset(self):
        qs = Exercise.objects.filter(
            Q(is_global=True) | Q(created_by=self.request.user)
        )
        muscle = self.request.GET.get("muscle")
        equipment = self.request.GET.get("equipment")
        q = self.request.GET.get("q", "").strip()

        if muscle:
            qs = qs.filter(muscle_group=muscle)
        if equipment:
            qs = qs.filter(equipment=equipment)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["muscle_groups"] = MuscleGroup.choices
        ctx["equipments"] = Equipment.choices
        ctx["active_muscle"] = self.request.GET.get("muscle", "")
        ctx["active_equipment"] = self.request.GET.get("equipment", "")
        ctx["search_query"] = self.request.GET.get("q", "")
        return ctx


class ExerciseCatalogCreateView(LoginRequiredMixin, TrainerRequiredMixin, CreateView):
    model = Exercise
    form_class = ExerciseCatalogForm
    template_name = "exercises/catalog_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("exercise-catalog-list")


class ExerciseCatalogDetailView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
    model = Exercise
    template_name = "exercises/catalog_detail.html"
    context_object_name = "exercise"

    def get_queryset(self):
        return Exercise.objects.filter(
            Q(is_global=True) | Q(created_by=self.request.user)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit"] = self.object.created_by == self.request.user
        return ctx


class ExerciseCatalogUpdateView(LoginRequiredMixin, TrainerRequiredMixin, UpdateView):
    model = Exercise
    form_class = ExerciseCatalogForm
    template_name = "exercises/catalog_form.html"

    def get_queryset(self):
        return Exercise.objects.filter(created_by=self.request.user)

    def get_success_url(self):
        return reverse_lazy("exercise-catalog-detail", kwargs={"pk": self.object.pk})


class ExerciseCatalogDeleteView(LoginRequiredMixin, TrainerRequiredMixin, DeleteView):
    model = Exercise
    template_name = "exercises/catalog_confirm_delete.html"
    success_url = reverse_lazy("exercise-catalog-list")

    def get_queryset(self):
        return Exercise.objects.filter(created_by=self.request.user)


class ExerciseCatalogSearchView(LoginRequiredMixin, TrainerRequiredMixin, View):
    """JSON endpoint for searching exercises (used by workout detail AJAX)."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        muscle = request.GET.get("muscle", "")
        qs = Exercise.objects.filter(
            Q(is_global=True) | Q(created_by=request.user)
        )
        if q:
            qs = qs.filter(name__icontains=q)
        if muscle:
            qs = qs.filter(muscle_group=muscle)
        qs = qs[:20]

        results = []
        for ex in qs:
            results.append({
                "id": ex.pk,
                "name": ex.name,
                "muscle_group": ex.get_muscle_group_display(),
                "equipment": ex.get_equipment_display(),
                "image": ex.image.url if ex.image else None,
                "default_sets": ex.default_sets,
                "default_reps": ex.default_reps,
                "default_rest": ex.default_rest_seconds,
                "description": ex.description[:120] if ex.description else "",
            })
        return JsonResponse({"results": results})
