import json
import logging

from django.utils import timezone

from accounts.models import User

from .models import AssistantAction, AssistantSession

logger = logging.getLogger("ai_assistant")


class AssistantActionService:
    SAFE_CLIENT_ACTIONS = {"navigate"}

    @staticmethod
    def _resolve_session(user, session_id=None):
        if not session_id:
            return None
        return AssistantSession.objects.filter(pk=session_id, user=user).first()

    @staticmethod
    def _json_safe(value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return {"raw": value}
            return parsed if isinstance(parsed, dict) else {"data": parsed}
        return {"value": str(value)}

    @classmethod
    def create_action(
        cls,
        *,
        user,
        action_type,
        source=AssistantAction.SourceChoices.TOOL,
        status=AssistantAction.StatusChoices.PROPOSED,
        session=None,
        screen_id="",
        label="",
        payload=None,
        result=None,
        entity_type="",
        entity_id="",
        error="",
    ):
        executed_at = timezone.now() if status == AssistantAction.StatusChoices.EXECUTED else None
        return AssistantAction.objects.create(
            user=user,
            session=session,
            action_type=action_type,
            label=label or action_type,
            source=source,
            status=status,
            screen_id=screen_id or "",
            entity_type=entity_type or "",
            entity_id=str(entity_id or ""),
            payload=cls._json_safe(payload),
            result=cls._json_safe(result),
            error=error or "",
            executed_at=executed_at,
        )

    @classmethod
    def record_tool_execution(
        cls,
        *,
        context,
        tool_name,
        payload=None,
        result=None,
        entity_type="",
        entity_id="",
    ):
        user_id = (context or {}).get("user_id")
        if not user_id:
            return None

        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return None

        result_data = cls._json_safe(result)
        error = result_data.get("error", "")
        status = AssistantAction.StatusChoices.FAILED if error else AssistantAction.StatusChoices.EXECUTED
        session = cls._resolve_session(user, (context or {}).get("session_id"))

        return cls.create_action(
            user=user,
            session=session,
            action_type=tool_name,
            source=AssistantAction.SourceChoices.TOOL,
            status=status,
            screen_id=(context or {}).get("screen_context", ""),
            payload=payload or {},
            result=result_data,
            entity_type=entity_type,
            entity_id=entity_id or result_data.get("id", ""),
            error=error,
        )

    @classmethod
    def execute_client_action(cls, *, user, session, action_type, params=None, screen_id=""):
        params = params or {}
        if action_type in cls.SAFE_CLIENT_ACTIONS:
            action = cls.create_action(
                user=user,
                session=session,
                action_type=action_type,
                source=AssistantAction.SourceChoices.UI,
                status=AssistantAction.StatusChoices.EXECUTED,
                screen_id=screen_id,
                label=params.get("label", action_type),
                payload=params,
                result={"handled_by": "client", "url": params.get("url", "")},
            )
            return {
                "success": True,
                "action_id": action.pk,
                "status": action.status,
                "message": f"Action '{action_type}' executed.",
            }

        action = cls.create_action(
            user=user,
            session=session,
            action_type=action_type or "unknown",
            source=AssistantAction.SourceChoices.UI,
            status=AssistantAction.StatusChoices.PROPOSED,
            screen_id=screen_id,
            label=params.get("label", action_type or "Action"),
            payload=params,
            result={"requires_server_handler": True},
        )
        return {
            "success": True,
            "action_id": action.pk,
            "status": action.status,
            "message": f"Action '{action.action_type}' registered for review.",
        }

    @classmethod
    def recent_actions_for_user(cls, user, limit=5):
        return [
            {
                "id": action.pk,
                "type": action.action_type,
                "label": action.label,
                "status": action.status,
                "source": action.source,
                "screen_id": action.screen_id,
                "entity_type": action.entity_type,
                "entity_id": action.entity_id,
                "error": action.error,
                "created_at": action.created_at.isoformat(),
            }
            for action in AssistantAction.objects.filter(user=user).order_by("-created_at")[:limit]
        ]


def safe_record_tool_execution(**kwargs):
    try:
        return AssistantActionService.record_tool_execution(**kwargs)
    except Exception:
        logger.exception("Failed to record assistant action audit")
        return None
