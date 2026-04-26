from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from athletes.models import Athlete, StudentRelationshipStatus
from core.mixins import LinkedStudentRequiredMixin, TrainerRequiredMixin
from workouts.models import WorkoutPlan

from .models import ClassSchedule
from .services import ScheduleService

DAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Timeline geometry (pixels)
TL_FIRST_HOUR = 6
TL_LAST_HOUR = 22
TL_ROW_PX = 64          # px per hour
TL_MIN_EVENT_PX = 36    # minimum event card height
TL_TOTAL_PX = (TL_LAST_HOUR - TL_FIRST_HOUR) * TL_ROW_PX  # 1024


def _week_start(ref_date):
    """Return the Monday of the week containing ref_date."""
    return ref_date - timedelta(days=ref_date.weekday())


def _event_top_height(scheduled_at, duration_minutes):
    """Return (top_px, height_px) for absolute positioning in the timeline."""
    top = round(((scheduled_at.hour - TL_FIRST_HOUR) + scheduled_at.minute / 60) * TL_ROW_PX)
    height = max(round(duration_minutes / 60 * TL_ROW_PX), TL_MIN_EVENT_PX)
    return top, height


class ScheduleView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "schedule/schedule.html"

    def get(self, request):
        semana_param = request.GET.get("semana", "")
        try:
            week_start = datetime.strptime(semana_param, "%Y-%m-%d").date()
            week_start = _week_start(week_start)
        except (ValueError, TypeError):
            week_start = _week_start(date.today())

        week_end = week_start + timedelta(days=6)
        week_days = [week_start + timedelta(days=i) for i in range(7)]

        classes = (
            ClassSchedule.objects.filter(
                trainer=request.user,
                athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
                scheduled_at__date__gte=week_start,
                scheduled_at__date__lte=week_end,
            )
            .select_related("athlete__user", "workout_plan")
            .order_by("scheduled_at")
        )

        # events_by_day: {date: [{"cls": ..., "top": px, "height": px}]}
        events_by_day = {d: [] for d in week_days}
        days_with_events = set()
        for cls in classes:
            day = cls.scheduled_at.date()
            if day not in events_by_day:
                continue
            top, height = _event_top_height(cls.scheduled_at, cls.duration_minutes)
            events_by_day[day].append({"cls": cls, "top": top, "height": height})
            days_with_events.add(day)

        # Hour markers for the timeline
        hours_data = [
            {"hour": h, "top_px": (h - TL_FIRST_HOUR) * TL_ROW_PX}
            for h in range(TL_FIRST_HOUR, TL_LAST_HOUR)
        ]

        prev_week = week_start - timedelta(days=7)
        next_week = week_start + timedelta(days=7)
        today = date.today()

        week_days_data = [
            {
                "date": d,
                "name": DAY_NAMES[i],
                "is_today": d == today,
                "has_events": d in days_with_events,
            }
            for i, d in enumerate(week_days)
        ]

        return render(request, self.template_name, {
            "week_days": week_days,
            "week_days_data": week_days_data,
            "events_by_day": events_by_day,
            "hours_data": hours_data,
            "timeline_height": TL_TOTAL_PX,
            "tl_row_px": TL_ROW_PX,
            "tl_first_hour": TL_FIRST_HOUR,
            "prev_week": prev_week.isoformat(),
            "next_week": next_week.isoformat(),
            "today": today,
            "has_any_events": bool(days_with_events),
        })


def _shared_context(request):
    """Base context shared by create and update forms."""
    athletes = (
        Athlete.objects.filter(
            trainer=request.user,
            relationship_status=StudentRelationshipStatus.ACTIVE,
        )
        .select_related("user")
        .order_by("user__first_name", "user__last_name")
    )
    workout_plans = (
        WorkoutPlan.objects.filter(
            athlete__trainer=request.user,
            athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
            is_archived=False,
        )
        .select_related("athlete__user")
        .order_by("athlete", "name")
    )
    return {
        "athletes": athletes,
        "workout_plans": workout_plans,
        "statuses": ClassSchedule.Status.choices,
    }


def _parse_form(request, data):
    """Parse and validate POST form data. Returns (fields_dict, errors_dict)."""
    errors = {}

    athlete_pk = data.get("athlete")
    scheduled_date = data.get("scheduled_date", "")
    scheduled_time = data.get("scheduled_time", "07:00")
    duration = data.get("duration_minutes", "60")
    workout_plan_pk = data.get("workout_plan") or None
    status = data.get("status", ClassSchedule.Status.SCHEDULED)
    notes = data.get("notes", "")

    athlete = None
    if not athlete_pk:
        errors["athlete"] = "Selecione um aluno."
    else:
        athlete = get_object_or_404(
            Athlete,
            pk=athlete_pk,
            trainer=request.user,
            relationship_status=StudentRelationshipStatus.ACTIVE,
        )

    scheduled_at = None
    if not scheduled_date:
        errors["scheduled_date"] = "Informe a data."
    else:
        try:
            scheduled_at = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            errors["scheduled_date"] = "Data ou hora inválida."

    if not duration.isdigit() or int(duration) < 1:
        errors["duration_minutes"] = "Informe uma duração válida."

    workout_plan = None
    if workout_plan_pk:
        workout_plan = WorkoutPlan.objects.filter(
            pk=workout_plan_pk,
            athlete=athlete,
            created_by=request.user,
            is_archived=False,
        ).first()
        if workout_plan is None:
            errors["workout_plan"] = "Selecione um treino deste aluno."

    return {
        "athlete": athlete,
        "scheduled_at": scheduled_at,
        "duration_minutes": int(duration) if duration.isdigit() else 60,
        "workout_plan": workout_plan,
        "status": status,
        "notes": notes,
    }, errors


class ClassCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "schedule/class_form.html"

    def get(self, request):
        ctx = _shared_context(request)
        ctx["pre_athlete"] = request.GET.get("athlete", "")
        ctx["pre_date"] = request.GET.get("data", "")
        ctx["pre_hour"] = request.GET.get("hora", "07")
        return render(request, self.template_name, ctx)

    def post(self, request):
        fields, errors = _parse_form(request, request.POST)
        if errors:
            ctx = _shared_context(request)
            ctx["errors"] = errors
            ctx["form_data"] = request.POST
            return render(request, self.template_name, ctx)

        ScheduleService.create_class(request.user, **fields)
        messages.success(request, "Aula agendada com sucesso!")
        week = _week_start(fields["scheduled_at"].date()).isoformat()
        return redirect(f"{reverse('schedule')}?semana={week}")


class ClassUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "schedule/class_form.html"

    def _get_class(self, request, pk):
        return get_object_or_404(
            ClassSchedule,
            pk=pk,
            trainer=request.user,
            athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
        )

    def get(self, request, pk):
        cls = self._get_class(request, pk)
        ctx = _shared_context(request)
        ctx["instance"] = cls
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        cls = self._get_class(request, pk)
        fields, errors = _parse_form(request, request.POST)
        if errors:
            ctx = _shared_context(request)
            ctx["instance"] = cls
            ctx["errors"] = errors
            ctx["form_data"] = request.POST
            return render(request, self.template_name, ctx)

        ScheduleService.update_class(request.user, cls, **fields)

        messages.success(request, "Aula atualizada com sucesso!")
        week = _week_start(fields["scheduled_at"].date()).isoformat()
        return redirect(f"{reverse('schedule')}?semana={week}")


class ClassDeleteView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "schedule/class_confirm_delete.html"

    def _get_class(self, request, pk):
        return get_object_or_404(
            ClassSchedule,
            pk=pk,
            trainer=request.user,
            athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
        )

    def get(self, request, pk):
        cls = self._get_class(request, pk)
        return render(request, self.template_name, {"class_obj": cls})

    def post(self, request, pk):
        cls = self._get_class(request, pk)
        week = _week_start(cls.scheduled_at.date()).isoformat()
        cls.delete()
        messages.success(request, "Aula removida da agenda.")
        return redirect(f"{reverse('schedule')}?semana={week}")


class StudentScheduleView(LoginRequiredMixin, LinkedStudentRequiredMixin, View):
    template_name = "schedule/student_schedule.html"

    def get(self, request):
        profile = request.user.get_athlete_profile()
        now = timezone.now()
        upcoming_classes = (
            ClassSchedule.objects.filter(athlete=profile, scheduled_at__gte=now)
            .select_related("trainer", "workout_plan")
            .order_by("scheduled_at")
        )
        recent_classes = (
            ClassSchedule.objects.filter(athlete=profile, scheduled_at__lt=now)
            .select_related("trainer", "workout_plan")
            .order_by("-scheduled_at")[:10]
        )
        return render(request, self.template_name, {
            "profile": profile,
            "next_class": upcoming_classes.first(),
            "upcoming_classes": upcoming_classes[:10],
            "recent_classes": recent_classes,
        })
