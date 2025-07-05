#!/usr/bin/env python3
"""
Update database schema to allow NULL supermercado_id and use EAN directly as producto_id.
"""

def update_schema():
    """Update the database schema"""
    
    print("🔧 UPDATING DATABASE SCHEMA")
    print("=" * 50)
    
    try:
        from backend.database.connection import engine
        from sqlalchemy import text
        
        with engine.connect() as connection:
            # Start transaction
            trans = connection.begin()
            
            try:
                # Allow NULL in supermercado_id
                print("1. Allowing NULL in supermercado_id...")
                connection.execute(text("""
                    ALTER TABLE precios 
                    ALTER COLUMN supermercado_id DROP NOT NULL;
                """))
                
                # Remove foreign key constraint on producto_id if it exists
                print("2. Removing foreign key constraint on producto_id...")
                try:
                    connection.execute(text("""
                        ALTER TABLE precios 
                        DROP CONSTRAINT IF EXISTS precios_producto_id_fkey;
                    """))
                except Exception as e:
                    print(f"   Note: FK constraint may not exist: {e}")
                
                # Commit changes
                trans.commit()
                print("✅ Schema updated successfully!")
                
                # Verify changes
                print("\n3. Verifying schema changes...")
                result = connection.execute(text("""
                    SELECT column_name, is_nullable, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'precios' 
                    AND column_name IN ('producto_id', 'supermercado_id')
                    ORDER BY column_name;
                """))
                
                for row in result:
                    print(f"   {row.column_name}: {row.data_type}, nullable={row.is_nullable}")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error updating schema: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def main():
    print("DATABASE SCHEMA UPDATE")
    print("=" * 60)
    
    if update_schema():
        print("\n✅ SUCCESS! Database schema updated.")
        print("Now you can run: python test_ean_direct.py")
        return 0
    else:
        print("\n❌ FAILED! Schema update failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
