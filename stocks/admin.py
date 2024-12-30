from django.contrib import admin

from .models import Stock

# Register your models here.


class StockAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "marketPrice", "sectionIndex"]


admin.site.register(Stock)
