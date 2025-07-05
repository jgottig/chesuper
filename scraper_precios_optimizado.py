import requests
import pandas as pd
import time
import os
from datetime import datetime
from typing import Dict, List, Any
import logging

# Import database components
from config import get_config
from price_manager import PriceManager
from utils import setup_logging, format_number

# --- Configuración ---
PRODUCTOS_FILE = "base_de_productos_rosario.xlsx"
PRECIOS_FILE = "precios_obtenidos_rosario.xlsx"
PRODUCTO_API_URL = "https://d3e6htiiul5ek9.cloudfront.net/prod/producto"

# --- STRING DE SUCURSALES (MANTENER TODAS PARA MÁXIMA COBERTURA) ---
ARRAY_SUCURSALES_ROSARIO = "2002-1-38,22-1-31,22-1-3,2002-1-67,22-1-17,22-1-20,12-1-97,22-1-18,12-1-99,22-1-6,23-1-6260,22-1-16,22-1-24,22-1-1,10-1-268,10-1-33,23-1-6262,10-1-32,2002-1-101,12-1-95,12-1-165,23-1-6256,22-1-26,2002-1-166,2002-1-6,9-3-5218,10-1-41,16-1-1202,23-1-6264,22-1-5"

# --- Configuración optimizada ---
SLEEP_TIME = 1.0
BATCH_SAVE_SIZE = 50  # Guardar más frecuentemente
MAX_RETRIES = 3
TIMEOUT = 15

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
    'Connection': 'keep-alive'
}

# --- Configuración de logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_precios.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurar el handler de consola para evitar errores de Unicode en Windows
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Remover handlers existentes y agregar el configurado
logger.handlers.clear()
logger.addHandler(logging.FileHandler('scraper_precios.log', encoding='utf-8'))
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

class OptimizedPriceScraper:
    """
    Scraper optimizado de precios que mantiene máxima cobertura de productos
    pero optimiza el almacenamiento deduplicando por bandera/supermercado.
    Ahora guarda directamente en Supabase.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
        # Initialize database components
        self.config = get_config()
        self.logger = setup_logging({'level': 'INFO'})
        self.price_manager = PriceManager(self.config, self.logger)
        
        self.stats = {
            'productos_procesados': 0,
            'productos_con_precios': 0,
            'total_precios_encontrados': 0,
            'errores': 0,
            'banderas_unicas': set(),
            'inicio': datetime.now()
        }
        
        # Test database connection (no need to load caches since we use EAN directly)
        if not self.price_manager.test_database_connection():
            raise Exception("Cannot connect to database")
        
        self.logger.info("✅ Database connection established - ready to insert prices")
    
    def procesar_respuesta_optimizada(self, data: Dict[str, Any], ean: str) -> List[Dict[str, Any]]:
        """
        Procesa la respuesta de la API manteniendo solo 1 precio por supermercado,
        pero asegurando máxima cobertura de productos.
        
        Args:
            data: Respuesta de la API
            ean: EAN del producto
            
        Returns:
            Lista de precios optimizada (1 por bandera/supermercado)
        """
        precios_por_bandera = {}
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if 'sucursales' not in data or not data['sucursales']:
            return []
        
        for sucursal in data['sucursales']:
            if 'preciosProducto' not in sucursal:
                continue
                
            bandera = sucursal.get('banderaDescripcion', '').strip()
            if not bandera:
                continue
            
            # Si ya tengo precio para esta bandera, skip (optimización clave)
            if bandera in precios_por_bandera:
                continue
                
            precios = sucursal['preciosProducto']
            precio_lista = precios.get('precioLista')
            
            # Solo procesar si tiene precio lista válido
            if not precio_lista or precio_lista <= 0:
                continue
            
            # Extraer precio promo A si existe
            precio_promo_a = None
            if 'promo1' in precios and precios['promo1']:
                precio_promo_a = precios['promo1'].get('precio')
                if precio_promo_a and precio_promo_a <= 0:
                    precio_promo_a = None
            
            # Crear registro optimizado
            precio_info = {
                'ean': str(ean),
                'fecha_actualizacion': fecha_actual,
                'bandera': bandera,
                'sucursal': f"{bandera} - {sucursal.get('sucursalNombre', 'N/A')}",
                'precio_lista': float(precio_lista),
                'precio_promo_a': float(precio_promo_a) if precio_promo_a else None,
                'supermercado': sucursal.get('comercioRazonSocial', bandera)
            }
            
            precios_por_bandera[bandera] = precio_info
            self.stats['banderas_unicas'].add(bandera)
        
        return list(precios_por_bandera.values())
    
    def obtener_precios_producto(self, ean: str) -> List[Dict[str, Any]]:
        """
        Obtiene precios para un producto específico con reintentos y manejo de errores.
        
        Args:
            ean: EAN del producto
            
        Returns:
            Lista de precios del producto
        """
        params = {
            'id_producto': ean,
            'array_sucursales': ARRAY_SUCURSALES_ROSARIO
        }
        
        for intento in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    PRODUCTO_API_URL, 
                    params=params, 
                    timeout=TIMEOUT
                )
                response.raise_for_status()
                data = response.json()
                
                return self.procesar_respuesta_optimizada(data, ean)
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Intento {intento + 1}/{MAX_RETRIES} falló para EAN {ean}: {e}")
                if intento < MAX_RETRIES - 1:
                    time.sleep(2 ** intento)  # Backoff exponencial
                else:
                    logger.error(f"Error final para EAN {ean}: {e}")
                    self.stats['errores'] += 1
                    return []
            
            except Exception as e:
                logger.error(f"Error inesperado para EAN {ean}: {e}")
                self.stats['errores'] += 1
                return []
        
        return []
    
    def cargar_productos_desde_bd(self) -> List[str]:
        """
        Carga la lista de EANs desde la base de datos.
        
        Returns:
            Lista de EANs desde la tabla productos
        """
        try:
            from backend.database.models import Producto
            
            with self.price_manager.get_session() as session:
                productos = session.query(Producto.ean).all()
                eans = [str(producto.ean) for producto in productos]
                
            print(f"📦 Cargados {len(eans)} productos desde la base de datos")
            return eans
            
        except Exception as e:
            print(f"❌ Error cargando productos desde BD: {e}")
            print(f"🔄 Fallback: intentando cargar desde Excel...")
            return self.cargar_productos_desde_excel()
    
    def cargar_productos_desde_excel(self) -> List[str]:
        """
        Carga la lista de EANs desde el archivo Excel (fallback).
        
        Returns:
            Lista de EANs desde el Excel
        """
        try:
            df_productos = pd.read_excel(PRODUCTOS_FILE)
            eans = df_productos['ean'].astype(str).tolist()
            print(f"📄 Cargados {len(eans)} productos desde Excel (fallback)")
            return eans
        except Exception as e:
            print(f"❌ Error cargando productos desde Excel: {e}")
            return []
    
    def cargar_datos_existentes(self) -> tuple[int, set]:
        """
        Carga información de precios existentes desde la base de datos.
        
        Returns:
            Tupla con (total_precios_existentes, set_eans_con_precios)
        """
        try:
            # Get current price count from database
            total_precios = self.price_manager.get_price_count()
            print(f"💾 Base de datos contiene {format_number(total_precios)} precios existentes")
            
            # For now, return empty set of processed EANs to allow reprocessing
            # This maintains the current logic of updating existing prices
            return total_precios, set()
            
        except Exception as e:
            print(f"❌ Error cargando datos existentes desde base de datos: {e}")
            return 0, set()
    
    def guardar_precios_en_bd(self, lista_precios: List[Dict]):
        """
        Guarda los precios en la base de datos Supabase.
        
        Args:
            lista_precios: Lista de precios a guardar
        """
        if not lista_precios:
            return
        
        try:
            # Save prices to database using batch operation
            inserted, updated, skipped = self.price_manager.batch_save_prices(lista_precios)
            
            self.logger.info(f"Precios guardados en BD: {inserted} insertados, {updated} actualizados, {skipped} omitidos")
            
            # Also save to Excel for backup (optional)
            self.guardar_progreso_excel(lista_precios)
            
        except Exception as e:
            self.logger.error(f"Error guardando precios en base de datos: {e}")
    
    def guardar_progreso_excel(self, lista_precios: List[Dict]):
        """
        Guarda el progreso actual en el archivo Excel (backup).
        
        Args:
            lista_precios: Lista completa de precios a guardar
        """
        if not lista_precios:
            return
        
        try:
            df = pd.DataFrame(lista_precios)
            
            # Eliminar duplicados completos
            df.drop_duplicates(inplace=True)
            
            # Ordenar por EAN y bandera para mejor organización
            df.sort_values(['ean', 'bandera'], inplace=True)
            
            # Guardar en Excel como backup
            df.to_excel(PRECIOS_FILE, index=False, engine='openpyxl')
            self.logger.debug(f"Backup Excel guardado: {len(df)} registros en {PRECIOS_FILE}")
            
        except Exception as e:
            self.logger.error(f"Error guardando backup Excel: {e}")
    
    def mostrar_estadisticas(self):
        """
        Muestra estadísticas del proceso de scraping.
        """
        tiempo_transcurrido = datetime.now() - self.stats['inicio']
        
        logger.info("=" * 60)
        logger.info("ESTADÍSTICAS DEL SCRAPING OPTIMIZADO")
        logger.info("=" * 60)
        logger.info(f"Tiempo transcurrido: {tiempo_transcurrido}")
        logger.info(f"Productos procesados: {self.stats['productos_procesados']}")
        logger.info(f"Productos con precios: {self.stats['productos_con_precios']}")
        logger.info(f"Total precios encontrados: {self.stats['total_precios_encontrados']}")
        logger.info(f"Errores: {self.stats['errores']}")
        logger.info(f"Banderas únicas encontradas: {len(self.stats['banderas_unicas'])}")
        
        if self.stats['banderas_unicas']:
            logger.info("Supermercados encontrados:")
            for bandera in sorted(self.stats['banderas_unicas']):
                logger.info(f"  - {bandera}")
        
        if self.stats['productos_procesados'] > 0:
            tasa_exito = (self.stats['productos_con_precios'] / self.stats['productos_procesados']) * 100
            logger.info(f"Tasa de éxito: {tasa_exito:.1f}%")
            
            if tiempo_transcurrido.total_seconds() > 0:
                productos_por_hora = (self.stats['productos_procesados'] / tiempo_transcurrido.total_seconds()) * 3600
                logger.info(f"Velocidad: {productos_por_hora:.1f} productos/hora")
        
        logger.info("=" * 60)
    
    def ejecutar_scraping_completo(self, limite_productos: int = None, forzar_actualizacion: bool = False):
        """
        Ejecuta el scraping completo de precios con todas las optimizaciones.
        
        Args:
            limite_productos: Límite de productos a procesar (None = todos)
            forzar_actualizacion: Si True, reprocesa productos ya existentes
        """
        print("🚀 Iniciando scraping optimizado de precios...")
        
        # Cargar lista de productos desde la base de datos
        eans_a_procesar = self.cargar_productos_desde_bd()
        
        if not eans_a_procesar:
            print("❌ No se pudieron cargar productos")
            return
        
        # Aplicar límite si se especifica
        if limite_productos:
            eans_a_procesar = eans_a_procesar[:limite_productos]
            logger.info(f"Limitando a {limite_productos} productos")
        
        # Cargar datos existentes desde base de datos
        total_precios_existentes, eans_procesados = self.cargar_datos_existentes()
        
        # Para mantener la lógica actual, procesamos todos los productos
        # La base de datos se encarga de actualizar precios existentes
        eans_pendientes = eans_a_procesar
        logger.info(f"Procesando {len(eans_pendientes)} productos (actualizando precios existentes)")
        
        if not eans_pendientes:
            logger.info("No hay productos para procesar.")
            self.mostrar_estadisticas()
            return
        
        # Procesar productos
        productos_procesados_en_sesion = 0
        precios_batch = []  # Batch para guardar en BD
        
        try:
            for i, ean in enumerate(eans_pendientes):
                print(f"\n📦 Procesando {i+1}/{len(eans_pendientes)}: EAN {ean}")
                
                precios_producto = self.obtener_precios_producto(ean)
                
                self.stats['productos_procesados'] += 1
                productos_procesados_en_sesion += 1
                
                if precios_producto:
                    precios_batch.extend(precios_producto)
                    self.stats['productos_con_precios'] += 1
                    self.stats['total_precios_encontrados'] += len(precios_producto)
                    
                    # Mostrar supermercados encontrados
                    supermercados = [p['bandera'] for p in precios_producto]
                    print(f"   ✅ {len(precios_producto)} precios guardados ({', '.join(supermercados)})")
                    
                    # Guardar inmediatamente en base de datos
                    self.guardar_precios_en_bd(precios_producto)
                else:
                    print(f"   ❌ Sin precios disponibles")
                
                # Mostrar progreso cada 10 productos
                if productos_procesados_en_sesion % 10 == 0:
                    db_stats = self.price_manager.get_operation_stats()
                    print(f"\n📊 Progreso: {productos_procesados_en_sesion}/{len(eans_pendientes)} productos | {db_stats['precios_insertados']} precios guardados")
                
                # Pausa entre requests
                time.sleep(SLEEP_TIME)
        
        except KeyboardInterrupt:
            logger.info("Proceso interrumpido por el usuario. Los precios ya procesados están guardados en BD.")
        
        except Exception as e:
            logger.error(f"Error durante el scraping: {e}")
        
        finally:
            # Mostrar estadísticas finales
            self.mostrar_estadisticas()
            
            # Mostrar estadísticas de base de datos
            db_stats = self.price_manager.get_operation_stats()
            logger.info("ESTADÍSTICAS DE BASE DE DATOS:")
            logger.info(f"  - Precios insertados: {db_stats['precios_insertados']}")
            logger.info(f"  - Precios actualizados: {db_stats['precios_actualizados']}")
            logger.info(f"  - Precios omitidos: {db_stats['precios_omitidos']}")
            logger.info(f"  - Productos no encontrados: {db_stats['productos_no_encontrados']}")
            logger.info(f"  - Supermercados no encontrados: {db_stats['supermercados_no_encontrados']}")
            
            logger.info("Scraping completado - Datos guardados en Supabase.")


def main():
    """
    Función principal para ejecutar el scraper optimizado.
    """
    scraper = OptimizedPriceScraper()
    
    # Opciones de ejecución
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Modo test: solo 10 productos
            scraper.ejecutar_scraping_completo(limite_productos=10)
        elif sys.argv[1] == "--force":
            # Forzar actualización completa
            scraper.ejecutar_scraping_completo(forzar_actualizacion=True)
        elif sys.argv[1].startswith("--limit="):
            # Límite personalizado
            limite = int(sys.argv[1].split("=")[1])
            scraper.ejecutar_scraping_completo(limite_productos=limite)
        else:
            print("Opciones disponibles:")
            print("  --test          : Procesar solo 10 productos (modo prueba)")
            print("  --force         : Forzar actualización completa")
            print("  --limit=N       : Procesar solo N productos")
            print("  (sin parámetros): Procesar productos pendientes")
    else:
        # Ejecución normal: solo productos pendientes
        scraper.ejecutar_scraping_completo()


if __name__ == "__main__":
    main()
