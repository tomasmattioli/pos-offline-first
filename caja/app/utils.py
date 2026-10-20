from decimal import Decimal


def to_decimal(text: str) -> Decimal:
    """Convierte un valor guardado como texto en la DB a Decimal exacto."""
    return Decimal(text)


def to_text(value: Decimal) -> str:
    """Convierte un Decimal a texto para guardar en la DB sin pérdida de precisión."""
    return str(value)
