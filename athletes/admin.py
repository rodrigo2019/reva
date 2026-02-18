from django.contrib import admin

from .models import Athlete


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
	list_display = ("user", "trainer", "created_at")

# Register your models here.
