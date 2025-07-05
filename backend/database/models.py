"""
Modelos SQLAlchemy para las tablas de CheSuper
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .connection import Base

class Producto(Base):
    """
    Modelo para la tabla productos
    """
    __tablename__ = "productos"
    
    id = Column(Integer, primary_key=True, index=True)
    ean = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(500), nullable=False, index=True)
    marca = Column(String(200))
    categoria = Column(String(100))
    completeness_score = Column(String(10))  # Mantengo como varchar según tu tabla
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    image_url = Column(String(1000))  # Campo opcional para futuro uso
    
    def __repr__(self):
        return f"<Producto(id={self.id}, ean='{self.ean}', nombre='{self.nombre[:50]}...')>"

class Supermercado(Base):
    """
    Modelo para la tabla supermercados
    """
    __tablename__ = "supermercados"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    activo = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Supermercado(id={self.id}, nombre='{self.nombre}', codigo='{self.codigo}')>"

class Precio(Base):
    """
    Modelo para la tabla precios
    """
    __tablename__ = "precios"
    
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(BigInteger, nullable=False, index=True)  # EAN directo, sin FK
    supermercado_id = Column(Integer, nullable=True, index=True)  # Permitir NULL, sin FK
    sucursal = Column(String(200))
    precio_lista = Column(Numeric(10, 2))
    precio_promo_a = Column(Numeric(10, 2))
    precio_promo_b = Column(Numeric(10, 2))
    fecha_actualizacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    activo = Column(Boolean, default=True)
    bandera = Column(String(100))  # Campo bandera agregado
    super_razon_social = Column(String(200))  # Campo super_razon_social agregado
    
    def __repr__(self):
        return f"<Precio(id={self.id}, producto_id={self.producto_id}, precio_lista={self.precio_lista})>"
