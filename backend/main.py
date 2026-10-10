from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pyodbc
from statistics import median, stdev

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def conectar_bd():
    return pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=192.168.0.102;'
        'DATABASE=Cultivos;'
        'UID=python_user;'
        'PWD=CultivosSQL2026!;'
    )

class OfertaRequest(BaseModel):
    cliente: str
    producto: str
    dia: str
    descuento: int

@app.get("/clientes")
def get_clientes():
    try:
        conn = conectar_bd()
        cursor = conn.cursor()
        query = """
        SELECT DISTINCT c.clienteid, c.razsoc 
        FROM Cultivos.dbo.Cliente c
        WHERE c.tclienteid = 'YWV6L_75H0NKDGB'
        ORDER BY c.razsoc
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        clientes = [{"codigo": str(row[0]), "nombre": str(row[1])} for row in rows]
        return {"status": "ok", "clientes": clientes}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/productos")
def get_productos():
    try:
        conn = conectar_bd()
        cursor = conn.cursor()
        query = """
        SELECT DISTINCT p.productoid, p.descrip 
        FROM Cultivos.dbo.Producto p
        WHERE p.productoid IN ('000001','000002','000003','000004','000005','000006','000007','000008','000009','000010','000011','000012','000013','000014','000015','00017')
        ORDER BY p.descrip
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        productos = [{"codigo": str(row[0]), "nombre": str(row[1])} for row in rows]
        return {"status": "ok", "productos": productos}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/analizar")
def analizar_oferta(request: OfertaRequest):
    try:
        conn = conectar_bd()
        cursor = conn.cursor()
        
        # Mapear día en español a número (1=domingo, 2=lunes, etc.)
        dias_map = {
            "domingo": 1,
            "lunes": 2,
            "martes": 3,
            "miércoles": 4,
            "jueves": 5,
            "viernes": 6,
            "sábado": 7
        }
        
        dia_numero = dias_map.get(request.dia.lower(), 1)
        
        # Query para traer últimas 10 compras del día específico
        query = f"""
        SELECT TOP 10
            m.fechaop,
            DATENAME(WEEKDAY, m.fechaop) AS dia_semana,
            CAST(d.cdadfact AS DECIMAL(18,2)) AS cantidad,
            CAST(d.totalitem AS DECIMAL(18,2)) AS total,
            CAST(d.totalitem / NULLIF(d.cdadfact, 0) AS DECIMAL(18,2)) AS precio_unitario
        FROM Cultivos.dbo.MovVentas m
        INNER JOIN Cultivos.dbo.MovVentasDetalle d ON m.movvtasid = d.movvtasid
        INNER JOIN Cultivos.dbo.Cliente c ON m.clienteid = c.clienteid
        INNER JOIN Cultivos.dbo.Producto p ON d.productoid = p.productoid
        WHERE m.estado <> 128
          AND DATEPART(WEEKDAY, m.fechaop) = {dia_numero}
          AND c.clienteid = '{request.cliente}'
          AND p.productoid = '{request.producto}'
          AND m.fechaop >= DATEADD(MONTH, -6, CAST(GETDATE() AS DATE))
        ORDER BY m.fechaop DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {
                "status": "error",
                "message": "No hay datos disponibles para este cliente, producto y día"
            }
        
        # Procesar datos
        compras = []
        cantidades = []
        precios = []
        
        for row in rows:
            cantidad = float(row[2])
            precio = float(row[4]) if row[4] else 0
            
            compras.append({
                "fecha": row[0].strftime("%d/%m/%Y"),
                "dia_semana": row[1],
                "cantidad": round(cantidad, 2),
                "total": round(float(row[3]), 2),
                "precio_unitario": round(precio, 2)
            })
            
            cantidades.append(cantidad)
            precios.append(precio)
        
        # Estadísticas
        cantidad_min = min(cantidades)
        cantidad_max = max(cantidades)
        cantidad_promedio = sum(cantidades) / len(cantidades)
        cantidad_mediana = median(cantidades) if len(cantidades) > 1 else cantidad_promedio
        cantidad_desv_std = stdev(cantidades) if len(cantidades) > 1 else 0
        
        precio_promedio = sum(precios) / len(precios) if precios else 0
        precio_con_descuento = precio_promedio * (1 - request.descuento / 100)
        
        # Propuesta: mediana + 10%
        cantidad_recomendada = cantidad_mediana * 1.1
        
        return {
            "status": "ok",
            "data": {
                "cliente": request.cliente,
                "producto": request.producto,
                "dia": request.dia,
                "descuento_pct": request.descuento,
                "estadisticas": {
                    "cantidad_minima": round(cantidad_min, 2),
                    "cantidad_maxima": round(cantidad_max, 2),
                    "cantidad_promedio": round(cantidad_promedio, 2),
                    "cantidad_mediana": round(cantidad_mediana, 2),
                    "cantidad_desv_std": round(cantidad_desv_std, 2),
                    "cantidad_recomendada": round(cantidad_recomendada, 2)
                },
                "precios": {
                    "precio_promedio": round(precio_promedio, 2),
                    "precio_con_descuento": round(precio_con_descuento, 2),
                    "descuento_pct": f"{request.descuento}%"
                },
                "compras_analizadas": len(compras),
                "historial": compras
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)