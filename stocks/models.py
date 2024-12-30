from django.db import models

# from django.contrib.auth.models import AbstractUser


# Create your models here.
class Stock(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    marketPrice = models.DecimalField(default="0.00", max_digits=10, decimal_places=2)
    sectionIndex = models.CharField(max_length=255)
    details = models.JSONField()

    def __str__(self):
        return f"{self.id} - {self.name}"
