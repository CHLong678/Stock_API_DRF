# Generated by Django 5.1.4 on 2024-12-25 07:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stock',
            name='id',
            field=models.CharField(max_length=255, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='stock',
            name='marketPrice',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=10),
        ),
    ]
