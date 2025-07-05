"""
Configuración de conexión a la base de datos PostgreSQL (Supabase)
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Intentar con DATABASE_URL primero, si no funciona usar credenciales individuales
if DATABASE_URL:
    connection_string = DATABASE_URL
else:
    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        raise ValueError("Faltan credenciales de base de datos en las variables de entorno")
    connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"🔗 Intentando conectar a: {DB_HOST if DB_HOST else 'URL completa'}")

# Crear engine de SQLAlchemy con configuración optimizada para producción
engine = create_engine(
    connection_string,
    pool_pre_ping=True,      # Verificar conexiones antes de usarlas
    pool_recycle=300,        # Reciclar conexiones cada 5 minutos
    pool_size=5,             # Número de conexiones en el pool
    max_overflow=10,         # Conexiones adicionales permitidas
    pool_timeout=30,         # Timeout para obtener conexión del pool
    connect_args={
        "connect_timeout": 10,    # Timeout de conexión inicial
        "application_name": "che-super-api"  # Identificar la aplicación
    },
    echo=False               # Cambiar a True para debug SQL
)

# Crear sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos
Base = declarative_base()

def get_db():
    """
    Generador de sesiones de base de datos para FastAPI
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_connection():
    """
    Función para probar la conexión a la base de datos
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ Conexión a la base de datos exitosa")
            return True
    except Exception as e:
        print(f"❌ Error de conexión a la base de datos: {e}")
        return False

if __name__ == "__main__":
    test_connection()
