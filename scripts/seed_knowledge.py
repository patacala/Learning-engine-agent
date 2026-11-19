"""Seed the knowledge base with vehicle catalog data."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from learning_engine.infrastructure.database.connection import async_session_factory
from learning_engine.engines.knowledge.indexer import index_document

VEHICLES = [
    {
        "title": "Toyota Corolla 2025",
        "category": "sedan",
        "content": (
            "Toyota Corolla 2025. Sedán compacto. Motor 2.0L, 169 HP. "
            "Transmisión CVT. Consumo: 13 km/l ciudad, 17 km/l carretera. "
            "Capacidad: 5 pasajeros. Cajuela: 371 litros. "
            "Equipamiento: pantalla táctil 8\", Apple CarPlay, Android Auto, "
            "Toyota Safety Sense 3.0 (frenado automático, alerta de cambio de carril). "
            "Precio desde: $420,000 MXN. Ideal para familias pequeñas y uso diario. "
            "Garantía: 3 años o 100,000 km. Disponible en 8 colores."
        ),
        "metadata": {
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2025,
            "price_from": 420000,
            "type": "sedan",
            "segment": "compact",
        },
    },
    {
        "title": "Toyota RAV4 2025",
        "category": "suv",
        "content": (
            "Toyota RAV4 2025. SUV compacta. Motor 2.5L, 203 HP. "
            "Transmisión automática 8 velocidades. AWD disponible. "
            "Consumo: 11 km/l ciudad, 15 km/l carretera. "
            "Capacidad: 5 pasajeros. Cajuela: 580 litros. "
            "Equipamiento: pantalla 10.5\", JBL audio, Toyota Safety Sense 3.0, "
            "techo panorámico, cámara 360°. "
            "Precio desde: $620,000 MXN. Ideal para familias y aventura. "
            "Garantía: 3 años o 100,000 km."
        ),
        "metadata": {
            "brand": "Toyota",
            "model": "RAV4",
            "year": 2025,
            "price_from": 620000,
            "type": "suv",
            "segment": "compact_suv",
        },
    },
    {
        "title": "Toyota Camry 2025",
        "category": "sedan",
        "content": (
            "Toyota Camry 2025. Sedán mediano. Motor 2.5L Hybrid, 225 HP combinados. "
            "Transmisión eCVT. Consumo: 21 km/l ciudad, 19 km/l carretera. "
            "Capacidad: 5 pasajeros. Cajuela: 428 litros. "
            "Equipamiento: pantalla 12.3\", sistema de audio premium, "
            "Toyota Safety Sense 3.0, asientos calefactados, ventilados. "
            "Precio desde: $680,000 MXN. Ideal para ejecutivos y familias. "
            "Garantía: 3 años o 100,000 km. Batería híbrida: 10 años."
        ),
        "metadata": {
            "brand": "Toyota",
            "model": "Camry",
            "year": 2025,
            "price_from": 680000,
            "type": "sedan",
            "segment": "midsize",
        },
    },
    {
        "title": "Honda Civic 2025",
        "category": "sedan",
        "content": (
            "Honda Civic 2025. Sedán compacto deportivo. Motor 1.5L Turbo, 180 HP. "
            "Transmisión CVT. Consumo: 12 km/l ciudad, 16 km/l carretera. "
            "Capacidad: 5 pasajeros. Cajuela: 399 litros. "
            "Equipamiento: pantalla 9\", Bose audio, Honda Sensing "
            "(frenado automático, control de crucero adaptativo). "
            "Precio desde: $470,000 MXN. Ideal para jóvenes profesionales. "
            "Garantía: 3 años o 60,000 km."
        ),
        "metadata": {
            "brand": "Honda",
            "model": "Civic",
            "year": 2025,
            "price_from": 470000,
            "type": "sedan",
            "segment": "compact",
        },
    },
    {
        "title": "Financiamiento y Promociones",
        "category": "financing",
        "content": (
            "Opciones de financiamiento disponibles: "
            "Crédito tradicional: tasa desde 9.9% anual, hasta 72 meses. "
            "Leasing: mensualidades más bajas, opción de compra al final. "
            "Plan de ahorro: 12, 24 o 36 meses sin intereses. "
            "Promoción del mes: 0% de enganche en modelos seleccionados. "
            "Aceptamos auto a cuenta como parte de pago. "
            "Seguro incluido en el primer año con cualquier plan. "
            "Requisitos: identificación oficial, comprobante de ingresos, "
            "comprobante de domicilio."
        ),
        "metadata": {"type": "financing", "valid_until": "2025-12-31"},
    },
]


async def main():
    async with async_session_factory() as session:
        for vehicle in VEHICLES:
            await index_document(
                session=session,
                title=vehicle["title"],
                content=vehicle["content"],
                category=vehicle["category"],
                metadata=vehicle.get("metadata"),
            )
            print(f"  Indexed: {vehicle['title']}")

        await session.commit()
        print(f"\nSeeded {len(VEHICLES)} documents successfully.")


if __name__ == "__main__":
    asyncio.run(main())
