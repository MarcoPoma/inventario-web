import sqlite3
from datetime import datetime, timedelta
import os
import io

DB_PATH = os.path.join(os.path.dirname(__file__), "inventario.db")

TIPOS_MOVIMIENTO = ["INGRESO", "SALIDA", "AJUSTE_POSITIVO", "AJUSTE_NEGATIVO", "AJUSTE"]

UNIDADES_DEFAULT = [
    "Cajas", "Centímetros", "Docenas", "Gramos", "Kilogramos",
    "Litros", "Metros", "Metros Cuadrados", "Metros Cúbicos",
    "Mililitros", "Paquetes", "Piezas", "Por Medida", "Por Tallas", "Por Unidad",
    "Toneladas", "Unidades"
]

GRUPOS_DEFAULT = [
    "Consumibles", "Empaques", "Equipos", "General", "Herramientas",
    "Materia Prima", "Producto en Proceso", "Producto Terminado",
    "Químicos", "Repuestos", "Suministros"
]

CATEGORIAS = [
    {"id": "EPPS",        "nombre": "EPPs",                 "icono": "🦺", "color": "#e74c3c"},
    {"id": "DORMITORIO",  "nombre": "Dormitorio",            "icono": "🛏️", "color": "#8e44ad"},
    {"id": "LIMPIEZA",    "nombre": "Útiles de Limpieza",    "icono": "🧹", "color": "#27ae60"},
    {"id": "ESCRITORIO",  "nombre": "Útiles de Escritorio",  "icono": "✏️", "color": "#2980b9"},
    {"id": "INFORMATICO", "nombre": "Equipos Informáticos",  "icono": "💻", "color": "#16a085"},
    {"id": "SEGURIDAD",   "nombre": "Seguridad",             "icono": "🔒", "color": "#d35400"},
]

CATEGORIAS_IDS = [c["id"] for c in CATEGORIAS]

def conectar():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operador',
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            unidad TEXT DEFAULT 'Unidades',
            grupo TEXT DEFAULT 'General',
            categoria TEXT DEFAULT 'GENERAL',
            tiene_variantes INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 0,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS variantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_producto TEXT NOT NULL,
            nombre_variante TEXT NOT NULL,
            stock_minimo INTEGER DEFAULT 0,
            FOREIGN KEY (codigo_producto) REFERENCES productos(codigo),
            UNIQUE(codigo_producto, nombre_variante)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            variante TEXT DEFAULT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            costo_unitario REAL DEFAULT 0,
            costo_total REAL DEFAULT 0,
            destinatario TEXT DEFAULT '',
            usuario TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            observaciones TEXT DEFAULT '',
            stock_resultante REAL DEFAULT 0,
            FOREIGN KEY (codigo) REFERENCES productos(codigo)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grupos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    """)

    # Migraciones para bases de datos existentes
    migraciones = [
        "ALTER TABLE productos ADD COLUMN categoria TEXT DEFAULT 'GENERAL'",
        "ALTER TABLE productos ADD COLUMN tiene_variantes INTEGER DEFAULT 0",
        "ALTER TABLE movimientos ADD COLUMN variante TEXT DEFAULT NULL",
        "ALTER TABLE movimientos ADD COLUMN costo_unitario REAL DEFAULT 0",
        "ALTER TABLE movimientos ADD COLUMN costo_total REAL DEFAULT 0",
        "ALTER TABLE movimientos ADD COLUMN destinatario TEXT DEFAULT ''",
    ]
    for sql in migraciones:
        try:
            cursor.execute(sql)
        except:
            pass

    from werkzeug.security import generate_password_hash
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)",
                       ("admin", generate_password_hash("admin123"), "Administrador", "admin"))
        cursor.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)",
                       ("operador", generate_password_hash("oper123"), "Operador General", "operador"))
        cursor.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)",
                       ("visitante", generate_password_hash("visit123"), "Visitante", "readonly"))

    cursor.execute("SELECT COUNT(*) FROM unidades")
    if cursor.fetchone()[0] == 0:
        for u in UNIDADES_DEFAULT:
            cursor.execute("INSERT OR IGNORE INTO unidades (nombre) VALUES (?)", (u,))

    cursor.execute("SELECT COUNT(*) FROM grupos")
    if cursor.fetchone()[0] == 0:
        for g in GRUPOS_DEFAULT:
            cursor.execute("INSERT OR IGNORE INTO grupos (nombre) VALUES (?)", (g,))

    conn.commit()
    conn.close()

# ── USUARIOS ──────────────────────────────────────────────────────────────────

def obtener_usuario(username):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username=? AND activo=1", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def obtener_todos_usuarios():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nombre, rol, activo, fecha_creacion FROM usuarios ORDER BY nombre")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def crear_usuario(username, password, nombre, rol):
    from werkzeug.security import generate_password_hash
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)",
                       (username.strip(), generate_password_hash(password), nombre.strip(), rol))
        conn.commit()
        conn.close()
        return True, "Usuario creado correctamente."
    except sqlite3.IntegrityError:
        return False, "Ya existe un usuario con ese nombre."
    except Exception as e:
        return False, f"Error: {str(e)}"

def editar_usuario(user_id, nombre, rol, nueva_password=None):
    from werkzeug.security import generate_password_hash
    try:
        conn = conectar()
        cursor = conn.cursor()
        if nueva_password:
            cursor.execute("UPDATE usuarios SET nombre=?, rol=?, password=? WHERE id=?",
                           (nombre.strip(), rol, generate_password_hash(nueva_password), user_id))
        else:
            cursor.execute("UPDATE usuarios SET nombre=?, rol=? WHERE id=?",
                           (nombre.strip(), rol, user_id))
        conn.commit()
        conn.close()
        return True, "Usuario actualizado correctamente."
    except Exception as e:
        return False, f"Error: {str(e)}"

def eliminar_usuario(user_id):
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET activo=0 WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        return True, "Usuario eliminado correctamente."
    except Exception as e:
        return False, f"Error: {str(e)}"

# ── PRODUCTOS ─────────────────────────────────────────────────────────────────

def registrar_producto(codigo, nombre, unidad, grupo, stock_minimo, categoria="GENERAL", tiene_variantes=0, variantes=[]):
    try:
        conn = conectar()
        cursor = conn.cursor()
        codigo = codigo.strip().upper()
        nombre = nombre.strip()
        if len(nombre) < 2:
            return False, "El nombre debe tener al menos 2 caracteres."
        cursor.execute("""
            INSERT INTO productos (codigo, nombre, unidad, grupo, categoria, tiene_variantes, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, unidad or "Unidades", grupo or "General",
              categoria.upper() if categoria else "GENERAL",
              1 if tiene_variantes else 0,
              max(0, int(stock_minimo or 0))))

        # Insertar variantes si aplica
        if tiene_variantes and variantes:
            for v in variantes:
                v_nombre = str(v.get("nombre", "")).strip()
                v_stock_min = int(v.get("stockMin", 0) or 0)
                if v_nombre:
                    cursor.execute("""
                        INSERT OR IGNORE INTO variantes (codigo_producto, nombre_variante, stock_minimo)
                        VALUES (?, ?, ?)
                    """, (codigo, v_nombre, v_stock_min))

        conn.commit()
        conn.close()
        return True, "Producto registrado correctamente."
    except sqlite3.IntegrityError:
        return False, "Ya existe un producto con este código."
    except Exception as e:
        return False, f"Error: {str(e)}"

def editar_producto(codigo, nombre, unidad, grupo, stock_minimo, categoria="GENERAL", tiene_variantes=0, variantes=[]):
    try:
        conn = conectar()
        cursor = conn.cursor()
        codigo = codigo.strip().upper()
        cursor.execute("""
            UPDATE productos SET nombre=?, unidad=?, grupo=?, categoria=?, tiene_variantes=?, stock_minimo=?
            WHERE codigo=?
        """, (nombre.strip(), unidad or "Unidades", grupo or "General",
              categoria.upper() if categoria else "GENERAL",
              1 if tiene_variantes else 0,
              max(0, int(stock_minimo or 0)), codigo))

        if tiene_variantes and variantes:
            cursor.execute("DELETE FROM variantes WHERE codigo_producto=?", (codigo,))
            for v in variantes:
                v_nombre = str(v.get("nombre", "")).strip()
                v_stock_min = int(v.get("stockMin", 0) or 0)
                if v_nombre:
                    cursor.execute("""
                        INSERT OR IGNORE INTO variantes (codigo_producto, nombre_variante, stock_minimo)
                        VALUES (?, ?, ?)
                    """, (codigo, v_nombre, v_stock_min))

        conn.commit()
        conn.close()
        return True, "Producto actualizado correctamente."
    except Exception as e:
        return False, f"Error: {str(e)}"

def eliminar_producto(codigo):
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM variantes WHERE codigo_producto=?", (codigo.strip().upper(),))
        cursor.execute("DELETE FROM productos WHERE codigo=?", (codigo.strip().upper(),))
        if cursor.rowcount == 0:
            return False, "Producto no encontrado."
        conn.commit()
        conn.close()
        return True, "Producto eliminado correctamente."
    except Exception as e:
        return False, f"Error: {str(e)}"

def obtener_variantes(codigo, cursor=None):
    close_after = False
    if cursor is None:
        conn = conectar()
        cursor = conn.cursor()
        close_after = True
    cursor.execute("SELECT nombre_variante, stock_minimo FROM variantes WHERE codigo_producto=? ORDER BY nombre_variante", (codigo.upper(),))
    rows = cursor.fetchall()
    if close_after:
        conn.close()
    return [{"nombre": r["nombre_variante"], "stockMin": r["stock_minimo"]} for r in rows]

def calcular_stock(codigo, variante=None, cursor=None):
    close_after = False
    if cursor is None:
        conn = conectar()
        cursor = conn.cursor()
        close_after = True

    if variante:
        cursor.execute("SELECT tipo, cantidad FROM movimientos WHERE codigo=? AND variante=?",
                       (codigo.strip().upper(), variante))
    else:
        cursor.execute("SELECT tipo, cantidad FROM movimientos WHERE codigo=? AND (variante IS NULL OR variante='')",
                       (codigo.strip().upper(),))

    movs = cursor.fetchall()
    total = 0.0
    for m in movs:
        tipo = m["tipo"].upper()
        cant = float(m["cantidad"] or 0)
        if tipo in ("INGRESO", "AJUSTE_POSITIVO", "AJUSTE"):
            total += cant
        elif tipo in ("SALIDA", "AJUSTE_NEGATIVO"):
            total -= cant

    if close_after:
        conn.close()
    return max(0, round(total, 2))

def calcular_stock_total_producto(codigo, cursor=None):
    """Suma stock de todas las variantes o stock directo si no tiene variantes"""
    close_after = False
    if cursor is None:
        conn = conectar()
        cursor = conn.cursor()
        close_after = True

    cursor.execute("SELECT tiene_variantes FROM productos WHERE codigo=?", (codigo.upper(),))
    prod = cursor.fetchone()
    if not prod:
        if close_after: conn.close()
        return 0

    if prod["tiene_variantes"]:
        cursor.execute("SELECT nombre_variante FROM variantes WHERE codigo_producto=?", (codigo.upper(),))
        variantes = cursor.fetchall()
        total = sum(calcular_stock(codigo, v["nombre_variante"], cursor) for v in variantes)
    else:
        total = calcular_stock(codigo, None, cursor)

    if close_after:
        conn.close()
    return total

def obtener_stock(categoria=None):
    conn = conectar()
    cursor = conn.cursor()
    if categoria and categoria != "TODOS":
        cursor.execute("SELECT * FROM productos WHERE categoria=? ORDER BY nombre", (categoria.upper(),))
    else:
        cursor.execute("SELECT * FROM productos ORDER BY nombre")
    productos = cursor.fetchall()
    resultado = []
    for p in productos:
        stock = calcular_stock_total_producto(p["codigo"], cursor)
        variantes = obtener_variantes(p["codigo"], cursor) if p["tiene_variantes"] else []

        # Stock por variante
        variantes_con_stock = []
        for v in variantes:
            v_stock = calcular_stock(p["codigo"], v["nombre"], cursor)
            variantes_con_stock.append({
                "nombre": v["nombre"],
                "stockMin": v["stockMin"],
                "cantidad": v_stock
            })

        # Costo promedio y valor invertido (solo ingresos, nunca resta)
        costo = obtener_costo_promedio(p["codigo"], cursor)
        valor_invertido = obtener_valor_invertido(p["codigo"], cursor)

        resultado.append({
            "codigo": p["codigo"],
            "nombre": p["nombre"],
            "unidad": p["unidad"],
            "grupo": p["grupo"],
            "categoria": p["categoria"] if p["categoria"] else "GENERAL",
            "tieneVariantes": bool(p["tiene_variantes"]),
            "variantes": variantes_con_stock,
            "stockMin": p["stock_minimo"],
            "cantidad": stock,
            "costoPromedio": costo,
            "valorTotal": valor_invertido
        })
    conn.close()
    return resultado

def obtener_costo_promedio(codigo, cursor=None):
    """Calcula el costo promedio ponderado de los ingresos"""
    close_after = False
    if cursor is None:
        conn = conectar()
        cursor = conn.cursor()
        close_after = True
    cursor.execute("""
        SELECT SUM(cantidad * costo_unitario) as total_valor, SUM(cantidad) as total_cant
        FROM movimientos
        WHERE codigo=? AND tipo='INGRESO' AND costo_unitario > 0
    """, (codigo.upper(),))
    row = cursor.fetchone()
    if close_after:
        conn.close()
    if row and row["total_cant"] and row["total_cant"] > 0:
        return round(row["total_valor"] / row["total_cant"], 2)
    return 0.0

def obtener_stock_por_categoria():
    conn = conectar()
    cursor = conn.cursor()
    resultado = {}
    for cat in CATEGORIAS:
        cursor.execute("SELECT codigo, stock_minimo FROM productos WHERE categoria=?", (cat["id"],))
        prods = cursor.fetchall()
        total = len(prods)
        sin_stock = 0
        stock_bajo = 0
        valor_cat = 0.0
        for p in prods:
            stock = calcular_stock_total_producto(p["codigo"], cursor)
            valor_cat += obtener_valor_invertido(p["codigo"], cursor)
            if stock <= 0:
                sin_stock += 1
            elif p["stock_minimo"] > 0 and stock <= p["stock_minimo"]:
                stock_bajo += 1
        resultado[cat["id"]] = {
            "total": total,
            "sinStock": sin_stock,
            "stockBajo": stock_bajo,
            "valorTotal": round(valor_cat, 2)
        }
    conn.close()
    return resultado

def buscar_producto_por_codigo(texto):
    conn = conectar()
    cursor = conn.cursor()
    # Busca por codigo (starts with) O por nombre (contains)
    like_codigo = f"{texto.upper()}%"
    like_nombre = f"%{texto.lower()}%"
    cursor.execute("""
        SELECT codigo, nombre, unidad, grupo, categoria, tiene_variantes
        FROM productos
        WHERE codigo LIKE ? OR LOWER(nombre) LIKE ? OR LOWER(codigo) LIKE ?
        ORDER BY codigo LIMIT 10
    """, (like_codigo, like_nombre, f"%{texto.lower()}%"))
    rows = cursor.fetchall()
    resultado = []
    for r in rows:
        variantes = obtener_variantes(r["codigo"], cursor) if r["tiene_variantes"] else []
        resultado.append({
            "codigo": r["codigo"],
            "nombre": r["nombre"],
            "unidad": r["unidad"],
            "grupo": r["grupo"],
            "tieneVariantes": bool(r["tiene_variantes"]),
            "variantes": [v["nombre"] for v in variantes]
        })
    conn.close()
    return resultado

def buscar_producto(texto):
    conn = conectar()
    cursor = conn.cursor()
    like = f"%{texto.lower()}%"
    cursor.execute("""
        SELECT * FROM productos
        WHERE LOWER(codigo) LIKE ? OR LOWER(nombre) LIKE ? OR LOWER(grupo) LIKE ? OR LOWER(categoria) LIKE ?
        ORDER BY nombre
    """, (like, like, like, like))
    productos = cursor.fetchall()
    resultado = []
    for p in productos:
        stock = calcular_stock_total_producto(p["codigo"], cursor)
        resultado.append([p["codigo"], p["nombre"], p["unidad"], p["grupo"], p["stock_minimo"], stock, p["categoria"]])
    conn.close()
    return resultado

def obtener_detalle_producto(codigo):
    conn = conectar()
    cursor = conn.cursor()
    codigo = codigo.strip().upper()
    cursor.execute("SELECT * FROM productos WHERE codigo=?", (codigo,))
    p = cursor.fetchone()
    if not p:
        conn.close()
        return None

    stock_actual = calcular_stock_total_producto(codigo, cursor)
    variantes = obtener_variantes(codigo, cursor) if p["tiene_variantes"] else []
    variantes_con_stock = []
    for v in variantes:
        v_stock = calcular_stock(codigo, v["nombre"], cursor)
        variantes_con_stock.append({"nombre": v["nombre"], "stockMin": v["stockMin"], "cantidad": v_stock})

    costo = obtener_costo_promedio(codigo, cursor)
    valor_invertido = obtener_valor_invertido(codigo, cursor)

    cursor.execute("""
        SELECT fecha, tipo, variante, cantidad, costo_unitario, costo_total,
               destinatario, usuario, observaciones, stock_resultante
        FROM movimientos WHERE codigo=? ORDER BY timestamp DESC
    """, (codigo,))
    movs = cursor.fetchall()
    historial = [{
        "fecha": m["fecha"],
        "tipo": m["tipo"],
        "variante": m["variante"] or "",
        "cantidad": m["cantidad"],
        "costoUnitario": m["costo_unitario"] or 0,
        "costoTotal": m["costo_total"] or 0,
        "destinatario": m["destinatario"] or "",
        "usuario": m["usuario"],
        "observaciones": m["observaciones"] or "",
        "stockResultante": m["stock_resultante"]
    } for m in movs]

    conn.close()
    return {
        "codigo": p["codigo"], "nombre": p["nombre"], "unidad": p["unidad"],
        "grupo": p["grupo"], "categoria": p["categoria"] if p["categoria"] else "GENERAL",
        "tieneVariantes": bool(p["tiene_variantes"]),
        "variantes": variantes_con_stock,
        "stockMin": p["stock_minimo"],
        "fechaCreacion": p["fecha_creacion"],
        "stockActual": stock_actual,
        "costoPromedio": costo,
        "valorTotal": valor_invertido,
        "historial": historial,
        "totalMovimientos": len(historial)
    }

# ── MOVIMIENTOS ───────────────────────────────────────────────────────────────

def registrar_movimiento(codigo, fecha, tipo, cantidad, usuario, observaciones="",
                          variante=None, costo_unitario=0, destinatario=""):
    try:
        conn = conectar()
        cursor = conn.cursor()
        codigo = codigo.strip().upper()
        tipo = tipo.strip().upper()
        cantidad = float(cantidad)
        costo_unitario = float(costo_unitario or 0)
        costo_total = round(cantidad * costo_unitario, 2)

        if cantidad <= 0:
            return False, "La cantidad debe ser mayor a 0."
        if tipo not in TIPOS_MOVIMIENTO:
            return False, f"Tipo de movimiento inválido: {tipo}"

        cursor.execute("SELECT codigo, tiene_variantes FROM productos WHERE codigo=?", (codigo,))
        prod = cursor.fetchone()
        if not prod:
            return False, "El producto no existe. Regístrelo primero."

        # Validar variante si el producto la tiene
        if prod["tiene_variantes"]:
            if not variante:
                return False, "Este producto requiere especificar una variante (talla/número)."
            cursor.execute("SELECT id FROM variantes WHERE codigo_producto=? AND nombre_variante=?",
                           (codigo, variante))
            if not cursor.fetchone():
                return False, f"La variante '{variante}' no existe para este producto."

        stock_actual = calcular_stock(codigo, variante, cursor)

        if tipo in ("SALIDA", "AJUSTE_NEGATIVO") and stock_actual < cantidad:
            var_texto = f" (variante: {variante})" if variante else ""
            return False, f"Stock insuficiente{var_texto}. Disponible: {stock_actual}, Solicitado: {cantidad}"

        if tipo in ("INGRESO", "AJUSTE_POSITIVO", "AJUSTE"):
            stock_resultante = stock_actual + cantidad
        else:
            stock_resultante = stock_actual - cantidad

        stock_resultante = max(0, stock_resultante)

        cursor.execute("""
            INSERT INTO movimientos
            (codigo, variante, fecha, tipo, cantidad, costo_unitario, costo_total,
             destinatario, usuario, observaciones, stock_resultante)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (codigo, variante or None, fecha, tipo, cantidad, costo_unitario, costo_total,
              destinatario or "", usuario, observaciones or "", stock_resultante))

        conn.commit()
        conn.close()
        return True, "Movimiento registrado correctamente."
    except Exception as e:
        return False, f"Error: {str(e)}"

def obtener_historial(fecha_desde, fecha_hasta, tipo_filtro=""):
    conn = conectar()
    cursor = conn.cursor()
    query = """
        SELECT m.id, m.codigo, m.variante, m.fecha, m.tipo, m.cantidad,
               m.costo_unitario, m.costo_total, m.destinatario,
               m.usuario, m.observaciones, m.stock_resultante, p.nombre as producto
        FROM movimientos m
        LEFT JOIN productos p ON m.codigo = p.codigo
        WHERE m.fecha BETWEEN ? AND ?
    """
    params = [fecha_desde, fecha_hasta]
    if tipo_filtro:
        query += " AND m.tipo=?"
        params.append(tipo_filtro.upper())
    query += " ORDER BY m.timestamp DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r["id"],
        "codigo": r["codigo"],
        "variante": r["variante"] or "",
        "fecha": r["fecha"],
        "tipo": r["tipo"],
        "cantidad": r["cantidad"],
        "costoUnitario": r["costo_unitario"] or 0,
        "costoTotal": r["costo_total"] or 0,
        "destinatario": r["destinatario"] or "",
        "usuario": r["usuario"],
        "observaciones": r["observaciones"] or "",
        "stockResultante": r["stock_resultante"],
        "producto": r["producto"] or "Producto no encontrado"
    } for r in rows]

# ── DASHBOARD ─────────────────────────────────────────────────────────────────

def obtener_resumen():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM productos")
    total_productos = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as total FROM movimientos")
    total_movimientos = cursor.fetchone()["total"]

    # Valor total invertido = suma de todos los costos de ingresos
    cursor.execute("""
        SELECT COALESCE(SUM(costo_total), 0) as valor
        FROM movimientos WHERE tipo='INGRESO' AND costo_unitario > 0
    """)
    valor_total_invertido = round(cursor.fetchone()["valor"], 2)

    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    sin_stock = 0
    stock_bajo = 0
    grupos_map = {}
    top_productos = []

    for p in productos:
        stock = calcular_stock_total_producto(p["codigo"], cursor)
        if stock <= 0:
            sin_stock += 1
        elif p["stock_minimo"] > 0 and stock <= p["stock_minimo"]:
            stock_bajo += 1
        grupo = p["grupo"] or "General"
        grupos_map[grupo] = grupos_map.get(grupo, 0) + 1
        top_productos.append({"nombre": p["nombre"], "stock": stock})

    un_mes = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) as total FROM movimientos WHERE fecha >= ?", (un_mes,))
    movimientos_mes = cursor.fetchone()["total"]
    conn.close()

    top_5 = sorted(top_productos, key=lambda x: x["stock"], reverse=True)[:5]
    top_5 = [{"nombre": p["nombre"][:15]+"…" if len(p["nombre"])>15 else p["nombre"], "stock": p["stock"]} for p in top_5 if p["stock"]>0]
    por_grupo = [{"grupo": k, "cantidad": v} for k, v in grupos_map.items()]

    return {
        "totalProductos": total_productos,
        "totalMovimientos": total_movimientos,
        "sinStock": sin_stock,
        "stockBajo": stock_bajo,
        "movimientosUltimoMes": movimientos_mes,
        "valorTotalInvertido": valor_total_invertido,
        "topProductos": top_5,
        "porGrupo": por_grupo
    }

# ── LISTAS ────────────────────────────────────────────────────────────────────

def obtener_listas():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM unidades ORDER BY nombre")
    unidades = [r["nombre"] for r in cursor.fetchall()]
    cursor.execute("SELECT nombre FROM grupos ORDER BY nombre")
    grupos = [r["nombre"] for r in cursor.fetchall()]
    conn.close()
    return {"unidades": unidades, "grupos": grupos, "categorias": CATEGORIAS}

def agregar_unidad(nombre):
    try:
        conn = conectar()
        conn.execute("INSERT INTO unidades (nombre) VALUES (?)", (nombre.strip(),))
        conn.commit()
        conn.close()
        return True, "Unidad agregada."
    except sqlite3.IntegrityError:
        return False, "Ya existe esa unidad."

def agregar_grupo(nombre):
    try:
        conn = conectar()
        conn.execute("INSERT INTO grupos (nombre) VALUES (?)", (nombre.strip(),))
        conn.commit()
        conn.close()
        return True, "Grupo agregado."
    except sqlite3.IntegrityError:
        return False, "Ya existe ese grupo."

# ── INTEGRIDAD ────────────────────────────────────────────────────────────────

def validar_integridad():
    errores = []
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT codigo, nombre, stock_minimo FROM productos")
    for p in cursor.fetchall():
        if not p["nombre"] or len(p["nombre"]) < 2:
            errores.append(f"Producto {p['codigo']} tiene nombre inválido")
        if p["stock_minimo"] < 0:
            errores.append(f"Producto {p['codigo']} tiene stock mínimo negativo")
        stock = calcular_stock_total_producto(p["codigo"], cursor)
        if stock < 0:
            errores.append(f"Producto {p['codigo']} tiene stock negativo: {stock}")
    cursor.execute("""
        SELECT m.codigo FROM movimientos m
        LEFT JOIN productos p ON m.codigo=p.codigo WHERE p.codigo IS NULL
    """)
    for m in cursor.fetchall():
        errores.append(f"Movimiento para producto inexistente: {m['codigo']}")
    conn.close()
    return errores

# ── EXPORT CSV ────────────────────────────────────────────────────────────────

def exportar_stock_csv():
    stock = obtener_stock()
    output = io.StringIO()
    output.write("\ufeff")
    output.write("Código,Nombre,Categoría,Unidad,Stock Mínimo,Stock Actual,Costo Promedio,Valor Total,Estado\n")
    for p in stock:
        if p["cantidad"] <= 0:
            estado = "Sin Stock"
        elif p["stockMin"] > 0 and p["cantidad"] <= p["stockMin"]:
            estado = "Stock Bajo"
        else:
            estado = "Normal"
        output.write(f'"{p["codigo"]}","{p["nombre"]}","{p["categoria"]}","{p["unidad"]}",'
                     f'{p["stockMin"]},{p["cantidad"]},{p["costoPromedio"]},{p["valorTotal"]},"{estado}"\n')
    return output.getvalue()

# ── IMPORTAR DESDE EXCEL ──────────────────────────────────────────────────────

def importar_desde_excel(file_bytes):
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return {"ok": 0, "errores": 0, "detalles": ["El archivo está vacío."]}

        headers = [str(h).strip().lower().replace(" ","_") if h else "" for h in rows[0]]
        col_map = {}
        for i, h in enumerate(headers):
            if "codigo" in h or "código" in h: col_map["codigo"] = i
            elif "nombre" in h: col_map["nombre"] = i
            elif "categoria" in h or "categoría" in h: col_map["categoria"] = i
            elif "unidad" in h: col_map["unidad"] = i
            elif "stock_min" in h or "minimo" in h or "mínimo" in h: col_map["stock_minimo"] = i

        faltantes = [r for r in ["codigo","nombre","categoria"] if r not in col_map]
        if faltantes:
            return {"ok": 0, "errores": 0, "detalles": [f"Faltan columnas: {', '.join(faltantes)}"]}

        ok = 0; errores = 0; detalles = []
        for fila_num, row in enumerate(rows[1:], 2):
            try:
                codigo = str(row[col_map["codigo"]]).strip().upper() if row[col_map["codigo"]] else ""
                nombre = str(row[col_map["nombre"]]).strip() if row[col_map["nombre"]] else ""
                categoria = str(row[col_map["categoria"]]).strip().upper() if row[col_map["categoria"]] else ""
                unidad = str(row[col_map["unidad"]]).strip() if "unidad" in col_map and row[col_map["unidad"]] else "Unidades"
                stock_min = int(row[col_map["stock_minimo"]]) if "stock_minimo" in col_map and row[col_map["stock_minimo"]] else 0

                if not codigo or codigo == "NONE":
                    detalles.append(f"Fila {fila_num}: Código vacío — omitida"); errores += 1; continue
                if not nombre or nombre == "NONE":
                    detalles.append(f"Fila {fila_num}: Nombre vacío ({codigo}) — omitida"); errores += 1; continue
                if categoria not in CATEGORIAS_IDS:
                    detalles.append(f"Fila {fila_num}: Categoría '{categoria}' inválida para {codigo} — se usó GENERAL")
                    categoria = "GENERAL"

                success, msg = registrar_producto(codigo, nombre, unidad, "General", stock_min, categoria)
                if success: ok += 1
                else: detalles.append(f"Fila {fila_num}: {codigo} — {msg}"); errores += 1
            except Exception as e:
                detalles.append(f"Fila {fila_num}: Error — {str(e)}"); errores += 1

        return {"ok": ok, "errores": errores, "detalles": detalles}
    except Exception as e:
        return {"ok": 0, "errores": 0, "detalles": [f"No se pudo leer el archivo: {str(e)}"]}

def generar_plantilla_excel():
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"
    headers = ["Codigo","Nombre","Categoria","Unidad","Stock_Minimo"]
    hf = PatternFill(start_color="2E86AB", end_color="2E86AB", fill_type="solid")
    hfont = Font(color="FFFFFF", bold=True)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hf; cell.font = hfont
        cell.alignment = Alignment(horizontal="center")
    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 14
    ejemplos = [
        ["EPP-001","Botas de seguridad talla 42","EPPS","Pares",5],
        ["LIM-001","Detergente industrial 5L","LIMPIEZA","Litros",3],
        ["ESC-001","Papel bond A4 x 500","ESCRITORIO","Paquetes",2],
    ]
    ef = PatternFill(start_color="EBF5FB", end_color="EBF5FB", fill_type="solid")
    for r, row in enumerate(ejemplos, 2):
        for c, val in enumerate(row, 1):
            ws.cell(row=r, column=c, value=val).fill = ef
    ws2 = wb.create_sheet("Categorias_Validas")
    ws2.append(["ID_Categoria","Nombre"])
    for cat in CATEGORIAS:
        ws2.append([cat["id"], cat["nombre"]])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

def obtener_valor_invertido(codigo, cursor=None):
    """Suma solo los costos de ingresos — nunca resta por salidas"""
    close_after = False
    if cursor is None:
        conn = conectar()
        cursor = conn.cursor()
        close_after = True
    cursor.execute("""
        SELECT COALESCE(SUM(costo_total), 0) as valor
        FROM movimientos
        WHERE codigo=? AND tipo IN ('INGRESO', 'AJUSTE_POSITIVO')
    """, (codigo.upper(),))
    row = cursor.fetchone()
    valor = round(row["valor"], 2) if row else 0.0
    if close_after:
        conn.close()
    return valor

# ── NOTA DE SALIDA PDF ────────────────────────────────────────────────────────

def obtener_salidas_por_fecha(fecha):
    """Obtiene todos los movimientos de salida de una fecha específica"""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.codigo, m.variante, m.fecha, m.cantidad,
               m.costo_unitario, m.costo_total, m.destinatario,
               m.usuario, m.observaciones,
               p.nombre, p.unidad, p.categoria
        FROM movimientos m
        LEFT JOIN productos p ON m.codigo = p.codigo
        WHERE m.fecha = ? AND m.tipo IN ('SALIDA', 'AJUSTE_NEGATIVO')
        ORDER BY m.timestamp ASC
    """, (fecha,))
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r["id"],
        "codigo": r["codigo"],
        "variante": r["variante"] or "",
        "fecha": r["fecha"],
        "cantidad": r["cantidad"],
        "costoUnitario": r["costo_unitario"] or 0,
        "costoTotal": r["costo_total"] or 0,
        "destinatario": r["destinatario"] or "",
        "usuario": r["usuario"],
        "observaciones": r["observaciones"] or "",
        "nombre": r["nombre"] or "Producto no encontrado",
        "unidad": r["unidad"] or "Unidades",
        "categoria": r["categoria"] or ""
    } for r in rows]

def generar_nota_salida_pdf(movimiento):
    """Genera un PDF de nota de salida para un movimiento específico"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    elements = []

    # Estilos
    estilo_empresa = ParagraphStyle('empresa', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER)
    estilo_ruc = ParagraphStyle('ruc', fontSize=10, fontName='Helvetica', alignment=TA_CENTER)
    estilo_titulo = ParagraphStyle('titulo', fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=6)
    estilo_normal = ParagraphStyle('normal', fontSize=10, fontName='Helvetica')
    estilo_bold = ParagraphStyle('bold', fontSize=10, fontName='Helvetica-Bold')
    estilo_pie = ParagraphStyle('pie', fontSize=9, fontName='Helvetica', alignment=TA_CENTER)

    # ── CABECERA ──
    elements.append(Paragraph("DMU TRANSPORTES E.I.R.L", estilo_empresa))
    elements.append(Paragraph("RUC: 20613430238", estilo_ruc))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph("NOTA DE SALIDA", estilo_titulo))
    elements.append(Spacer(1, 0.2*cm))

    # Número de nota
    num_nota = f"N001-{movimiento['id']:04d}"
    cabecera_data = [
        ['', '', '', '', f"Nº {num_nota}"]
    ]
    cabecera_table = Table(cabecera_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm, 5*cm])
    cabecera_table.setStyle(TableStyle([
        ('ALIGN', (4,0), (4,0), 'RIGHT'),
        ('FONTNAME', (4,0), (4,0), 'Helvetica-Bold'),
        ('FONTSIZE', (4,0), (4,0), 12),
        ('TEXTCOLOR', (4,0), (4,0), colors.HexColor('#1a3a5c')),
    ]))
    elements.append(cabecera_table)
    elements.append(Spacer(1, 0.3*cm))

    # ── DATOS DEL MOVIMIENTO ──
    color_header = colors.HexColor('#2E86AB')
    color_light = colors.HexColor('#f0f7ff')

    info_data = [
        [Paragraph('<b>ENTREGADO A:</b>', estilo_normal),
         Paragraph(movimiento['destinatario'] or '—', estilo_normal),
         Paragraph('<b>FECHA:</b>', estilo_normal),
         Paragraph(movimiento['fecha'], estilo_normal)],
        [Paragraph('<b>ÁREA / CATEGORÍA:</b>', estilo_normal),
         Paragraph(movimiento['categoria'], estilo_normal),
         Paragraph('<b>NOTA DE SALIDA:</b>', estilo_normal),
         Paragraph(num_nota, estilo_bold)],
        [Paragraph('<b>OBSERVACIONES:</b>', estilo_normal),
         Paragraph(movimiento['observaciones'] or '—', estilo_normal),
         Paragraph('<b>REGISTRADO POR:</b>', estilo_normal),
         Paragraph(movimiento['usuario'], estilo_normal)],
    ]

    info_table = Table(info_data, colWidths=[4*cm, 6*cm, 4*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), color_light),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.5*cm))

    # ── TABLA DE PRODUCTOS ──
    tabla_data = [['Código', 'Descripción', 'Variante', 'U.M.', 'Cantidad', 'Costo Unit.', 'Total']]

    descripcion = movimiento['nombre']
    variante = movimiento['variante'] or '—'
    cantidad = movimiento['cantidad']
    costo_unit = movimiento['costoUnitario']
    total = movimiento['costoTotal']

    tabla_data.append([
        movimiento['codigo'],
        descripcion,
        variante,
        movimiento['unidad'],
        str(cantidad),
        f"S/. {costo_unit:.2f}",
        f"S/. {total:.2f}"
    ])

    # Fila vacías para completar
    for _ in range(5):
        tabla_data.append(['', '', '', '', '', '', ''])

    # Fila total
    tabla_data.append(['', '', '', '', '', 'TOTAL:', f"S/. {total:.2f}"])

    col_widths = [2.5*cm, 5*cm, 2.5*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm]
    prod_table = Table(tabla_data, colWidths=col_widths, rowHeights=[0.8*cm] + [0.7*cm]*6 + [0.8*cm])
    prod_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0,0), (-1,0), color_header),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        # Datos
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (4,1), (6,-1), 'RIGHT'),
        ('ALIGN', (0,1), (3,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        # Fila total
        ('BACKGROUND', (0,-1), (-1,-1), color_light),
        ('FONTNAME', (5,-1), (6,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (5,-1), (6,-1), 10),
        # Zebra
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#f8fafc')),
    ]))
    elements.append(prod_table)
    elements.append(Spacer(1, 1*cm))

    # ── FIRMAS ──
    firmas_data = [
        [Paragraph('___________________', estilo_pie),
         Paragraph('___________________', estilo_pie),
         Paragraph('___________________', estilo_pie)],
        [Paragraph('RESPONSABLE', estilo_pie),
         Paragraph('AUTORIZADO POR', estilo_pie),
         Paragraph('RECIBÍ CONFORME', estilo_pie)],
    ]
    firmas_table = Table(firmas_data, colWidths=[6*cm, 6*cm, 6*cm])
    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(firmas_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def generar_notas_salida_pdf_dia(fecha):
    """Genera un PDF con todas las notas de salida del día (una por movimiento)"""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, PageBreak
    import io

    movimientos = obtener_salidas_por_fecha(fecha)
    if not movimientos:
        return None, 0

    # Generar PDF con todas las notas (una por página)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    all_elements = []
    for i, mov in enumerate(movimientos):
        # Generar elementos de cada nota
        elements = _elementos_nota(mov)
        all_elements.extend(elements)
        if i < len(movimientos) - 1:
            all_elements.append(PageBreak())

    doc.build(all_elements)
    buffer.seek(0)
    return buffer.getvalue(), len(movimientos)

def _elementos_nota(movimiento):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    elements = []
    color_header = colors.HexColor('#2E86AB')
    color_light = colors.HexColor('#f0f7ff')

    ep = ParagraphStyle('ep', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER)
    er = ParagraphStyle('er', fontSize=10, fontName='Helvetica', alignment=TA_CENTER)
    et = ParagraphStyle('et', fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)
    en = ParagraphStyle('en', fontSize=9, fontName='Helvetica')
    eb = ParagraphStyle('eb', fontSize=9, fontName='Helvetica-Bold')
    epi = ParagraphStyle('epi', fontSize=9, fontName='Helvetica', alignment=TA_CENTER)

    num_nota = f"N001-{movimiento['id']:04d}"

    elements.append(Paragraph("DMU TRANSPORTES E.I.R.L", ep))
    elements.append(Paragraph("RUC: 20613430238", er))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph("NOTA DE SALIDA", et))

    # Número
    n_data = [['', '', '', '', Paragraph(f"<b>Nº {num_nota}</b>", eb)]]
    n_table = Table(n_data, colWidths=[3*cm,3*cm,3*cm,3*cm,5*cm])
    n_table.setStyle(TableStyle([('ALIGN',(4,0),(4,0),'RIGHT'),('FONTSIZE',(0,0),(-1,-1),10)]))
    elements.append(n_table)
    elements.append(Spacer(1, 0.2*cm))

    # Info
    info_data = [
        [Paragraph('<b>ENTREGADO A:</b>', en), Paragraph(movimiento['destinatario'] or '—', en),
         Paragraph('<b>FECHA:</b>', en), Paragraph(movimiento['fecha'], en)],
        [Paragraph('<b>CATEGORÍA:</b>', en), Paragraph(movimiento['categoria'], en),
         Paragraph('<b>NOTA Nº:</b>', en), Paragraph(num_nota, eb)],
        [Paragraph('<b>OBSERVACIONES:</b>', en), Paragraph(movimiento['observaciones'] or '—', en),
         Paragraph('<b>REGISTRADO POR:</b>', en), Paragraph(movimiento['usuario'], en)],
    ]
    info_table = Table(info_data, colWidths=[4*cm,6*cm,4*cm,4*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),color_light),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('PADDING',(0,0),(-1,-1),5),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.4*cm))

    # Tabla productos
    cantidad = movimiento['cantidad']
    costo_unit = movimiento['costoUnitario']
    total = movimiento['costoTotal']
    variante = movimiento['variante'] or '—'

    t_data = [['Código','Descripción','Variante','U.M.','Cantidad','Costo Unit.','Total']]
    t_data.append([movimiento['codigo'], movimiento['nombre'], variante,
                   movimiento['unidad'], str(cantidad),
                   f"S/. {costo_unit:.2f}", f"S/. {total:.2f}"])
    for _ in range(5):
        t_data.append(['','','','','','',''])
    t_data.append(['','','','','','TOTAL:', f"S/. {total:.2f}"])

    prod_table = Table(t_data, colWidths=[2.5*cm,5*cm,2.5*cm,2*cm,2*cm,2.5*cm,2.5*cm],
                       rowHeights=[0.8*cm]+[0.7*cm]*6+[0.8*cm])
    prod_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),color_header),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),9),
        ('ALIGN',(0,0),(-1,0),'CENTER'),
        ('FONTSIZE',(0,1),(-1,-1),9),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(4,1),(6,-1),'RIGHT'),
        ('ALIGN',(0,1),(3,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(0,-1),(-1,-1),color_light),
        ('FONTNAME',(5,-1),(6,-1),'Helvetica-Bold'),
        ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#f8fafc')),
    ]))
    elements.append(prod_table)
    elements.append(Spacer(1, 0.8*cm))

    # Firmas
    f_data = [
        [Paragraph('___________________', epi), Paragraph('___________________', epi), Paragraph('___________________', epi)],
        [Paragraph('RESPONSABLE', epi), Paragraph('AUTORIZADO POR', epi), Paragraph('RECIBÍ CONFORME', epi)],
    ]
    f_table = Table(f_data, colWidths=[6*cm,6*cm,6*cm])
    f_table.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('PADDING',(0,0),(-1,-1),4)]))
    elements.append(f_table)

    return elements