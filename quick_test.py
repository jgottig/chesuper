#!/usr/bin/env python3
"""
Test rápido del backend migrado.
"""

def main():
    print("🧪 TEST RÁPIDO DEL BACKEND")
    print("=" * 40)
    
    try:
        # Test básico de importación
        print("1. Importando servicio...")
        from backend.database_service import db_service
        print("✅ Servicio importado")
        
        # Test de conexión básica
        print("\n2. Probando conexión...")
        categorias = db_service.get_categorias()
        print(f"✅ {len(categorias)} categorías encontradas")
        
        # Test simple de productos
        print("\n3. Probando productos (método simple)...")
        session = db_service.get_session()
        from backend.database.models import Producto
        productos_count = session.query(Producto).count()
        print(f"✅ {productos_count} productos en base de datos")
        
        # Test simple de precios
        print("\n4. Probando precios (método simple)...")
        from backend.database.models import Precio
        precios_count = session.query(Precio).filter(Precio.activo == True).count()
        print(f"✅ {precios_count} precios activos en base de datos")
        
        print("\n🎉 TESTS BÁSICOS EXITOSOS!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            db_service.close_session()
            print("🔒 Sesión cerrada")
        except:
            pass

if __name__ == "__main__":
    main()
