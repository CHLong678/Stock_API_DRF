from rest_framework import serializers
from .models import Stock


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            "id",
            "name",
            "marketPrice",
            "sectionIndex",
            "details",
        ]

    def validate_marketPrice(self, value):
        if value <= 0:
            raise serializers.ValidationError("Market price must be a positive number.")
        return value


class AddStocksFollowSerializer(serializers.Serializer):
    stock_symbols = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        help_text="List stock symbols to follow",
    )

    def validate_stock_symbols(self, value):
        missing_stocks = [
            symbol for symbol in value if not Stock.objects.filter(id=symbol).exists()
        ]
        if missing_stocks:
            raise serializers.ValidationError(
                f"Stocks not found: {', '.join(missing_stocks)}"
            )
        return value
