import os
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from werkzeug.security import check_password_hash
from functools import wraps
from database import (
    inicializar_db, obtener_usuario, obtener_todos_usuarios,
    crear_usuario, editar_usuario, eliminar_usuario,
    registrar_producto, editar_producto, eliminar_producto,
    obtener_stock, obtener_stock_por_categoria, buscar_producto,
    buscar_producto_por_codigo, obtener_detalle_producto,
    registrar_movimiento, obtener_historial, obtener_resumen,
    obtener_listas, agregar_unidad, agregar_grupo,
    validar_integridad, exportar_stock_csv, CATEGORIAS,
    importar_desde_excel, generar_plantilla_excel
)

app = Flask(__name__)
app.secret_key = "inventario_pro_secret_2024_xyz"
inicializar_db()

def login_requerido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def solo_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("rol") != "admin":
            return jsonify({"ok": False, "msg": "Acceso denegado."}), 403
        return f(*args, **kwargs)
    return decorated

def no_readonly(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("rol") == "readonly":
            return jsonify({"ok": False, "msg": "No tienes permisos."}), 403
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    if "usuario" in session: return redirect(url_for("inventario"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("usuario","").strip()
        password = request.form.get("password","").strip()
        user = obtener_usuario(username)
        if user and check_password_hash(user["password"], password):
            session["usuario"] = user["username"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("inventario"))
        else:
            error = "Usuario o contraseña incorrectos"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/inventario")
@login_requerido
def inventario():
    return render_template("inventario.html",
        nombre=session.get("nombre"), rol=session.get("rol"),
        usuario=session.get("usuario"), categorias=CATEGORIAS)

@app.route("/api/sesion")
@login_requerido
def api_sesion():
    return jsonify({"usuario": session.get("usuario"), "nombre": session.get("nombre"), "rol": session.get("rol")})

@app.route("/api/resumen")
@login_requerido
def api_resumen():
    return jsonify(obtener_resumen())

@app.route("/api/categorias/resumen")
@login_requerido
def api_categorias_resumen():
    return jsonify(obtener_stock_por_categoria())

@app.route("/api/stock")
@login_requerido
def api_stock():
    return jsonify(obtener_stock(request.args.get("categoria","TODOS")))

@app.route("/api/producto/buscar")
@login_requerido
def api_buscar_codigo():
    return jsonify(buscar_producto_por_codigo(request.args.get("codigo","")))

@app.route("/api/producto/search")
@login_requerido
def api_buscar_producto():
    return jsonify(buscar_producto(request.args.get("q","")))

@app.route("/api/producto/detalle/<codigo>")
@login_requerido
def api_detalle_producto(codigo):
    detalle = obtener_detalle_producto(codigo)
    return jsonify(detalle) if detalle else (jsonify({"error": "No encontrado"}), 404)

@app.route("/api/producto/registrar", methods=["POST"])
@login_requerido
@no_readonly
def api_registrar_producto():
    data = request.json
    ok, msg = registrar_producto(
        data.get("codigo",""), data.get("nombre",""),
        data.get("unidad","Unidades"), data.get("grupo","General"),
        data.get("stockMin",0), data.get("categoria","GENERAL"),
        data.get("tieneVariantes", 0), data.get("variantes", [])
    )
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/producto/editar", methods=["POST"])
@login_requerido
@no_readonly
def api_editar_producto():
    data = request.json
    ok, msg = editar_producto(
        data.get("codigo",""), data.get("nombre",""),
        data.get("unidad","Unidades"), data.get("grupo","General"),
        data.get("stockMin",0), data.get("categoria","GENERAL"),
        data.get("tieneVariantes", 0), data.get("variantes", [])
    )
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/producto/eliminar", methods=["POST"])
@login_requerido
@solo_admin
def api_eliminar_producto():
    data = request.json
    ok, msg = eliminar_producto(data.get("codigo",""))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/movimiento/registrar", methods=["POST"])
@login_requerido
@no_readonly
def api_registrar_movimiento():
    data = request.json
    ok, msg = registrar_movimiento(
        data.get("codigo",""), data.get("fecha",""), data.get("tipo",""),
        data.get("cantidad",0), session.get("usuario","Sistema"),
        data.get("observaciones",""), data.get("variante") or None,
        data.get("costoUnitario",0), data.get("destinatario","")
    )
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/historial")
@login_requerido
def api_historial():
    desde = request.args.get("desde","")
    hasta = request.args.get("hasta","")
    tipo = request.args.get("tipo","")
    if not desde or not hasta: return jsonify([])
    return jsonify(obtener_historial(desde, hasta, tipo))

@app.route("/api/listas")
@login_requerido
def api_listas():
    return jsonify(obtener_listas())

@app.route("/api/listas/unidad", methods=["POST"])
@login_requerido
@solo_admin
def api_agregar_unidad():
    ok, msg = agregar_unidad(request.json.get("nombre",""))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/listas/grupo", methods=["POST"])
@login_requerido
@solo_admin
def api_agregar_grupo():
    ok, msg = agregar_grupo(request.json.get("nombre",""))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/usuarios")
@login_requerido
@solo_admin
def api_usuarios():
    return jsonify(obtener_todos_usuarios())

@app.route("/api/usuario/crear", methods=["POST"])
@login_requerido
@solo_admin
def api_crear_usuario():
    data = request.json
    ok, msg = crear_usuario(data.get("username",""), data.get("password",""), data.get("nombre",""), data.get("rol","operador"))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/usuario/editar", methods=["POST"])
@login_requerido
@solo_admin
def api_editar_usuario():
    data = request.json
    ok, msg = editar_usuario(data.get("id"), data.get("nombre",""), data.get("rol","operador"), data.get("password") or None)
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/usuario/eliminar", methods=["POST"])
@login_requerido
@solo_admin
def api_eliminar_usuario():
    data = request.json
    if data.get("username") == session.get("usuario"):
        return jsonify({"ok": False, "msg": "No puedes eliminar tu propio usuario."})
    ok, msg = eliminar_usuario(data.get("id"))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/validar")
@login_requerido
@solo_admin
def api_validar():
    return jsonify({"errores": validar_integridad()})

@app.route("/api/exportar/csv")
@login_requerido
def api_exportar_csv():
    return Response(exportar_stock_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=inventario.csv"})

@app.route("/api/importar/excel", methods=["POST"])
@login_requerido
@solo_admin
def api_importar_excel():
    if "archivo" not in request.files:
        return jsonify({"ok": False, "msg": "No se recibió ningún archivo."})
    archivo = request.files["archivo"]
    if not archivo.filename.endswith((".xlsx",".xls")):
        return jsonify({"ok": False, "msg": "Solo se aceptan archivos .xlsx o .xls"})
    resultado = importar_desde_excel(archivo.read())
    return jsonify(resultado)

@app.route("/api/importar/plantilla")
@login_requerido
def api_descargar_plantilla():
    return Response(generar_plantilla_excel(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_inventario.xlsx"})

@app.route("/api/movimiento/masivo", methods=["POST"])
@login_requerido
@no_readonly
def api_registrar_movimiento_masivo():
    data = request.json
    codigo = data.get("codigo", "")
    fecha = data.get("fecha", "")
    tipo = data.get("tipo", "")
    costo_unitario = data.get("costoUnitario", 0)
    destinatario = data.get("destinatario", "")
    observaciones = data.get("observaciones", "")
    movimientos = data.get("movimientos", [])

    if not movimientos:
        return jsonify({"ok": False, "msg": "No hay movimientos para registrar."})

    resultados = []
    errores = []

    for mov in movimientos:
        variante = mov.get("variante")
        cantidad = float(mov.get("cantidad", 0) or 0)
        if cantidad <= 0:
            continue
        ok, msg = registrar_movimiento(
            codigo, fecha, tipo, cantidad,
            session.get("usuario", "Sistema"),
            observaciones, variante, costo_unitario, destinatario
        )
        if ok:
            resultados.append(f"{variante or 'Sin variante'}: {cantidad}")
        else:
            errores.append(f"{variante or 'Sin variante'}: {msg}")

    if not resultados and not errores:
        return jsonify({"ok": False, "msg": "No se ingresaron cantidades."})

    return jsonify({
        "ok": len(resultados) > 0,
        "msg": f"{len(resultados)} movimiento(s) registrado(s).",
        "registrados": resultados,
        "errores": errores
    })

@app.route("/api/reportes/nota-salida")
@login_requerido
def api_nota_salida():
    fecha = request.args.get("fecha", "")
    mov_id = request.args.get("movId", None)
    if not fecha:
        return jsonify({"error": "Fecha requerida"}), 400
    from database import generar_notas_salida_pdf_dia, obtener_salidas_por_fecha, _elementos_nota
    
    if mov_id:
        # Una sola nota por movimiento específico
        movimientos = obtener_salidas_por_fecha(fecha)
        mov = next((m for m in movimientos if str(m['id']) == str(mov_id)), None)
        if not mov:
            return jsonify({"error": "Movimiento no encontrado"}), 404
        from database import generar_nota_salida_pdf
        pdf_bytes = generar_nota_salida_pdf(mov)
    else:
        # Todas las notas del día
        pdf_bytes, total = generar_notas_salida_pdf_dia(fecha)
        if not pdf_bytes:
            return jsonify({"error": "No hay salidas para esa fecha"}), 404

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=nota_salida_{fecha}.pdf"}
    )

@app.route("/api/movimiento/masivo/v2", methods=["POST"])
@login_requerido
@no_readonly
def api_registrar_movimiento_masivo_v2():
    data = request.json
    codigo = data.get("codigo", "")
    fecha = data.get("fecha", "")
    tipo = data.get("tipo", "")
    destinatario = data.get("destinatario", "")
    observaciones = data.get("observaciones", "")
    movimientos = data.get("movimientos", [])

    if not movimientos:
        return jsonify({"ok": False, "msg": "No hay movimientos para registrar."})

    resultados = []
    errores = []

    for mov in movimientos:
        variante = mov.get("variante")
        cantidad = float(mov.get("cantidad", 0) or 0)
        costo_unitario = float(mov.get("costoUnitario", 0) or 0)
        if cantidad <= 0:
            continue
        ok, msg = registrar_movimiento(
            codigo, fecha, tipo, cantidad,
            session.get("usuario", "Sistema"),
            observaciones, variante, costo_unitario, destinatario
        )
        if ok:
            resultados.append(f"{variante or 'Sin variante'}: {cantidad}")
        else:
            errores.append(f"{variante or 'Sin variante'}: {msg}")

    if not resultados and not errores:
        return jsonify({"ok": False, "msg": "No se ingresaron cantidades."})

    return jsonify({
        "ok": len(resultados) > 0,
        "msg": f"{len(resultados)} movimiento(s) registrado(s).",
        "registrados": resultados,
        "errores": errores
    })

IMAGENES_DIR = os.path.join('static', 'imagenes')
os.makedirs(IMAGENES_DIR, exist_ok=True)

@app.route("/api/producto/imagen", methods=["POST"])
@login_requerido
@no_readonly
def api_subir_imagen_producto():
    if 'imagen' not in request.files:
        return jsonify({"ok": False, "msg": "No se envió imagen"})
    archivo = request.files['imagen']
    codigo = request.form.get('codigo', '').strip().upper()
    if not codigo or archivo.filename == '':
        return jsonify({"ok": False, "msg": "Datos incompletos"})
    ext = os.path.splitext(archivo.filename)[1].lower()  # .jpg, .png, .webp, etc.
    ruta = os.path.join(IMAGENES_DIR, f"{codigo}{ext}")
    archivo.save(ruta)
    return jsonify({"ok": True, "msg": "Imagen guardada"})


@app.route("/api/producto/imagen", methods=["POST"])
@login_requerido
@no_readonly
def api_subir_imagen_producto():
    if 'imagen' not in request.files:
        return jsonify({"ok": False, "msg": "No se envió imagen"})
    archivo = request.files['imagen']
    codigo = request.form.get('codigo', '').strip().upper()
    if not codigo or archivo.filename == '':
        return jsonify({"ok": False, "msg": "Datos incompletos"})
    
    img = Image.open(archivo).convert("RGB")
    ruta = os.path.join(IMAGENES_DIR, f"{codigo}.png")
    img.save(ruta, "PNG")
    return jsonify({"ok": True, "msg": "Imagen guardada"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)



