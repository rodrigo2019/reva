"""Student self-service tools."""

from .registry import (
    student_accept_ai_workout,
    student_create_ai_workout_draft,
    student_create_personal_event,
    student_delete_personal_event,
    student_finish_workout_session,
    student_get_today,
    student_get_workout_detail,
    student_list_my_schedule,
    student_list_my_workouts,
    student_log_set,
    student_request_trainer_link,
    student_save_anamnesis,
    student_start_workout_session,
    student_update_load,
    student_update_personal_event,
    student_update_profile,
)

__all__ = [
    "student_get_today",
    "student_list_my_workouts",
    "student_get_workout_detail",
    "student_start_workout_session",
    "student_log_set",
    "student_finish_workout_session",
    "student_update_load",
    "student_update_profile",
    "student_save_anamnesis",
    "student_list_my_schedule",
    "student_create_personal_event",
    "student_update_personal_event",
    "student_delete_personal_event",
    "student_create_ai_workout_draft",
    "student_accept_ai_workout",
    "student_request_trainer_link",
]
