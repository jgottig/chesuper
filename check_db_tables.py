#!/usr/bin/env python3
"""
Simple script to check database tables content.
"""

def check_tables():
    try:
        from backend.database.connection import SessionLocal
        from backend.database.models import Producto, Supermercado, Precio
        
        print("🔍 CHECKING DATABASE TABLES")
        print("=" * 50)
        
        with SessionLocal() as session:
            # Check productos
            productos = session.query(Producto).limit(3).all()
            print(f"📦 PRODUCTOS: {session.query(Producto).count()} total")
            for p in productos:
                print(f"  - ID: {p.id}, EAN: {p.ean}, Nombre: {p.nombre[:30]}...")
            
            # Check supermercados
            supermercados = session.query(Supermercado).all()
            print(f"\n🏪 SUPERMERCADOS: {len(supermercados)} total")
            for s in supermercados:
                print(f"  - ID: {s.id}, Código: '{s.codigo}', Nombre: {s.nombre}")
            
            # Check precios
            precios_count = session.query(Precio).count()
            print(f"\n💰 PRECIOS: {precios_count} total")
            
            if precios_count > 0:
                precios = session.query(Precio).limit(3).all()
                for p in precios:
                    print(f"  - ID: {p.id}, Producto: {p.producto_id}, Super: {p.supermercado_id}, Precio: ${p.precio_lista}")
        
        print("\n" + "=" * 50)
        
        # If no supermercados, suggest creating them
        if len(supermercados) == 0:
            print("⚠️  NO HAY SUPERMERCADOS EN LA BASE DE DATOS")
            print("Necesitas crear supermercados primero. Ejemplo:")
            print("INSERT INTO supermercados (nombre, codigo, activo) VALUES")
            print("('Coto', 'COTO', true),")
            print("('Carrefour', 'CARREFOUR', true),")
            print("('Jumbo', 'JUMBO', true);")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_tables()
