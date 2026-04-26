"""
Management command to seed LLM model entries.

Based on ai_engine's seed_llm_models, adapted for REVA's supported models.
"""

from django.core.management.base import BaseCommand

from ai_assistant.models import LLMModel


MODELS_DATA = [
    # OpenAI models (Azure)
    {
        "name": "GPT-4o",
        "provider": "openai",
        "model": "gpt-4o",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 1,
        "input_price_per_1m_tokens": 2.50,
        "output_price_per_1m_tokens": 10.00,
    },
    {
        "name": "GPT-4o Mini",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tag": "recommended",
        "temperature": 0.5,
        "display_order": 2,
        "input_price_per_1m_tokens": 0.15,
        "output_price_per_1m_tokens": 0.60,
    },
    {
        "name": "GPT-4.1",
        "provider": "openai",
        "model": "gpt-4.1",
        "tag": "recommended",
        "temperature": 0.5,
        "display_order": 3,
        "input_price_per_1m_tokens": 2.00,
        "output_price_per_1m_tokens": 8.00,
    },
    {
        "name": "GPT-4.1 Mini",
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "tag": "recommended",
        "temperature": 0.5,
        "display_order": 4,
        "input_price_per_1m_tokens": 0.40,
        "output_price_per_1m_tokens": 1.60,
    },
    {
        "name": "GPT-4.1 Nano",
        "provider": "openai",
        "model": "gpt-4.1-nano",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 5,
        "input_price_per_1m_tokens": 0.10,
        "output_price_per_1m_tokens": 0.40,
    },
    {
        "name": "GPT-5",
        "provider": "openai",
        "model": "gpt-5",
        "tag": "recommended",
        "temperature": 0.5,
        "display_order": 6,
        "input_price_per_1m_tokens": 5.00,
        "output_price_per_1m_tokens": 20.00,
    },
    {
        "name": "GPT-5 Mini",
        "provider": "openai",
        "model": "gpt-5-mini",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 7,
        "input_price_per_1m_tokens": 1.00,
        "output_price_per_1m_tokens": 4.00,
    },
    {
        "name": "GPT-5 Nano",
        "provider": "openai",
        "model": "gpt-5-nano",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 8,
        "input_price_per_1m_tokens": 0.20,
        "output_price_per_1m_tokens": 0.80,
    },
    {
        "name": "O3",
        "provider": "openai",
        "model": "o3",
        "tag": "regular",
        "temperature": 1.0,
        "display_order": 9,
        "input_price_per_1m_tokens": 10.00,
        "output_price_per_1m_tokens": 40.00,
    },
    {
        "name": "O4 Mini",
        "provider": "openai",
        "model": "o4-mini",
        "tag": "regular",
        "temperature": 1.0,
        "display_order": 10,
        "input_price_per_1m_tokens": 1.10,
        "output_price_per_1m_tokens": 4.40,
    },
    # Anthropic models
    {
        "name": "Claude Sonnet 4",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 20,
        "input_price_per_1m_tokens": 3.00,
        "output_price_per_1m_tokens": 15.00,
    },
    {
        "name": "Claude 3.5 Haiku",
        "provider": "anthropic",
        "model": "claude-3-5-haiku-20241022",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 21,
        "input_price_per_1m_tokens": 0.80,
        "output_price_per_1m_tokens": 4.00,
    },
    # DeepSeek models
    {
        "name": "DeepSeek R1",
        "provider": "deepseek",
        "model": "DeepSeek-R1",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 30,
        "input_price_per_1m_tokens": 0.55,
        "output_price_per_1m_tokens": 2.19,
    },
    {
        "name": "DeepSeek V3",
        "provider": "deepseek",
        "model": "DeepSeek-V3",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 31,
        "input_price_per_1m_tokens": 0.27,
        "output_price_per_1m_tokens": 1.10,
    },
    # Google models
    {
        "name": "Gemini 2.5 Flash",
        "provider": "google",
        "model": "gemini-2.5-flash",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 40,
        "input_price_per_1m_tokens": 0.15,
        "output_price_per_1m_tokens": 0.60,
    },
    {
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "model": "gemini-2.5-pro",
        "tag": "regular",
        "temperature": 0.5,
        "display_order": 41,
        "input_price_per_1m_tokens": 1.25,
        "output_price_per_1m_tokens": 10.00,
    },
]


class Command(BaseCommand):
    help = "Seed AI LLM model entries for the REVA assistant"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for data in MODELS_DATA:
            model_id = data.pop("model")
            obj, created = LLMModel.objects.get_or_create(
                model=model_id,
                defaults=data,
            )

            if not created:
                # Update existing
                for key, value in data.items():
                    setattr(obj, key, value)
                obj.save()
                updated_count += 1
            else:
                created_count += 1

            data["model"] = model_id  # restore for next iteration

        self.stdout.write(
            self.style.SUCCESS(
                f"LLM models seeded: {created_count} created, {updated_count} updated."
            )
        )
